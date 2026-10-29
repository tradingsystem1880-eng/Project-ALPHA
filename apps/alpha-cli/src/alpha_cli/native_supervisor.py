"""Internal synthetic process owner, including one fixed pinned native loop child.

Objects below are trusted-code interfaces, not a sandbox against hostile same-UID Python.
The child receives neither the control path nor the owner lock descriptor. Process-group
cleanup is deliberately narrower than arbitrary descendant containment.
There is no production activation or caller-supplied command surface.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import math
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, BinaryIO, Literal

from alpha_cli.control_store import ControlStore
from alpha_cli.durable_lease import DurableJobLease, _observe_retained_child, terminate_and_reap
from alpha_core import DataError

if TYPE_CHECKING:
    from alpha_cli._native_loop_admission import NativeLaunch

if sys.platform != "win32":
    import fcntl

Fixture = Literal["success", "failure", "wait", "descendant", "escape", "native_loop"]
_FIXTURES = {"success", "failure", "wait", "descendant", "escape", "native_loop"}
_MARKER = "ALPHA synthetic native lifecycle v1\n"
_SEAL = object()


def _native_launch_type() -> type[NativeLaunch]:
    """The canonical NativeLaunch class, imported only on native-loop paths that use it."""
    from alpha_cli._native_loop_admission import NativeLaunch

    return NativeLaunch


class _FixtureDeadlineExpired(DataError):
    """Launch preparation exhausted the fixed fixture's remaining deadline."""


class _FixtureCancelledBeforeSpawn(DataError):
    """The live owner received a stop request before payload effects."""


_PAYLOAD = """import os,pathlib,signal,subprocess,sys,time
mode,work=sys.argv[1:]
root=pathlib.Path(work)
(root/'payload.pid').write_text(str(os.getpid()))
if mode in ('descendant','escape'):
    child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],
                           start_new_session=mode=='escape')
    (root/'descendant.pid').write_text(str(child.pid))
if mode=='descendant':
    def stop(sig,frame):
        child.wait(timeout=2)
        raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop)
if mode in ('wait','descendant'): time.sleep(60)
else:
    time.sleep(0.1)
    raise SystemExit(0 if mode=='success' else 7)
"""


def _require_retained_child_capability() -> None:
    """Reject unavailable observation primitives before any owner effects."""
    if not callable(getattr(os, "waitid", None)) or not all(
        type(getattr(os, name, None)) is int
        for name in ("P_PID", "WEXITED", "WNOHANG", "WNOWAIT", "CLD_EXITED")
    ):
        raise DataError("synthetic native supervisor requires non-reaping child observation")


def host_identity() -> dict[str, str]:
    """One explicit profile; unknown OS/namespace information denies fixture execution."""
    if sys.platform != "linux" or os.name != "posix":
        raise DataError("synthetic native supervisor supports linux-posix-v1 only")
    _require_retained_child_capability()
    if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
        raise DataError("synthetic native supervisor requires the default SIGCHLD disposition")
    try:
        boot = str(uuid.UUID(Path("/proc/sys/kernel/random/boot_id").read_text().strip()))
        namespace = os.readlink("/proc/self/ns/pid")
    except (OSError, ValueError) as exc:
        raise DataError("native supervisor host epoch is unavailable") from exc
    if not namespace.startswith("pid:["):
        raise DataError("native supervisor process namespace is unavailable")
    return {"profile": "linux-posix-v1", "boot": boot, "pid_namespace": namespace}


@contextlib.contextmanager
def synthetic_workspace() -> Iterator[Path]:
    """Allocate a new disposable fixture root; never opt an existing database into execution."""
    host_identity()
    with tempfile.TemporaryDirectory(prefix="alpha-native-fixture-") as directory:
        root = Path(directory).resolve()
        (root / "synthetic-only").write_text(_MARKER)
        yield root


def _fixture_root(root: Path) -> Path:
    if (
        root.is_symlink()
        or root != root.resolve()
        or root.parent != Path(tempfile.gettempdir()).resolve()
        or not root.name.startswith("alpha-native-fixture-")
    ):
        raise DataError("native fixture requires a disposable synthetic workspace")
    marker = root / "synthetic-only"
    if marker.is_symlink() or not marker.is_file() or marker.read_text() != _MARKER:
        raise DataError("native fixture requires its synthetic-only marker")
    return root


def _lock_path(root: Path, job_id: str) -> Path:
    # Canonical UUIDs also keep all paths under the fixture root.
    if str(uuid.UUID(job_id)) != job_id:
        raise DataError("native fixture job identity must be a canonical UUID")
    control = root / "control"
    if control.is_symlink():
        raise DataError("native fixture control root must not be a symlink")
    control.mkdir(exist_ok=True)
    return control / f"native-{job_id}.lock"


def _open_lock(root: Path, job_id: str) -> BinaryIO:
    descriptor = os.open(_lock_path(root, job_id), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    return os.fdopen(descriptor, "rb+")


def _request_live_stop(root: Path, job_id: str) -> bool:
    """Best-effort stop transport only; delivery is never a cleanup or authority receipt."""
    _fixture_root(root)
    host_identity()
    path = _lock_path(root, job_id).with_suffix(".stop")
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as control:
        control.settimeout(0.1)
        try:
            control.sendto(b"cancel\n", str(path))
        except OSError:
            return False  # Durable intent still goes through the existing store.
    return True


@dataclass(frozen=True)
class _Observation:
    owner: _Owner
    kind: Literal["native_started", "native_outcome", "native_uncertain"]
    fields: Mapping[str, object]
    seal: object


class _Owner:
    """Retain actual process/lock handles; callers cannot substitute receipt dictionaries."""

    def __init__(
        self,
        root: Path,
        job_id: str,
        fixture: str,
        seconds: float,
        lock: BinaryIO,
        *,
        native: NativeLaunch | None = None,
    ):
        if fixture not in _FIXTURES or not math.isfinite(seconds) or not 0 < seconds <= 60:
            raise DataError("native fixture kind/deadline is invalid")
        self.host = host_identity()
        self.root = _fixture_root(root)
        self.job_id = job_id
        self.fixture = fixture
        if (native is not None and type(native) is not _native_launch_type()) or (
            (fixture == "native_loop") != (native is not None)
        ):
            raise DataError("native loop fixture requires its fixed launch identity")
        self.native = native
        self.native_admission: dict[str, object] | None = None
        self.seconds = seconds
        self.lock = lock
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.pid = os.getpid()
        self.owner_id = str(uuid.uuid4())
        self.started = time.monotonic()
        self.deadline = self.started + seconds
        self.process: subprocess.Popen[bytes] | None = None
        self.spawn_attempted = False
        self.cleanup_attempted = False
        self._cleanup_complete = False
        self._cleanup_failure: Exception | None = None
        self._cleanup_lock = threading.Lock()
        self._issued: dict[str, _Observation] = {}
        self._on_spawn: Callable[[], None] | None = None
        self.heartbeat_due = threading.Event()
        self._stop_reason: str | None = None
        self.cancel_received = False
        self._stop_lock = threading.Lock()
        self._control: socket.socket | None = None
        self._control_identity: tuple[int, int] | None = None
        # Synthetic runtime identity is measured here, independently of the proposal hash.
        self.runtime = hashlib.sha256(
            Path(__file__).read_bytes() + Path(sys.executable).resolve().read_bytes()
        ).hexdigest()
        self.birth = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]

    def open_control(self) -> None:
        """Bind before dispatch; never replace an existing owner endpoint."""
        path = _lock_path(self.root, self.job_id).with_suffix(".stop")
        control = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            control.bind(str(path))
            control.setblocking(False)
            metadata = path.stat(follow_symlinks=False)
        except BaseException:
            control.close()
            raise
        self._control = control
        self._control_identity = (metadata.st_dev, metadata.st_ino)

    def close_control(self) -> None:
        control, self._control = self._control, None
        if control is None:
            return
        control.close()
        path = _lock_path(self.root, self.job_id).with_suffix(".stop")
        try:
            metadata = path.stat(follow_symlinks=False)
        except FileNotFoundError:
            return
        if (metadata.st_dev, metadata.st_ino) == self._control_identity:
            path.unlink()

    def request_stop(self, reason: str) -> None:
        if reason not in {"cancelled", "timeout", "owner_error"}:
            raise DataError("invalid native fixture stop reason")
        with self._stop_lock:
            if reason == "cancelled":
                self.cancel_received = True
            if self._stop_reason is None:
                self._stop_reason = reason

    @property
    def stop_reason(self) -> str | None:
        with self._stop_lock:
            return self._stop_reason

    def poll_stop(self, *, check_deadline: bool = True) -> bool:
        """Safety path: monotonic time, bounded nonblocking socket I/O, no journal access."""
        if check_deadline and time.monotonic() >= self.deadline:
            self.request_stop("timeout")
        control = self._control
        if control is not None:
            try:
                message = control.recv(32)
            except BlockingIOError:
                pass
            except OSError:
                self.request_stop("owner_error")
                raise
            else:
                if message == b"cancel\n":
                    self.request_stop("cancelled")
        return self.stop_reason is not None

    def poll_safety(self) -> bool:
        """Contain background monitor failure; main-thread interrupts keep normal semantics."""
        try:
            return self.poll_stop()
        except BaseException as exc:
            self.request_stop("owner_error")
            raise DataError("synthetic safety monitor failed") from exc

    def verify(self) -> None:
        if self.pid != os.getpid() or self.lock.closed or self.host != host_identity():
            raise DataError("native owner is not the current live issuing process")
        current = os.stat(_lock_path(self.root, self.job_id), follow_symlinks=False)
        retained = os.fstat(self.lock.fileno())
        if (current.st_dev, current.st_ino) != (retained.st_dev, retained.st_ino):
            raise DataError("native owner lock identity changed")

    def claim_fields(self) -> dict[str, object]:
        self.verify()
        lock = os.fstat(self.lock.fileno())
        return {
            "owner_id": self.owner_id,
            "owner_pid": self.pid,
            "owner_birth": self.birth,
            "host": self.host,
            "lock_device": lock.st_dev,
            "lock_inode": lock.st_ino,
            "runtime_sha256": self.runtime,
            "fixture": self.fixture,
            "seconds": self.seconds,
            "cleanup_scope": "posix_process_group",
        }

    def spawn(self) -> _Observation:
        """Create the fixed fixture ourselves; no caller argv or process handle is admitted."""
        if (
            self.process is not None
            or self.spawn_attempted
            or "native_outcome" in self._issued
            or "native_uncertain" in self._issued
        ):
            raise DataError("native owner already observed its child")
        self.verify()
        command = (
            self.native.command(self.native_admission)
            if self.native is not None
            else [
                sys.executable,
                "-c",
                _PAYLOAD,
                self.fixture,
                str(self.root / f"payload-{self.job_id}"),
            ]
        )
        work = self.root / f"payload-{self.job_id}"
        work.mkdir()
        if self.poll_stop():
            if self.stop_reason == "cancelled":
                raise _FixtureCancelledBeforeSpawn("native fixture cancelled before payload spawn")
            raise _FixtureDeadlineExpired(
                "native fixture deadline expired during launch preparation"
            )
        self.spawn_attempted = True
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=None
            if self.native is not None and self.native.study is not None
            else subprocess.DEVNULL,
            start_new_session=True,
            cwd=work,
            # Only the owner's validated temp root: the admitted worker re-checks its workspace.
            env={"PATH": os.defpath, "LANG": "C.UTF-8", "TMPDIR": str(self.root.parent)},
        )
        self.process = process  # Retain before every post-spawn validation.
        observed = self._issue("native_started", {"leader_pid": process.pid})
        if self._on_spawn is not None:
            self._on_spawn()
        self.verify()
        if os.getpgid(process.pid) != process.pid:
            raise DataError("native owner requires a fresh isolated synthetic child")
        return observed

    def _issue(
        self,
        kind: Literal["native_started", "native_outcome", "native_uncertain"],
        fields: dict[str, object],
    ) -> _Observation:
        detached = fields.copy()
        if "rule_result" in detached:
            binding = detached["rule_result"]
            if (
                not isinstance(binding, Mapping)
                or set(binding) != {"schema", "receipt_sha256"}
                or any(type(value) is not str for value in binding.values())
            ):
                raise DataError("issued rule result requires its closed immutable string binding")
            # Both the caller's dictionary and the issued nested view must be detached.
            # Closed string leaves need no generic recursive payload/signing mechanism.
            detached["rule_result"] = MappingProxyType(dict(binding))
        value = _Observation(self, kind, MappingProxyType(detached), _SEAL)
        self._issued[kind] = value
        return value

    def without_child(self, reason: str) -> _Observation:
        self.verify()
        terminal = self._issued.get("native_outcome") or self._issued.get("native_uncertain")
        if terminal is not None:
            return terminal
        if self.process is not None:
            raise DataError("native no-child observation cannot bypass retained child cleanup")
        if reason not in {"cancelled", "timeout", "owner_error"}:
            raise DataError("native no-spawn observation requires a stop cause")
        if self.spawn_attempted:
            return self._issue("native_uncertain", {"reason": "payload spawn outcome unobserved"})
        return self._issue(
            "native_outcome",
            {
                "reason": reason,
                "returncode": None,
                "elapsed_seconds": time.monotonic() - self.started,
                "cleanup_scope": "no_payload_spawn_attempted",
                "scientific_acceptance": "not_admitted",
            },
        )

    def observe_exit(self) -> int | None:
        """All native liveness checks retain the leader identity until final cleanup."""
        with self._cleanup_lock:
            process = self.process
            if process is None:
                raise DataError("native owner has no retained child to observe")
            if process.returncode is not None:
                return process.returncode
            return _observe_retained_child(process)

    def _cleanup_once(self) -> None:
        """Share retained-child cleanup with the lease; never repeat numeric group control."""
        process = self.process
        if process is None:
            raise DataError("native owner has no retained child to clean")
        with self._cleanup_lock:
            if self.cleanup_attempted:
                if not self._cleanup_complete:
                    raise DataError(
                        "native cleanup already attempted and remains unverified"
                    ) from self._cleanup_failure
                return
            self.cleanup_attempted = True
            try:
                if process.returncode is not None:
                    from alpha_cli.durable_lease import _process_group_exists

                    if _process_group_exists(process.pid):
                        raise DataError("reaped leader cannot authorize a surviving numeric group")
                else:
                    terminate_and_reap(
                        process, grace_seconds=0.2, process_group_id=process.pid, retain_leader=True
                    )
            except Exception as exc:
                self._cleanup_failure = exc
                raise
            self._cleanup_complete = True

    def finish(self, reason: str) -> _Observation:
        terminal = self._issued.get("native_outcome") or self._issued.get("native_uncertain")
        if terminal is not None:
            self.verify()
            return terminal
        process = self.process
        if process is None or reason not in {"exit", "timeout", "cancelled", "owner_error"}:
            raise DataError("native owner has no observed child outcome")
        try:
            self._cleanup_once()
        except Exception as exc:
            self.verify()
            return self._issue("native_uncertain", {"reason": f"cleanup unverified: {exc}"[:1024]})
        # Losing journal/host/lock provenance must not skip retained-child cleanup.
        self.verify()
        if self.fixture == "escape":
            return self._issue(
                "native_uncertain",
                {"reason": "known synthetic escape exceeds process-group cleanup scope"},
            )
        rule_result: dict[str, object] = {}
        if self.native is not None and reason == "exit" and process.returncode == 0:
            try:
                receipt_bytes = self.native.verify_result(
                    self.root / f"payload-{self.job_id}", self.native_admission
                )
                if self.native.study is not None:
                    rule_result = {
                        "rule_result": {
                            "schema": "SyntheticNativeRuleObservationV1",
                            "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                        }
                    }
            except (DataError, OSError, ValueError) as exc:
                return self._issue(
                    "native_uncertain", {"reason": f"native result unverified: {exc}"[:1024]}
                )
        return self._issue(
            "native_outcome",
            {
                **rule_result,
                "reason": reason,
                "returncode": process.returncode,
                "elapsed_seconds": time.monotonic() - self.started,
                "cleanup_scope": "posix_process_group",
                "scientific_acceptance": "not_admitted",
            },
        )


def _verify_observation(value: object) -> _Observation:
    if type(value) is not _Observation or value.seal is not _SEAL:
        raise DataError("native outcome requires an issued supervisor observation")
    if value.owner._issued.get(value.kind) is not value:
        raise DataError("native outcome is not the owner's issued observation")
    value.owner.verify()
    return value


def _run_owner(
    root: Path,
    job_id: str,
    fixture: str,
    seconds: float,
    lock: BinaryIO,
    *,
    native: NativeLaunch | None = None,
) -> None:
    owner = _Owner(root, job_id, fixture, seconds, lock, native=native)
    store = ControlStore(root)
    owner.open_control()
    lease: DurableJobLease | None = None
    started_published = False
    reason = "owner_error"

    def arm_safety() -> None:
        nonlocal lease
        process = owner.process
        assert process is not None
        lease = DurableJobLease.start_for_process(
            process,
            renew=owner.heartbeat_due.set,
            fail_journal=lambda message: None,
            cancel_requested=owner.poll_safety,
            cancel_journal=lambda: None,
            cleanup=owner._cleanup_once,
            observe_exit=owner.observe_exit,
            interval_seconds=0.05,
            terminate_grace_seconds=0.2,
            label="synthetic native child",
        )

    owner._on_spawn = arm_safety
    try:
        store.claim_native_fixture(job_id, owner)
        # The durable claim precedes payload effects. Safety is armed at the retained
        # Popen before any post-spawn verification or journal publication can block.
        try:
            if store.job_cancellation_requested(job_id):
                owner.request_stop("cancelled")
            if owner.poll_stop():
                reason = owner.stop_reason or "owner_error"
                return
            try:
                observed_start = owner.spawn()
            except _FixtureDeadlineExpired:
                reason = "timeout"
                return
            except _FixtureCancelledBeforeSpawn:
                reason = "cancelled"
                return
            store.record_native_fixture_observation(job_id, observed_start)
            started_published = True
            process = owner.process
            assert process is not None and lease is not None
            while owner.observe_exit() is None:
                if lease.failed:
                    owner.request_stop("owner_error")
                    break
                if lease.cancelled or owner.stop_reason is not None:
                    break
                if owner.heartbeat_due.is_set():
                    owner.heartbeat_due.clear()
                    try:
                        store.heartbeat_native_fixture(job_id, owner)
                        if store.job_cancellation_requested(job_id):
                            owner.request_stop("cancelled")
                    except Exception:
                        owner.request_stop("owner_error")
                        break
                time.sleep(0.02)
            else:
                reason = "exit"
        finally:
            if owner.process is not None:
                # Cleanup never waits for reporting or a journal-bearing thread. The
                # shared result remains uncertain if the one OS cleanup attempt fails.
                try:
                    owner._cleanup_once()
                except Exception:
                    reason = "owner_error"  # finish publishes the cached uncertainty.
                finally:
                    if lease is not None:
                        lease.stop_renewal()
                        if lease.failed and owner.stop_reason is None:
                            reason = "owner_error"
                try:
                    owner.poll_stop(check_deadline=False)
                except OSError:
                    owner.request_stop("owner_error")
                reason = owner.stop_reason or reason
                observation = owner.finish(reason)
            else:
                observation = owner.without_child(reason)
            pending_start = owner._issued.get("native_started")
            if pending_start is not None and not started_published:
                # Retry only the immutable journal observation, never payload dispatch.
                store.record_native_fixture_observation(job_id, pending_start)
            store.record_native_fixture_observation(job_id, observation)
            # A late request can arrive while a clean outcome is being published. It
            # remains a stop request, and only the store may consume the clean outcome.
            try:
                owner.poll_stop(check_deadline=False)
            except OSError:
                owner.request_stop("owner_error")
            if owner.cancel_received:
                from alpha_cli._native_fixture_store import cancel

                cancel(store, job_id, "live synthetic owner received a stop request", notify=False)
    finally:
        owner.close_control()


def start_synthetic_owner(
    root: Path,
    job_id: str,
    *,
    fixture: Fixture = "success",
    seconds: float = 2.0,
    native: NativeLaunch | None = None,
) -> subprocess.Popen[bytes]:
    """Start one trusted owner only. Reconnect is a separate, non-spawning store operation."""
    _fixture_root(root)
    host_identity()
    if (native is not None and type(native) is not _native_launch_type()) or (
        (fixture == "native_loop") != (native is not None)
    ):
        raise DataError("native loop fixture requires its fixed launch identity")
    native_args = (
        []
        if native is None
        else ["--native-source", str(native.source), "--native-mode", native.mode]
    )
    if native is not None and native.authority is not None:
        if native.authority.root != root:
            raise DataError("rule native owner belongs to another store")
        native.authority.verify()
        native_args += [
            "--rule-project",
            native.authority.project_id,
            "--rule-contract",
            native.authority.contract_id,
        ]
    lock = _open_lock(root, job_id)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Historical claims prohibit respawn even if their owner released its lock.
        if ControlStore(root).native_fixture_status(job_id).get("claim") is not None:
            raise DataError("native fixture already has a launch claim; reconnect only")
        environment = {
            "PATH": os.defpath,
            "LANG": "C.UTF-8",
            "PYTHONPATH": str(Path(__file__).resolve().parent.parent),
            # The child re-runs _fixture_root, which compares against its own temp directory.
            "TMPDIR": str(root.parent),
        }
        with (root / "control" / f"native-{job_id}.log").open("xb") as log:
            return subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "alpha_cli.native_supervisor",
                    str(root),
                    job_id,
                    fixture,
                    str(seconds),
                    str(lock.fileno()),
                    *native_args,
                ],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                pass_fds=(lock.fileno(),),
                env=environment,
            )
    except BlockingIOError as exc:
        raise DataError("native fixture owner lock is occupied; reconnect only") from exc
    finally:
        # Close our descriptor; LOCK_UN would also release the inherited owner's lock.
        lock.close()


def _entry() -> None:
    if sys.platform != "linux" or os.name != "posix":
        raise DataError("synthetic native supervisor supports linux-posix-v1 only")
    _require_retained_child_capability()
    parser = argparse.ArgumentParser(description="Internal fixed synthetic fixture owner")
    parser.add_argument("root", type=Path)
    parser.add_argument("job_id")
    parser.add_argument("fixture", choices=sorted(_FIXTURES))
    parser.add_argument("seconds", type=float)
    parser.add_argument("lock_fd", type=int)
    parser.add_argument("--native-source", type=Path)
    parser.add_argument("--native-mode", default="INCONCLUSIVE")
    parser.add_argument("--rule-project")
    parser.add_argument("--rule-contract")
    args = parser.parse_args()
    # This dedicated owner is the sole reaper. Establish default disposition here,
    # clearing inherited auto-reaping flags before any claim or child effects.
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    with os.fdopen(args.lock_fd, "rb+") as lock:
        study = authority = None
        if args.rule_project is not None or args.rule_contract is not None:
            from alpha_cli._native_rule_authority import RuleAuthority
            from alpha_cli._native_rule_protocol import contract_is_costed, selected_study

            if not args.rule_project or not args.rule_contract:
                raise DataError("rule owner requires complete authority identity")
            authority = RuleAuthority(args.root, args.rule_project, args.rule_contract)
            study = selected_study(contract_is_costed(authority.verify()))
        native = (
            None
            if args.native_source is None
            else _native_launch_type()(
                args.native_source, args.native_mode, study=study, authority=authority
            )
        )
        if native is None:
            _run_owner(args.root, args.job_id, args.fixture, args.seconds, lock)
        else:
            _run_owner(args.root, args.job_id, args.fixture, args.seconds, lock, native=native)


if __name__ == "__main__":
    # Use the canonical module's classes even when launched through python -m.
    from alpha_cli.native_supervisor import _entry as main

    main()

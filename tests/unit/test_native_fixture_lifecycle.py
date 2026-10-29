"""Public, disposable synthetic lifecycle conformance; no native workflow is executed."""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import hashlib
import inspect
import json
import math
import os
import re
import select
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from alpha_cli.control_store import ControlStore
from alpha_cli.durable_lease import DurableJobLease, terminate_and_reap
from alpha_cli.native_supervisor import (
    Fixture,
    _lock_path,
    _open_lock,
    _Owner,
    _request_live_stop,
    start_synthetic_owner,
    synthetic_workspace,
)
from alpha_core import DataError
from tests.unit.test_research_control_store import (
    PROJECT_ID,
    _approved_native_d1,
    _native_d1_job,
    _project,
)

JOB = "4c657d82-fc1a-44d8-b49b-bfdcfe93c52c"
Case = tuple[Path, ControlStore, str, dict[str, object]]
_ESCAPE_RELEASE_BARRIER = """    deadline=time.monotonic()+10
    while mode=='escape' and not (root/'release-escape').exists():
        if time.monotonic()>=deadline: raise RuntimeError('escape release barrier expired')
        time.sleep(0.01)
    time.sleep(0.1)
"""


@pytest.fixture
def case() -> Iterator[Case]:
    if sys.platform != "linux":
        pytest.skip("requires the Linux native owner profile")
    with synthetic_workspace() as root:
        store = ControlStore(root)
        _project(store)
        contract, _ = _approved_native_d1(store)
        _, reservation = _native_d1_job(store, contract, job_id=JOB)
        yield root, store, contract, reservation


def test_case_finalizer_never_signals_a_saved_payload_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = cast(Callable[[], Iterator[Case]], inspect.unwrap(case))()
    root, _, _, _ = next(fixture)
    marker = root / f"payload-{JOB}" / "payload.pid"
    marker.parent.mkdir()
    marker.write_text("2147483647")
    signals: list[tuple[int, int]] = []
    with monkeypatch.context() as scoped:
        scoped.setattr(os, "killpg", lambda pid, sig: signals.append((pid, sig)))
        with pytest.raises(StopIteration):
            next(fixture)
    assert signals == [], "case finalizer treated a saved payload marker as signal authority"


def _until(store: ControlStore, state: str, seconds: float = 8) -> dict[str, object]:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = store.native_fixture_status(JOB)
        if result["state"] == state:
            return result
        time.sleep(0.02)
    raise AssertionError(f"expected {state}; last state {result}")


@contextlib.contextmanager
def _owner(root: Path, fixture: Fixture = "wait") -> Iterator[_Owner]:
    with _open_lock(root, JOB) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield _Owner(root, JOB, fixture, 2, lock)


def _owner_seconds(root: Path) -> float:
    """The claimed fixture deadline if it fits the synthetic contract (0 < s <= 60), else 10."""
    try:
        claim = ControlStore(root).native_fixture_status(JOB)["claim"]
    except (DataError, OSError, sqlite3.Error):
        return 10.0
    seconds = claim.get("seconds") if isinstance(claim, dict) else None
    if (
        isinstance(seconds, int | float)
        and not isinstance(seconds, bool)
        and math.isfinite(seconds)
        and 0 < seconds <= 60
    ):
        return float(seconds)
    return 10.0


def _stop_test_owner(root: Path, process: subprocess.Popen[bytes]) -> None:
    """Ask the retained owner to clean its child; uncertainty never authorizes takeover."""
    deadline = time.monotonic() + 3
    while process.poll() is None:
        if _request_live_stop(root, JOB):
            break
        if time.monotonic() >= deadline:
            # Bounded observation of our own child after uncertain stop delivery; no signal, no
            # takeover. The owner ends itself at its fixture deadline; 8 s is the cleanup allowance.
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=_owner_seconds(root) + 8)
            assert process.returncode is not None, (
                "live owner stop is uncertain; no saved-PID fallback"
            )
            break
        time.sleep(0.01)
    process.wait(timeout=8)
    state = ControlStore(root).native_fixture_status(JOB)["state"]
    assert state in {"closed", "pending_scientific_admission"}, (
        f"owner ended without verified payload cleanup: {state}"
    )


def test_assertion_failure_still_requests_cleanup_from_the_live_owner(case: Case) -> None:
    root, store, _, _ = case
    process = start_synthetic_owner(root, JOB, fixture="wait", seconds=10)
    try:
        with pytest.raises(AssertionError, match="synthetic assertion failure"):
            try:
                _until_started(root, store, process, require_remaining=_POST_READY_DEADLINE_SECONDS)
                raise AssertionError("synthetic assertion failure")
            finally:
                _stop_test_owner(root, process)
        assert process.returncode == 0
        assert store.native_fixture_status(JOB)["state"] == "closed"
        assert store.get_job(JOB)["status"] == "cancelled"
    finally:
        _stop_test_owner(root, process)


def test_normal_exit_is_pending_science_and_reconnect_never_respawns(case: Case) -> None:
    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    # Fixture budget for a cold owner and payload start; not a start-up requirement.
    # The production deadline still governs.
    process = start_synthetic_owner(root, JOB, seconds=5)
    try:
        result = _until(store, "pending_scientific_admission")
        assert process.wait(timeout=3) == 0
        outcome = cast(dict[str, object], result["outcome"])
        assert outcome["returncode"] == 0
        assert outcome["scientific_acceptance"] == "not_admitted"
        assert outcome["cleanup_scope"] == "posix_process_group"
        assert store.get_job(JOB)["status"] == "running"
        assert store.heavyweight_job_capacity()["active_count"] == 1
        assert store.native_fixture_status(JOB, reconnect=True) == result
        with pytest.raises(DataError, match="reconnect only"):
            start_synthetic_owner(root, JOB)
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
        assert store.research_case_summary(PROJECT_ID)["terminal_attempt_count"] == 1  # D0 only
    finally:
        _stop_test_owner(root, process)


def test_fabricated_owner_and_observation_are_rejected(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract, _ = _approved_native_d1(store)
    _native_d1_job(store, contract, job_id=JOB)
    with pytest.raises(DataError, match="live trusted fixture owner"):
        store.claim_native_fixture(JOB, {"owner_id": "a" * 64})
    with pytest.raises(DataError, match="issued supervisor observation"):
        store.record_native_fixture_observation(JOB, {"returncode": 0, "cleanup": True})
    assert store.get_job(JOB)["job_id"] == JOB
    with store._transaction(write=False) as connection:
        assert not connection.execute(
            "SELECT 1 FROM job_events WHERE job_id=? AND event_type LIKE 'native_%'", (JOB,)
        ).fetchall()
    assert not (tmp_path / f"payload-{JOB}").exists()


def test_claim_is_single_use_and_generic_mutators_cannot_release_it(case: Case) -> None:
    root, store, contract, reservation = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        with pytest.raises(DataError, match="already has a launch claim"):
            store.claim_native_fixture(JOB, owner)
        actions: list[Callable[[], object]] = [
            lambda: store.set_job_status(JOB, "succeeded"),
            lambda: store.append_job_result(JOB, {"schema": "SyntheticNativeLifecycleV1"}),
            lambda: store.append_job_event(JOB, event_type="heartbeat", payload={}),
            lambda: store.transition_research_execution(
                PROJECT_ID,
                to_state="idle",
                contract_id=contract,
                actor="owner",
                reason="bypass",
                next_action="none",
                responsibility="owner",
            ),
            lambda: store.record_research_attempt(
                PROJECT_ID,
                contract,
                kind="d1-deep-research",
                status="failed",
                config_fingerprint=str(reservation["config_fingerprint"]),
                budget_used={},
                error="bypass",
                details={"attempt_number": 1, "evidence_zone": "D1"},
                launch_reservation_id=str(reservation["reservation_id"]),
            ),
        ]
        for action in actions:
            with pytest.raises(DataError, match="protected lifecycle"):
                action()
        assert store.reconcile_interrupted_jobs(at=datetime.now(UTC) + timedelta(days=1)) == []
    result = store.native_fixture_status(JOB, reconnect=True)
    assert result["state"] == "quarantined"
    assert store.get_job(JOB)["status"] == "running"
    assert store.heavyweight_job_capacity()["active_count"] == 1


# ("failure", 5) is a cold-start fixture budget; ("wait", 0.3) is the strict timeout control.
@pytest.mark.parametrize("fixture,seconds", [("failure", 5), ("wait", 0.3)])
def test_clean_failure_or_timeout_links_attempt_without_refund(
    case: Case, fixture: Fixture, seconds: float
) -> None:
    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    process = start_synthetic_owner(root, JOB, fixture=fixture, seconds=seconds)
    try:
        _until(store, "closed")
        assert process.wait(timeout=3) == 0
        outcome = cast(dict[str, object], store.native_fixture_status(JOB)["outcome"])
        assert outcome["reason"] == ("timeout" if fixture == "wait" else "exit")
        assert store.get_job(JOB)["status"] == "failed"
        assert store.heavyweight_job_capacity()["active_count"] == 0
        summary = store.research_case_summary(PROJECT_ID)
        assert summary["elapsed_budget"] == before
        assert summary["unfinalized_launch_count"] == 0
    finally:
        _stop_test_owner(root, process)


@pytest.mark.parametrize("fixture", ["wait", "descendant"])
def test_cancellation_reaps_qualified_group_and_closes_once(case: Case, fixture: Fixture) -> None:
    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    process = start_synthetic_owner(root, JOB, fixture=fixture, seconds=5)
    try:
        _until_started(root, store, process, require_remaining=_POST_READY_DEADLINE_SECONDS)
        store.cancel_native_fixture(JOB, reason="synthetic owner cancellation")
        _until(store, "closed")
        assert process.wait(timeout=3) == 0
        assert store.get_job(JOB)["status"] == "cancelled"
        assert store.cancel_native_fixture(JOB, reason="idempotent repeat")["state"] == "closed"
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
        assert store.heavyweight_job_capacity()["active_count"] == 0
        pid = int((root / f"payload-{JOB}" / "payload.pid").read_text())
        with pytest.raises(ProcessLookupError):
            os.killpg(pid, 0)
    finally:
        _stop_test_owner(root, process)


# Hang guard only, not a start-up requirement: readiness or a named no-start cause decides first.
_START_HANG_GUARD_SECONDS = 60.0
# Owner deadline that must remain at readiness for the post-ready reconnect/cancel/close checks;
# a fixture precondition (the observed post-ready cleanup took 0.72 s), not the production contract.
_POST_READY_DEADLINE_SECONDS = 1.0
# Cadence for no-start checks before the payload marker exists (each is a full store read).
_NO_START_CHECK_SECONDS = 0.5


def _owner_deadline_remaining(claim: dict[str, object]) -> float:
    """Conservative lower bound on the owner's remaining preparation deadline.

    It is measured from the owner process birth, which precedes its imports, whereas the real
    deadline starts later in ``_Owner.__init__``; the true remaining time is never smaller.
    """
    with open("/proc/uptime") as uptime:
        boot = time.time() - float(uptime.read().split()[0])
    started = boot + int(str(claim["owner_birth"])) / os.sysconf("SC_CLK_TCK")
    return float(cast(float, claim["seconds"])) - (time.time() - started)


def _until_started(
    root: Path,
    store: ControlStore,
    process: subprocess.Popen[bytes] | None,
    *,
    require_remaining: float | None = None,
) -> dict[str, float]:
    """Wait for this owner's claim and payload marker, failing at once on a named no-start cause.

    ``process`` is the launcher whose exit before readiness means nothing will start (``None`` for
    an in-process owner, whose own exception surfaces when its future is awaited).
    ``require_remaining`` (> 0, opt-in) is the owner deadline the caller's post-ready checks need;
    it applies only to subprocess owners, whose birth bounds the deadline conservatively. By
    default no budget is checked, so intentional-timeout and in-process owners keep their meaning.
    """
    begun = time.monotonic()
    marker = root / f"payload-{JOB}" / "payload.pid"
    log = root / "control" / f"native-{JOB}.log"
    # A status read is a full store read; before the marker appears consult it only this often,
    # so observing the start never competes with the owner's own claim and preparation.
    next_status = begun
    while time.monotonic() - begun < _START_HANG_GUARD_SECONDS:
        launcher_exited = process is not None and process.poll() is not None
        now = time.monotonic()
        if marker.exists() or launcher_exited or now >= next_status:
            next_status = now + _NO_START_CHECK_SECONDS
            status = store.native_fixture_status(JOB)
            claim = cast(dict[str, object] | None, status["claim"])
            # Terminal and launcher evidence come first, so a leftover payload marker can never
            # make a dead, quarantined or finished owner look ready. Each job's payload directory
            # and claim are one-shot, so a marker can only belong to this claimed owner.
            if status.get("outcome") is not None or status["state"] == "quarantined":
                raise AssertionError(f"owner reached a terminal state without starting: {status}")
            if launcher_exited:
                assert process is not None
                raise AssertionError(
                    f"launcher exited before start (returncode {process.returncode})"
                )
            if marker.exists() and claim is not None:
                remaining = _owner_deadline_remaining(claim)
                if require_remaining and remaining < require_remaining:
                    raise AssertionError(
                        f"ready with insufficient owner deadline remaining "
                        f"(conservative lower bound {remaining:.2f} s)"
                    )
                return {
                    "ready_seconds": time.monotonic() - begun,
                    "deadline_remaining_lower_bound": remaining,
                }
            if claim is None and log.exists():
                # The launch lock is held without a gap from the launcher into the owner;
                # acquiring it here means no owner holds it. Released at once, so ownership is
                # never taken.
                with _open_lock(root, JOB) as lock:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        pass
                    else:
                        fcntl.flock(lock, fcntl.LOCK_UN)
                        raise AssertionError(
                            "owner exited before claiming; the launch lock is free"
                        )
        time.sleep(0.02)
    raise AssertionError(
        f"synthetic payload did not start within the {_START_HANG_GUARD_SECONDS:g} s hang guard "
        "(not a start-up requirement)"
    )


def test_owner_child_inherits_the_workspace_temp_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if sys.platform != "linux":
        pytest.skip("requires the Linux native owner profile")
    # Short and non-default: the owner's AF_UNIX control path must stay under the OS limit.
    temp = Path(tempfile.mkdtemp(prefix="t", dir="/tmp")).resolve()
    try:
        monkeypatch.setenv("TMPDIR", str(temp))
        monkeypatch.setattr(tempfile, "tempdir", None)
        with synthetic_workspace() as root:
            assert root.parent == temp
            store = ControlStore(root)
            _project(store)
            contract, _ = _approved_native_d1(store)
            _native_d1_job(store, contract, job_id=JOB)
            # Fixture budget for the TMPDIR inheritance check (cold owner plus payload start);
            # not a start-up requirement. The production deadline still governs.
            process = start_synthetic_owner(root, JOB, seconds=5)
            try:
                _until(store, "pending_scientific_admission")
                assert process.wait(timeout=3) == 0
            finally:
                if process.poll() is None:
                    _stop_test_owner(root, process)
    finally:
        temp.rmdir()


def test_owner_refuses_a_workspace_outside_or_aliasing_its_temp_root(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, store, _, _ = case
    elsewhere = Path(tempfile.mkdtemp(prefix="t", dir="/tmp")).resolve()
    alias = elsewhere / "alpha-native-fixture-alias"
    try:
        alias.symlink_to(root)
        with pytest.raises(DataError, match="disposable synthetic workspace"):
            start_synthetic_owner(alias, JOB)
        with monkeypatch.context() as scoped:
            scoped.setenv("TMPDIR", str(elsewhere))
            scoped.setattr(tempfile, "tempdir", None)
            with pytest.raises(DataError, match="disposable synthetic workspace"):
                start_synthetic_owner(root, JOB)
        assert store.native_fixture_status(JOB)["claim"] is None
        assert not (root / "control" / f"native-{JOB}.log").exists()
    finally:
        alias.unlink(missing_ok=True)
        elsewhere.rmdir()


def test_cancel_pending_process_evidence_is_not_scientific_success(case: Case) -> None:
    root, store, _, _ = case
    # Fixture budget for a cold owner and payload start; not a start-up requirement.
    # The production deadline still governs.
    process = start_synthetic_owner(root, JOB, seconds=5)
    try:
        _until(store, "pending_scientific_admission")
        assert process.wait(timeout=3) == 0
        store.cancel_native_fixture(JOB, reason="abandon process-only result")
        assert store.get_job(JOB)["status"] == "cancelled"
        summary = store.research_case_summary(PROJECT_ID)
        assert summary["terminal_attempt_count"] == 2
        assert summary["execution_state"] == "failed"
        assert summary["active_job_id"] is None
    finally:
        _stop_test_owner(root, process)


def test_cancel_pending_failure_still_reaps_its_owner(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    owners: list[subprocess.Popen[bytes]] = []
    real_start = start_synthetic_owner  # bound before the module name is patched

    def start(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        owners.append(real_start(*args, **kwargs))
        return owners[-1]

    def fail(*_: object, **__: object) -> dict[str, object]:
        # Precondition: the owner has bound its stop endpoint, so the finally's stop request
        # is deliverable and the injected failure is the only one raised.
        stop = _lock_path(case[0], JOB).with_suffix(".stop")
        deadline = time.monotonic() + _START_HANG_GUARD_SECONDS
        while not stop.exists() and owners[0].poll() is None:
            assert time.monotonic() < deadline, "owner never bound its stop endpoint"
            time.sleep(0.02)
        raise AssertionError("synthetic readiness failure")

    module = sys.modules[__name__]
    monkeypatch.setattr(module, "start_synthetic_owner", start)
    monkeypatch.setattr(module, "_until", fail)
    with pytest.raises(AssertionError, match="synthetic readiness failure"):
        test_cancel_pending_process_evidence_is_not_scientific_success(case)
    (owner,) = owners
    assert owner.returncode is not None  # waited by the test's own finally, never leaked


def test_undeliverable_stop_waits_out_the_owner_deadline_and_reaps(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, store, _, _ = case
    process = start_synthetic_owner(root, JOB, fixture="wait", seconds=5)
    try:
        _until_started(root, store, process)
        assert _owner_seconds(root) == 5.0
        with monkeypatch.context() as scoped:
            scoped.setattr(sys.modules[__name__], "_request_live_stop", lambda *_: False)
            _stop_test_owner(root, process)  # stop never delivered: bounded wait only
        assert process.returncode == 0
        outcome = cast(dict[str, object], store.native_fixture_status(JOB)["outcome"])
        assert outcome["reason"] == "timeout"
    finally:
        _stop_test_owner(root, process)


def test_still_live_owner_after_bounded_wait_fails_loudly_without_signals(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, store, _, _ = case
    process = start_synthetic_owner(root, JOB, fixture="wait", seconds=20)
    try:
        _until_started(root, store, process)
        with monkeypatch.context() as scoped:
            module = sys.modules[__name__]
            scoped.setattr(module, "_request_live_stop", lambda *_: False)
            scoped.setattr(module, "_owner_seconds", lambda _: 0.0)  # bound = cleanup allowance
            with pytest.raises(AssertionError, match="live owner stop is uncertain"):
                _stop_test_owner(root, process)
        assert process.poll() is None  # still live: never signalled, never reported cleaned
        assert store.native_fixture_status(JOB)["state"] == "owner_active"
    finally:
        _stop_test_owner(root, process)


def test_owner_death_quarantines_without_signalling_or_relaunch(case: Case) -> None:
    if sys.platform != "linux":
        pytest.skip("requires Linux pidfd ownership")
    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    owner_process = start_synthetic_owner(root, JOB, fixture="wait", seconds=5)
    payload_pidfd: int | None = None
    payload_verified = False
    exited = select.poll()
    try:
        _until_started(root, store, owner_process)
        pid = int((root / f"payload-{JOB}" / "payload.pid").read_text())
        identity = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        assert identity[0] != "Z" and int(identity[1]) == owner_process.pid
        payload_pidfd = os.pidfd_open(pid)
        exited.register(payload_pidfd, select.POLLIN)
        retained = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        assert retained[19] == identity[19] and int(retained[1]) == owner_process.pid
        assert owner_process.poll() is None and not exited.poll(0)
        payload_verified = True
        owner_process.kill()
        owner_process.wait(timeout=3)
        assert not _request_live_stop(root, JOB)  # A stale endpoint is not a replacement owner.
        result = store.native_fixture_status(JOB, reconnect=True)
        assert result["state"] == "quarantined"
        assert not exited.poll(0)  # Reconnect did not clean the retained live payload.
        assert store.native_fixture_status(JOB, reconnect=True) == result
        assert store.get_job(JOB)["status"] == "running"
        assert store.heavyweight_job_capacity()["active_count"] == 1
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
        with pytest.raises(DataError, match="reconnect only"):
            start_synthetic_owner(root, JOB)
    finally:
        try:
            if owner_process.poll() is None:
                store.cancel_native_fixture(JOB, reason="test cleanup through retained live owner")
            owner_process.wait(timeout=8)
            if payload_pidfd is not None and payload_verified:
                with contextlib.suppress(ProcessLookupError):
                    signal.pidfd_send_signal(payload_pidfd, signal.SIGKILL)
                assert exited.poll(3000), "retained deliberate-crash payload did not exit"
        finally:
            if payload_pidfd is not None:
                os.close(payload_pidfd)


def _startup_facts(root: Path, store: ControlStore, started: float) -> dict[str, object]:
    """Diagnostic-only, read-only facts that workspace teardown would otherwise delete."""
    facts: dict[str, object] = {"elapsed_seconds": round(time.monotonic() - started, 3)}
    try:
        facts["status"] = store.native_fixture_status(JOB)
    except (DataError, OSError, sqlite3.Error) as exc:  # recorded as evidence of the failure
        facts["status_error"] = repr(exc)
    log = root / "control" / f"native-{JOB}.log"
    facts["owner_log"] = log.read_text(errors="replace")[-4000:] if log.exists() else None
    files: dict[str, object] = {}
    for folder in ("control", f"payload-{JOB}"):
        if (root / folder).is_dir():
            for path in sorted((root / folder).iterdir()):
                try:
                    files[str(path.relative_to(root))] = path.stat().st_mtime
                except FileNotFoundError:  # the owner may unlink its socket while we look
                    files[str(path.relative_to(root))] = "removed during capture"
    facts["files"] = files
    return facts


def _retain(failure: BaseException, record: Callable[[], None]) -> None:
    """Run a diagnostic capture; its own failure is noted and never replaces ``failure``."""
    try:
        record()
    except Exception as exc:  # noqa: BLE001 - diagnostics must not mask the original failure
        failure.add_note(f"diagnostic capture failed: {exc!r}")


# Opt-in startup-margin reporting: a run name (never a path) under the ignored evidence root.
_MARGIN_RECEIPT_ENV = "ALPHA_STARTUP_MARGIN_RUN"
_MARGIN_RECEIPT_ROOT = Path(__file__).resolve().parents[2] / ".alpha" / "state" / "startup-margins"


def _write_margin_receipt(node_id: str, readiness: dict[str, float]) -> None:
    """Write one exclusive receipt into a pre-created, empty run directory; unset does nothing."""
    run = os.environ.get(_MARGIN_RECEIPT_ENV)
    if not run:
        return
    folder = _MARGIN_RECEIPT_ROOT / run
    if (
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", run) is None
        or _MARGIN_RECEIPT_ROOT.is_symlink()
        or folder.is_symlink()
        or not folder.is_dir()
    ):
        raise AssertionError(f"{_MARGIN_RECEIPT_ENV} must name an existing run directory")
    if any(folder.iterdir()):
        raise AssertionError(f"startup-margin run directory is not empty: {folder}")
    name = hashlib.sha256(node_id.encode()).hexdigest()[:16] + ".json"
    receipt = {"test": node_id, **{f"start_{key}": value for key, value in readiness.items()}}
    descriptor = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(receipt, handle, sort_keys=True)


def test_margin_receipt_is_opt_in_exclusive_and_confined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys.modules[__name__], "_MARGIN_RECEIPT_ROOT", tmp_path)
    readiness = {"ready_seconds": 2.5, "deadline_remaining_lower_bound": 2.25}
    monkeypatch.delenv(_MARGIN_RECEIPT_ENV, raising=False)
    _write_margin_receipt("t::a", readiness)
    assert list(tmp_path.iterdir()) == []
    for bad in ("../escape", "/abs", "missing"):
        monkeypatch.setenv(_MARGIN_RECEIPT_ENV, bad)
        with pytest.raises(AssertionError, match="existing run directory"):
            _write_margin_receipt("t::a", readiness)
    (tmp_path / "run1").mkdir()
    monkeypatch.setenv(_MARGIN_RECEIPT_ENV, "run1")
    _write_margin_receipt("t::a", readiness)
    (receipt,) = (tmp_path / "run1").iterdir()
    assert json.loads(receipt.read_text()) == {
        "test": "t::a",
        "start_ready_seconds": 2.5,
        "start_deadline_remaining_lower_bound": 2.25,
    }
    with pytest.raises(AssertionError, match="not empty"):
        _write_margin_receipt("t::a", readiness)
    assert json.loads(receipt.read_text())["start_ready_seconds"] == 2.5


def test_controller_death_preserves_same_owner_for_cancel(
    case: Case,
    tmp_path: Path,
    record_property: Callable[[str, object], None],
    request: pytest.FixtureRequest,
) -> None:
    root, store, _, _ = case
    code = (
        "from pathlib import Path; import time; "
        "from alpha_cli.native_supervisor import start_synthetic_owner; "
        f"start_synthetic_owner(Path({str(root)!r}), {JOB!r}, fixture='wait', seconds=5); "
        "time.sleep(30)"
    )
    started = time.monotonic()
    controller = subprocess.Popen([sys.executable, "-c", code])
    evidence = tmp_path / "native-lifecycle-diagnostic.json"
    diagnostic: dict[str, object] = {}
    startup_failure: AssertionError | None = None

    def record(key: str, extra: dict[str, object] | None = None) -> None:
        diagnostic[key] = {**_startup_facts(root, store, started), **(extra or {})}
        evidence.write_text(json.dumps(diagnostic, default=str, indent=2))

    try:
        try:
            readiness = _until_started(
                root, store, controller, require_remaining=_POST_READY_DEADLINE_SECONDS
            )
        except AssertionError as failure:
            startup_failure = failure
            failure.add_note(f"startup diagnostic retained at {evidence}")
            _retain(failure, lambda: record("at_failure"))
            raise
        # Start-up latency is recorded evidence (the former fixed window's accidental canary).
        for name, value in readiness.items():
            record_property(f"start_{name}", round(value, 3))
        claim = store.native_fixture_status(JOB)["claim"]
        controller.kill()
        controller.wait(timeout=3)
        assert store.native_fixture_status(JOB, reconnect=True)["claim"] == claim
        assert store.native_fixture_status(JOB)["state"] == "owner_active"
        store.cancel_native_fixture(JOB, reason="cancel after controller restart")
        _until(store, "closed")
        assert store.get_job(JOB)["status"] == "cancelled"
        # Closed is a journal fact; the detached owner may still be finishing its
        # final cancellation read. Retain the workspace until its actual lock closes.
        with _open_lock(root, JOB) as lock:
            deadline = time.monotonic() + 5
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    assert time.monotonic() < deadline, "detached owner did not release its lock"
                    time.sleep(0.02)
                else:
                    break
    finally:
        cleanup_started = time.monotonic()
        if controller.poll() is None:
            controller.kill()
        controller.wait(timeout=3)
        with _open_lock(root, JOB) as lock:
            deadline = time.monotonic() + 8
            while True:
                _request_live_stop(root, JOB)
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    assert time.monotonic() < deadline, "detached owner cleanup is uncertain"
                    time.sleep(0.02)
                else:
                    break
        if startup_failure is not None:
            released = round(time.monotonic() - cleanup_started, 3)
            _retain(
                startup_failure,
                lambda: record(
                    "after_cleanup",
                    {
                        "controller_returncode": controller.returncode,
                        "lock_released_after_seconds": released,
                    },
                ),
            )
        assert store.native_fixture_status(JOB)["state"] in {"unclaimed", "closed"}
    # Reached only after every assertion and cleanup check passed.
    _write_margin_receipt(request.node.nodeid, readiness)


def test_concurrent_claims_commit_once_and_claim_spawn_gap_stays_charged(case: Case) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:

        def attempt(_: int) -> str:
            try:
                store.claim_native_fixture(JOB, owner)
            except DataError:
                return "denied"
            return "claimed"

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(attempt, range(2))) == ["claimed", "denied"]
    assert not (root / f"payload-{JOB}").exists()
    assert store.native_fixture_status(JOB, reconnect=True)["state"] == "quarantined"
    assert store.heavyweight_job_capacity()["active_count"] == 1


def test_unsupported_host_denies_before_database_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("alpha_cli.native_supervisor.sys.platform", "darwin")
    monkeypatch.setattr(
        ControlStore, "_open", lambda self: pytest.fail("unsupported host opened DB")
    )
    from alpha_cli.native_supervisor import _MARKER

    with tempfile.TemporaryDirectory(prefix="alpha-native-fixture-") as directory:
        root = Path(directory).resolve()
        (root / "synthetic-only").write_text(_MARKER)
        with pytest.raises(DataError, match="linux-posix-v1 only"):
            start_synthetic_owner(root, JOB)


def test_foreign_host_epoch_cannot_reconnect_or_cancel(case: Case) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
    with store._transaction(write=True) as connection:
        row = connection.execute(
            "SELECT payload_json FROM job_events WHERE event_type='native_claim' AND job_id=?",
            (JOB,),
        ).fetchone()
        payload = json.loads(row[0])
        payload["host"]["boot"] = "foreign-host-epoch"
        connection.execute(
            "UPDATE job_events SET payload_json=? WHERE job_id=? AND event_type='native_claim'",
            (json.dumps(payload), JOB),
        )
    with pytest.raises(DataError, match="foreign/unknown host epoch"):
        store.native_fixture_status(JOB, reconnect=True)
    with pytest.raises(DataError, match="foreign/unknown host epoch"):
        store.cancel_native_fixture(JOB, reason="no foreign takeover")
    assert store.get_job(JOB)["status"] == "running"


def test_finalized_reservation_cannot_be_claimed(case: Case) -> None:
    root, store, contract, reservation = case
    store.record_research_attempt(
        PROJECT_ID,
        contract,
        kind="d1-deep-research",
        status="failed",
        config_fingerprint=str(reservation["config_fingerprint"]),
        budget_used={},
        error="synthetic terminal failure before claim",
        details={"attempt_number": 1, "evidence_zone": "D1"},
        launch_reservation_id=str(reservation["reservation_id"]),
    )
    with _owner(root) as owner, pytest.raises(DataError, match="already has a terminal attempt"):
        store.claim_native_fixture(JOB, owner)


def test_issued_observation_is_immutable_and_replays_once(case: Case) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        started = owner.spawn()
        child = owner.process
        assert child is not None
        try:
            store.record_native_fixture_observation(JOB, started)
            observation = owner.finish("cancelled")
            with pytest.raises(TypeError):
                observation.fields["returncode"] = 0  # type: ignore[index]
            altered = dataclasses.replace(observation, fields={"returncode": 0})
            with pytest.raises(DataError, match="owner's issued observation"):
                store.record_native_fixture_observation(JOB, altered)
            first = store.record_native_fixture_observation(JOB, observation)
            assert store.record_native_fixture_observation(JOB, observation) == first
            assert store.research_case_summary(PROJECT_ID)["terminal_attempt_count"] == 2
        finally:
            terminate_and_reap(
                child, grace_seconds=0.2, process_group_id=child.pid, retain_leader=True
            )


def test_failure_closure_rolls_back_event_attempt_link_and_status(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import _native_fixture_store as native_store

    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        started = owner.spawn()
        child = owner.process
        assert child is not None
        try:
            store.record_native_fixture_observation(JOB, started)
            observation = owner.finish("cancelled")
            original = native_store._failure_close

            def interrupted(*args: Any, **kwargs: Any) -> None:
                original(*args, **kwargs)
                raise RuntimeError("injected failure after all closure writes")

            with monkeypatch.context() as scoped:
                scoped.setattr(native_store, "_failure_close", interrupted)
                with pytest.raises(RuntimeError, match="after all closure writes"):
                    store.record_native_fixture_observation(JOB, observation)
            assert store.native_fixture_status(JOB)["outcome"] is None
            assert store.get_job(JOB)["status"] == "running"
            summary = store.research_case_summary(PROJECT_ID)
            assert summary["unfinalized_launch_count"] == 1
            assert summary["terminal_attempt_count"] == 1
            store.record_native_fixture_observation(JOB, observation)
            assert store.get_job(JOB)["status"] == "failed"
        finally:
            terminate_and_reap(
                child, grace_seconds=0.2, process_group_id=child.pid, retain_leader=True
            )


def test_uncertain_cleanup_never_releases_capacity(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        started = owner.spawn()
        child = owner.process
        assert child is not None
        try:
            store.record_native_fixture_observation(JOB, started)
            with monkeypatch.context() as scoped:

                def denied(*args: Any, **kwargs: Any) -> None:
                    raise PermissionError("synthetic cleanup denied")

                scoped.setattr("alpha_cli.native_supervisor.terminate_and_reap", denied)
                observation = owner.finish("cancelled")
            store.record_native_fixture_observation(JOB, observation)
            assert store.native_fixture_status(JOB)["state"] == "quarantined"
            assert store.heavyweight_job_capacity()["active_count"] == 1
            assert child.poll() is None
        finally:
            terminate_and_reap(
                child, grace_seconds=0.2, process_group_id=child.pid, retain_leader=True
            )


def test_lost_lock_provenance_still_cleans_retained_child(case: Case) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        started = owner.spawn()
        child = owner.process
        assert child is not None
        try:
            store.record_native_fixture_observation(JOB, started)
            lock_path = root / "control" / f"native-{JOB}.lock"
            lock_path.rename(lock_path.with_suffix(".old"))
            lock_path.touch()
            with pytest.raises(DataError, match="lock identity changed"):
                owner.finish("cancelled")
            assert child.poll() is not None
            assert store.get_job(JOB)["status"] == "running"
        finally:
            terminate_and_reap(
                child, grace_seconds=0.2, process_group_id=child.pid, retain_leader=True
            )


def test_cancel_before_claim_dispatches_no_payload(case: Case) -> None:
    root, store, _, _ = case
    store.request_job_cancellation(JOB, actor="fixture", reason="stop before launch")
    with _owner(root) as owner, pytest.raises(DataError, match="cancellation prohibits"):
        store.claim_native_fixture(JOB, owner)
    assert store.native_fixture_status(JOB)["state"] == "unclaimed"
    assert not (root / f"payload-{JOB}").exists()


def test_live_owner_can_close_cancel_before_any_spawn(case: Case) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        store.request_job_cancellation(JOB, actor="fixture", reason="stop before spawn")
        store.record_native_fixture_observation(JOB, owner.without_child("cancelled"))
        assert store.get_job(JOB)["status"] == "cancelled"
        assert store.native_fixture_status(JOB)["state"] == "closed"
        assert not (root / f"payload-{JOB}").exists()


def test_spawn_before_started_record_is_quarantined(case: Case) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        owner.spawn()  # The observed start never reached the database.
        child = owner.process
        assert child is not None
        try:
            assert child.poll() is None
        finally:
            terminate_and_reap(
                child, grace_seconds=0.2, process_group_id=child.pid, retain_leader=True
            )
    with pytest.MonkeyPatch.context() as scoped:
        scoped.setattr(os, "killpg", lambda *args: pytest.fail("reconnect signalled a saved PGID"))
        result = store.native_fixture_status(JOB, reconnect=True)
    assert result["state"] == "quarantined"
    assert store.get_job(JOB)["status"] == "running"


def test_owner_from_other_store_and_changed_phase_are_denied(case: Case) -> None:
    root, store, _, _ = case
    with (
        synthetic_workspace() as other,
        _owner(other) as owner,
        pytest.raises(DataError, match="another synthetic store"),
    ):
        store.claim_native_fixture(JOB, owner)
    with store._transaction(write=True) as connection:
        connection.execute(
            "UPDATE research_phase_events SET phase='confirmation_review' "
            "WHERE project_id=? AND sequence="
            "(SELECT MAX(sequence) FROM research_phase_events WHERE project_id=?)",
            (PROJECT_ID, PROJECT_ID),
        )
    with _owner(root) as owner, pytest.raises(DataError, match="active approved D1 contract"):
        store.claim_native_fixture(JOB, owner)


def test_native_phase_and_review_mutations_are_guarded(case: Case) -> None:
    root, store, contract, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        with (
            store._transaction(write=True) as connection,
            pytest.raises(DataError, match="protected lifecycle"),
        ):
            store._append_research_phase_event(
                connection,
                project_id=PROJECT_ID,
                contract_id=contract,
                phase="closed",
                actor="fixture",
                reason="bypass",
                next_action="none",
                responsibility="owner",
                blocker=None,
                recovery=None,
                at=datetime.now(UTC).isoformat(),
            )
        with pytest.raises(DataError, match="protected lifecycle"):
            store.review_research_contract(
                PROJECT_ID,
                contract,
                scope="exploration",
                decision="approve",
                actor="owner",
                actor_kind="human",
                reason="bypass",
            )
        with pytest.raises(DataError, match="unsupported append-only"):
            store.append_job_event(JOB, event_type="native_outcome", payload={"returncode": 0})


def test_heartbeat_failure_cannot_be_reported_as_success(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.native_supervisor import _run_owner

    root, store, _, _ = case

    def fail_heartbeat(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("synthetic heartbeat storage failure")

    monkeypatch.setattr(ControlStore, "heartbeat_native_fixture", fail_heartbeat)
    with _open_lock(root, JOB) as lock:
        _run_owner(root, JOB, "descendant", 5, lock)
    outcome = cast(dict[str, object], store.native_fixture_status(JOB)["outcome"])
    assert outcome["reason"] == "owner_error"
    assert store.get_job(JOB)["status"] == "failed"


def test_claimed_pre_spawn_filesystem_failure_is_accounted(case: Case) -> None:
    from alpha_cli.native_supervisor import _run_owner

    root, store, _, _ = case
    (root / f"payload-{JOB}").mkdir()
    with _open_lock(root, JOB) as lock, pytest.raises(FileExistsError):
        _run_owner(root, JOB, "success", 2, lock)
    outcome = cast(dict[str, object], store.native_fixture_status(JOB)["outcome"])
    assert outcome["cleanup_scope"] == "no_payload_spawn_attempted"
    assert store.get_job(JOB)["status"] == "failed"


def test_escaped_descendant_is_outside_the_declared_cleanup_scope(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform != "linux":
        pytest.skip("requires Linux pidfd ownership")
    from alpha_cli import native_supervisor as supervisor

    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    marker = root / f"payload-{JOB}" / "descendant.pid"
    release = marker.parent / "release-escape"
    monkeypatch.setattr(
        supervisor,
        "_PAYLOAD",
        supervisor._PAYLOAD.replace("    time.sleep(0.1)\n", _ESCAPE_RELEASE_BARRIER),
    )
    escaped_pidfd: int | None = None
    escaped_verified = False
    exited = select.poll()
    with _owner(root, "escape") as owner:
        store.claim_native_fixture(JOB, owner)
        started = owner.spawn()
        leader = owner.process
        assert leader is not None
        try:
            store.record_native_fixture_observation(JOB, started)
            deadline = time.monotonic() + 3
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert marker.exists(), "fixed escape did not publish readiness"
            escaped = int(marker.read_text())
            identity = Path(f"/proc/{escaped}/stat").read_text().rsplit(")", 1)[1].split()
            assert identity[0] != "Z" and int(identity[1]) == leader.pid
            escaped_pidfd = os.pidfd_open(escaped)
            exited.register(escaped_pidfd, select.POLLIN)
            retained = Path(f"/proc/{escaped}/stat").read_text().rsplit(")", 1)[1].split()
            assert retained[19] == identity[19] and int(retained[1]) == leader.pid
            assert leader.poll() is None and not exited.poll(0)
            escaped_verified = True
            release.touch()
            leader.wait(timeout=3)
            observation = owner.finish("exit")
            store.record_native_fixture_observation(JOB, observation)
            assert observation.kind == "native_uncertain"
            assert store.native_fixture_status(JOB)["state"] == "quarantined"
            assert store.get_job(JOB)["status"] == "running"
            assert store.heavyweight_job_capacity()["active_count"] == 1
            summary = store.research_case_summary(PROJECT_ID)
            assert summary["elapsed_budget"] == before
            assert summary["unfinalized_launch_count"] == 1
            assert not exited.poll(0)  # The retained escaped child remains outside containment.
        finally:
            release.touch()
            try:
                terminate_and_reap(
                    leader, grace_seconds=0.2, process_group_id=leader.pid, retain_leader=True
                )
            finally:
                if escaped_pidfd is not None:
                    try:
                        if escaped_verified:
                            with contextlib.suppress(ProcessLookupError):
                                signal.pidfd_send_signal(escaped_pidfd, signal.SIGKILL)
                            assert exited.poll(3000), "retained synthetic escape did not exit"
                    finally:
                        os.close(escaped_pidfd)


def test_saved_pid_is_never_signal_authority(case: Case, monkeypatch: pytest.MonkeyPatch) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
    with store._transaction(write=True) as connection:
        row = connection.execute(
            "SELECT payload_json FROM job_events WHERE job_id=? AND event_type='native_claim'",
            (JOB,),
        ).fetchone()
        payload = json.loads(row[0])
        payload.update(owner_pid=1, owner_birth="reused-pid-diagnostic")
        connection.execute(
            "UPDATE job_events SET payload_json=? WHERE job_id=? AND event_type='native_claim'",
            (json.dumps(payload), JOB),
        )
    with monkeypatch.context() as scoped:
        scoped.setattr(os, "kill", lambda *args: pytest.fail("reconnect signalled a stored PID"))
        scoped.setattr(os, "killpg", lambda *args: pytest.fail("reconnect signalled a stored PGID"))
        assert store.native_fixture_status(JOB, reconnect=True)["state"] == "quarantined"


@pytest.mark.parametrize("field", ["spec_sha256", "job_id"])
def test_persisted_claim_binding_corruption_fails_closed(case: Case, field: str) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
    with store._transaction(write=True) as connection:
        row = connection.execute(
            "SELECT payload_json FROM job_events WHERE job_id=? AND event_type='native_claim'",
            (JOB,),
        ).fetchone()
        payload = json.loads(row[0])
        payload[field] = "fabricated"
        connection.execute(
            "UPDATE job_events SET payload_json=? WHERE job_id=? AND event_type='native_claim'",
            (json.dumps(payload), JOB),
        )
    with pytest.raises(DataError, match="identity/order|reserved invocation"):
        store.native_fixture_status(JOB, reconnect=True)


def test_lock_loss_immediately_after_spawn_does_not_skip_cleanup(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, store, _, _ = case
    real_popen = subprocess.Popen
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)

        def replace_lock(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
            process = real_popen(*args, **kwargs)
            path = root / "control" / f"native-{JOB}.lock"
            path.rename(path.with_suffix(".old"))
            path.touch()
            return process

        with monkeypatch.context() as scoped:
            scoped.setattr("alpha_cli.native_supervisor.subprocess.Popen", replace_lock)
            with pytest.raises(DataError, match="lock identity changed"):
                owner.spawn()
        child = owner.process
        assert child is not None
        try:
            with pytest.raises(DataError, match="lock identity changed"):
                owner.finish("owner_error")
            assert child.poll() is not None
            assert store.get_job(JOB)["status"] == "running"
        finally:
            terminate_and_reap(
                child, grace_seconds=0.2, process_group_id=child.pid, retain_leader=True
            )


def test_cancellation_timestamp_follows_a_competing_heartbeat(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.control_store import _at

    root, store, _, _ = case
    with _owner(root, "success") as owner:
        store.claim_native_fixture(JOB, owner)
        started = owner.spawn()
        child = owner.process
        assert child is not None
        child.wait(timeout=3)
        store.record_native_fixture_observation(JOB, started)
        store.record_native_fixture_observation(JOB, owner.finish("exit"))
    original = store._transaction
    injected = False

    @contextlib.contextmanager
    def competing_heartbeat(*, write: bool) -> Iterator[sqlite3.Connection]:
        nonlocal injected
        with original(write=write) as connection:
            if write and not injected:
                injected = True
                # Reproduce a newer heartbeat winning before the canceller gets its lock.
                time.sleep(0.01)
                timestamp = _at(None)
                connection.execute(
                    "UPDATE jobs SET updated_at=?, heartbeat_at=? WHERE job_id=?",
                    (timestamp, timestamp, JOB),
                )
            yield connection

    monkeypatch.setattr(store, "_transaction", competing_heartbeat)
    assert store.cancel_native_fixture(JOB, reason="racing heartbeat")["state"] == "closed"
    assert injected
    assert store.get_job(JOB)["status"] == "cancelled"


def test_unobserved_spawn_failure_is_single_use_and_quarantined(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, store, _, _ = case
    calls = 0

    def failed_spawn(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        nonlocal calls
        calls += 1
        raise OSError("synthetic spawn result unavailable")

    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        with monkeypatch.context() as scoped:
            scoped.setattr("alpha_cli.native_supervisor.subprocess.Popen", failed_spawn)
            with pytest.raises(OSError, match="result unavailable"):
                owner.spawn()
            with pytest.raises(DataError, match="already observed"):
                owner.spawn()
        store.record_native_fixture_observation(JOB, owner.without_child("owner_error"))
        assert calls == 1
        assert store.native_fixture_status(JOB)["state"] == "quarantined"
        assert store.heavyweight_job_capacity()["active_count"] == 1


def test_joining_renewal_transfers_cleanup_without_claiming_exit(case: Case) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        store.record_native_fixture_observation(JOB, owner.spawn())
        child = owner.process
        assert child is not None
        lease = DurableJobLease.start_for_process(
            child,
            renew=lambda: None,
            fail_journal=lambda message: pytest.fail("renewal join published a failure"),
            interval_seconds=0.05,
        )
        try:
            lease.stop_renewal()
            assert not lease.failed
            assert child.poll() is None
            assert store.get_job(JOB)["status"] == "running"
            observation = owner.finish("timeout")
            lease.stop()  # Existing stop semantics still verify the now-clean group.
            lease.raise_if_failed()
            store.record_native_fixture_observation(JOB, observation)
            assert observation.fields["reason"] == "timeout"
        finally:
            terminate_and_reap(
                child, grace_seconds=0.2, process_group_id=child.pid, retain_leader=True
            )


def _controller(
    root: Path, *, before: str = "", tmpdir: str | None = None
) -> subprocess.Popen[bytes]:
    code = (
        "from pathlib import Path; import time; "
        "from alpha_cli.native_supervisor import start_synthetic_owner; "
        f"{before}"
        f"start_synthetic_owner(Path({str(root)!r}), {JOB!r}, fixture='wait', seconds=5); "
        "time.sleep(30)"
    )
    env = None if tmpdir is None else {**os.environ, "TMPDIR": tmpdir}
    return subprocess.Popen([sys.executable, "-c", code], env=env)


def _release_launch(root: Path, launcher: subprocess.Popen[bytes]) -> None:
    """Owned cleanup only: end our launcher, then ask any owner to stop and await its lock."""
    if launcher.poll() is None:
        launcher.kill()
    launcher.wait(timeout=3)
    with _open_lock(root, JOB) as lock:
        deadline = time.monotonic() + 8
        while True:
            _request_live_stop(root, JOB)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                assert time.monotonic() < deadline, "owner cleanup is uncertain"
                time.sleep(0.02)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)
                break


def _prompt(begun: float) -> None:
    assert time.monotonic() - begun < _START_HANG_GUARD_SECONDS / 2, "no-start was not prompt"


def test_readiness_waits_past_a_slow_launcher_without_spending_the_owner_deadline(
    case: Case, record_property: Callable[[str, object], None]
) -> None:
    root, store, _, _ = case
    controller = _controller(root, before="time.sleep(7); ")
    try:
        readiness = _until_started(root, store, controller)
        # Seven seconds before the owner exists exceed the former fixed 6 s window, yet the
        # owner's own preparation deadline (which starts after its birth) is left intact.
        # Readiness alone proves it: the owner's spawn refuses dispatch once its 5 s deadline
        # has passed (recorded as a no-start timeout), so a spawned payload after more than
        # 7 s means the pre-owner delay was never charged to that deadline.
        assert readiness["ready_seconds"] > 7
        # The birth-based bound also counts pre-deadline start-up; recorded, never asserted.
        record_property(
            "start_deadline_remaining_lower_bound",
            round(readiness["deadline_remaining_lower_bound"], 3),
        )
    finally:
        _release_launch(root, controller)


def test_readiness_names_an_insufficient_owner_deadline(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, store, _, _ = case
    # The owner keeps its real 5 s deadline; only the fixture's post-ready requirement exceeds it,
    # so the named precondition must fire deterministically once the owner is genuinely ready.
    monkeypatch.setattr(sys.modules[__name__], "_POST_READY_DEADLINE_SECONDS", 30.0)
    process = start_synthetic_owner(root, JOB, fixture="wait", seconds=5)
    begun = time.monotonic()
    try:
        with pytest.raises(AssertionError, match="insufficient owner deadline remaining"):
            _until_started(root, store, process, require_remaining=_POST_READY_DEADLINE_SECONDS)
        _prompt(begun)
    finally:
        _stop_test_owner(root, process)


def test_readiness_fails_promptly_on_terminal_no_start(case: Case) -> None:
    root, store, _, _ = case
    process = start_synthetic_owner(root, JOB, fixture="wait", seconds=0.001)
    begun = time.monotonic()
    try:
        with pytest.raises(AssertionError, match="terminal state without starting"):
            _until_started(root, store, process)
        _prompt(begun)
        outcome = cast(dict[str, object] | None, store.native_fixture_status(JOB)["outcome"])
        assert outcome is not None and outcome["cleanup_scope"] == "no_payload_spawn_attempted"
        assert not (root / f"payload-{JOB}" / "payload.pid").exists()
    finally:
        _stop_test_owner(root, process)


def test_readiness_fails_promptly_when_the_launcher_exits(case: Case) -> None:
    root, store, _, _ = case
    controller = _controller(root, before="raise SystemExit(3); ")
    begun = time.monotonic()
    try:
        with pytest.raises(AssertionError, match="launcher exited before start .returncode 3"):
            _until_started(root, store, controller)
        _prompt(begun)
        assert store.native_fixture_status(JOB)["claim"] is None
    finally:
        _release_launch(root, controller)


def test_readiness_fails_promptly_when_the_owner_dies_before_claiming(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform != "linux":
        pytest.skip("requires the Linux native owner profile")
    # A real owner fails closed before its claim: the control socket path exceeds AF_UNIX limits.
    long_tmp = (tmp_path / ("t" * 40)).resolve()
    long_tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(long_tmp))
    with synthetic_workspace() as root:
        store = ControlStore(root)
        _project(store)
        contract, _ = _approved_native_d1(store)
        _native_d1_job(store, contract, job_id=JOB)
        controller = _controller(root, tmpdir=str(long_tmp))
        begun = time.monotonic()
        try:
            with pytest.raises(AssertionError, match="owner exited before claiming"):
                _until_started(root, store, controller)
            _prompt(begun)
            assert store.native_fixture_status(JOB)["claim"] is None
            log = (root / "control" / f"native-{JOB}.log").read_text()
            assert "AF_UNIX path too long" in log
        finally:
            _release_launch(root, controller)


@pytest.mark.parametrize(("required", "raises"), [(None, False), (0.0, False), (1.0, True)])
def test_remaining_budget_check_is_opt_in(
    case: Case, monkeypatch: pytest.MonkeyPatch, required: float | None, raises: bool
) -> None:
    root, store, _, _ = case
    # An exhausted conservative bound, as for intentional-timeout or in-process owners.
    monkeypatch.setattr(sys.modules[__name__], "_owner_deadline_remaining", lambda claim: -5.0)
    process = start_synthetic_owner(root, JOB, fixture="wait", seconds=10)
    try:
        if raises:
            with pytest.raises(AssertionError, match="insufficient owner deadline remaining"):
                _until_started(root, store, process, require_remaining=required)
        else:
            ready = _until_started(root, store, process, require_remaining=required)
            assert ready["deadline_remaining_lower_bound"] == -5.0
    finally:
        _stop_test_owner(root, process)

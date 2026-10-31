"""Small durable heartbeat lease for caller-owned child processes.

The CLI remains the control-plane authority: callers supply callbacks that invoke the typed
``alpha project job-event`` / ``job-status`` commands.  This module only owns the timing and child
process lifecycle needed to keep a live durable journal from being reconciled as abandoned.
"""

from __future__ import annotations

import contextlib
import math
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import Any, Final, Self

DEFAULT_HEARTBEAT_INTERVAL_SECONDS: Final = 5.0
MAX_HEARTBEAT_INTERVAL_SECONDS: Final = 10.0
DEFAULT_TERMINATE_GRACE_SECONDS: Final = 2.0
_PROCESS_GROUP_POLL_SECONDS: Final = 0.02


class DurableLeaseError(RuntimeError):
    """A durable heartbeat could not be renewed while its child was still alive."""


class DurableLeaseCancelled(RuntimeError):
    """The owner reaped its child and completed its cancellation journal callback."""


def _isolated_process_group_id(
    process: subprocess.Popen[Any], observe_exit: Callable[[], int | None] | None = None
) -> int:
    """Resolve and verify the dedicated session created for one durable child."""
    try:
        process_group = os.getpgid(process.pid)
    except ProcessLookupError as exc:
        if (observe_exit or process.poll)() is not None and not _process_group_exists(process.pid):
            return process.pid
        raise DurableLeaseError(
            "leased child exited before its process group was verified"
        ) from exc
    if process_group != process.pid:
        raise DurableLeaseError("leased child does not own an isolated process group")
    return process_group


def _process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - the lease owns its child group.
        return True
    return True


def _signal_process_group(process_group_id: int, sig: signal.Signals) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process_group_id, sig)


def _wait_for_process_group_exit(
    process: subprocess.Popen[Any], process_group_id: int, *, deadline: float
) -> bool:
    while _process_group_exists(process_group_id):
        process.poll()  # Reap a cooperative leader while descendants wind down.
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return False
        time.sleep(min(_PROCESS_GROUP_POLL_SECONDS, remaining))
    return True


def _observe_retained_child(process: subprocess.Popen[Any]) -> int | None:
    """Observe a Linux direct child without releasing the PID that anchors its group.

    The trusted owner must serialize this with final cleanup and use no other reaper.
    A cached Popen return code is not retained kernel ownership.
    """
    if sys.platform != "linux":
        raise DurableLeaseError("retained child observation requires Linux")
    result = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    if result is None:
        return None
    return result.si_status if result.si_code == os.CLD_EXITED else -result.si_status


def _terminate_retaining_leader(process: subprocess.Popen[Any], grace_seconds: float) -> None:
    """Keep the direct child waitable until after the final possible group signal."""
    group_id = process.pid
    if process.returncode is not None:
        if _process_group_exists(group_id):
            raise DurableLeaseError("reaped leader cannot authorize a surviving numeric group")
        return
    _observe_retained_child(process)  # Lost wait ownership denies *all* destructive signals.
    _signal_process_group(group_id, signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    while (remaining := deadline - time.monotonic()) > 0:
        _observe_retained_child(process)  # WNOWAIT retains even an exited zombie leader.
        time.sleep(min(_PROCESS_GROUP_POLL_SECONDS, remaining))
    _observe_retained_child(process)
    _signal_process_group(group_id, signal.SIGKILL)
    # No destructive group operation is permitted after this release of the anchor.
    process.wait(timeout=grace_seconds)
    deadline = time.monotonic() + grace_seconds
    while _process_group_exists(group_id):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DurableLeaseError("process group remains after final leader reap; no safe retry")
        time.sleep(min(_PROCESS_GROUP_POLL_SECONDS, remaining))


def terminate_and_reap(
    process: subprocess.Popen[Any],
    *,
    grace_seconds: float = DEFAULT_TERMINATE_GRACE_SECONDS,
    process_group_id: int | None = None,
    retain_leader: bool = False,
) -> None:
    """Terminate every member of an isolated child group, then reap its direct leader."""
    if not math.isfinite(grace_seconds) or grace_seconds <= 0.0:
        raise ValueError("terminate grace_seconds must be finite and > 0")
    try:
        group_id = (
            _isolated_process_group_id(process) if process_group_id is None else process_group_id
        )
        if group_id != process.pid:
            raise DurableLeaseError("leased process group id does not match its isolated leader")
        if retain_leader:
            _terminate_retaining_leader(process, grace_seconds)
            return
        _signal_process_group(group_id, signal.SIGTERM)
        exited = _wait_for_process_group_exit(
            process,
            group_id,
            deadline=time.monotonic() + grace_seconds,
        )
        if not exited:
            _signal_process_group(group_id, signal.SIGKILL)
            if not _wait_for_process_group_exit(
                process,
                group_id,
                deadline=time.monotonic() + grace_seconds,
            ):
                raise DurableLeaseError("leased process group still exists after SIGKILL")
        process.wait(timeout=grace_seconds)
    except DurableLeaseError:
        raise
    except subprocess.TimeoutExpired as exc:
        raise DurableLeaseError("leased child could not be reaped after SIGKILL") from exc
    except Exception as exc:
        raise DurableLeaseError(
            f"leased process-group cleanup could not be verified: {exc}"
        ) from exc


class DurableJobLease:
    """Renew a durable job heartbeat independently of the child process's stdout.

    An optional trusted-owner cleanup callback shares one retained-child cleanup attempt.
    It must raise when cleanup cannot be verified; failure never falls back to signalling
    the numeric group again. This callback is not a caller-supplied evidence boundary.
    A trusted observer may retain a leader until that shared cleanup finishes; it must
    serialize observation and reaping. Default callers retain their existing poll behavior.
    """

    def __init__(
        self,
        process: subprocess.Popen[Any],
        *,
        renew: Callable[[], object],
        fail_journal: Callable[[str], object],
        cancel_requested: Callable[[], bool] | None = None,
        cancel_journal: Callable[[], object] | None = None,
        cleanup: Callable[[], None] | None = None,
        observe_exit: Callable[[], int | None] | None = None,
        interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        terminate_grace_seconds: float = DEFAULT_TERMINATE_GRACE_SECONDS,
        label: str = "durable child",
    ) -> None:
        if (
            not math.isfinite(interval_seconds)
            or interval_seconds <= 0.0
            or interval_seconds > MAX_HEARTBEAT_INTERVAL_SECONDS
        ):
            raise ValueError("heartbeat interval_seconds must be finite and in (0, 10]")
        if not math.isfinite(terminate_grace_seconds) or terminate_grace_seconds <= 0.0:
            raise ValueError("terminate_grace_seconds must be finite and > 0")
        clean_label = label.strip()
        if not clean_label:
            raise ValueError("durable lease label must not be blank")
        if (cancel_requested is None) != (cancel_journal is None):
            raise ValueError("cancel_requested and cancel_journal must be configured together")
        self._process = process
        self._observe_exit = observe_exit
        self._process_group_id = (
            _isolated_process_group_id(process)
            if observe_exit is None
            else _isolated_process_group_id(process, observe_exit)
        )
        self._renew = renew
        self._fail_journal = fail_journal
        self._cancel_requested = cancel_requested
        self._cancel_journal = cancel_journal
        self._cleanup = cleanup
        self._interval_seconds = interval_seconds
        self._terminate_grace_seconds = terminate_grace_seconds
        self._label = clean_label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._failure: Exception | None = None
        self._failure_context = "heartbeat renewal"
        self._cancelled = False
        self._cleanup_failure: Exception | None = None
        self._journal_failure: Exception | None = None
        self._failure_lock = threading.Lock()

    @classmethod
    def start_for_process(
        cls,
        process: subprocess.Popen[Any],
        *,
        renew: Callable[[], object],
        fail_journal: Callable[[str], object],
        cancel_requested: Callable[[], bool] | None = None,
        cancel_journal: Callable[[], object] | None = None,
        cleanup: Callable[[], None] | None = None,
        observe_exit: Callable[[], int | None] | None = None,
        interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        terminate_grace_seconds: float = DEFAULT_TERMINATE_GRACE_SECONDS,
        label: str = "durable child",
    ) -> Self:
        """Construct and start a lease under one fail-closed post-spawn ownership boundary."""
        try:
            lease = cls(
                process,
                renew=renew,
                fail_journal=fail_journal,
                cancel_requested=cancel_requested,
                cancel_journal=cancel_journal,
                cleanup=cleanup,
                observe_exit=observe_exit,
                interval_seconds=interval_seconds,
                terminate_grace_seconds=terminate_grace_seconds,
                label=label,
            )
        except Exception as init_exc:
            clean_label = label.strip() or "durable child"
            try:
                if cleanup is not None:
                    cleanup()
                else:
                    terminate_and_reap(
                        process,
                        grace_seconds=terminate_grace_seconds,
                        process_group_id=process.pid,
                    )
            except Exception as cleanup_exc:
                raise DurableLeaseError(
                    f"{clean_label} lease initialization failed: {init_exc}; "
                    f"child cleanup also failed: {cleanup_exc}"
                ) from cleanup_exc
            message = f"{clean_label} lease initialization failed: {init_exc}"[:4096]
            try:
                fail_journal(message)
            except Exception as journal_exc:
                raise DurableLeaseError(
                    f"{message}; terminal journal update also failed: {journal_exc}"
                ) from init_exc
            raise DurableLeaseError(message) from init_exc
        lease.start()
        return lease

    @property
    def failed(self) -> bool:
        """Whether lifecycle handling or terminal publication failed."""
        with self._failure_lock:
            return self._failure is not None

    @property
    def cancelled(self) -> bool:
        """Whether cleanup and the cancellation journal callback both succeeded."""
        with self._failure_lock:
            return self._cancelled

    def start(self) -> None:
        """Start the single lease-renewal thread."""
        if self._thread is not None:
            raise RuntimeError("durable lease has already been started")
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"alpha-heartbeat-{self._label.replace(' ', '-')[:32]}",
        )
        try:
            self._thread.start()
        except Exception as exc:
            self._fail("heartbeat thread start", exc)
            self.raise_if_failed()

    def stop_renewal(self) -> None:
        """Join renewal and return child cleanup to the owner without publishing a status.

        The caller must still terminate/reap and verify its child before recording any
        terminal outcome. This operation alone establishes no process-exit evidence.
        """
        self._stop.set()
        thread = self._thread
        if (
            thread is not None
            and thread is not threading.current_thread()
            and thread.ident is not None
        ):
            thread.join()

    def stop(self) -> None:
        """Stop, join, and verify group cleanup before a terminal status can be published."""
        self.stop_renewal()
        with self._failure_lock:
            terminal_outcome = self._failure is not None or self._cancelled
        if terminal_outcome:
            return
        try:
            leader_alive = (self._observe_exit or self._process.poll)() is None
        except Exception as exc:
            self._fail("process-group liveness", exc)
            return
        if leader_alive:
            self._fail(
                "child cleanup",
                DurableLeaseError("lease stopped while child was still alive"),
            )
            return
        try:
            group_alive = _process_group_exists(self._process_group_id)
        except Exception as exc:
            self._fail("process-group liveness", exc)
            return
        if group_alive and not self._terminate():
            with self._failure_lock:
                cleanup_failure = self._cleanup_failure
                self._failure = cleanup_failure or DurableLeaseError("leased child cleanup failed")
                self._failure_context = "child cleanup"

    def raise_if_failed(self) -> None:
        """Raise after the owner has stopped the loop and regained child ownership."""
        with self._failure_lock:
            failure = self._failure
            failure_context = self._failure_context
            cleanup_failure = self._cleanup_failure
            journal_failure = self._journal_failure
        if failure is None:
            return
        details = [f"{self._label} {failure_context} failed: {failure}"]
        if cleanup_failure is not None:
            details.append(f"child cleanup also failed: {cleanup_failure}")
        if journal_failure is not None:
            details.append(f"terminal journal update also failed: {journal_failure}")
        raise DurableLeaseError("; ".join(details)) from failure

    def raise_if_cancelled(self) -> None:
        """Raise the distinct cancellation outcome after stop/join and child reap."""
        with self._failure_lock:
            cancelled = self._cancelled
        if cancelled:
            raise DurableLeaseCancelled(f"{self._label} was cancelled")

    def _run(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            if self._observe_exit is None:
                self._process.poll()  # Existing callers reap while descendants retain the lease.
            observed_exit: int | None = None
            try:
                if self._observe_exit is not None:
                    observed_exit = self._observe_exit()
                group_alive = _process_group_exists(self._process_group_id)
            except Exception as exc:
                self._fail("process-group liveness", exc)
                return
            if not group_alive:
                return
            try:
                self._renew()
            except Exception as exc:
                self._fail("heartbeat renewal", exc)
                return
            if self._cancel_requested is not None:
                try:
                    requested = self._cancel_requested()
                    if not isinstance(requested, bool):
                        raise TypeError("cancellation projection must return a boolean")
                except Exception as exc:
                    self._fail("cancellation poll", exc)
                    return
                if requested:
                    self._cancel()
                    return
            if self._observe_exit is not None and observed_exit is not None:
                # A retained zombie still makes the group visible. Finish physical
                # cleanup now, independently of reporting, before a later deadline
                # can misclassify an already-observed normal exit.
                if not self._terminate():
                    with self._failure_lock:
                        self._failure = self._cleanup_failure
                        self._failure_context = "child cleanup"
                return

    def _fail(self, context: str, failure: Exception) -> None:
        with self._failure_lock:
            self._failure = failure
            self._failure_context = context
        if not self._terminate():
            self._stop.set()
            return
        message = f"{self._label} {context} failed: {failure}"[:4096]
        try:
            self._fail_journal(message)
        except Exception as journal_exc:
            with self._failure_lock:
                self._journal_failure = journal_exc
        self._stop.set()

    def _cancel(self) -> None:
        if not self._terminate():
            with self._failure_lock:
                cleanup_failure = self._cleanup_failure
                self._failure = cleanup_failure or DurableLeaseError("leased child cleanup failed")
                self._failure_context = "child cleanup"
            self._stop.set()
            return
        cancel_journal = self._cancel_journal
        if cancel_journal is not None:
            try:
                cancel_journal()
            except Exception as journal_exc:
                with self._failure_lock:
                    self._journal_failure = journal_exc
                    self._failure = journal_exc
                    self._failure_context = "cancellation publication"
                self._stop.set()
                return
        with self._failure_lock:
            self._cancelled = True
        self._stop.set()

    def _terminate(self) -> bool:
        try:
            if self._cleanup is not None:
                self._cleanup()
            else:
                terminate_and_reap(
                    self._process,
                    grace_seconds=self._terminate_grace_seconds,
                    process_group_id=self._process_group_id,
                )
        except Exception as cleanup_exc:
            with self._failure_lock:
                self._cleanup_failure = cleanup_exc
            return False
        return True


__all__ = [
    "DEFAULT_HEARTBEAT_INTERVAL_SECONDS",
    "DurableJobLease",
    "DurableLeaseCancelled",
    "DurableLeaseError",
    "terminate_and_reap",
]

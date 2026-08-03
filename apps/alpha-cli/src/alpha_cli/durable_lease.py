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
    """The durable owner observed an audited cancellation request and reaped its child."""


def _isolated_process_group_id(process: subprocess.Popen[Any]) -> int:
    """Resolve and verify the dedicated session created for one durable child."""
    try:
        process_group = os.getpgid(process.pid)
    except ProcessLookupError as exc:
        if process.poll() is not None and not _process_group_exists(process.pid):
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


def terminate_and_reap(
    process: subprocess.Popen[Any],
    *,
    grace_seconds: float = DEFAULT_TERMINATE_GRACE_SECONDS,
    process_group_id: int | None = None,
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
    """Renew a durable job heartbeat independently of the child process's stdout."""

    def __init__(
        self,
        process: subprocess.Popen[Any],
        *,
        renew: Callable[[], object],
        fail_journal: Callable[[str], object],
        cancel_requested: Callable[[], bool] | None = None,
        cancel_journal: Callable[[], object] | None = None,
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
        self._process_group_id = _isolated_process_group_id(process)
        self._renew = renew
        self._fail_journal = fail_journal
        self._cancel_requested = cancel_requested
        self._cancel_journal = cancel_journal
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
                interval_seconds=interval_seconds,
                terminate_grace_seconds=terminate_grace_seconds,
                label=label,
            )
        except Exception as init_exc:
            clean_label = label.strip() or "durable child"
            try:
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
        """Whether heartbeat renewal failed while the child was live."""
        with self._failure_lock:
            return self._failure is not None

    @property
    def cancelled(self) -> bool:
        """Whether the owner observed and completed an audited cancellation request."""
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

    def stop(self) -> None:
        """Stop, join, and verify group cleanup before a terminal status can be published."""
        self._stop.set()
        thread = self._thread
        if (
            thread is not None
            and thread is not threading.current_thread()
            and thread.ident is not None
        ):
            thread.join()
        with self._failure_lock:
            terminal_outcome = self._failure is not None or self._cancelled
        if terminal_outcome:
            return
        try:
            leader_alive = self._process.poll() is None
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
            cleanup_failure = self._cleanup_failure
            journal_failure = self._journal_failure
        if not cancelled:
            return
        details = [f"{self._label} was cancelled"]
        if cleanup_failure is not None:
            details.append(f"child cleanup also failed: {cleanup_failure}")
        if journal_failure is not None:
            details.append(f"cancelled journal update also failed: {journal_failure}")
        raise DurableLeaseCancelled("; ".join(details))

    def _run(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            self._process.poll()  # Reap an exited leader while descendants retain the lease.
            try:
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
        with self._failure_lock:
            self._cancelled = True
        cancel_journal = self._cancel_journal
        if cancel_journal is not None:
            try:
                cancel_journal()
            except Exception as journal_exc:
                with self._failure_lock:
                    self._journal_failure = journal_exc
        self._stop.set()

    def _terminate(self) -> bool:
        try:
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

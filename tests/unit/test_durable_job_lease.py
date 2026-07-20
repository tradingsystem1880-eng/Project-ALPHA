"""Durable child-process heartbeat leases."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import alpha_cli.durable_lease as durable_lease
from alpha_cli.control_store import ControlStore
from alpha_cli.durable_lease import (
    DurableJobLease,
    DurableLeaseCancelled,
    DurableLeaseError,
    terminate_and_reap,
)
from alpha_core import DataError


def _running_job(store: ControlStore, *, job_id: str) -> None:
    store.create_job(
        kind="ml_train",
        request={"test": True},
        job_id=job_id,
    )
    store.set_job_status(job_id, "running")


def _silent_child(seconds: float = 0.25) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-c", f"import time; time.sleep({seconds!r})"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )


def _process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - tests own their child processes.
        return True
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.exists():
        fields = proc_stat.read_text(encoding="utf-8").split()
        return len(fields) < 3 or fields[2] != "Z"
    return True


def test_silent_child_renews_lease_and_only_becomes_reconcilable_after_stop(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    job_id = "11111111-1111-4111-8111-111111111111"
    _running_job(store, job_id=job_id)
    heartbeats = 0

    def renew() -> None:
        nonlocal heartbeats
        heartbeats += 1
        store.append_job_event(job_id, event_type="heartbeat", payload={"surface": "test"})

    child = _silent_child()
    lease = DurableJobLease(
        child,
        renew=renew,
        fail_journal=lambda message: store.set_job_status(job_id, "failed", terminal_error=message),
        interval_seconds=0.03,
        label="test silent child",
    )
    lease.start()
    deadline = time.monotonic() + 1
    while heartbeats < 2 and child.poll() is None and time.monotonic() < deadline:
        time.sleep(0.005)
    assert heartbeats >= 2
    assert child.poll() is None
    row = store.get_job(job_id)
    heartbeat_at = datetime.fromisoformat(str(row["heartbeat_at"]).replace("Z", "+00:00"))
    assert (
        store.reconcile_interrupted_jobs(
            stale_after_seconds=30,
            at=heartbeat_at + timedelta(seconds=29),
        )
        == []
    )
    assert store.heavyweight_job_capacity()["active_count"] == 1
    with pytest.raises(DataError, match="heavyweight job capacity is occupied"):
        store.create_job(
            kind="kronos_forecast",
            request={"test": "second reservation"},
            job_id="77777777-7777-4777-8777-777777777777",
        )

    child.communicate(timeout=2)
    lease.stop()
    lease.raise_if_failed()
    reconciled = store.reconcile_interrupted_jobs(
        stale_after_seconds=30,
        at=heartbeat_at + timedelta(seconds=31),
    )
    assert [item["job_id"] for item in reconciled] == [job_id]


def test_exited_leader_keeps_descendant_group_leased_until_audited_cancellation(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    job_id = "12121212-1212-4212-8212-121212121212"
    _running_job(store, job_id=job_id)
    ready_path = tmp_path / "leased-descendant.pid"
    nested_code = (
        "import os, signal, sys, time\n"
        "from pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
        "time.sleep(30)\n"
    )
    leader_code = (
        "import subprocess, sys\n"
        f"subprocess.Popen([sys.executable, '-c', {nested_code!r}, sys.argv[1]])\n"
    )
    leader = subprocess.Popen(
        [sys.executable, "-c", leader_code, str(ready_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    heartbeats = 0
    cancel_now = threading.Event()

    def renew() -> None:
        nonlocal heartbeats
        heartbeats += 1
        store.append_job_event(job_id, event_type="heartbeat", payload={"surface": "test"})

    lease = DurableJobLease(
        leader,
        renew=renew,
        fail_journal=lambda message: store.set_job_status(job_id, "failed", terminal_error=message),
        cancel_requested=cancel_now.is_set,
        cancel_journal=lambda: store.set_job_status(job_id, "cancelled"),
        interval_seconds=0.02,
        terminate_grace_seconds=0.2,
        label="test descendant group",
    )
    nested_pid: int | None = None
    try:
        lease.start()
        deadline = time.monotonic() + 2
        while (
            not ready_path.exists() or leader.poll() is None or heartbeats < 2
        ) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready_path.exists()
        nested_pid = int(ready_path.read_text(encoding="utf-8"))
        assert leader.poll() is not None
        assert _process_is_alive(nested_pid)
        assert heartbeats >= 2

        row = store.get_job(job_id)
        heartbeat_at = datetime.fromisoformat(str(row["heartbeat_at"]).replace("Z", "+00:00"))
        assert (
            store.reconcile_interrupted_jobs(
                stale_after_seconds=30,
                at=heartbeat_at + timedelta(seconds=29),
            )
            == []
        )
        assert store.heavyweight_job_capacity()["active_count"] == 1

        cancel_now.set()
        deadline = time.monotonic() + 2
        while not lease.cancelled and not lease.failed and time.monotonic() < deadline:
            time.sleep(0.01)
        lease.stop()
        assert lease.failed is False
        with pytest.raises(DurableLeaseCancelled, match="was cancelled"):
            lease.raise_if_cancelled()
        assert store.get_job(job_id)["status"] == "cancelled"
        deadline = time.monotonic() + 1
        while _process_is_alive(nested_pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not _process_is_alive(nested_pid)
    finally:
        if durable_lease._process_group_exists(leader.pid):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(leader.pid, signal.SIGKILL)
        with contextlib.suppress(subprocess.TimeoutExpired):
            leader.wait(timeout=1)
        if leader.stdout is not None:
            leader.stdout.close()
        if nested_pid is not None and _process_is_alive(nested_pid):
            with contextlib.suppress(ProcessLookupError):
                os.kill(nested_pid, signal.SIGKILL)


def test_renewal_failure_terminates_reaps_and_fails_the_journal(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    job_id = "22222222-2222-4222-8222-222222222222"
    _running_job(store, job_id=job_id)
    attempts = 0

    def renew() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise RuntimeError("heartbeat projection unavailable")
        store.append_job_event(job_id, event_type="heartbeat", payload={"surface": "test"})

    child = _silent_child(30.0)
    lease = DurableJobLease(
        child,
        renew=renew,
        fail_journal=lambda message: store.set_job_status(job_id, "failed", terminal_error=message),
        interval_seconds=0.02,
        terminate_grace_seconds=0.2,
        label="test failing child",
    )
    lease.start()
    deadline = time.monotonic() + 2
    while child.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    lease.stop()

    assert child.poll() is not None
    with pytest.raises(DurableLeaseError, match="heartbeat projection unavailable"):
        lease.raise_if_failed()
    row = store.get_job(job_id)
    assert row["status"] == "failed"
    assert "heartbeat renewal failed" in str(row["terminal_error"])


def test_stop_with_live_leader_terminates_before_reporting_failure() -> None:
    child = _silent_child(30.0)
    journal: list[str] = []
    lease = DurableJobLease(
        child,
        renew=lambda: None,
        fail_journal=journal.append,
        interval_seconds=0.02,
        terminate_grace_seconds=0.2,
        label="live leader stop",
    )

    lease.stop()

    assert child.poll() is not None
    with pytest.raises(DurableLeaseError, match="lease stopped while child was still alive"):
        lease.raise_if_failed()
    assert journal and "child cleanup failed" in journal[0]


def test_terminate_and_reap_kills_sigterm_ignoring_nested_child(tmp_path: Path) -> None:
    ready_path = tmp_path / "nested-child-ready"
    nested_code = (
        "import os, signal, sys, time\n"
        "from pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
        "time.sleep(30)\n"
    )
    leader_code = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {nested_code!r}, sys.argv[1]])\n"
        "time.sleep(30)\n"
    )
    leader = subprocess.Popen(
        [sys.executable, "-c", leader_code, str(ready_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    nested_pid: int | None = None
    try:
        deadline = time.monotonic() + 2
        while not ready_path.exists() and leader.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready_path.exists()
        nested_pid = int(ready_path.read_text(encoding="utf-8"))
        assert _process_is_alive(nested_pid)

        terminate_and_reap(leader, grace_seconds=0.2)

        assert leader.poll() is not None
        deadline = time.monotonic() + 1
        while _process_is_alive(nested_pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not _process_is_alive(nested_pid)
    finally:
        if leader.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(leader.pid, signal.SIGKILL)
        with contextlib.suppress(subprocess.TimeoutExpired):
            leader.wait(timeout=1)
        if nested_pid is not None and _process_is_alive(nested_pid):
            with contextlib.suppress(ProcessLookupError):
                os.kill(nested_pid, signal.SIGKILL)


def test_cancel_cleanup_failure_keeps_durable_capacity_reserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    job_id = "33333333-3333-4333-8333-333333333333"
    _running_job(store, job_id=job_id)
    cancelled_calls = 0

    def fail_cleanup(*_args: object, **_kwargs: object) -> None:
        raise DurableLeaseError("process group survived SIGKILL")

    def cancel_journal() -> None:
        nonlocal cancelled_calls
        cancelled_calls += 1
        store.set_job_status(job_id, "cancelled")

    monkeypatch.setattr(durable_lease, "terminate_and_reap", fail_cleanup)
    child = _silent_child(30.0)
    lease = DurableJobLease(
        child,
        renew=lambda: None,
        fail_journal=lambda message: store.set_job_status(job_id, "failed", terminal_error=message),
        cancel_requested=lambda: True,
        cancel_journal=cancel_journal,
        interval_seconds=0.02,
        terminate_grace_seconds=0.2,
        label="test uncleanable child",
    )
    try:
        lease.start()
        deadline = time.monotonic() + 2
        while not lease.failed and time.monotonic() < deadline:
            time.sleep(0.01)
        lease.stop()

        assert lease.failed
        assert not lease.cancelled
        lease.raise_if_cancelled()
        with pytest.raises(DurableLeaseError, match="process group survived SIGKILL"):
            lease.raise_if_failed()
        assert cancelled_calls == 0
        assert store.get_job(job_id)["status"] == "running"
        assert store.heavyweight_job_capacity()["active_count"] == 1
    finally:
        if child.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
        with contextlib.suppress(subprocess.TimeoutExpired):
            child.wait(timeout=1)


def test_success_cleanup_failure_keeps_durable_capacity_reserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    job_id = "44444444-4444-4444-8444-444444444444"
    _running_job(store, job_id=job_id)
    child = _silent_child(0.05)
    lease = DurableJobLease(
        child,
        renew=lambda: None,
        fail_journal=lambda message: store.set_job_status(job_id, "failed", terminal_error=message),
        interval_seconds=0.02,
        terminate_grace_seconds=0.2,
        label="test successful leader",
    )
    lease.start()
    child.wait(timeout=1)

    monkeypatch.setattr(durable_lease, "_process_group_exists", lambda _group_id: True)

    def fail_cleanup(*_args: object, **_kwargs: object) -> None:
        raise DurableLeaseError("descendant cleanup failed")

    monkeypatch.setattr(durable_lease, "terminate_and_reap", fail_cleanup)
    lease.stop()

    with pytest.raises(DurableLeaseError, match="descendant cleanup failed"):
        lease.raise_if_failed()
    assert store.get_job(job_id)["status"] == "running"
    assert store.heavyweight_job_capacity()["active_count"] == 1


def test_fast_exited_child_without_a_process_group_can_still_be_leased(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = _silent_child(0.01)
    child.wait(timeout=1)

    def missing_process_group(_pid: int) -> int:
        raise ProcessLookupError

    monkeypatch.setattr(os, "getpgid", missing_process_group)
    monkeypatch.setattr(durable_lease, "_process_group_exists", lambda _group_id: False)
    lease = DurableJobLease(
        child,
        renew=lambda: None,
        fail_journal=lambda _message: None,
        interval_seconds=0.02,
        label="test fast child",
    )

    lease.start()
    lease.stop()
    lease.raise_if_failed()


def test_live_child_with_unverifiable_process_group_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = _silent_child(30.0)

    def missing_process_group(_pid: int) -> int:
        raise ProcessLookupError

    monkeypatch.setattr(os, "getpgid", missing_process_group)
    try:
        with pytest.raises(DurableLeaseError, match="process group was verified"):
            DurableJobLease(
                child,
                renew=lambda: None,
                fail_journal=lambda _message: None,
                interval_seconds=0.02,
                label="test unverifiable child",
            )
    finally:
        if child.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
        with contextlib.suppress(subprocess.TimeoutExpired):
            child.wait(timeout=1)


def test_constructor_failure_boundary_reaps_before_failing_journal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = _silent_child(30.0)
    journal: list[str] = []

    def initialization_failure(_process: subprocess.Popen[str]) -> int:
        raise DurableLeaseError("process group identity unavailable")

    monkeypatch.setattr(durable_lease, "_isolated_process_group_id", initialization_failure)

    with pytest.raises(DurableLeaseError, match="lease initialization failed"):
        DurableJobLease.start_for_process(
            child,
            renew=lambda: None,
            fail_journal=journal.append,
            interval_seconds=0.02,
            terminate_grace_seconds=0.2,
            label="constructor boundary",
        )
    assert child.poll() is not None
    assert journal and "process group identity unavailable" in journal[0]


def test_constructor_cleanup_failure_does_not_terminalize_journal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = _silent_child(30.0)
    journal: list[str] = []

    def initialization_failure(_process: subprocess.Popen[str]) -> int:
        raise DurableLeaseError("process group identity unavailable")

    def cleanup_failure(*_args: object, **_kwargs: object) -> None:
        raise DurableLeaseError("process group survived SIGKILL")

    monkeypatch.setattr(durable_lease, "_isolated_process_group_id", initialization_failure)
    monkeypatch.setattr(durable_lease, "terminate_and_reap", cleanup_failure)
    try:
        with pytest.raises(DurableLeaseError, match="child cleanup also failed"):
            DurableJobLease.start_for_process(
                child,
                renew=lambda: None,
                fail_journal=journal.append,
                interval_seconds=0.02,
                terminate_grace_seconds=0.2,
                label="constructor boundary",
            )
        assert child.poll() is None
        assert journal == []
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=1)


@pytest.mark.parametrize("interval", [0.0, float("nan"), 10.01])
def test_lease_rejects_invalid_heartbeat_intervals(interval: float) -> None:
    child = _silent_child(30.0)
    try:
        with pytest.raises(ValueError, match="heartbeat interval_seconds"):
            DurableJobLease(
                child,
                renew=lambda: None,
                fail_journal=lambda _message: None,
                interval_seconds=interval,
            )
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=1)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"terminate_grace_seconds": 0.0}, "terminate_grace_seconds"),
        ({"label": "   "}, "label must not be blank"),
        ({"cancel_requested": lambda: False}, "must be configured together"),
        ({"cancel_journal": lambda: None}, "must be configured together"),
    ],
)
def test_lease_rejects_incomplete_or_invalid_configuration(
    kwargs: dict[str, object], message: str
) -> None:
    child = _silent_child(30.0)
    try:
        with pytest.raises(ValueError, match=message):
            DurableJobLease(
                child,
                renew=lambda: None,
                fail_journal=lambda _message: None,
                **kwargs,  # type: ignore[arg-type]
            )
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=1)


def test_lease_start_is_one_shot() -> None:
    child = _silent_child(0.05)
    lease = DurableJobLease(
        child,
        renew=lambda: None,
        fail_journal=lambda _message: None,
        interval_seconds=0.02,
    )
    lease.start()
    with pytest.raises(RuntimeError, match="already been started"):
        lease.start()
    child.wait(timeout=1)
    lease.stop()


def test_heartbeat_thread_start_failure_reaps_child_before_failing_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    job_id = "13131313-1313-4313-8313-131313131313"
    _running_job(store, job_id=job_id)
    child = _silent_child(30.0)
    lease = DurableJobLease(
        child,
        renew=lambda: None,
        fail_journal=lambda message: store.set_job_status(job_id, "failed", terminal_error=message),
        interval_seconds=0.02,
        terminate_grace_seconds=0.2,
        label="thread start failure",
    )

    def fail_start(_thread: threading.Thread) -> None:
        raise RuntimeError("thread resources exhausted")

    monkeypatch.setattr(threading.Thread, "start", fail_start)

    with pytest.raises(DurableLeaseError, match="thread resources exhausted"):
        lease.start()
    lease.stop()
    assert child.poll() is not None
    assert store.get_job(job_id)["status"] == "failed"


def test_heartbeat_thread_start_cleanup_failure_keeps_capacity_reserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    job_id = "14141414-1414-4414-8414-141414141414"
    _running_job(store, job_id=job_id)
    child = _silent_child(30.0)
    lease = DurableJobLease(
        child,
        renew=lambda: None,
        fail_journal=lambda message: store.set_job_status(job_id, "failed", terminal_error=message),
        interval_seconds=0.02,
        terminate_grace_seconds=0.2,
        label="uncleanable thread start failure",
    )

    def fail_start(_thread: threading.Thread) -> None:
        raise RuntimeError("thread resources exhausted")

    def fail_cleanup(*_args: object, **_kwargs: object) -> None:
        raise DurableLeaseError("process group survived SIGKILL")

    monkeypatch.setattr(threading.Thread, "start", fail_start)
    monkeypatch.setattr(durable_lease, "terminate_and_reap", fail_cleanup)
    try:
        with pytest.raises(DurableLeaseError, match="process group survived SIGKILL"):
            lease.start()
        lease.stop()
        assert child.poll() is None
        assert store.get_job(job_id)["status"] == "running"
        assert store.heavyweight_job_capacity()["active_count"] == 1
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=1)


def test_terminate_rejects_invalid_grace_and_mismatched_group() -> None:
    child = _silent_child(30.0)
    try:
        with pytest.raises(ValueError, match="grace_seconds"):
            terminate_and_reap(child, grace_seconds=0.0, process_group_id=child.pid)
        with pytest.raises(DurableLeaseError, match="does not match"):
            terminate_and_reap(child, grace_seconds=0.1, process_group_id=child.pid + 1)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=1)


def test_post_kill_process_group_survival_fails_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = _silent_child(30.0)
    monkeypatch.setattr(durable_lease, "_process_group_exists", lambda _group_id: True)
    try:
        with pytest.raises(DurableLeaseError, match="still exists after SIGKILL"):
            terminate_and_reap(child, grace_seconds=0.03, process_group_id=child.pid)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=1)


def test_signal_permission_error_is_normalized_as_cleanup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = _silent_child(30.0)
    original_killpg = os.killpg

    def signal_failure(_group_id: int, _signal: int) -> None:
        raise PermissionError("signal permission denied")

    monkeypatch.setattr(os, "killpg", signal_failure)
    try:
        with pytest.raises(DurableLeaseError, match="cleanup could not be verified"):
            terminate_and_reap(child, grace_seconds=0.03, process_group_id=child.pid)
    finally:
        with contextlib.suppress(ProcessLookupError):
            original_killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=1)


def test_stop_liveness_probe_failure_enters_fail_closed_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = _silent_child(0.01)
    child.wait(timeout=1)
    journal: list[str] = []
    lease = DurableJobLease(
        child,
        renew=lambda: None,
        fail_journal=journal.append,
        interval_seconds=0.02,
        label="stop liveness probe",
    )
    probes = 0

    def group_probe(_group_id: int) -> bool:
        nonlocal probes
        probes += 1
        if probes == 1:
            raise OSError("group liveness unavailable")
        return False

    monkeypatch.setattr(durable_lease, "_process_group_exists", group_probe)
    lease.stop()

    with pytest.raises(DurableLeaseError, match="group liveness unavailable"):
        lease.raise_if_failed()
    assert journal and "process-group liveness failed" in journal[0]


def test_invalid_cancellation_projection_fails_and_reaps_child() -> None:
    child = _silent_child(30.0)
    journal: list[str] = []
    lease = DurableJobLease(
        child,
        renew=lambda: None,
        fail_journal=journal.append,
        cancel_requested=lambda: "yes",  # type: ignore[arg-type,return-value]
        cancel_journal=lambda: None,
        interval_seconds=0.02,
        terminate_grace_seconds=0.2,
        label="invalid cancellation projection",
    )
    lease.start()
    deadline = time.monotonic() + 2
    while child.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    lease.stop()

    with pytest.raises(DurableLeaseError, match="cancellation projection must return a boolean"):
        lease.raise_if_failed()
    assert child.poll() is not None
    assert journal and "cancellation poll failed" in journal[0]


def test_terminal_journal_failures_remain_visible_to_the_owner() -> None:
    failed_child = _silent_child(30.0)

    def renewal_failure() -> None:
        raise RuntimeError("renewal failed")

    def journal_failure(_message: str) -> None:
        raise RuntimeError("failed journal unavailable")

    failed = DurableJobLease(
        failed_child,
        renew=renewal_failure,
        fail_journal=journal_failure,
        interval_seconds=0.02,
        terminate_grace_seconds=0.2,
        label="journal failure",
    )
    failed.start()
    deadline = time.monotonic() + 2
    while failed_child.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    failed.stop()
    with pytest.raises(DurableLeaseError, match="terminal journal update also failed"):
        failed.raise_if_failed()

    cancelled_child = _silent_child(30.0)

    def cancel_journal_failure() -> None:
        raise RuntimeError("cancel journal unavailable")

    cancelled = DurableJobLease(
        cancelled_child,
        renew=lambda: None,
        fail_journal=lambda _message: None,
        cancel_requested=lambda: True,
        cancel_journal=cancel_journal_failure,
        interval_seconds=0.02,
        terminate_grace_seconds=0.2,
        label="cancel journal failure",
    )
    cancelled.start()
    deadline = time.monotonic() + 2
    while cancelled_child.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    cancelled.stop()
    with pytest.raises(DurableLeaseCancelled, match="cancelled journal update also failed"):
        cancelled.raise_if_cancelled()

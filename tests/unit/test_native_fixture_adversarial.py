"""Adversarial public fixture tests; never execute a native research workflow."""

from __future__ import annotations

import contextlib
import os
import select
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from alpha_cli.control_store import ControlStore
from alpha_cli.durable_lease import DurableJobLease, terminate_and_reap
from alpha_cli.native_supervisor import start_synthetic_owner
from alpha_core import DataError
from tests.unit.test_native_fixture_lifecycle import (
    _ESCAPE_RELEASE_BARRIER,
    JOB,
    Case,
    _owner,
    _stop_test_owner,
    _until,
    _until_started,
)
from tests.unit.test_native_fixture_lifecycle import case as case
from tests.unit.test_research_control_store import PROJECT_ID


@pytest.mark.parametrize("uncertain", [False, True])
def test_terminal_cleanup_is_issued_once_without_reusing_a_reaped_pgid(
    case: Case, monkeypatch: pytest.MonkeyPatch, uncertain: bool
) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        store.record_native_fixture_observation(JOB, owner.spawn())
        child = owner.process
        assert child is not None
        try:
            with monkeypatch.context() as scoped:
                if uncertain:

                    def denied(*args: Any, **kwargs: Any) -> None:
                        raise PermissionError("synthetic cleanup remains unknown")

                    scoped.setattr("alpha_cli.native_supervisor.terminate_and_reap", denied)
                first = owner.finish("cancelled")
            recorded = store.record_native_fixture_observation(JOB, first)
            with monkeypatch.context() as scoped:
                scoped.setattr(
                    "alpha_cli.native_supervisor.terminate_and_reap",
                    lambda *args, **kwargs: pytest.fail("terminal owner repeated cleanup"),
                )
                assert owner.finish("owner_error") is first
                assert store.record_native_fixture_observation(JOB, first) == recorded
        finally:
            terminate_and_reap(
                child, grace_seconds=0.2, process_group_id=child.pid, retain_leader=True
            )


def test_no_spawn_completion_cannot_later_dispatch_or_replace_its_receipt(case: Case) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        first = owner.without_child("cancelled")
        store.record_native_fixture_observation(JOB, first)
        try:
            with pytest.raises(DataError, match="terminal|already observed"):
                owner.spawn()
            assert owner.without_child("owner_error") is first
            assert store.record_native_fixture_observation(JOB, first)["reason"] == "cancelled"
        finally:
            if owner.process is not None:
                terminate_and_reap(
                    owner.process,
                    grace_seconds=0.2,
                    process_group_id=owner.process.pid,
                    retain_leader=True,
                )


def test_pre_spawn_work_cannot_dispatch_after_deadline(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        real_mkdir = Path.mkdir

        def slow_mkdir(path: Path, *args: Any, **kwargs: Any) -> None:
            real_mkdir(path, *args, **kwargs)
            if path == root / f"payload-{JOB}":
                owner.deadline = time.monotonic() - 1  # Work consumed the remaining allowance.

        try:
            with monkeypatch.context() as scoped:
                scoped.setattr(Path, "mkdir", slow_mkdir)
                with pytest.raises(DataError, match="deadline"):
                    owner.spawn()
            assert owner.process is None
            assert not owner.spawn_attempted
            store.record_native_fixture_observation(JOB, owner.without_child("timeout"))
            assert store.get_job(JOB)["status"] == "failed"
        finally:
            if owner.process is not None:
                terminate_and_reap(
                    owner.process,
                    grace_seconds=0.2,
                    process_group_id=owner.process.pid,
                    retain_leader=True,
                )


@pytest.mark.parametrize("first_kind", ["native_outcome", "cancel_requested"])
def test_completion_and_duplicate_cancellation_serialize_in_either_order(
    case: Case, monkeypatch: pytest.MonkeyPatch, first_kind: str
) -> None:
    from alpha_cli import _native_fixture_store as native_store

    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    with _owner(root, "success") as owner:
        store.claim_native_fixture(JOB, owner)
        store.record_native_fixture_observation(JOB, owner.spawn())
        child = owner.process
        assert child is not None
        child.wait(timeout=3)
        observation = owner.finish("exit")
        held, release = threading.Event(), threading.Event()
        original = native_store._append

        def held_writer(*args: Any, **kwargs: Any) -> None:
            original(*args, **kwargs)
            if args[2] == first_kind and not held.is_set():
                held.set()
                if not release.wait(timeout=5):
                    raise RuntimeError("synthetic writer barrier timed out")

        def publish() -> dict[str, object]:
            return store.record_native_fixture_observation(JOB, observation)

        def cancel() -> dict[str, object]:
            return store.cancel_native_fixture(JOB, reason="concurrent synthetic cancellation")

        monkeypatch.setattr(native_store, "_append", held_writer)
        operations = [publish, cancel, publish, cancel]
        if first_kind == "cancel_requested":
            operations[0], operations[1] = operations[1], operations[0]
        with ThreadPoolExecutor(max_workers=4) as pool:
            first = pool.submit(operations[0])
            try:
                assert held.wait(timeout=5)
                others = [pool.submit(operation) for operation in operations[1:]]
            finally:
                release.set()
            first.result(timeout=8)
            for future in others:
                future.result(timeout=8)
        assert store.get_job(JOB)["status"] == "cancelled"
        assert store.heavyweight_job_capacity()["active_count"] == 0
        result = store.native_fixture_status(JOB, reconnect=True)
        assert result["outcome"]["returncode"] == 0  # type: ignore[index]
        summary = store.research_case_summary(PROJECT_ID)
        assert summary["elapsed_budget"] == before
        assert summary["terminal_attempt_count"] == 2
        assert summary["unfinalized_launch_count"] == 0
        assert summary["active_job_id"] is None
        with store._transaction(write=False) as connection:
            counts = dict(
                connection.execute(
                    "SELECT event_type,COUNT(*) FROM job_events WHERE job_id=? GROUP BY event_type",
                    (JOB,),
                ).fetchall()
            )
        assert counts["native_outcome"] == counts["cancel_requested"] == 1


def test_owner_killed_before_closure_commit_leaves_no_partial_terminal_state(case: Case) -> None:
    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    marker = root / "closure-written"
    code = """import sys,time
from pathlib import Path
from alpha_cli import _native_fixture_store as storage
from alpha_cli.native_supervisor import _open_lock,_run_owner
root=Path(sys.argv[1]); job=sys.argv[2]
original=storage._failure_close
def pause(*args,**kwargs):
    original(*args,**kwargs)
    (root/'closure-written').write_text('uncommitted synthetic closure')
    time.sleep(60)
storage._failure_close=pause
with _open_lock(root,job) as lock:
    _run_owner(root,job,'failure',3,lock)
"""
    process = subprocess.Popen([sys.executable, "-c", code, str(root), JOB])
    try:
        deadline = time.monotonic() + 8
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists(), "owner must reach uncommitted closure before being killed"
        process.kill()
        process.wait(timeout=3)
        fresh = ControlStore(root)
        result = fresh.native_fixture_status(JOB, reconnect=True)
        assert result["state"] == "quarantined"
        assert result["outcome"] is None
        assert fresh.get_job(JOB)["status"] == "running"
        assert fresh.heavyweight_job_capacity()["active_count"] == 1
        summary = fresh.research_case_summary(PROJECT_ID)
        assert summary["elapsed_budget"] == before
        assert summary["terminal_attempt_count"] == 1
        assert summary["unfinalized_launch_count"] == 1
        assert fresh.native_fixture_status(JOB, reconnect=True) == result
    finally:
        if process.poll() is None:
            if marker.exists():
                # This fault barrier is published only after retained payload cleanup.
                process.kill()
            else:
                _stop_test_owner(root, process)
        process.wait(timeout=3)


# A writer frozen mid-commit can surface as SQLITE_BUSY or, inside WAL-index updates, as
# SQLITE_PROTOCOL; both mean another process holds the store's write path.
_WRITE_CONTENTION = frozenset({sqlite3.SQLITE_BUSY, sqlite3.SQLITE_PROTOCOL})


def _write_contention(exc: BaseException | None) -> bool:
    # Primary result code only: extended BUSY variants share SQLITE_BUSY's low byte.
    return isinstance(exc, sqlite3.OperationalError) and (
        exc.sqlite_errorcode & 0xFF in _WRITE_CONTENTION
    )


def _write_locked(store: ControlStore) -> bool:
    """Probe without waiting whether another process holds the store's write path."""
    probe = sqlite3.connect(store._database_path(), timeout=0, isolation_level=None)
    try:
        probe.execute("BEGIN IMMEDIATE")
        probe.execute("ROLLBACK")
        return False
    except sqlite3.OperationalError as exc:
        if not _write_contention(exc):
            raise
        return True
    finally:
        probe.close()


def _await_stopped(process: subprocess.Popen[bytes]) -> None:
    """kill(SIGSTOP) returns before the target stops; wait until the kernel reports it."""
    deadline = time.monotonic() + 5
    while Path(f"/proc/{process.pid}/stat").read_text().rsplit(")", 1)[1].split()[0] not in {
        "T",
        "t",
    }:
        assert time.monotonic() < deadline, "owner did not reach the stopped state"
        time.sleep(0.001)


def _suspend_owner(
    process: subprocess.Popen[bytes], store: ControlStore, *, holding_write: bool
) -> None:
    """SIGSTOP the owner at a verified point inside or outside its store write transaction.

    The owner publishes its start observation and then heartbeats through write transactions,
    so a bare SIGSTOP freezes it at an arbitrary point relative to the write lock.
    """
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if holding_write and not _write_locked(store):
            time.sleep(0.001)
            continue
        process.send_signal(signal.SIGSTOP)
        _await_stopped(process)
        if _write_locked(store) == holding_write:
            return
        process.send_signal(signal.SIGCONT)
        time.sleep(0.001)
    raise AssertionError("could not suspend the owner at the requested write-lock state")


def test_suspended_owner_expiry_never_authorizes_takeover(case: Case) -> None:
    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    process = start_synthetic_owner(root, JOB, fixture="wait", seconds=2)
    try:
        _until_started(root, store)
        _suspend_owner(process, store, holding_write=False)
        claim = store.native_fixture_status(JOB)["claim"]
        time.sleep(2.1)
        assert store.reconcile_interrupted_jobs(at=datetime.now(UTC) + timedelta(days=1)) == []
        assert store.native_fixture_status(JOB, reconnect=True)["claim"] == claim
        with pytest.raises(DataError, match="occupied; reconnect only"):
            start_synthetic_owner(root, JOB)
        store.cancel_native_fixture(JOB, reason="cancel suspended owner")
        assert store.heavyweight_job_capacity()["active_count"] == 1
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
        process.send_signal(signal.SIGCONT)
        _until(store, "closed")
        assert process.wait(timeout=3) == 0
        assert store.get_job(JOB)["status"] == "cancelled"
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGCONT)
        _stop_test_owner(root, process)


def test_owner_suspended_inside_write_transaction_fails_closed_without_takeover(
    case: Case,
) -> None:
    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    process = start_synthetic_owner(root, JOB, fixture="wait", seconds=10)
    try:
        _until_started(root, store)
        claim = store.native_fixture_status(JOB)["claim"]
        _suspend_owner(process, store, holding_write=True)
        # Even a reader's connection setup may block here; only the fail-closed result matters.
        with pytest.raises(
            DataError, match="control store transaction failed|cannot initialize control store"
        ) as blocked:
            store.reconcile_interrupted_jobs(at=datetime.now(UTC) + timedelta(days=1))
        assert _write_contention(blocked.value.__cause__)
        process.send_signal(signal.SIGCONT)
        assert store.reconcile_interrupted_jobs(at=datetime.now(UTC) + timedelta(days=1)) == []
        assert store.native_fixture_status(JOB, reconnect=True)["claim"] == claim
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
        # The resumed owner, not a takeover, closes the job at its own deadline.
        _until(store, "closed", seconds=20)
        assert process.wait(timeout=5) == 0
        job = store.get_job(JOB)
        assert job["status"] == "failed"
        assert "timeout" in str(job["terminal_error"])
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGCONT)
        _stop_test_owner(root, process)


def test_detached_escape_retains_charge_and_capacity_after_owner_exit(case: Case) -> None:
    if sys.platform != "linux":
        pytest.skip("requires Linux pidfd ownership")
    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    marker = root / f"payload-{JOB}" / "descendant.pid"
    release = marker.parent / "release-escape"
    code = (
        "import sys\nfrom pathlib import Path\n"
        "from alpha_cli import native_supervisor as supervisor\n"
        "root=Path(sys.argv[1]); job=sys.argv[2]\n"
        "supervisor._PAYLOAD=supervisor._PAYLOAD.replace("
        f"'    time.sleep(0.1)\\n', {_ESCAPE_RELEASE_BARRIER!r})\n"
        "with supervisor._open_lock(root,job) as lock:\n"
        "    supervisor._run_owner(root,job,'escape',5,lock)\n"
    )
    process = subprocess.Popen([sys.executable, "-c", code, str(root), JOB], start_new_session=True)
    escaped_pidfd: int | None = None
    escaped_verified = False
    exited = select.poll()
    try:
        _until_started(root, store)
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "fixed escape did not publish readiness"
        leader = int((marker.parent / "payload.pid").read_text())
        leader_stat = Path(f"/proc/{leader}/stat").read_text().rsplit(")", 1)[1].split()
        assert leader_stat[0] != "Z" and int(leader_stat[1]) == process.pid
        escaped = int(marker.read_text())
        identity = Path(f"/proc/{escaped}/stat").read_text().rsplit(")", 1)[1].split()
        assert identity[0] != "Z" and int(identity[1]) == leader
        escaped_pidfd = os.pidfd_open(escaped)
        exited.register(escaped_pidfd, select.POLLIN)
        retained = Path(f"/proc/{escaped}/stat").read_text().rsplit(")", 1)[1].split()
        assert retained[19] == identity[19] and int(retained[1]) == leader
        assert process.poll() is None and not exited.poll(0)
        escaped_verified = True
        release.touch()
        assert process.wait(timeout=8) == 0
        assert not exited.poll(0)
        result = store.native_fixture_status(JOB, reconnect=True)
        assert result["state"] == "quarantined"
        assert result["outcome"] is None
        store.cancel_native_fixture(JOB, reason="cancellation cannot prove escaped cleanup")
        assert store.get_job(JOB)["status"] == "running"
        assert store.heavyweight_job_capacity()["active_count"] == 1
        summary = store.research_case_summary(PROJECT_ID)
        assert summary["elapsed_budget"] == before
        assert summary["unfinalized_launch_count"] == 1
        with pytest.raises(DataError, match="reconnect only"):
            start_synthetic_owner(root, JOB)
    finally:
        try:
            with contextlib.suppress(FileNotFoundError):
                release.touch()  # A rejected startup may never create the payload directory.
        finally:
            try:
                process.wait(timeout=8)
            finally:
                if escaped_pidfd is not None:
                    try:
                        if escaped_verified:
                            with contextlib.suppress(ProcessLookupError):
                                signal.pidfd_send_signal(escaped_pidfd, signal.SIGKILL)
                            assert exited.poll(3000), "retained detached escape did not exit"
                    finally:
                        os.close(escaped_pidfd)


def test_detached_escape_start_failure_still_reaps_the_retained_owner(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, _, _ = case
    process = subprocess.Popen(
        [sys.executable, "-c", "raise SystemExit(7)"], start_new_session=True
    )

    def rejected_start(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("synthetic owner rejected before payload creation")

    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(subprocess, "Popen", lambda *args, **kwargs: process)
            scoped.setattr(__name__ + "._until_started", rejected_start)
            with pytest.raises(RuntimeError, match="synthetic owner rejected"):
                test_detached_escape_retains_charge_and_capacity_after_owner_exit(case)
        assert process.returncode == 7, "failed-start cleanup did not reap its retained owner"
        assert not (root / f"payload-{JOB}").exists()
    finally:
        process.wait(timeout=3)


def test_no_child_observation_cannot_bypass_retained_child_cleanup(case: Case) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        store.record_native_fixture_observation(JOB, owner.spawn())
        child = owner.process
        assert child is not None
        try:
            with pytest.raises(DataError, match="retained child"):
                owner.without_child("owner_error")
            observation = owner.finish("owner_error")
            assert child.poll() is not None
            store.record_native_fixture_observation(JOB, observation)
        finally:
            terminate_and_reap(
                child, grace_seconds=0.2, process_group_id=child.pid, retain_leader=True
            )


def test_provenance_failure_after_cleanup_never_repeats_group_signalling(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        store.record_native_fixture_observation(JOB, owner.spawn())
        child = owner.process
        assert child is not None
        try:
            path = root / "control" / f"native-{JOB}.lock"
            path.rename(path.with_suffix(".old"))
            path.touch()
            with pytest.raises(DataError, match="lock identity changed"):
                owner.finish("owner_error")
            assert child.poll() is not None
            with monkeypatch.context() as scoped:
                scoped.setattr(
                    "alpha_cli.native_supervisor.terminate_and_reap",
                    lambda *args, **kwargs: pytest.fail("lost provenance repeated PGID cleanup"),
                )
                with pytest.raises(DataError, match="already attempted|lock identity changed"):
                    owner.finish("owner_error")
        finally:
            terminate_and_reap(
                child, grace_seconds=0.2, process_group_id=child.pid, retain_leader=True
            )


def test_preparation_expiry_is_recorded_as_timeout_by_the_runner(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.native_supervisor import _open_lock, _Owner, _run_owner

    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    real_spawn = _Owner.spawn

    def expires_during_preparation(owner: _Owner) -> Any:
        owner.deadline = 0
        return real_spawn(owner)

    monkeypatch.setattr(_Owner, "spawn", expires_during_preparation)
    with _open_lock(root, JOB) as lock:
        _run_owner(root, JOB, "success", 2, lock)
    result = store.native_fixture_status(JOB)
    assert result["outcome"]["reason"] == "timeout"  # type: ignore[index]
    assert result["outcome"]["cleanup_scope"] == "no_payload_spawn_attempted"  # type: ignore[index]
    assert not (root / f"payload-{JOB}" / "payload.pid").exists()
    assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before


def test_blocked_publication_keeps_capacity_and_full_charge_until_cleanup(
    case: Case, record_property: Callable[[str, object], None]
) -> None:
    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    marker, release = root / "publication-blocked", root / "release-publication"
    code = """import sys,time
from pathlib import Path
from alpha_cli.control_store import ControlStore
from alpha_cli.native_supervisor import _open_lock,_run_owner
root=Path(sys.argv[1]); job=sys.argv[2]
original=ControlStore.record_native_fixture_observation
def blocked(self,job,observation):
    if observation.kind=='native_started':
        (root/'publication-blocked').write_text('synthetic storage stall')
        while not (root/'release-publication').exists(): time.sleep(0.01)
    return original(self,job,observation)
ControlStore.record_native_fixture_observation=blocked
with _open_lock(root,job) as lock:
    _run_owner(root,job,'wait',3,lock)
"""
    process = subprocess.Popen([sys.executable, "-c", code, str(root), JOB])
    try:
        deadline = time.monotonic() + 8
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists()
        time.sleep(3.1)  # Observe the storage stall after the configured deadline.
        pid = int((root / f"payload-{JOB}" / "payload.pid").read_text())

        def payload_running() -> bool:
            try:
                state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
            except FileNotFoundError:
                return False
            return state != "Z"

        cleanup_limit = time.monotonic() + 1.0
        while payload_running() and time.monotonic() < cleanup_limit:
            time.sleep(0.02)
        record_property("payload_running_after_deadline_during_storage_stall", payload_running())
        record_property("configured_seconds", 3)
        assert not payload_running(), "journal publication blocked deadline cleanup"
        assert store.native_fixture_status(JOB)["outcome"] is None
        assert store.reconcile_interrupted_jobs(at=datetime.now(UTC) + timedelta(days=1)) == []
        assert store.heavyweight_job_capacity()["active_count"] == 1
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
        release.touch()
        _until(store, "closed")
        assert process.wait(timeout=3) == 0
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
    finally:
        release.touch(exist_ok=True)
        _stop_test_owner(root, process)


@pytest.mark.parametrize(
    "mode",
    ["cancellation", "heartbeat", "initialization", "thread_start", "initialization_uncertain"],
)
def test_lease_and_owner_share_one_cleanup_across_failure_paths(
    case: Case, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from alpha_cli import native_supervisor as supervisor
    from alpha_cli.durable_lease import DurableLeaseError

    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    cleanup_calls = 0
    children: list[subprocess.Popen[bytes]] = []
    original = terminate_and_reap

    def counted(*args: Any, **kwargs: Any) -> None:
        nonlocal cleanup_calls
        cleanup_calls += 1
        children.append(args[0])
        if mode == "initialization_uncertain":
            raise PermissionError("synthetic cleanup cannot be verified")
        original(*args, **kwargs)

    if mode.startswith("initialization"):

        def bad_initialization(*args: Any, **kwargs: Any) -> None:
            raise ValueError("synthetic lease initialization failure")

        monkeypatch.setattr(DurableJobLease, "__init__", bad_initialization)
    elif mode == "thread_start":
        original_start = threading.Thread.start

        def bad_lease_thread(thread: threading.Thread) -> None:
            if thread.name.startswith("alpha-heartbeat-"):
                raise RuntimeError("synthetic heartbeat thread unavailable")
            original_start(thread)

        monkeypatch.setattr(threading.Thread, "start", bad_lease_thread)
    elif mode == "heartbeat":

        def bad_heartbeat(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("synthetic heartbeat persistence failure")

        monkeypatch.setattr(ControlStore, "heartbeat_native_fixture", bad_heartbeat)
    monkeypatch.setattr(supervisor, "terminate_and_reap", counted)
    monkeypatch.setattr("alpha_cli.durable_lease.terminate_and_reap", counted)
    try:
        with supervisor._open_lock(root, JOB) as lock, ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(supervisor._run_owner, root, JOB, "descendant", 5, lock)
            if mode == "cancellation":
                _until_started(root, store)
                store.cancel_native_fixture(JOB, reason="cancel the retained synthetic group")
            try:
                running.result(timeout=8)
            except (DataError, DurableLeaseError) as exc:
                assert mode in {"initialization", "thread_start", "initialization_uncertain"}
                expected_cause = {
                    "initialization": "lease initialization failed",
                    "thread_start": "heartbeat thread start failed",
                    "initialization_uncertain": "child cleanup also failed",
                }
                assert expected_cause[mode] in str(exc)
        assert cleanup_calls == 1
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
        if mode == "initialization_uncertain":
            assert store.native_fixture_status(JOB)["state"] == "quarantined"
            assert store.heavyweight_job_capacity()["active_count"] == 1
        else:
            assert store.get_job(JOB)["status"] == (
                "cancelled" if mode == "cancellation" else "failed"
            )
    finally:
        for child in children:
            if child.poll() is None:
                original(child, grace_seconds=0.2, process_group_id=child.pid, retain_leader=True)


def test_interrupted_cleanup_cannot_later_be_reported_clean(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, store, _, _ = case
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        store.record_native_fixture_observation(JOB, owner.spawn())
        child = owner.process
        assert child is not None
        try:
            with monkeypatch.context() as scoped:

                def interrupted(*args: Any, **kwargs: Any) -> None:
                    raise KeyboardInterrupt("synthetic interruption during cleanup")

                scoped.setattr("alpha_cli.native_supervisor.terminate_and_reap", interrupted)
                with pytest.raises(KeyboardInterrupt):
                    owner.finish("owner_error")
            observation = owner.finish("owner_error")
            assert observation.kind == "native_uncertain"
            assert child.poll() is None
            store.record_native_fixture_observation(JOB, observation)
            assert store.heavyweight_job_capacity()["active_count"] == 1
        finally:
            terminate_and_reap(
                child, grace_seconds=0.2, process_group_id=child.pid, retain_leader=True
            )

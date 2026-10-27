"""Fixed synthetic safety control remains independent of synchronous journal reporting."""

from __future__ import annotations

import contextlib
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

import pytest

from alpha_cli.control_store import ControlStore
from alpha_cli.durable_lease import terminate_and_reap
from alpha_cli.native_supervisor import (
    Fixture,
    _open_lock,
    _request_live_stop,
    _run_owner,
    start_synthetic_owner,
)
from tests.unit.test_native_fixture_lifecycle import (
    JOB,
    Case,
    _stop_test_owner,
    _until,
    _until_started,
)
from tests.unit.test_native_fixture_lifecycle import case as case
from tests.unit.test_research_control_store import PROJECT_ID


def _running(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def _stopped(pid: int, *, seconds: float = 1.0) -> float:
    started = time.monotonic()
    while _running(pid) and time.monotonic() - started < seconds:
        time.sleep(0.01)
    assert not _running(pid), "synthetic process cleanup waited for journal recovery"
    return time.monotonic() - started


def _pid(root: Path) -> int:
    marker = root / f"payload-{JOB}" / "payload.pid"
    deadline = time.monotonic() + 5
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert marker.exists(), "fixed synthetic payload did not publish readiness"
    return int(marker.read_text())


@contextlib.contextmanager
def _blocked_owner(
    case: Case,
    monkeypatch: pytest.MonkeyPatch,
    *,
    kind: str = "native_started",
    fixture: Fixture = "wait",
    seconds: float = 10,
) -> Iterator[tuple[threading.Event, Future[None]]]:
    root, _, _, _ = case
    entered, release = threading.Event(), threading.Event()
    original = ControlStore.record_native_fixture_observation
    original_heartbeat = ControlStore.heartbeat_native_fixture

    def publish(store: ControlStore, job_id: str, observation: Any) -> dict[str, object]:
        if observation.kind == kind:
            entered.set()
            if not release.wait(timeout=15):
                raise RuntimeError("synthetic publication barrier exceeded its bound")
        return original(store, job_id, observation)

    monkeypatch.setattr(ControlStore, "record_native_fixture_observation", publish)

    def heartbeat(store: ControlStore, job_id: str, owner: object) -> None:
        assert not threading.current_thread().name.startswith("alpha-heartbeat-")
        if kind == "heartbeat":
            entered.set()
            if not release.wait(timeout=15):
                raise RuntimeError("synthetic heartbeat publication barrier exceeded its bound")
        original_heartbeat(store, job_id, owner)

    monkeypatch.setattr(ControlStore, "heartbeat_native_fixture", heartbeat)
    with _open_lock(root, JOB) as lock, ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(_run_owner, root, JOB, fixture, seconds, lock)
        try:
            assert entered.wait(timeout=8), "owner did not reach the publication barrier"
            yield release, running
        finally:
            release.set()
            running.result(timeout=8)


@pytest.mark.parametrize("first_writer", ["owner", "client"])
def test_live_cancel_precedes_blocked_status_and_commits_exactly_once(
    case: Case, monkeypatch: pytest.MonkeyPatch, first_writer: str
) -> None:
    from alpha_cli import _native_fixture_store as storage

    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    with _blocked_owner(case, monkeypatch) as (release_owner, owner):
        pid = _pid(root)
        entered, release_client = threading.Event(), threading.Event()
        original = storage.status

        def stalled_status(*args: Any, **kwargs: Any) -> dict[str, object]:
            if threading.current_thread().name.startswith("cancel-client"):
                entered.set()
                if not release_client.wait(timeout=10):
                    raise RuntimeError("synthetic cancel reporting barrier timed out")
            return original(*args, **kwargs)

        monkeypatch.setattr(storage, "status", stalled_status)
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="cancel-client") as pool:
            cancelled = pool.submit(
                store.cancel_native_fixture, JOB, reason="stop during journal stall"
            )
            try:
                assert entered.wait(timeout=5)
                _stopped(pid)
                assert store.get_job(JOB)["status"] == "running"
                assert store.heavyweight_job_capacity()["active_count"] == 1
                assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
                if first_writer == "owner":
                    release_owner.set()
                    owner.result(timeout=8)
                    assert not cancelled.done()
                    assert store.get_job(JOB)["status"] == "cancelled"
                    release_client.set()
                else:
                    release_client.set()
                    cancelled.result(timeout=8)
                    assert store.get_job(JOB)["status"] == "running"
                    release_owner.set()
                cancelled.result(timeout=8)
                owner.result(timeout=8)
            finally:
                release_client.set()
                release_owner.set()
        assert store.get_job(JOB)["status"] == "cancelled"
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
        with store._transaction(write=False) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM job_events WHERE job_id=? AND event_type='cancel_requested'",
                (JOB,),
            ).fetchone()[0]
        assert count == 1


@pytest.mark.parametrize(
    "kind,fixture", [("native_started", "wait"), ("native_outcome", "success")]
)
def test_client_exit_after_transport_does_not_lose_cancellation(
    case: Case, monkeypatch: pytest.MonkeyPatch, kind: str, fixture: Fixture
) -> None:
    root, store, _, _ = case
    with _blocked_owner(case, monkeypatch, kind=kind, fixture=fixture) as (release, owner):
        pid = _pid(root)
        code = (
            "import os,sys; from pathlib import Path; "
            "from alpha_cli.native_supervisor import _request_live_stop; "
            "assert _request_live_stop(Path(sys.argv[1]),sys.argv[2]); os._exit(0)"
        )
        client = subprocess.Popen([sys.executable, "-c", code, str(root), JOB])
        assert client.wait(timeout=5) == 0
        _stopped(pid)
        assert store.get_job(JOB)["status"] == "running"
        release.set()
        owner.result(timeout=8)
        assert store.get_job(JOB)["status"] == "cancelled"
        assert store.research_case_summary(PROJECT_ID)["unfinalized_launch_count"] == 0


@pytest.mark.parametrize("stop", ["deadline", "cancel"])
def test_sqlite_writer_lock_cannot_block_physical_cleanup(
    case: Case, stop: str, record_property: Callable[[str, object], None]
) -> None:
    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    process = start_synthetic_owner(
        root, JOB, fixture="wait", seconds=3 if stop == "deadline" else 10
    )
    writer = sqlite3.connect(root / "control" / "workstation.sqlite3", isolation_level=None)
    try:
        _until_started(root, store)
        pid = _pid(root)
        deadline = time.monotonic() + 5
        while True:
            with store._transaction(write=False) as connection:
                published = connection.execute(
                    "SELECT 1 FROM job_events WHERE job_id=? AND event_type='native_started'",
                    (JOB,),
                ).fetchone()
            if published is not None:
                break
            assert time.monotonic() < deadline
            time.sleep(0.01)
        writer.execute("BEGIN IMMEDIATE")
        with ThreadPoolExecutor(max_workers=1) as pool:
            cancellation = None
            try:
                if stop == "cancel":
                    cancellation = pool.submit(
                        store.cancel_native_fixture, JOB, reason="writer locked"
                    )
                elapsed = _stopped(pid, seconds=4 if stop == "deadline" else 1)
                record_property("cleanup_seconds_while_sqlite_locked", elapsed)
                assert (
                    writer.execute("SELECT status FROM jobs WHERE job_id=?", (JOB,)).fetchone()[0]
                    == "running"
                )
                assert (
                    writer.execute(
                        "SELECT COUNT(*) FROM research_launch_attempt_links WHERE reservation_id=?",
                        (case[3]["reservation_id"],),
                    ).fetchone()[0]
                    == 0
                )
            finally:
                writer.rollback()
            if cancellation is not None:
                cancellation.result(timeout=8)
        _until(store, "closed")
        assert process.wait(timeout=3) == 0
        assert store.get_job(JOB)["status"] == ("failed" if stop == "deadline" else "cancelled")
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
    finally:
        writer.rollback()
        writer.close()
        _stop_test_owner(root, process)


def test_failed_publication_still_cleans_without_false_terminal_accounting(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    reached = threading.Event()
    observed_pid: list[int] = []

    def failed(store: ControlStore, job_id: str, observation: Any) -> dict[str, object]:
        if observation.kind == "native_started":
            observed_pid.append(_pid(root))
            reached.set()
        raise RuntimeError("synthetic journal publication unavailable")

    monkeypatch.setattr(ControlStore, "record_native_fixture_observation", failed)
    with _open_lock(root, JOB) as lock, ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(_run_owner, root, JOB, "wait", 10, lock)
        assert reached.wait(timeout=5)
        with pytest.raises(RuntimeError, match="publication unavailable"):
            running.result(timeout=8)
        _stopped(observed_pid[0])
    assert store.native_fixture_status(JOB, reconnect=True)["state"] == "quarantined"
    assert store.get_job(JOB)["status"] == "running"
    assert store.heavyweight_job_capacity()["active_count"] == 1
    assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before


def test_malformed_and_wrong_job_control_messages_cannot_dispatch_or_stop_another_job(
    case: Case,
) -> None:
    root, store, _, _ = case
    process = start_synthetic_owner(root, JOB, fixture="wait", seconds=10)
    try:
        _until_started(root, store)
        pid = _pid(root)
        endpoint = root / "control" / f"native-{JOB}.stop"
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sender:
            for message in (b"launch\n", b"cancel wrong-job\n", b"cancel\n" + b"x" * 64):
                sender.sendto(message, str(endpoint))
        assert not _request_live_stop(root, "11111111-1111-4111-8111-111111111111")
        time.sleep(0.25)
        assert _running(pid)
        store.cancel_native_fixture(JOB, reason="valid job-bound stop")
        _stopped(pid)
        _until(store, "closed")
        assert process.wait(timeout=3) == 0
        assert store.get_job(JOB)["status"] == "cancelled"
    finally:
        _stop_test_owner(root, process)


@pytest.mark.parametrize("fault", ["monitor_socket", "cleanup_permission"])
def test_safety_faults_clean_or_quarantine_without_reporting_success(
    case: Case, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from alpha_cli import native_supervisor as supervisor

    root, store, _, _ = case
    owners: list[supervisor._Owner] = []
    original = supervisor._Owner.open_control
    cleanup_attempted = threading.Event()
    retained: list[subprocess.Popen[bytes]] = []

    def capture(owner: supervisor._Owner) -> None:
        original(owner)
        owners.append(owner)

    def denied(process: subprocess.Popen[bytes], **kwargs: Any) -> None:
        retained.append(process)
        cleanup_attempted.set()
        raise PermissionError("synthetic OS cleanup permission failure")

    monkeypatch.setattr(supervisor._Owner, "open_control", capture)
    if fault == "cleanup_permission":
        monkeypatch.setattr(supervisor, "terminate_and_reap", denied)
    try:
        with _blocked_owner(case, monkeypatch, seconds=2) as (release, owner):
            pid = _pid(root)
            assert owners
            if fault == "monitor_socket":
                assert owners[0]._control is not None
                owners[0]._control.close()
                _stopped(pid)
            else:
                assert cleanup_attempted.wait(timeout=4)
                assert _running(pid)
            assert store.get_job(JOB)["status"] == "running"
            assert store.heavyweight_job_capacity()["active_count"] == 1
            release.set()
            owner.result(timeout=8)
        if fault == "cleanup_permission":
            assert store.native_fixture_status(JOB)["state"] == "quarantined"
            assert store.heavyweight_job_capacity()["active_count"] == 1
            assert len(retained) == 1  # No retry through an alternate cleanup path.
        else:
            assert store.get_job(JOB)["status"] == "failed"
            result = cast(dict[str, object], store.native_fixture_status(JOB)["outcome"])
            assert result["reason"] == "owner_error"
    finally:
        for process in retained:
            terminate_and_reap(
                process, grace_seconds=0.2, process_group_id=process.pid, retain_leader=True
            )


@pytest.mark.parametrize("error", [RuntimeError, SystemExit])
def test_monitor_loop_failure_stops_the_retained_child_before_reporting_recovers(
    case: Case, monkeypatch: pytest.MonkeyPatch, error: type[BaseException]
) -> None:
    from alpha_cli import native_supervisor as supervisor

    root, store, _, _ = case
    owners: list[supervisor._Owner] = []
    original_open, original_poll = supervisor._Owner.open_control, supervisor._Owner.poll_stop
    monitor_fault_armed, early_monitor_poll = threading.Event(), threading.Event()

    def capture(owner: supervisor._Owner) -> None:
        original_open(owner)
        owners.append(owner)

    def fail_monitor(owner: supervisor._Owner, **kwargs: Any) -> bool:
        if threading.current_thread().name.startswith("alpha-heartbeat-"):
            if not monitor_fault_armed.is_set():
                early_monitor_poll.set()
                return original_poll(owner, **kwargs)
            raise error("synthetic safety loop failure")
        return original_poll(owner, **kwargs)

    monkeypatch.setattr(supervisor._Owner, "open_control", capture)
    monkeypatch.setattr(supervisor._Owner, "poll_stop", fail_monitor)
    with _blocked_owner(case, monkeypatch) as (release, running):
        assert early_monitor_poll.wait(timeout=5), "monitor did not poll before readiness"
        pid = _pid(root)
        assert _running(pid)
        monitor_fault_armed.set()
        try:
            _stopped(pid)
            assert store.get_job(JOB)["status"] == "running"
            assert store.heavyweight_job_capacity()["active_count"] == 1
        finally:
            # On a failing regression, clean only our retained fixture handle.
            owners[0].request_stop("owner_error")
            owners[0]._cleanup_once()
            release.set()
        running.result(timeout=8)
    assert store.get_job(JOB)["status"] == "failed"


def test_reaped_leader_cannot_authorize_signalling_a_reused_group(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import native_supervisor as supervisor
    from tests.unit.test_native_fixture_lifecycle import _owner

    root, store, _, _ = case
    with _owner(root, "success") as owner:
        store.claim_native_fixture(JOB, owner)
        store.record_native_fixture_observation(JOB, owner.spawn())
        assert owner.process is not None
        owner.process.wait(timeout=3)
        with monkeypatch.context() as scoped:
            scoped.setattr("alpha_cli.durable_lease._process_group_exists", lambda group: True)
            scoped.setattr(
                supervisor,
                "terminate_and_reap",
                lambda *args, **kwargs: pytest.fail(
                    "reaped leader authorized numeric group control"
                ),
            )
            observation = owner.finish("exit")
        assert observation.kind == "native_uncertain"
        store.record_native_fixture_observation(JOB, observation)
        assert store.heavyweight_job_capacity()["active_count"] == 1


@pytest.mark.parametrize("reaper", ["popen", "waitpid"])
def test_competing_reap_before_first_signal_cannot_authorize_group_control(
    case: Case, monkeypatch: pytest.MonkeyPatch, reaper: str
) -> None:
    from alpha_cli import durable_lease
    from alpha_cli import native_supervisor as supervisor
    from tests.unit.test_native_fixture_lifecycle import _owner

    root, store, _, _ = case
    signals: list[signal.Signals] = []
    original = terminate_and_reap
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        store.record_native_fixture_observation(JOB, owner.spawn())
        process = owner.process
        assert process is not None

        def competing_reap(*args: Any, **kwargs: Any) -> None:
            # Deterministically occupy the old check-to-first-signal window. No PID
            # recycling is needed: the signal spy models a now-unrelated group.
            os.killpg(process.pid, signal.SIGTERM)
            if reaper == "popen":
                process.wait(timeout=3)
            else:
                os.waitpid(process.pid, 0)
            with monkeypatch.context() as scoped:
                scoped.setattr(durable_lease, "_process_group_exists", lambda group: True)
                scoped.setattr(
                    durable_lease, "_signal_process_group", lambda group, sig: signals.append(sig)
                )
                original(*args, **kwargs)

        monkeypatch.setattr(supervisor, "terminate_and_reap", competing_reap)
        observation = owner.finish("owner_error")
        assert observation.kind == "native_uncertain"
        assert signals == [], "lost wait ownership authorized a numeric group signal"
        store.record_native_fixture_observation(JOB, observation)
        assert store.heavyweight_job_capacity()["active_count"] == 1
        process.wait(timeout=3)


def test_leader_identity_is_retained_between_term_and_last_kill(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform != "linux":
        pytest.skip("requires Linux non-reaping child observation")
    from alpha_cli import durable_lease
    from tests.unit.test_native_fixture_lifecycle import _owner

    root, _, _, _ = case
    with _owner(root) as owner:
        owner.spawn()
        process = owner.process
        assert process is not None
        signals: list[signal.Signals] = []

        def signal_group(group: int, sig: signal.Signals) -> None:
            assert group == process.pid
            assert process.returncode is None, "leader was reaped before the final group signal"
            # A waitable direct child anchors this numeric identity, even after exit.
            os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            os.killpg(group, sig)
            signals.append(sig)
            if sig == signal.SIGTERM:
                _stopped(process.pid)

        with monkeypatch.context() as scoped:
            scoped.setattr(durable_lease, "_signal_process_group", signal_group)
            # Keep the group visible through KILL; after final reap a new numeric
            # occupant must receive probes only, never another destructive signal.
            scoped.setattr(
                durable_lease,
                "_process_group_exists",
                lambda group: signal.SIGKILL not in signals or process.returncode is None,
            )
            owner._cleanup_once()
        assert signals == [signal.SIGTERM, signal.SIGKILL]
        assert process.returncode is not None


def test_native_owner_and_lease_observe_exit_without_releasing_the_leader(case: Case) -> None:
    from alpha_cli.durable_lease import DurableJobLease
    from tests.unit.test_native_fixture_lifecycle import _owner

    root, _, _, _ = case
    with _owner(root, "success") as owner:
        owner.spawn()
        process = owner.process
        assert process is not None
        deadline = time.monotonic() + 3
        while owner.observe_exit() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert owner.observe_exit() == 0
        assert process.returncode is None
        observed = threading.Event()

        def renew() -> None:
            assert process.returncode is None
            assert owner.observe_exit() == 0
            observed.set()

        lease = DurableJobLease.start_for_process(
            process,
            renew=renew,
            fail_journal=lambda message: pytest.fail(message),
            cancel_requested=lambda: True,
            cancel_journal=lambda: None,
            cleanup=owner._cleanup_once,
            observe_exit=owner.observe_exit,
            interval_seconds=0.02,
        )
        try:
            assert observed.wait(timeout=3)
            deadline = time.monotonic() + 3
            while not lease.cancelled and time.monotonic() < deadline:
                time.sleep(0.01)
            assert lease.cancelled
            lease.raise_if_failed()
            assert process.returncode == 0
        finally:
            owner._cleanup_once()
            lease.stop_renewal()


def test_group_visible_after_final_reap_is_quarantined_without_more_signals(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import durable_lease
    from tests.unit.test_native_fixture_lifecycle import _owner

    root, store, _, _ = case
    signals: list[signal.Signals] = []
    original = durable_lease._signal_process_group
    with _owner(root) as owner:
        store.claim_native_fixture(JOB, owner)
        store.record_native_fixture_observation(JOB, owner.spawn())

        def signal_group(group: int, sig: signal.Signals) -> None:
            signals.append(sig)
            original(group, sig)

        with monkeypatch.context() as scoped:
            scoped.setattr(durable_lease, "_signal_process_group", signal_group)
            scoped.setattr(durable_lease, "_process_group_exists", lambda group: True)
            observation = owner.finish("cancelled")
            assert owner.finish("cancelled") is observation
        assert observation.kind == "native_uncertain"
        assert signals == [signal.SIGTERM, signal.SIGKILL]
        store.record_native_fixture_observation(JOB, observation)
        assert store.heavyweight_job_capacity()["active_count"] == 1


def test_profile_without_nonreaping_observation_is_denied_before_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if sys.platform != "linux":
        pytest.skip("requires the Linux native observation profile")
    from alpha_cli.native_supervisor import host_identity
    from alpha_core import DataError

    monkeypatch.delattr(os, "WNOWAIT")
    with pytest.raises(DataError, match="non-reaping child observation"):
        host_identity()


@pytest.mark.parametrize("kind", ["native_started", "heartbeat"])
def test_natural_exit_during_publication_stall_does_not_become_timeout(
    case: Case, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    root, store, _, _ = case
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    with _blocked_owner(case, monkeypatch, kind=kind, fixture="success", seconds=1) as (
        release,
        running,
    ):
        pid = _pid(root)
        _stopped(pid)  # Physical success precedes the monotonic deadline.
        time.sleep(1.2)  # Reporting alone remains stalled beyond that deadline.
        assert store.get_job(JOB)["status"] == "running"
        assert store.heavyweight_job_capacity()["active_count"] == 1
        release.set()
        running.result(timeout=8)
    status = store.native_fixture_status(JOB)
    outcome = cast(dict[str, object], status["outcome"])
    assert outcome["reason"] == "exit"
    assert outcome["returncode"] == 0
    assert status["state"] == "pending_scientific_admission"
    assert store.get_job(JOB)["status"] == "running"
    assert store.heavyweight_job_capacity()["active_count"] == 1
    assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before


@pytest.mark.parametrize("disposition", [signal.SIG_IGN, lambda sig, frame: None])
def test_nondefault_sigchld_profile_is_denied_before_spawn(
    monkeypatch: pytest.MonkeyPatch, disposition: Any
) -> None:
    if sys.platform != "linux":
        pytest.skip("requires the Linux native SIGCHLD profile")
    from alpha_cli.native_supervisor import host_identity
    from alpha_core import DataError

    monkeypatch.setattr(signal, "getsignal", lambda sig: disposition)
    with pytest.raises(DataError, match="default SIGCHLD disposition"):
        host_identity()


def test_detached_entry_establishes_default_sigchld_before_claim(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import native_supervisor as supervisor

    root, _, _, _ = case
    configured: list[tuple[int, Any]] = []
    called: list[str] = []

    def configure(sig: int, handler: Any) -> None:
        configured.append((sig, handler))

    def run(*args: Any) -> None:
        assert configured == [(signal.SIGCHLD, signal.SIG_DFL)]
        called.append("claim boundary")

    monkeypatch.setattr(signal, "signal", configure)
    monkeypatch.setattr(supervisor, "_run_owner", run)
    with _open_lock(root, JOB) as lock:
        descriptor = os.dup(lock.fileno())
        monkeypatch.setattr(
            sys, "argv", ["synthetic-owner", str(root), JOB, "success", "2", str(descriptor)]
        )
        supervisor._entry()
    assert called == ["claim boundary"]


@pytest.mark.parametrize("stop", ["deadline", "cancel"])
def test_blocked_heartbeat_reporting_cannot_hold_the_process_open(
    case: Case,
    monkeypatch: pytest.MonkeyPatch,
    stop: str,
    record_property: Callable[[str, object], None],
) -> None:
    root, store, _, _ = case
    with _blocked_owner(
        case,
        monkeypatch,
        kind="heartbeat",
        seconds=3 if stop == "deadline" else 10,
    ) as (release, running):
        pid = _pid(root)
        if stop == "cancel":
            assert _request_live_stop(root, JOB)
        elapsed = _stopped(pid, seconds=4 if stop == "deadline" else 1)
        record_property("cleanup_seconds_while_heartbeat_blocked", elapsed)
        assert store.get_job(JOB)["status"] == "running"
        assert store.heavyweight_job_capacity()["active_count"] == 1
        release.set()
        running.result(timeout=8)
    outcome = cast(dict[str, object], store.native_fixture_status(JOB)["outcome"])
    assert outcome["reason"] == ("timeout" if stop == "deadline" else "cancelled")


def test_cancel_queued_during_claim_publication_prevents_payload_dispatch(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, store, _, _ = case
    entered, release = threading.Event(), threading.Event()
    original = ControlStore.claim_native_fixture

    def claim(store: ControlStore, job_id: str, owner: object) -> dict[str, object]:
        entered.set()
        if not release.wait(timeout=10):
            raise RuntimeError("synthetic claim publication barrier timed out")
        return original(store, job_id, owner)

    monkeypatch.setattr(ControlStore, "claim_native_fixture", claim)
    with _open_lock(root, JOB) as lock, ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(_run_owner, root, JOB, "wait", 10, lock)
        try:
            assert entered.wait(timeout=5)
            assert _request_live_stop(root, JOB)
        finally:
            release.set()
        running.result(timeout=8)
    assert not (root / f"payload-{JOB}").exists()
    assert store.get_job(JOB)["status"] == "cancelled"
    outcome = cast(dict[str, object], store.native_fixture_status(JOB)["outcome"])
    assert outcome["cleanup_scope"] == "no_payload_spawn_attempted"

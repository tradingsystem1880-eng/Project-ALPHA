"""Public, disposable synthetic lifecycle conformance; no native workflow is executed."""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import inspect
import json
import os
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


def _stop_test_owner(root: Path, process: subprocess.Popen[bytes]) -> None:
    """Ask the retained owner to clean its child; uncertainty never authorizes takeover."""
    deadline = time.monotonic() + 3
    while process.poll() is None:
        if _request_live_stop(root, JOB):
            break
        assert time.monotonic() < deadline, "live owner stop is uncertain; no saved-PID fallback"
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
                _until_started(root, store)
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
    process = start_synthetic_owner(root, JOB)
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


@pytest.mark.parametrize("fixture,seconds", [("failure", 2), ("wait", 0.3)])
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
        _until_started(root, store)
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


def _until_started(root: Path, store: ControlStore) -> None:
    deadline = time.monotonic() + 6
    marker = root / f"payload-{JOB}" / "payload.pid"
    while time.monotonic() < deadline:
        if marker.exists() and store.native_fixture_status(JOB)["claim"] is not None:
            return
        time.sleep(0.02)
    raise AssertionError("synthetic payload did not start")


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
            process = start_synthetic_owner(root, JOB)
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
    process = start_synthetic_owner(root, JOB)
    _until(store, "pending_scientific_admission")
    assert process.wait(timeout=3) == 0
    store.cancel_native_fixture(JOB, reason="abandon process-only result")
    assert store.get_job(JOB)["status"] == "cancelled"
    summary = store.research_case_summary(PROJECT_ID)
    assert summary["terminal_attempt_count"] == 2
    assert summary["execution_state"] == "failed"
    assert summary["active_job_id"] is None


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
        _until_started(root, store)
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


def test_controller_death_preserves_same_owner_for_cancel(case: Case) -> None:
    root, store, _, _ = case
    code = (
        "from pathlib import Path; import time; "
        "from alpha_cli.native_supervisor import start_synthetic_owner; "
        f"start_synthetic_owner(Path({str(root)!r}), {JOB!r}, fixture='wait', seconds=5); "
        "time.sleep(30)"
    )
    controller = subprocess.Popen([sys.executable, "-c", code])
    try:
        _until_started(root, store)
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
        assert store.native_fixture_status(JOB)["state"] in {"unclaimed", "closed"}


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

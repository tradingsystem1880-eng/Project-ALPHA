"""Actual native worker with artificial data; never real-market research acceptance."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from alpha_cli import owner_auth
from alpha_cli._native_daily_rule_protocol import draft_daily_contract
from alpha_cli._native_daily_rule_study import bind_daily_study, daily_rule_terms_proposal
from alpha_cli._native_loop_admission import NativeLaunch
from alpha_cli._native_rule_artifacts import d0_fingerprint, publish_rule_run
from alpha_cli._native_rule_authority import RuleAuthority
from alpha_cli._native_rule_completion import complete_rule_trial
from alpha_cli._native_rule_environment import (
    measure_rule_environment,
    rule_implementation_fingerprints,
)
from alpha_cli.control_store import ControlStore, research_case_revision
from alpha_cli.crypto_price_snapshot_query import query_binance_daily_price_snapshot
from alpha_cli.native_supervisor import (
    _open_lock,
    _run_owner,
    prepare_daily_workspace,
    start_daily_owner,
)
from alpha_core import DataError
from tests.unit.test_crypto_price_snapshot_query import _full_discovery_fixture
from tests.unit.test_native_rule_authority import configured_rule_source as configured_rule_source
from tests.unit.test_research_control_store import (
    PROJECT_ID,
    START,
    _d0_acceptance_ref,
    _native_d1_job,
)


def _reservations(store: ControlStore) -> list[dict[str, object]]:
    with store._transaction(write=False) as connection:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM research_launch_reservations ORDER BY reservation_id"
            ).fetchall()
        ]


def _case(
    root: Path, monkeypatch: pytest.MonkeyPatch, source: Path
) -> tuple[ControlStore, str, NativeLaunch]:
    """Genuine disposable storage/query + test owner ceremony, no invented authority rows."""
    import alpha_cli.crypto_bulk_store as backend
    from alpha_cli._native_daily_rule_container import daily_container_profile

    bulk, snapshot, manifest_id = _full_discovery_fixture(root)
    config = root / "crypto" / "storage-config.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('{"artificial_fixture":"callback-backed test volume"}')
    snapshots = root / "crypto" / "snapshots"
    snapshots.mkdir()
    (snapshots / (snapshot.snapshot_id + ".json")).write_text(json.dumps(snapshot.to_dict()))
    end = datetime(2023, 1, 1, tzinfo=UTC)
    query = query_binance_daily_price_snapshot(
        snapshot,
        bulk,
        normalized_manifest_id=manifest_id,
        start=datetime(2020, 1, 1, tzinfo=UTC),
        end=end,
        available_by=end,
    )
    economics, resources = daily_rule_terms_proposal()
    study = bind_daily_study(
        query,
        snapshot_sha256=snapshot.snapshot_id,
        runtime_profile_sha256=measure_rule_environment(True),
        container_image_id=daily_container_profile()["image_id"],
        storage_config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
        economics=economics,
        resources=resources,
        data_origin="artificial_fixture",
    )
    monkeypatch.setattr(backend, "configured_crypto_bulk_store", lambda selected: bulk)
    fingerprints = rule_implementation_fingerprints(True, daily_study=study)
    store = ControlStore(root)
    store.create_project(
        name="Artificial daily native lifecycle",
        hypothesis="Mechanics only",
        falsification_criterion="Reject changed bindings",
        project_id=PROJECT_ID,
        at=START,
    )
    reference = store.create_research_source(
        PROJECT_ID,
        title="Artificial fixture",
        locator="artificial:native-daily",
        provider="synthetic",
        access_mode="metadata_only",
        metadata={"data_origin": "artificial_fixture"},
        at=START,
    )
    pack = store.create_research_source_pack(
        PROJECT_ID,
        source_ids=[str(reference["source_id"])],
        definition={"data_origin": "artificial_fixture"},
        at=START,
    )
    payload = draft_daily_contract(
        str(pack["pack_id"]),
        fingerprints,
        {
            "variants": 5,
            "wall_seconds": 60,
            "source_requests": 0,
            "rdagent_native_v1_model_calls": 0,
            "rdagent_native_v1_input_tokens": 0,
            "rdagent_native_v1_output_tokens": 0,
            "rdagent_native_v1_tool_calls": 0,
            "rdagent_native_v1_loop_steps": 5,
            "rdagent_native_v1_cpu_milliseconds": 60000,
        },
        study,
    )
    created = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="test-agent",
        author_kind="agent",
        at=START,
    )
    cid = str(created["contract_id"])
    for phase in ("triage", "exploration_review"):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase=cast(Any, phase),
            contract_id=cid,
            actor="test-agent",
            reason="Artificial fixture",
            next_action="Review",
            responsibility="owner",
            at=START,
        )
    request = {"contract_id": cid}
    binding = owner_auth.action_binding(
        data_dir=root,
        action_type="approve_exploration",
        project_id=PROJECT_ID,
        artifact_hash=cid.removeprefix("rc_"),
        expected_case_revision=research_case_revision(store.research_case_summary(PROJECT_ID)),
        consequence_summary="Artificial native mechanics only",
        reason="Test ceremony",
        payload=request,
    )
    envelope = owner_auth.local_confirmation_options(data_dir=root, binding=binding, now=START)
    owner_auth.verify_local_confirmation(
        data_dir=root,
        challenge_id=str(envelope["challenge_id"]),
        confirmation_token=str(envelope["confirmation_token"]),
        payload=request,
        now=START,
    )
    store.review_research_contract(
        PROJECT_ID,
        cid,
        scope="exploration",
        decision="approve",
        actor="owner:local-confirmation",
        actor_kind="human",
        reason="Artificial fixture",
        at=START,
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=cid,
        actor="test-agent",
        reason="D0 mechanics",
        next_action="Run D0",
        responsibility="codex",
        at=START,
    )
    store.transition_research_execution(
        PROJECT_ID,
        to_state="queued",
        contract_id=cid,
        actor="test-agent",
        reason="D0",
        next_action="Run D0",
        responsibility="codex",
        at=START,
    )
    fingerprint = d0_fingerprint(payload)
    reservation = store.reserve_d0_research_launch(
        PROJECT_ID, cid, config_fingerprint=fingerprint, at=START
    )
    manifest = publish_rule_run(
        root,
        project_id=PROJECT_ID,
        contract_id=cid,
        contract=payload,
        execution_fingerprint=fingerprint,
    )
    store.record_research_attempt(
        PROJECT_ID,
        cid,
        kind="d0-synthetic-pilot",
        status="completed",
        config_fingerprint=fingerprint,
        budget_used={},
        run_id=manifest["run_id"],
        details={
            "attempt_number": 1,
            "evidence_zone": "D0",
            "d0_acceptance_ref": _d0_acceptance_ref(root, manifest["run_id"]),
        },
        launch_reservation_id=str(reservation["reservation_id"]),
        at=START,
    )
    store.transition_research_execution(
        PROJECT_ID,
        to_state="idle",
        contract_id=cid,
        actor="test-agent",
        reason="D0 complete",
        next_action="Native",
        responsibility="codex",
        at=START,
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="deep_research",
        contract_id=cid,
        actor="test-agent",
        reason="D0 complete",
        next_action="Native",
        responsibility="codex",
        at=START,
    )
    authority = RuleAuthority(root, PROJECT_ID, cid)
    prepare_daily_workspace(authority)
    launch = NativeLaunch(source, "INCONCLUSIVE", study=study, authority=authority)
    return store, cid, launch


@pytest.mark.usefixtures("owned_test_process")
@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux retained native ownership")
def test_actual_daily_native_reopen_publication_recovery_and_no_respawn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured_rule_source: Path,
) -> None:
    root = tmp_path.resolve()
    store, cid, launch = _case(root, monkeypatch, configured_rule_source)
    job = "a655f253-3ffc-4b03-bd81-5343f29357df"
    _, reservation = _native_d1_job(
        store,
        cid,
        job_id=job,
        manifest_sha256=launch.fingerprint,
        started_at=START + timedelta(minutes=12),
    )
    with pytest.raises(DataError, match="trusted clean"):
        complete_rule_trial(store, job, launch)
    # The owner runs in this test process so only the explicit artificial storage callback is
    # injected. Its actual pinned native Python child is separately spawned and retained.
    with _open_lock(root, job) as lock:
        _run_owner(root, job, "native_loop", 59, lock, native=launch)
    status = ControlStore(root).native_fixture_status(job)
    assert status["state"] == "pending_scientific_admission", status
    outcome = cast(dict[str, Any], status["outcome"])
    assert outcome["rule_result"]["schema"] == "DailyNativeRuleObservationV1"
    before = _reservations(store)
    from alpha_cli import _native_rule_completion as completion

    publisher = publish_rule_run

    def interrupted(*args: Any, **kwargs: Any) -> Any:
        publisher(*args, **kwargs)
        raise OSError("artificial interruption after immutable publication")

    monkeypatch.setattr(completion, "publish_rule_run", interrupted)
    with pytest.raises(OSError, match="artificial interruption"):
        complete_rule_trial(store, job, launch)
    assert _reservations(ControlStore(root)) == before
    monkeypatch.setattr(completion, "publish_rule_run", publisher)
    result = complete_rule_trial(ControlStore(root), job, launch)
    assert result == complete_rule_trial(ControlStore(root), job, launch)
    assert _reservations(ControlStore(root)) == before
    assert str(result["launch_reservation_id"]) == reservation["reservation_id"]
    from alpha_cli import daily_native_cmds as public_driver

    def forbidden_restart(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("completed public driver must never respawn")

    monkeypatch.setattr(public_driver, "start_daily_owner", forbidden_restart)
    for _ in range(2):
        reopened = public_driver.run_daily_deep(PROJECT_ID, data_dir=root)
        assert reopened["reconnected"] is True
        assert reopened["attempt"] == result
    from alpha_cli._native_daily_rule_restore import restore_daily_rule_evidence
    from tests.unit.test_native_rule_authority import _pilot

    reference = root / "independent-reference"
    reference.mkdir()
    for name in ("runs", "snapshots"):
        shutil.copytree(root / name, reference / name)
    # A later independent synthetic D0 reservation is authoritative and must survive restore.
    _pilot(root, project_id="3a55f253-3ffc-4b03-bd81-5343f29357df")
    authoritative_later = _reservations(ControlStore(root))
    assert len(authoritative_later) > len(before)
    parent = root / "runs" / str(result["run_id"])
    (parent / "query.json").unlink()
    recovered = restore_daily_rule_evidence(root, reference, job)
    assert recovered["control_database_replaced"] is False
    assert recovered["budget_or_exposure_reset"] is False
    assert _reservations(ControlStore(root)) == authoritative_later
    assert (parent / "query.json").read_bytes() == (
        reference / "runs" / str(result["run_id"]) / "query.json"
    ).read_bytes()
    assert restore_daily_rule_evidence(root, reference, job)["restored_files"] == []
    original = (parent / "query.json").read_bytes()
    (parent / "query.json").write_bytes(b"conflicting retained bytes")
    with pytest.raises(DataError, match="conflicting existing bytes"):
        restore_daily_rule_evidence(root, reference, job)
    (parent / "query.json").write_bytes(original)
    assert _reservations(ControlStore(root)) == authoritative_later
    with pytest.raises(DataError, match="reconnect only"):
        start_daily_owner(root, job, native=launch, seconds=60)


@pytest.mark.usefixtures("owned_test_process")
@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux retained native ownership")
def test_daily_cancellation_and_duplicate_restart_do_not_refund_or_respawn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured_rule_source: Path,
) -> None:
    from alpha_cli.native_supervisor import _Owner, _request_live_stop

    root = tmp_path.resolve()
    store, cid, launch = _case(root, monkeypatch, configured_rule_source)
    job = "b655f253-3ffc-4b03-bd81-5343f29357df"
    _native_d1_job(
        store,
        cid,
        job_id=job,
        manifest_sha256=launch.fingerprint,
        started_at=START + timedelta(minutes=12),
    )
    reserved = _reservations(store)
    spawn = _Owner.spawn

    def cancel_after_spawn(owner: _Owner) -> Any:
        observed = spawn(owner)
        assert _request_live_stop(root, job)
        return observed

    monkeypatch.setattr(_Owner, "spawn", cancel_after_spawn)
    with _open_lock(root, job) as lock:
        _run_owner(root, job, "native_loop", 59, lock, native=launch)
    status = ControlStore(root).native_fixture_status(job, reconnect=True)
    assert status["state"] == "closed"
    assert cast(dict[str, Any], status["outcome"])["reason"] == "cancelled"
    assert _reservations(ControlStore(root)) == reserved
    with pytest.raises(DataError, match="trusted clean"):
        complete_rule_trial(ControlStore(root), job, launch)
    with pytest.raises(DataError, match="reconnect only"):
        start_daily_owner(root, job, native=launch, seconds=59)
    assert _reservations(ControlStore(root)) == reserved


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux retained native ownership")
def test_daily_lost_owner_is_quarantined_without_releasing_exposure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured_rule_source: Path,
) -> None:
    from alpha_cli.native_supervisor import _Owner

    root = tmp_path.resolve()
    store, cid, launch = _case(root, monkeypatch, configured_rule_source)
    job = "c655f253-3ffc-4b03-bd81-5343f29357df"
    _native_d1_job(
        store,
        cid,
        job_id=job,
        manifest_sha256=launch.fingerprint,
        started_at=START + timedelta(minutes=12),
    )
    reserved = _reservations(store)
    with _open_lock(root, job) as lock:
        owner = _Owner(root, job, "native_loop", 59, lock, native=launch)
        store.claim_native_fixture(job, owner)
    status = ControlStore(root).native_fixture_status(job, reconnect=True)
    assert status["state"] == "quarantined"
    assert _reservations(ControlStore(root)) == reserved
    with pytest.raises(DataError, match="trusted clean"):
        complete_rule_trial(ControlStore(root), job, launch)
    with pytest.raises(DataError, match="reconnect only"):
        start_daily_owner(root, job, native=launch, seconds=59)
    assert _reservations(ControlStore(root)) == reserved


def _owner_loss_fixture() -> None:
    """Isolated fault-injection owner; never a product CLI or admissible research route."""
    import os

    import alpha_cli.crypto_bulk_store as backend
    import alpha_cli.native_supervisor as supervisor
    from alpha_cli._native_daily_rule_protocol import study_from_contract
    from tests.unit.test_crypto_price_snapshot_query import _store

    root, job, contract_id, source = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
    ready_fd, go_fd = int(sys.argv[5]), int(sys.argv[6])
    patches = pytest.MonkeyPatch()
    patches.setattr(backend, "configured_crypto_bulk_store", lambda selected=None: _store(root))
    authority = RuleAuthority(root, PROJECT_ID, contract_id)
    study = study_from_contract(authority.verify())
    launch = NativeLaunch(source, "INCONCLUSIVE", study=study, authority=authority)
    original = supervisor._Owner.spawn

    def wait_in_running(owner: supervisor._Owner) -> Any:
        assert owner.native_admission is not None
        # Existing closed worker wait stage deliberately injects an I/O hang. No successful
        # receipt could pass the original mode binding; this is resource-containment proof only.
        owner.native_admission = {**owner.native_admission, "mode": "wait"}
        return original(owner)

    patches.setattr(supervisor._Owner, "spawn", wait_in_running)
    # Preparation can be slow under coverage/xdist. It is not part of the injected
    # fifteen-second payload experiment: do not start that owner clock until GO.
    with os.fdopen(ready_fd, "wb", buffering=0) as prepared:
        prepared.write(b"R")
    with os.fdopen(go_fd, "rb", buffering=0) as start:
        if start.read(1) != b"G":
            raise RuntimeError("fault-injection parent closed before GO")
    with _open_lock(root, job) as lock:
        _run_owner(root, job, "native_loop", 15, lock, native=launch)


@pytest.mark.usefixtures("owned_test_process")
@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux retained native ownership")
def test_daily_owner_sigkill_leaves_bounded_container_and_quarantines_exposure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured_rule_source: Path,
) -> None:
    import os
    import signal
    import subprocess
    import time

    from alpha_cli._native_daily_rule_container import DailyRuleContainer
    from alpha_cli._native_fixture_store import _events

    root = tmp_path.resolve()
    store, cid, launch = _case(root, monkeypatch, configured_rule_source)
    job = "d655f253-3ffc-4b03-bd81-5343f29357df"
    _native_d1_job(
        store,
        cid,
        job_id=job,
        manifest_sha256=launch.fingerprint,
        started_at=START + timedelta(minutes=12),
    )
    reserved = _reservations(store)
    import select

    from alpha_cli._native_daily_rule_study import DailyRuleStudyV1

    assert isinstance(launch.study, DailyRuleStudyV1)
    study = launch.study
    log_path = root / "control" / "fault-injection-owner.log"
    ready_read, ready_write = os.pipe()
    go_read, go_write = os.pipe()
    container: DailyRuleContainer | None = None
    events: dict[str, dict[str, object]] = {}

    def diagnostics() -> str:
        with log_path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - 8000))
            return stream.read().decode(errors="replace")

    def retained_container(observed: dict[str, dict[str, object]]) -> DailyRuleContainer | None:
        claim = observed.get("native_claim")
        if claim is None:
            return None
        retained = DailyRuleContainer(
            work=root / ("payload-" + job),
            source=configured_rule_source,
            study=study,
            job_id=job,
            owner_id=str(claim["owner_id"]),
            reservation_id=str(claim["reservation_id"]),
            spec_sha256=str(claim["spec_sha256"]),
            cpu_milliseconds=60000,
            deadline_monotonic_ns=cast(int, claim["deadline_monotonic_ns"]),
        )
        assert retained.binding() == {key: claim[key] for key in retained.binding()}
        created = observed.get("native_container_created")
        if created is not None:
            retained.cid = str(created["container_id"])
        return retained

    with (
        os.fdopen(ready_read, "rb", buffering=0) as prepared,
        os.fdopen(go_write, "wb", buffering=0) as start,
        log_path.open("xb") as log,
    ):
        try:
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "tests.unit.test_native_daily_rule_lifecycle",
                    str(root),
                    job,
                    cid,
                    str(configured_rule_source),
                    str(ready_write),
                    str(go_read),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                pass_fds=(ready_write, go_read),
            )
        finally:
            os.close(ready_write)
            os.close(go_read)
        try:
            # This is a bounded fixture-import/verification readiness wait, not an enlarged
            # production execution allowance. The unchanged owner clock starts only after GO.
            ready_until = time.monotonic() + 120
            while time.monotonic() < ready_until:
                readable, _, _ = select.select([prepared], [], [], 0.1)
                if readable:
                    assert prepared.read(1) == b"R", diagnostics()
                    break
                assert child.poll() is None, diagnostics()
            else:
                raise AssertionError(
                    "fault owner preparation did not become ready: " + diagnostics()
                )
            start.write(b"G")
            until = time.monotonic() + 15
            while time.monotonic() < until:
                with store._transaction(write=False) as connection:
                    events = _events(connection, job)
                if container is None:
                    container = retained_container(events)
                if "native_started" in events:
                    break
                assert child.poll() is None, diagnostics()
                time.sleep(0.05)
            assert "native_started" in events, diagnostics()
            assert container is not None
            claim, created = events["native_claim"], events["native_container_created"]
            container.cid = str(created["container_id"])
            os.kill(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
            assert (
                ControlStore(root).native_fixture_status(job, reconnect=True)["state"]
                == "quarantined"
            )
            deadline = cast(int, claim["deadline_monotonic_ns"]) / 1_000_000_000 + 3
            while time.monotonic() < deadline:
                state = container._inspect()
                assert state is not None
                if state["State"]["Running"] is False:
                    break
                time.sleep(0.1)
            stopped = container._inspect()
            assert stopped is not None and stopped["State"]["Running"] is False
            assert stopped["State"]["ExitCode"] == 124
            assert _reservations(ControlStore(root)) == reserved
            assert (
                ControlStore(root).native_fixture_status(job, reconnect=True)["state"]
                == "quarantined"
            )
            with pytest.raises(DataError, match="trusted clean"):
                complete_rule_trial(ControlStore(root), job, launch)
        finally:
            try:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
            finally:
                # Creation can finish before its started journal event. Recover only the exact
                # predetermined owner/name/image/labels; never leave that resource behind merely
                # because the test failed during the readiness or publication window.
                if container is None:
                    with store._transaction(write=False) as connection:
                        events = _events(connection, job)
                    container = retained_container(events)
                if container is not None:
                    container.cleanup()
    assert container is not None and container.removed
    assert _reservations(ControlStore(root)) == reserved


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux qualified native profile")
def test_consumed_daily_approval_rejects_changed_execution_guards_before_new_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured_rule_source: Path,
) -> None:
    from alpha_cli import _native_rule_environment as environment

    root = tmp_path.resolve()
    store, cid, launch = _case(root, monkeypatch, configured_rule_source)
    before = _reservations(store)
    read_bytes = Path.read_bytes
    paths = (
        Path(environment.__file__).with_name("_native_daily_rule_container.py"),
        Path(environment.__file__).resolve().parents[4]
        / "workers/rdagent/daily_container_entry.py",
    )
    for changed in paths:

        def mutated(path: Path, target: Path = changed) -> bytes:
            original = read_bytes(path)
            return (
                original + b"\n# independent mutation of approved execution guard"
                if path == target
                else original
            )

        with monkeypatch.context() as patch:
            patch.setattr(Path, "read_bytes", mutated)
            with pytest.raises(DataError, match="code/runtime differs from exact owner approval"):
                NativeLaunch(
                    configured_rule_source,
                    "INCONCLUSIVE",
                    study=launch.study,
                    authority=RuleAuthority(root, PROJECT_ID, cid),
                )
        assert _reservations(ControlStore(root)) == before


if __name__ == "__main__":
    _owner_loss_fixture()

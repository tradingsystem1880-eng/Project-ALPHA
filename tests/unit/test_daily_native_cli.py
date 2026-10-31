"""Public daily CLI wiring with artificial data; no real-market acceptance or user approval."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from alpha_cli import daily_native_cmds, research_cmds
from alpha_cli._native_daily_rule_protocol import daily_operator, sha, study_from_contract
from alpha_cli._native_rule_authority import RuleAuthority
from alpha_cli.control_store import ControlStore
from alpha_cli.main import app
from alpha_core import DataError
from tests.unit.test_crypto_price_snapshot_query import _full_discovery_fixture
from tests.unit.test_native_daily_rule_admission import _contract
from tests.unit.test_native_daily_rule_lifecycle import _case, _reservations
from tests.unit.test_native_rule_authority import configured_rule_source as configured_rule_source
from tests.unit.test_research_control_store import PROJECT_ID, START


def _project_and_pack(root: Path) -> tuple[ControlStore, str]:
    store = ControlStore(root)
    store.create_project(
        name="Artificial daily CLI fixture",
        hypothesis="Engineering dispatch only",
        falsification_criterion="Mismatched input identities fail",
        project_id=PROJECT_ID,
        at=START,
    )
    source = store.create_research_source(
        PROJECT_ID,
        title="Artificial daily fixture",
        locator="artificial:daily-cli",
        provider="synthetic",
        access_mode="metadata_only",
        metadata={"data_origin": "artificial_fixture"},
        at=START,
    )
    pack = store.create_research_source_pack(
        PROJECT_ID,
        source_ids=[str(source["source_id"])],
        definition={"data_origin": "artificial_fixture"},
        at=START,
    )
    return store, str(pack["pack_id"])


def _count(store: ControlStore, table: str) -> int:
    assert table in {"research_contracts", "research_launch_reservations", "owner_action_receipts"}
    with store._transaction(write=False) as connection:
        return int(connection.execute("SELECT count(*) FROM " + table).fetchone()[0])


def test_daily_d0_dispatch_publishes_closed_mechanics_with_its_bound_hash(tmp_path: Path) -> None:
    payload = _contract(tmp_path)
    expected = sha(
        {"runtime": "DailyRuleD0V1", "operator": daily_operator(study_from_contract(payload))}
    )
    assert research_cmds._validate_registered_d0_contract(payload) == daily_operator(
        study_from_contract(payload)
    )
    assert research_cmds._registered_d0_execution_fingerprint(payload) == expected
    manifest = research_cmds._run_registered_d0_pilot(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id="rc_" + "e" * 64,
        contract=payload,
    )
    assert manifest["command"] == "research_daily_rule_pilot_v1"
    assert manifest["execution_fingerprint"] == expected
    assert manifest["evidence_zone"] == "D0"
    assert manifest["real_market_evidence"] is False
    assert manifest["data_origin"] == "artificial_fixture"
    assert manifest["scientific_acceptance"] == "not_admitted"
    assert set(manifest["artifacts"]) == {"baseline.json", "control.json", "d0_acceptance.json"}


@pytest.mark.parametrize("crowding", [False, True])
def test_existing_non_daily_d0_dispatch_and_hash_are_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, crowding: bool
) -> None:
    payload = {
        "protocol": {
            "d0_operator": {"name": "bybit_btcusdt_crowding_reversal" if crowding else "legacy"}
        }
    }
    validator = "validate_crypto_d0_contract" if crowding else "validate_d0_pilot_contract"
    fingerprinter = "crypto_d0_execution_fingerprint" if crowding else "d0_execution_fingerprint"
    runner = "run_crypto_crowding_pilot" if crowding else "run_synthetic_pilot"
    calls: list[tuple[str, object]] = []

    def validate(value: object) -> dict[str, object]:
        calls.append(("validate", value))
        return {"selected": validator}

    def fingerprint(value: object) -> str:
        calls.append(("fingerprint", value))
        return "unchanged-hash"

    def run(root: Path, **kwargs: object) -> dict[str, Any]:
        calls.append(("run", (root, kwargs)))
        return {"selected": runner}

    monkeypatch.setattr(research_cmds, validator, validate)
    monkeypatch.setattr(research_cmds, fingerprinter, fingerprint)
    monkeypatch.setattr(research_cmds, runner, run)
    assert research_cmds._validate_registered_d0_contract(payload) == {"selected": validator}
    assert research_cmds._registered_d0_execution_fingerprint(payload) == "unchanged-hash"
    assert research_cmds._run_registered_d0_pilot(
        tmp_path, project_id=PROJECT_ID, contract_id="contract", contract=payload
    ) == {"selected": runner}
    assert calls == [
        ("validate", payload),
        ("fingerprint", payload),
        (
            "run",
            (tmp_path, {"project_id": PROJECT_ID, "contract_id": "contract", "contract": payload}),
        ),
    ]


def test_public_draft_command_passes_exact_ids_and_config_without_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured: list[tuple[str, dict[str, object]]] = []

    def draft(project_id: str, **kwargs: object) -> dict[str, object]:
        captured.append((project_id, kwargs))
        return {"contract_id": "rc_" + "a" * 64, "approval_state": "pending"}

    monkeypatch.setattr(daily_native_cmds, "draft_daily_request", draft)
    result = CliRunner().invoke(
        app,
        [
            "research",
            "draft-daily",
            PROJECT_ID,
            "--source-pack-id",
            "sp_exact",
            "--snapshot-id",
            "b" * 64,
            "--normalized-manifest-id",
            "cm_exact",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["approval_state"] == "pending"
    assert captured == [
        (
            PROJECT_ID,
            {
                "data_dir": tmp_path,
                "source_pack_id": "sp_exact",
                "snapshot_id": "b" * 64,
                "normalized_manifest_id": "cm_exact",
            },
        )
    ]


def test_daily_draft_binds_snapshot_source_pack_and_storage_config_without_approving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alpha_cli._native_daily_rule_container as container
    import alpha_cli._native_rule_environment as runtime
    import alpha_cli.crypto_bulk_store as storage

    bulk, snapshot, manifest_id = _full_discovery_fixture(tmp_path)
    root = tmp_path / "control"
    config = root / "crypto" / "storage-config.json"
    config.write_text('{"fixture":"artificial callback storage"}')
    snapshots = root / "crypto" / "snapshots"
    snapshots.mkdir()
    (snapshots / (snapshot.snapshot_id + ".json")).write_text(json.dumps(snapshot.to_dict()))
    store, pack_id = _project_and_pack(root)
    monkeypatch.setattr(storage, "configured_crypto_bulk_store", lambda selected: bulk)
    # Only runtime measurement is supplied explicitly for this inert draft test. There is no
    # qualified worker, native launch, scientific result, or injected approval.
    monkeypatch.setattr(runtime, "measure_rule_environment", lambda costed: "a" * 64)
    monkeypatch.setattr(
        container, "daily_container_profile", lambda: {"image_id": "sha256:" + "e" * 64}
    )

    def fingerprints(costed: bool, *, daily_study: Any) -> dict[str, str]:
        assert costed is True
        return {
            "code": "b" * 64,
            "dependency_lock": "c" * 64,
            "evaluator": "d" * 64,
            "environment": daily_study.runtime_profile_sha256,
            "data": daily_study.query_sha256,
        }

    monkeypatch.setattr(runtime, "rule_implementation_fingerprints", fingerprints)
    record = daily_native_cmds.draft_daily_request(
        PROJECT_ID,
        data_dir=root,
        source_pack_id=pack_id,
        snapshot_id=snapshot.snapshot_id,
        normalized_manifest_id=manifest_id,
    )
    payload = record["payload"]
    assert isinstance(payload, dict)
    study = study_from_contract(payload)
    assert study.snapshot_sha256 == snapshot.snapshot_id
    assert study.storage_config_sha256 == hashlib.sha256(config.read_bytes()).hexdigest()
    assert study.runtime_profile_sha256 == "a" * 64
    assert study.container_image_id == "sha256:" + "e" * 64
    assert payload["source_pack_id"] == pack_id
    query = json.loads(study.query_document)
    assert query["normalized_manifest_id"] == manifest_id
    assert _count(store, "research_contracts") == 1
    assert _count(store, "research_launch_reservations") == 0
    assert _count(store, "owner_action_receipts") == 0
    case = store.research_case_summary(PROJECT_ID)
    assert case["phase"] == "exploration_review"
    with pytest.raises(DataError):
        RuleAuthority(root, PROJECT_ID, str(record["contract_id"])).verify()


@pytest.mark.parametrize("defect", ["wrong_project", "missing_storage", "bad_snapshot_id"])
def test_daily_draft_rejects_before_recording_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    store, pack_id = _project_and_pack(tmp_path)
    project = "3a55f253-3ffc-4b03-bd81-5343f29357df" if defect == "wrong_project" else PROJECT_ID
    with pytest.raises(DataError):
        daily_native_cmds.draft_daily_request(
            project,
            data_dir=tmp_path,
            source_pack_id=pack_id,
            snapshot_id="bad" if defect == "bad_snapshot_id" else "a" * 64,
            normalized_manifest_id="cm_does_not_exist",
        )
    assert _count(store, "research_contracts") == 0
    assert _count(store, "research_launch_reservations") == 0


def test_public_daily_pilot_uses_real_confirmation_and_closed_d0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, configured_rule_source: Path
) -> None:
    class StopBeforeReservation(Exception):
        pass

    reserve = ControlStore.reserve_d0_research_launch

    def stop(*args: Any, **kwargs: Any) -> Any:
        raise StopBeforeReservation

    # Reuse the genuine fixture owner ceremony, stopping immediately before its internal D0
    # reservation so the public command, rather than the fixture helper, performs that stage.
    monkeypatch.setattr(ControlStore, "reserve_d0_research_launch", stop)
    with pytest.raises(StopBeforeReservation):
        _case(tmp_path, monkeypatch, configured_rule_source)
    monkeypatch.setattr(ControlStore, "reserve_d0_research_launch", reserve)
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = CliRunner().invoke(app, ["research", "run", "pilot", PROJECT_ID, "--json"])
    assert result.exit_code == 0, result.output
    response = json.loads(result.output)
    assert response["manifest"]["command"] == "research_daily_rule_pilot_v1"
    assert response["manifest"]["real_market_evidence"] is False
    assert response["case"]["phase"] == "deep_research"
    assert (
        response["attempt"]["config_fingerprint"] == response["manifest"]["execution_fingerprint"]
    )
    assert len(_reservations(ControlStore(tmp_path))) == 1


def test_public_daily_deep_dispatches_to_native_driver_not_generic_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, configured_rule_source: Path
) -> None:
    store, _, _ = _case(tmp_path, monkeypatch, configured_rule_source)
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    calls: list[tuple[str, Path]] = []

    def transport(project_id: str, *, data_dir: Path) -> dict[str, object]:
        calls.append((project_id, data_dir))
        return {"job_id": "artificial-dispatch-fixture", "reconnected": True}

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("daily public command reached generic scientific execution")

    monkeypatch.setattr(daily_native_cmds, "run_daily_deep", transport)
    monkeypatch.setattr(research_cmds, "run_deep_research", forbidden)
    before = _reservations(store)
    result = CliRunner().invoke(app, ["research", "run", "deep", PROJECT_ID, "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["job_id"] == "artificial-dispatch-fixture"
    assert calls == [(PROJECT_ID, tmp_path)]
    assert _reservations(ControlStore(tmp_path)) == before


def test_daily_driver_uses_remaining_59_seconds_and_reconnects_without_respawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, configured_rule_source: Path
) -> None:
    store, _, launch = _case(tmp_path, monkeypatch, configured_rule_source)
    starts: list[tuple[str, float]] = []
    waits: list[float] = []

    class FakeOwnerTransport:
        # Only the transport is fake. The actual immutable contract, owner confirmation,
        # measured launch, durable job and pre-effect reservations remain genuine fixtures.
        def wait(self, *, timeout: float) -> int:
            waits.append(timeout)
            return 0

    def transport(root: Path, job_id: str, *, native: Any, seconds: float) -> Any:
        assert root == tmp_path
        assert native.study == launch.study
        assert native.authority == launch.authority
        starts.append((job_id, seconds))
        return FakeOwnerTransport()

    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", transport)
    result = daily_native_cmds.run_daily_deep(PROJECT_ID, data_dir=tmp_path)
    assert len(starts) == 1
    assert starts[0][1] == pytest.approx(59.0)
    assert waits == [pytest.approx(79.0)]
    assert result["native"] == {"claim": None, "state": "unclaimed"}
    reserved = _reservations(store)
    assert len(reserved) == 2
    raw_budget = next(row for row in reserved if row["phase"] == "deep_research")[
        "budget_reserved_json"
    ]
    assert isinstance(raw_budget, str)
    native_budget = json.loads(raw_budget)
    assert native_budget["wall_seconds"] == pytest.approx(59.0)
    assert native_budget["variants"] == 2
    reopened = daily_native_cmds.run_daily_deep(PROJECT_ID, data_dir=tmp_path)
    assert reopened["reconnected"] is True
    assert reopened["job_id"] == result["job_id"]
    assert len(starts) == 1
    assert _reservations(ControlStore(tmp_path)) == reserved


def test_daily_driver_startup_uncertainty_keeps_reservation_and_never_retries_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, configured_rule_source: Path
) -> None:
    store, _, _ = _case(tmp_path, monkeypatch, configured_rule_source)
    starts: list[str] = []

    def transport(root: Path, job_id: str, **kwargs: Any) -> Any:
        starts.append(job_id)
        raise OSError("artificial uncertain startup transport")

    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", transport)
    with pytest.raises(DataError, match="dispatch is uncertain") as caught:
        daily_native_cmds.run_daily_deep(PROJECT_ID, data_dir=tmp_path)
    assert isinstance(caught.value.__cause__, OSError)
    reserved = _reservations(store)
    assert len(reserved) == 2
    assert store.research_case_summary(PROJECT_ID)["active_job_id"] == starts[0]
    assert starts[0] in str(caught.value)
    result = daily_native_cmds.run_daily_deep(PROJECT_ID, data_dir=tmp_path)
    assert result["reconnected"] is True
    assert result["job_id"] == starts[0]
    assert starts == [result["job_id"]]
    assert _reservations(ControlStore(tmp_path)) == reserved


@pytest.mark.parametrize("committed", [False, True])
def test_daily_driver_reservation_failure_keeps_job_without_refund_or_second_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured_rule_source: Path,
    committed: bool,
) -> None:
    store, _, _ = _case(tmp_path, monkeypatch, configured_rule_source)
    before = _reservations(store)
    reserve = ControlStore.reserve_d1_native_research_launch

    def reject(*args: Any, **kwargs: Any) -> Any:
        if committed:
            reserve(*args, **kwargs)
        raise DataError("artificial reservation rejection")

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("reservation failure spawned a native owner")

    monkeypatch.setattr(ControlStore, "reserve_d1_native_research_launch", reject)
    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", forbidden)
    with pytest.raises(DataError, match="could not confirm its reservation") as caught:
        daily_native_cmds.run_daily_deep(PROJECT_ID, data_dir=tmp_path)
    assert isinstance(caught.value.__cause__, DataError)
    assert str(caught.value.__cause__) == "artificial reservation rejection"
    case = store.research_case_summary(PROJECT_ID)
    job_id = case["active_job_id"]
    assert isinstance(job_id, str)
    assert job_id in str(caught.value)
    assert case["execution_state"] == "running"
    retained = _reservations(ControlStore(tmp_path))
    if committed:
        assert len(retained) == len(before) + 1
    else:
        assert retained == before
    reconnected = daily_native_cmds.run_daily_deep(PROJECT_ID, data_dir=tmp_path)
    assert reconnected["reconnected"] is True
    assert reconnected["job_id"] == job_id
    assert _reservations(ControlStore(tmp_path)) == retained


@pytest.mark.parametrize("boundary", ["job_creation_commit", "active_binding_commit"])
def test_daily_driver_pre_dispatch_lost_response_retains_original_job_and_allowance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured_rule_source: Path,
    boundary: str,
) -> None:
    store, _, _ = _case(tmp_path, monkeypatch, configured_rule_source)
    before = _reservations(store)
    original_case = store.research_case_summary(PROJECT_ID)
    known_jobs: list[str] = []
    create = ControlStore.create_research_job
    transition = ControlStore.transition_research_execution

    def lose_creation_response(*args: Any, **kwargs: Any) -> Any:
        create(*args, **kwargs)
        known_jobs.append(str(kwargs["job_id"]))
        raise OSError("artificial response lost after job creation commit")

    def lose_binding_response(*args: Any, **kwargs: Any) -> Any:
        result = transition(*args, **kwargs)
        if kwargs.get("to_state") == "running":
            known_jobs.append(str(kwargs["active_job_id"]))
            raise OSError("artificial response lost after active binding commit")
        return result

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("interrupted pre-dispatch preparation spawned a native owner")

    if boundary == "job_creation_commit":
        monkeypatch.setattr(ControlStore, "create_research_job", lose_creation_response)
    else:
        monkeypatch.setattr(ControlStore, "transition_research_execution", lose_binding_response)
    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", forbidden)
    with pytest.raises(DataError, match="job preparation") as caught:
        daily_native_cmds.run_daily_deep(PROJECT_ID, data_dir=tmp_path)
    assert isinstance(caught.value.__cause__, OSError)
    assert "response lost after" in str(caught.value.__cause__)
    assert len(known_jobs) == 1
    job_id = known_jobs[0]
    assert job_id in str(caught.value)
    assert "do not launch a replacement" in str(caught.value)

    def retained_jobs() -> list[dict[str, object]]:
        with store._transaction(write=False) as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT job_id,status,request_json FROM jobs "
                    "WHERE project_id=? ORDER BY job_id",
                    (PROJECT_ID,),
                ).fetchall()
            ]

    recorded_jobs = retained_jobs()
    assert [row["job_id"] for row in recorded_jobs] == [job_id]
    interrupted = store.research_case_summary(PROJECT_ID)
    if boundary == "job_creation_commit":
        assert interrupted["execution_state"] == "queued"
        assert interrupted["active_job_id"] is None
        assert interrupted["checkpoint"] == f"daily-native:queued:{job_id}"
    else:
        assert interrupted["execution_state"] == "running"
        assert interrupted["active_job_id"] == job_id

    for _ in range(2):
        reopened = daily_native_cmds.run_daily_deep(PROJECT_ID, data_dir=tmp_path)
        assert reopened["job_id"] == job_id
        assert reopened["reconnected"] is True
        if boundary == "job_creation_commit":
            assert reopened["state"] == "pre_dispatch_interrupted"
            assert reopened["job_recorded"] is True
            assert reopened["reservation_recorded"] is False
        else:
            assert reopened["native"] == {"claim": None, "state": "unclaimed"}
        assert retained_jobs() == recorded_jobs
        assert _reservations(ControlStore(tmp_path)) == before
        current_case = store.research_case_summary(PROJECT_ID)
        assert current_case["remaining_budget"] == original_case["remaining_budget"]
        assert current_case["elapsed_budget"] == original_case["elapsed_budget"]
    assert known_jobs == [job_id]

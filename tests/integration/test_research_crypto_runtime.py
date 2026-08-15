from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from alpha_cli import research_cmds
from alpha_cli.control_store import ControlStore
from alpha_cli.research_crypto_binding import (
    load_crypto_empirical_d1,
    load_crypto_empirical_dataset,
)
from alpha_cli.research_crypto_d2 import (
    crypto_d2_execution_fingerprint,
    run_crypto_crowding_confirmation,
    validate_crypto_d2_evidence_artifacts,
)
from alpha_cli.research_crypto_runtime import (
    crypto_d0_execution_fingerprint,
    crypto_d1_execution_fingerprint,
    registered_crypto_d0_operator,
    run_crypto_crowding_deep,
    run_crypto_crowding_pilot,
    validate_crypto_d0_acceptance_artifact,
    validate_crypto_d0_contract,
    validate_crypto_d1_evidence_artifacts,
)
from alpha_core import DataError
from alpha_research import (
    CryptoCrowdingObservationV1,
    ResearchChartFingerprintV1,
    ResearchD2BoundaryV2,
    registered_crypto_crowding_plan,
)

PROJECT_ID = "f03802b8-df35-4f19-a90c-0b3437aa587d"
CONTRACT_ID = f"rc_{'a' * 64}"


def _contract() -> dict[str, object]:
    return {
        "answer_bundle_id": registered_crypto_crowding_plan().bundle_id,
        "source_pack_id": f"rsp_{'b' * 64}",
        "hashes": {
            "code": "1" * 64,
            "dependency_lock": "2" * 64,
            "environment": "3" * 64,
            "evaluator": "4" * 64,
            "data": None,
        },
        "protocol": {"d0_operator": registered_crypto_d0_operator()},
    }


def _contract_hash(contract: dict[str, object]) -> str:
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _observations(count: int = 700) -> tuple[CryptoCrowdingObservationV1, ...]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return tuple(
        CryptoCrowdingObservationV1(
            funding_time=(funding_time := start + timedelta(hours=8 * index)),
            funding_available_at=funding_time,
            funding_rate=0.001,
            open_interest=1_000.0 + index,
            open_interest_available_at=funding_time,
            premium=-0.001,
            premium_available_at=funding_time,
            entry_time=funding_time + timedelta(hours=1),
            entry_available_at=funding_time + timedelta(hours=1),
            entry_mark=100.0,
            entry_index=100.0,
            exit_time=funding_time + timedelta(hours=8),
            exit_available_at=funding_time + timedelta(hours=8),
            exit_mark=100.0,
            exit_index=100.0,
            long_short_ratio=1.0,
            recent_trend=0.0,
            recent_volatility=0.01,
            regime="normal",
            diagnostics_available_at=funding_time,
        )
        for index in range(count)
    )


def _empirical_contract(count: int = 700) -> tuple[dict[str, object], ResearchD2BoundaryV2]:
    observations = _observations(count)
    snapshot_id = "9" * 64
    chart = ResearchChartFingerprintV1(
        instrument="BTCUSDT",
        provider="bybit",
        venue="bybit",
        timezone="UTC",
        session="continuous_crypto",
        bar_construction="fixed_60_elapsed_minute_bars",
        bar_duration_seconds=3_600,
        anchor="provider_interval_start",
        adjustment_basis="provider_native_unadjusted",
        timestamp_semantics="interval_start_utc",
    )
    boundary = ResearchD2BoundaryV2.from_eligible_groups(
        dataset_fingerprint=snapshot_id,
        eligible_groups=tuple(item.funding_time.isoformat() for item in observations),
        chart_fingerprint=chart,
        event_formula="registered-crypto-crowding-v1",
        event_availability_timestamp="bybit_funding_event_point_in_time",
        primary_endpoint="event_mark_return_minus_index_return",
        primary_horizon="next_provider_declared_funding_timestamp",
        outcome_overlap_embargo_groups=1,
    )
    contract = _contract()
    cast_hashes = contract["hashes"]
    assert isinstance(cast_hashes, dict)
    cast_hashes["data"] = snapshot_id
    protocol = contract["protocol"]
    assert isinstance(protocol, dict)
    protocol.update(
        {
            "boundary_authority": {
                "kind": "empirical_dataset",
                "real_market_evidence": True,
                "empirical_confirmation_authorized": True,
            },
            "evidence_topology": {"boundary": boundary.to_dict()},
            "empirical_dataset": {
                "ref_id": f"rd_{'7' * 64}",
                "content_sha256": snapshot_id,
                "snapshot_id": snapshot_id,
                "snapshot_hash": "8" * 64,
                "operator_fingerprint": registered_crypto_crowding_plan().operator_fingerprint,
                "asset_master_version": "asset-master-v1",
                "qualification_versions": ["crypto-quality-v1"],
            },
        }
    )
    return contract, boundary


def _confirmation_contract(count: int = 700) -> tuple[dict[str, object], ResearchD2BoundaryV2]:
    contract, boundary = _empirical_contract(count)
    contract.update(
        {
            "schema": "ResearchContractV1",
            "scope": "confirmation",
            "approval_ready": True,
            "blocking_questions": [],
            "confirmation": {
                "variant_count": 1,
                "multiplicity_count": 1,
                "familywise_alpha": 0.05,
                "minimum_confirmation_events": 10,
            },
        }
    )
    return contract, boundary


def test_crypto_d0_runtime_publishes_idempotent_recomputable_non_evidence(
    tmp_path: Path,
) -> None:
    contract = _contract()
    assert research_cmds._is_crypto_crowding_contract(contract) is True
    assert research_cmds._validate_registered_d0_contract(contract) == (
        registered_crypto_d0_operator()
    )
    assert research_cmds._registered_d0_execution_fingerprint(contract) == (
        crypto_d0_execution_fingerprint(contract)
    )
    manifest = research_cmds._run_registered_d0_pilot(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
    )
    repeated = run_crypto_crowding_pilot(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
    )

    assert repeated == manifest
    assert manifest["evidence_zone"] == "D0"
    assert manifest["real_market_evidence"] is False
    assert manifest["eligible_for_holdout_or_execution"] is False
    assert manifest["places_orders"] is False
    assert manifest["snapshot_id"] is None
    assert manifest["d0_operator"] == registered_crypto_d0_operator()
    fixture = manifest["d0_operator"]["fixture"]
    assert fixture["fixture_id"] == "bybit_btcusdt_crowding_d0_v3"
    assert fixture["fixture_version"] == 3
    acceptance = validate_crypto_d0_acceptance_artifact(
        tmp_path / "runs" / str(manifest["run_id"]),
        manifest,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract_hash=_contract_hash(contract),
        execution_fingerprint=crypto_d0_execution_fingerprint(contract),
    )
    assert acceptance["real_market_evidence"] is False
    assert acceptance["measurements"]["passed"] is True  # type: ignore[index]


def test_crypto_d0_runtime_rejects_contract_drift_and_tampered_acceptance(
    tmp_path: Path,
) -> None:
    contract = _contract()
    drifted = {**contract, "answer_bundle_id": "other"}
    with pytest.raises(DataError, match="answer bundle"):
        validate_crypto_d0_contract(drifted)

    manifest = run_crypto_crowding_pilot(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
    )
    acceptance_path = tmp_path / "runs" / str(manifest["run_id"]) / "d0_acceptance.json"
    os.chmod(acceptance_path, 0o600)
    acceptance_path.write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="exact recomputation"):
        validate_crypto_d0_acceptance_artifact(
            acceptance_path.parent,
            manifest,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract_hash=_contract_hash(contract),
            execution_fingerprint=crypto_d0_execution_fingerprint(contract),
        )


def test_crypto_d1_runtime_publishes_and_reverifies_only_discovery_zone(tmp_path: Path) -> None:
    contract, boundary = _empirical_contract()
    observations = _observations()

    manifest = run_crypto_crowding_deep(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        observations=observations,
        boundary=boundary,
    )

    assert manifest["command"] == "research_deep"
    assert manifest["evidence_zone"] == "D1"
    assert manifest["dataset_hash"] == "9" * 64
    assert manifest["real_market_evidence"] is True
    assert manifest["eligible_for_holdout_or_execution"] is False
    assert manifest["places_orders"] is False
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    evidence = validate_crypto_d1_evidence_artifacts(
        run_dir,
        manifest,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        observations=observations,
        boundary=boundary,
    )
    assert evidence["schema"] == "ResearchGateEvidenceV1"
    assert evidence["evidence_zone"] == "D1"
    assert evidence["primary_result"]["status"] == "INCONCLUSIVE"  # type: ignore[index]
    assert crypto_d1_execution_fingerprint(contract) == manifest["execution_fingerprint"]
    assert (
        research_cmds._registered_d1_execution_fingerprint(contract)
        == manifest["execution_fingerprint"]
    )

    analyses = json.loads((run_dir / "d1_analyses.json").read_text(encoding="utf-8"))
    assert analyses["admission"]["start_index"] == boundary.d1.start_index
    assert analyses["admission"]["stop_index"] == (
        boundary.d1.stop_index - boundary.outcome_overlap_embargo_groups
    )


def test_crypto_d1_runtime_rejects_tampered_measurements(tmp_path: Path) -> None:
    contract, boundary = _empirical_contract()
    observations = _observations()
    manifest = run_crypto_crowding_deep(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        observations=observations,
        boundary=boundary,
    )
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    analyses_path = run_dir / "d1_analyses.json"
    os.chmod(analyses_path, 0o600)
    analyses_path.write_text("{}", encoding="utf-8")

    with pytest.raises(DataError, match="immutable manifest hash"):
        validate_crypto_d1_evidence_artifacts(
            run_dir,
            manifest,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
            observations=observations,
            boundary=boundary,
        )


def test_crypto_d1_runtime_marks_planted_discovery_ready_for_owner_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract, boundary = _empirical_contract(3_000)
    observations = list(_observations(3_000))
    for index in range(400, boundary.d1.stop_index - 1, 22):
        observations[index] = replace(
            observations[index],
            funding_rate=0.02,
            premium=0.001,
            exit_mark=99.0,
        )
    manifest = run_crypto_crowding_deep(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        observations=tuple(observations),
        boundary=boundary,
    )
    evidence = json.loads(
        (tmp_path / "runs" / str(manifest["run_id"]) / "research_gate_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["primary_result"]["status"] == "TESTED"
    assert evidence["negative_controls"]["status"] == "PASSED"
    assert evidence["confirmation_readiness"]["state"] == "ready"

    class ConfirmationStore:
        created_payload: dict[str, object] | None = None

        def create_research_contract(self, project_id: str, **kwargs: object) -> dict[str, object]:
            assert project_id == PROJECT_ID
            payload = kwargs["payload"]
            assert isinstance(payload, dict)
            self.created_payload = payload
            return {"contract_id": f"rc_{'c' * 64}"}

        def transition_research_phase(self, project_id: str, **kwargs: object) -> None:
            assert project_id == PROJECT_ID
            assert kwargs["to_phase"] == "confirmation_review"

        def research_case_summary(self, project_id: str) -> dict[str, object]:
            assert project_id == PROJECT_ID
            return {"phase": "confirmation_review"}

    fake_store = ConfirmationStore()
    monkeypatch.setattr(
        research_cmds,
        "_crypto_empirical_d1",
        lambda store, payload: (tuple(observations), boundary),
    )
    monkeypatch.setattr(
        research_cmds,
        "AlphaSettings",
        lambda: SimpleNamespace(data_dir=tmp_path),
    )
    confirmation, case = research_cmds._draft_crypto_confirmation(
        cast(ControlStore, fake_store),
        project_id=PROJECT_ID,
        exploration_id=CONTRACT_ID,
        payload=contract,
        manifest=manifest,
        created_by="codex",
    )
    assert confirmation["contract_id"] == f"rc_{'c' * 64}"
    assert case["phase"] == "confirmation_review"
    assert fake_store.created_payload is not None
    frozen = fake_store.created_payload["confirmation"]
    assert isinstance(frozen, dict)
    assert frozen["minimum_confirmation_events"] == 10
    assert frozen["d1_event_count"] >= 50
    assert frozen["boundary_sha256"] == boundary.boundary_sha256


def test_crypto_empirical_binding_reverifies_snapshot_and_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpha_cli import crypto_data_cmds

    contract, boundary = _empirical_contract()
    observations = _observations()
    ref_id = f"rd_{'7' * 64}"

    class Store:
        def get_research_dataset(self, selected_ref_id: str) -> dict[str, object]:
            assert selected_ref_id == ref_id
            return {
                "ref_id": ref_id,
                "dataset_kind": "snapshot",
                "instrument": "BTC",
                "provider": "crypto-data-house",
                "origin": {
                    "snapshot_schema": "CryptoSnapshotV1",
                    "snapshot_id": "9" * 64,
                    "manifest_sha256": "8" * 64,
                },
            }

    monkeypatch.setattr(
        crypto_data_cmds,
        "crypto_crowding_snapshot_compatibility",
        lambda snapshot_id: {
            "eligible": snapshot_id == "9" * 64,
            "bundle_id": "bybit_btcusdt_crowding_reversal_v1",
            "operator_fingerprint": registered_crypto_crowding_plan().operator_fingerprint,
            "asset_master_version": "asset-master-v1",
            "qualification_versions": ["crypto-quality-v1"],
        },
    )
    monkeypatch.setattr(
        crypto_data_cmds,
        "crypto_crowding_observations",
        lambda snapshot_id: observations if snapshot_id == "9" * 64 else (),
    )

    binding = load_crypto_empirical_dataset(Store(), ref_id)
    loaded, loaded_boundary = load_crypto_empirical_d1(Store(), contract)
    assert binding.snapshot_id == "9" * 64
    assert loaded == observations
    assert loaded_boundary == boundary

    empirical = contract["protocol"]["empirical_dataset"]  # type: ignore[index]
    assert isinstance(empirical, dict)
    empirical["qualification_versions"] = ["drifted"]
    with pytest.raises(DataError, match="approval-frozen binding"):
        load_crypto_empirical_d1(Store(), contract)

    class InvalidStore:
        def get_research_dataset(self, ref_id: str) -> dict[str, object]:
            return {}

    with pytest.raises(DataError, match="registered CryptoSnapshotV1"):
        load_crypto_empirical_dataset(InvalidStore(), ref_id)
    with pytest.raises(DataError, match="no frozen snapshot binding"):
        load_crypto_empirical_d1(Store(), {})

    empirical["qualification_versions"] = ["crypto-quality-v1"]
    topology = contract["protocol"]["evidence_topology"]  # type: ignore[index]
    assert isinstance(topology, dict)
    frozen_boundary = topology.pop("boundary")
    with pytest.raises(DataError, match="no sealed evidence boundary"):
        load_crypto_empirical_d1(Store(), contract)
    topology["boundary"] = frozen_boundary

    monkeypatch.setattr(
        crypto_data_cmds,
        "crypto_crowding_observations",
        lambda snapshot_id: observations[:-1],
    )
    with pytest.raises(DataError, match="snapshot membership"):
        load_crypto_empirical_d1(Store(), contract)


def test_crypto_d2_runtime_is_one_shot_zone_bound_and_recomputable(tmp_path: Path) -> None:
    contract, boundary = _confirmation_contract()
    observations = _observations()
    manifest = run_crypto_crowding_confirmation(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        observations=observations,
        boundary=boundary,
    )

    assert manifest["command"] == "research_confirm"
    assert manifest["evidence_zone"] == "D2"
    assert manifest["eligible_for_holdout_or_execution"] is False
    assert manifest["places_orders"] is False
    assert manifest["execution_fingerprint"] == crypto_d2_execution_fingerprint(contract)
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    evidence = validate_crypto_d2_evidence_artifacts(
        run_dir,
        manifest,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        observations=observations,
        boundary=boundary,
    )
    assert evidence["confirmation_classification"] == "INCONCLUSIVE"
    analyses = json.loads((run_dir / "d2_analyses.json").read_text(encoding="utf-8"))
    assert analyses["admission"]["start_index"] == boundary.d2.start_index
    assert analyses["admission"]["stop_index"] == (
        boundary.d2.stop_index - boundary.outcome_overlap_embargo_groups
    )


def test_crypto_d2_runtime_rejects_policy_drift_identity_drift_and_tampering(
    tmp_path: Path,
) -> None:
    contract, boundary = _confirmation_contract()
    observations = _observations()
    checkpoints: list[str] = []
    manifest = run_crypto_crowding_confirmation(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        observations=observations,
        boundary=boundary,
        on_checkpoint=checkpoints.append,
    )
    assert checkpoints == ["d2:sealed-share-verified", "d2:one-shot-family-complete"]

    with pytest.raises(DataError, match="canonical project and contract ids"):
        run_crypto_crowding_confirmation(
            tmp_path,
            project_id="bad",
            contract_id=CONTRACT_ID,
            contract=contract,
            observations=observations,
            boundary=boundary,
        )
    with pytest.raises(DataError, match="approval-ready confirmation"):
        crypto_d2_execution_fingerprint({**contract, "scope": "exploration"})
    drifted = dict(contract)
    drifted["confirmation"] = {
        **contract["confirmation"],  # type: ignore[dict-item]
        "minimum_confirmation_events": 9,
    }
    with pytest.raises(DataError, match="confirmation policy"):
        crypto_d2_execution_fingerprint(drifted)

    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    for changed, message in (
        ({**manifest, "command": "research_deep"}, "research_confirm D2 manifest"),
        ({**manifest, "project_id": "00000000-0000-4000-8000-000000000000"}, "authority"),
    ):
        with pytest.raises(DataError, match=message):
            validate_crypto_d2_evidence_artifacts(
                run_dir,
                changed,
                project_id=PROJECT_ID,
                contract_id=CONTRACT_ID,
                contract=contract,
                observations=observations,
                boundary=boundary,
            )
    with pytest.raises(DataError, match="frozen execution"):
        validate_crypto_d2_evidence_artifacts(
            run_dir,
            {**manifest, "dataset_hash": "0" * 64},
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
            observations=observations,
            boundary=boundary,
        )
    analyses_path = run_dir / "d2_analyses.json"
    with pytest.raises(DataError, match="does not bind"):
        validate_crypto_d2_evidence_artifacts(
            run_dir,
            {**manifest, "artifacts": {}},
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
            observations=observations,
            boundary=boundary,
        )
    original_analyses = analyses_path.read_bytes()
    os.chmod(analyses_path, 0o600)
    analyses_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(DataError, match="not canonical JSON"):
        validate_crypto_d2_evidence_artifacts(
            run_dir,
            manifest,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
            observations=observations,
            boundary=boundary,
        )
    analyses_path.write_bytes(original_analyses)
    analyses_path.write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="immutable manifest hash"):
        validate_crypto_d2_evidence_artifacts(
            run_dir,
            manifest,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
            observations=observations,
            boundary=boundary,
        )

    analyses_path.write_bytes(original_analyses)


def test_crypto_d2_runtime_classifies_a_planted_sealed_effect(tmp_path: Path) -> None:
    observations = list(_observations(1_400))
    contract, _ = _confirmation_contract()
    snapshot_id = "9" * 64
    chart = ResearchChartFingerprintV1(
        instrument="BTCUSDT",
        provider="bybit",
        venue="bybit",
        timezone="UTC",
        session="continuous_crypto",
        bar_construction="fixed_60_elapsed_minute_bars",
        bar_duration_seconds=3_600,
        anchor="provider_interval_start",
        adjustment_basis="provider_native_unadjusted",
        timestamp_semantics="interval_start_utc",
    )
    boundary = ResearchD2BoundaryV2.from_eligible_groups(
        dataset_fingerprint=snapshot_id,
        eligible_groups=tuple(item.funding_time.isoformat() for item in observations),
        chart_fingerprint=chart,
        event_formula="registered-crypto-crowding-v1",
        event_availability_timestamp="bybit_funding_event_point_in_time",
        primary_endpoint="event_mark_return_minus_index_return",
        primary_horizon="next_provider_declared_funding_timestamp",
        outcome_overlap_embargo_groups=1,
    )
    for index in range(boundary.d2.start_index + 10, boundary.d2.stop_index - 1, 21):
        observations[index] = replace(
            observations[index],
            funding_rate=0.02,
            premium=0.001,
            exit_mark=99.0,
        )
    protocol = contract["protocol"]
    assert isinstance(protocol, dict)
    topology = protocol["evidence_topology"]
    assert isinstance(topology, dict)
    topology["boundary"] = boundary.to_dict()

    manifest = run_crypto_crowding_confirmation(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        observations=tuple(observations),
        boundary=boundary,
    )
    evidence = json.loads(
        (tmp_path / "runs" / str(manifest["run_id"]) / "research_gate_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["confirmation_classification"] == "SUPPORTED"

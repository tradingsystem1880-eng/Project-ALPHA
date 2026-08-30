"""Owner/Codex research workflow from raw idea through the synthetic Gate-1 pilot."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from typer.testing import CliRunner

from alpha_cli import control_store as control_store_module
from alpha_cli import research_cmds
from alpha_cli.artifact_contract import artifact_metadata
from alpha_cli.control_store import ControlStore
from alpha_cli.main import app
from alpha_core import DataError
from alpha_research import CryptoCrowdingObservationV1
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()


def _invoke(*args: str) -> dict[str, object]:
    result = runner.invoke(app, ["research", *args, "--json"])
    assert result.exit_code == 0, result.output
    value: object = json.loads(result.output)
    assert isinstance(value, dict)
    return value


def _rewrite_d0_acceptance_and_manifest(data_dir: Path, run_id: str) -> None:
    run_dir = data_dir / "runs" / run_id
    acceptance_path = run_dir / "d0_acceptance.json"
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    acceptance["measurements"]["planted_events"] = []
    acceptance_path.write_text(
        json.dumps(acceptance, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["d0_acceptance.json"] = artifact_metadata(acceptance_path)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def test_proposal_options_are_executable_atomic_bundles_with_exact_prerequisites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke(
        "capture", "I notice the S&P500 bounces after double bottoms on the 4h time frame"
    )
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])
    empty = _invoke("proposal-options", project_id)
    assert empty["recommended_answer_bundle_id"] == "synthetic_spy_60m_four_hour_v1"
    assert empty["approval_ready"] is False
    assert [row["code"] for row in cast(list[dict[str, object]], empty["blockers"])] == [
        "SOURCE_PACK_REQUIRED"
    ]

    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Technical trading revisited",
        locator="doi:10.0000/example",
        provider="crossref",
        access_mode="metadata_only",
    )
    pack = store.create_research_source_pack(
        project_id, source_ids=[str(source["source_id"])], definition={}
    )
    dataset = store.register_research_dataset(
        dataset_kind="snapshot",
        instrument="SPY",
        provider="tiingo",
        start_ts="2010-01-01",
        end_ts="2024-12-31",
        bar_duration_minutes=1_440,
        origin={"snapshot_id": "spy-qualified", "manifest_sha256": "a" * 64},
        registered_by="owner",
    )
    store.record_research_dataset_audit(
        str(dataset["ref_id"]),
        project_id=project_id,
        run_id="deadbeefdeadbeef",
        summary={
            "audit_schema": "ResearchDataAuditV1",
            "blocking_count": 0,
            "limiting_count": 0,
            "notes": [],
        },
    )
    crypto = store.register_research_dataset(
        dataset_kind="snapshot",
        instrument="BTC",
        provider="crypto-data-house",
        start_ts="2026-08-04T00:00:00Z",
        end_ts="2026-08-14T00:00:00Z",
        bar_duration_minutes=60,
        origin={
            "snapshot_id": "b" * 64,
            "manifest_sha256": "c" * 64,
            "snapshot_schema": "CryptoSnapshotV1",
        },
        registered_by="owner",
    )

    options = _invoke("proposal-options", project_id)
    assert options["approval_ready"] is True
    assert (
        cast(list[dict[str, object]], options["compatible_source_packs"])[0]["pack_id"]
        == pack["pack_id"]
    )
    assert (
        cast(list[dict[str, object]], options["compatible_datasets"])[0]["ref_id"]
        == dataset["ref_id"]
    )
    assert crypto["ref_id"] not in {
        row["ref_id"] for row in cast(list[dict[str, object]], options["compatible_datasets"])
    }
    bundles = cast(list[dict[str, object]], options["valid_answer_bundles"])
    assert {
        (
            str(bundle["bundle_id"]),
            bool(bundle["available"]),
            tuple(cast(list[str], bundle["compatible_dataset_ids"])),
        )
        for bundle in bundles
    } == {
        ("synthetic_spy_60m_four_hour_v1", True, ()),
        ("tiingo_spy_daily_next_session_v1", True, (str(dataset["ref_id"]),)),
        ("bybit_btcusdt_crowding_reversal_v1", False, ()),
    }


def test_crypto_proposal_options_require_authoritatively_compatible_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke(
        "capture",
        "On Bybit BTCUSDT linear perpetuals, test whether extreme positive funding with rising "
        "open interest and premium predicts crowding reversal before the next funding event",
    )
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Perpetual funding mechanics",
        locator="doi:10.0000/crypto-example",
        provider="crossref",
        access_mode="metadata_only",
    )
    store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
        definition={},
    )
    compatible = store.register_research_dataset(
        dataset_kind="snapshot",
        instrument="BTC",
        provider="crypto-data-house",
        start_ts="2025-01-01T00:00:00Z",
        end_ts="2026-08-14T00:00:00Z",
        bar_duration_minutes=60,
        origin={
            "snapshot_id": "b" * 64,
            "manifest_sha256": "c" * 64,
            "snapshot_schema": "CryptoSnapshotV1",
        },
        registered_by="owner",
    )
    incompatible = store.register_research_dataset(
        dataset_kind="snapshot",
        instrument="BTC",
        provider="crypto-data-house",
        start_ts="2025-01-01T00:00:00Z",
        end_ts="2026-08-14T00:00:00Z",
        bar_duration_minutes=60,
        origin={
            "snapshot_id": "d" * 64,
            "manifest_sha256": "e" * 64,
            "snapshot_schema": "CryptoSnapshotV1",
        },
        registered_by="owner",
    )

    def compatibility(snapshot_id: str) -> dict[str, object]:
        if snapshot_id == "d" * 64:
            raise DataError("mixed quote asset")
        return {
            "snapshot_id": snapshot_id,
            "bundle_id": "bybit_btcusdt_crowding_reversal_v1",
            "operator_fingerprint": "f" * 64,
            "asset_master_version": "reviewed-native-v1",
            "qualification_versions": ["crypto-quality-v1"],
            "eligible": True,
        }

    monkeypatch.setattr(
        "alpha_cli.crypto_data_cmds.crypto_crowding_snapshot_compatibility",
        compatibility,
    )
    observation = cast(
        CryptoCrowdingObservationV1,
        SimpleNamespace(funding_time=datetime(2025, 1, 1, tzinfo=UTC)),
    )
    monkeypatch.setattr(
        "alpha_cli.crypto_data_cmds.crypto_crowding_observations",
        lambda _snapshot_id: (observation,),
    )

    binding = research_cmds._crypto_empirical_dataset(store, str(compatible["ref_id"]))
    assert binding.snapshot_id == "b" * 64
    assert binding.operator_fingerprint == "f" * 64
    assert binding.observations == (observation,)

    options = _invoke("proposal-options", project_id)

    assert options["recommended_answer_bundle_id"] == "bybit_btcusdt_crowding_reversal_v1"
    assert options["approval_ready"] is True
    bundles = cast(list[dict[str, object]], options["valid_answer_bundles"])
    selected = next(
        bundle for bundle in bundles if bundle["bundle_id"] == "bybit_btcusdt_crowding_reversal_v1"
    )
    assert selected["available"] is True
    assert selected["compatible_dataset_ids"] == [compatible["ref_id"]]
    assert incompatible["ref_id"] not in cast(list[str], selected["compatible_dataset_ids"])


def test_crypto_draft_freezes_exact_snapshot_operator_and_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke(
        "capture",
        "On Bybit BTCUSDT linear perpetuals, test whether extreme positive funding with rising "
        "open interest and premium predicts crowding reversal before the next funding event",
    )
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Perpetual funding mechanics",
        locator="doi:10.0000/crypto-example",
        provider="crossref",
        access_mode="metadata_only",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
        definition={},
    )
    dataset = store.register_research_dataset(
        dataset_kind="snapshot",
        instrument="BTC",
        provider="crypto-data-house",
        start_ts="2025-01-01T00:00:00Z",
        end_ts="2026-08-14T00:00:00Z",
        bar_duration_minutes=60,
        origin={
            "snapshot_id": "b" * 64,
            "manifest_sha256": "c" * 64,
            "snapshot_schema": "CryptoSnapshotV1",
        },
        registered_by="owner",
    )
    start = datetime(2025, 1, 1, tzinfo=UTC)
    binding = research_cmds._CryptoEmpiricalDataset(
        ref=dataset,
        snapshot_id="b" * 64,
        snapshot_hash="c" * 64,
        operator_fingerprint="f" * 64,
        asset_master_version="reviewed-native-v1",
        qualification_versions=("crypto-quality-v1",),
        observations=tuple(
            cast(
                CryptoCrowdingObservationV1,
                SimpleNamespace(funding_time=start + timedelta(hours=8 * index)),
            )
            for index in range(10)
        ),
    )
    monkeypatch.setattr(research_cmds, "_crypto_empirical_dataset", lambda *_args: binding)
    monkeypatch.setattr(
        "alpha_cli.crypto_data_cmds.crypto_crowding_snapshot_compatibility",
        lambda _snapshot_id: {
            "snapshot_id": "b" * 64,
            "bundle_id": "bybit_btcusdt_crowding_reversal_v1",
            "operator_fingerprint": "f" * 64,
            "eligible": True,
        },
    )
    options = _invoke("proposal-options", project_id)

    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer-bundle",
        "bybit_btcusdt_crowding_reversal_v1",
        "--dataset",
        str(dataset["ref_id"]),
        "--expected-case-revision",
        str(options["case_revision"]),
    )

    contract = cast(dict[str, object], drafted["contract"])
    payload = cast(dict[str, object], contract["payload"])
    assert payload["answer_bundle_id"] == "bybit_btcusdt_crowding_reversal_v1"
    assert cast(dict[str, object], payload["hashes"])["data"] == "b" * 64
    protocol = cast(dict[str, object], payload["protocol"])
    assert cast(dict[str, object], protocol["d0_operator"])["name"] == (
        "bybit_btcusdt_crowding_reversal"
    )
    authority = cast(dict[str, object], protocol["boundary_authority"])
    assert authority == {
        "kind": "empirical_dataset",
        "real_market_evidence": True,
        "empirical_confirmation_authorized": True,
    }
    empirical = cast(dict[str, object], protocol["empirical_dataset"])
    assert empirical["snapshot_id"] == "b" * 64
    assert empirical["operator_fingerprint"] == "f" * 64
    assert empirical["session_group_count"] == 10


def test_raw_idea_reaches_bounded_contract_review_and_synthetic_pilot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke(
        "capture",
        "I notice the S&P500 bounces after double bottoms on the 4h time frame",
    )
    project = captured["project"]
    contract = captured["contract"]
    case = captured["case"]
    assert isinstance(project, dict) and isinstance(contract, dict) and isinstance(case, dict)
    project_id = str(project["project_id"])
    assert case["phase"] == "triage"
    assert case["responsibility"] == "owner"
    payload = contract["payload"]
    assert isinstance(payload, dict)
    assert len(payload["blocking_questions"]) == 3
    assert payload["raw_idea"] == (
        "I notice the S&P500 bounces after double bottoms on the 4h time frame"
    )
    assert case["d2_state"] == "sealed"

    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Technical trading revisited",
        "--locator",
        "doi:10.0000/example",
        "--provider",
        "crossref",
        "--access-mode",
        "metadata_only",
    )
    pack = _invoke(
        "sources",
        "freeze",
        project_id,
        "--source-id",
        str(source["source_id"]),
    )
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        "chart_construction=spy_rth_60m_four_hour_window",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    frozen_contract = drafted["contract"]
    review_case = drafted["case"]
    assert isinstance(frozen_contract, dict) and isinstance(review_case, dict)
    frozen_id = str(frozen_contract["contract_id"])
    frozen_payload = frozen_contract["payload"]
    assert isinstance(frozen_payload, dict)
    assert frozen_payload["approval_ready"] is True
    assert frozen_payload["blocking_questions"] == []
    assert frozen_payload["source_pack_id"] == pack["pack_id"]
    hashes = frozen_payload["hashes"]
    assert isinstance(hashes, dict)
    assert hashes["data"] is None
    for field in ("code", "dependency_lock", "environment", "evaluator"):
        assert isinstance(hashes[field], str)
        assert len(hashes[field]) == 64
    assert review_case["phase"] == "exploration_review"
    assert review_case["responsibility"] == "owner"

    approved = _invoke(
        "approve",
        "exploration",
        project_id,
        frozen_id,
        "--actor",
        "owner",
        "--reason",
        "The bounded protocol and source pack are suitable for D0/D1 exploration.",
    )
    approved_case = approved["case"]
    assert isinstance(approved_case, dict)
    assert approved_case["phase"] == "pilot"
    assert approved_case["responsibility"] == "codex"

    pilot = _invoke("run", "pilot", project_id)
    manifest = pilot["manifest"]
    attempt = pilot["attempt"]
    pilot_case = pilot["case"]
    assert isinstance(manifest, dict) and isinstance(attempt, dict)
    assert isinstance(pilot_case, dict)
    assert manifest["evidence_zone"] == "D0"
    assert manifest["real_market_evidence"] is False
    assert pilot_case["phase"] == "deep_research"
    assert pilot_case["execution_state"] == "idle"
    assert pilot_case["responsibility"] == "codex"
    assert pilot_case["next_action"] == (
        "Launch `alpha research run deep` to execute the frozen analysis plan on D1."
    )
    assert pilot_case["attempt_count"] == 1
    assert pilot_case["terminal_attempt_count"] == 1
    assert pilot_case["unfinalized_launch_count"] == 0
    assert pilot_case["remaining_launches"] == 2
    assert pilot_case["elapsed_budget"] == {
        "source_requests": 0,
        "variants": 3,
        "wall_seconds": 1,
    }
    assert attempt["budget_used"] == {}
    assert attempt["launch_reservation_id"] == pilot_case["latest_launch_reservation_id"]
    details = attempt["details"]
    assert isinstance(details, dict)
    assert details["d0_acceptance_ref"] == {
        "artifact": "d0_acceptance.json",
        "content_sha256": manifest["artifacts"]["d0_acceptance.json"]["sha256"],
    }
    semantic = _invoke("semantic-projection", project_id)
    assert set(semantic) == {
        "schema",
        "schema_version",
        "source_verification",
        "authority",
        "run_id",
        "projection",
        "content_sha256",
    }
    assert semantic["schema"] == "VerifiedBlindSemanticReadV1"
    assert semantic["source_verification"] == "verified_completed_d0_recomputation"
    assert semantic["authority"] == "none"
    assert semantic["run_id"] == manifest["run_id"]
    current_status = _invoke("status", project_id)
    study_status = current_status["study_status"]
    assert isinstance(study_status, dict)
    assert study_status == {
        "schema": "ResearchStudyStatusV1",
        "schema_version": 1,
        "authority": "none",
        "project_id": project_id,
        "active_contract_id": frozen_id,
        "semantic": {
            "state": "definition_required",
            "source_state": "not_recorded",
            "case_contract_id": None,
            "case_revision": None,
            "verified_read_sha256": None,
            "projection_sha256": None,
            "run_id": None,
            "cutoff_confirmed_at": None,
            "event_count": 0,
            "head_sha256": control_store_module._semantic_empty_head_sha256(project_id),
            "definition": None,
            "review": None,
            "freeze": None,
            "next_owner_action": "Record a semantic definition with fresh Touch ID.",
        },
        "d1": {
            "launch_authority": "owner_cli_only",
            "status": "not_started",
            "attempts": [],
            "elapsed_budget": current_status["elapsed_budget"],
            "remaining_budget": current_status["remaining_budget"],
        },
        "promotion": {
            "packet_id": None,
            "readiness": current_status["promotion_readiness"],
        },
        "next_action": current_status["next_action"],
        "responsibility": current_status["responsibility"],
    }
    assert pilot_case["d2_state"] == "sealed"
    assert pilot_case["latest_run_id"] == manifest["run_id"]
    assert pilot_case["latest_run_fingerprint"] == manifest["execution_fingerprint"]
    assert "not real-market evidence" in str(pilot_case["latest_finding"])
    assert pilot_case["elapsed_time_seconds"] >= 0
    assert pilot_case["completed_milestones"][-1]["phase"] == "deep_research"
    assert pilot_case["remaining_milestones"] == [
        "confirmation_review",
        "sealed_confirmation",
        "research_decision",
        "closed",
    ]

    contradicted = runner.invoke(
        app,
        [
            "research",
            "decide",
            project_id,
            "--outcome",
            "CONTRADICTED",
            "--disposition",
            "reject",
            "--actor",
            "owner",
            "--reason",
            "D0 alone must not be presented as a market contradiction.",
            "--json",
        ],
    )
    assert contradicted.exit_code != 0
    after_rejected_claim = _invoke("status", project_id)
    assert after_rejected_claim["phase"] == "deep_research"
    assert after_rejected_claim["research_decision"] is None

    closed = _invoke(
        "decide",
        project_id,
        "--outcome",
        "INCONCLUSIVE",
        "--disposition",
        "park",
        "--actor",
        "owner",
        "--reason",
        "D0 passed, but empirical D1/D2 remain gated and no market claim is supportable.",
    )
    closed_case = cast(dict[str, object], closed["case"])
    assert closed_case["phase"] == "closed"
    assert closed_case["d2_state"] == "sealed"
    terminal = _invoke("report", project_id)
    assert terminal["report_schema"] == "ResearchGatePacketV1"
    assert terminal["scientific_outcome"] == "INCONCLUSIVE"
    assert terminal["recommended_disposition"] == "park"


def test_interrupted_pilot_recovery_rejects_post_admission_d0_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke(
        "capture",
        "I notice the S&P500 bounces after double bottoms on the 4h time frame",
    )
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Synthetic recovery protocol",
        locator="owner:synthetic-recovery",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        "chart_construction=spy_rth_60m_four_hour_window",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    contract = cast(dict[str, object], drafted["contract"])
    _invoke(
        "approve",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "Approve the recovery integrity fixture.",
    )

    original_transition = ControlStore.transition_research_phase
    interrupted = False

    def interrupt_after_terminal_attempt(
        self: ControlStore, *args: object, **kwargs: object
    ) -> dict[str, object]:
        nonlocal interrupted
        if kwargs.get("to_phase") in {"research_decision", "deep_research"} and not interrupted:
            interrupted = True
            raise RuntimeError("simulated process interruption after D0 admission")
        return original_transition(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(ControlStore, "transition_research_phase", interrupt_after_terminal_attempt)
    first = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
    assert first.exit_code != 0
    checkpoint = store.research_case_summary(project_id)
    assert checkpoint["phase"] == "pilot"
    assert checkpoint["execution_state"] == "idle"
    run_id = cast(str, checkpoint["latest_run_id"])
    _rewrite_d0_acceptance_and_manifest(tmp_path, run_id)

    recovery = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
    assert recovery.exit_code != 0
    assert "deterministic" in recovery.output
    assert "recomputation" in recovery.output
    database = sqlite3.connect(tmp_path / "control" / "workstation.sqlite3")
    latest_phase = database.execute(
        "SELECT phase FROM research_phase_events WHERE project_id = ? "
        "ORDER BY sequence DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    database.close()
    assert latest_phase == ("pilot",)


def test_generated_dossier_export_and_verify_use_current_sqlite_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic-only double bottom detector validation")
    project = captured["project"]
    assert isinstance(project, dict)
    project_id = str(project["project_id"])

    exported = _invoke("export", project_id)
    path = Path(str(exported["path"]))
    assert path.is_file()
    assert "GENERATED PROJECTION" in path.read_text(encoding="utf-8")
    verified = _invoke("verify", project_id, "--path", str(path))
    assert verified["sha256"] == exported["sha256"]

    path.write_text(path.read_text(encoding="utf-8") + "manual edit\n", encoding="utf-8")
    failed = runner.invoke(
        app,
        ["research", "verify", project_id, "--path", str(path), "--json"],
    )
    assert failed.exit_code != 0
    assert "does not match its deterministic projection" in failed.output


def test_pause_resume_and_cancel_preserve_the_active_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Pause and resume a bounded source-feasibility check")
    project = cast(dict[str, object], captured["project"])
    contract = cast(dict[str, object], captured["contract"])
    project_id = str(project["project_id"])
    contract_id = str(contract["contract_id"])
    ControlStore(tmp_path).transition_research_execution(
        project_id,
        to_state="queued",
        contract_id=contract_id,
        actor="codex",
        reason="Queue the bounded triage checkpoint.",
        next_action="Codex checks source feasibility.",
        responsibility="codex",
    )

    paused = _invoke(
        "pause",
        project_id,
        "--reason",
        "Owner requested a checkpoint.",
        "--checkpoint",
        "triage:source-feasibility",
    )
    assert paused["execution_state"] == "paused"
    assert paused["checkpoint"] == "triage:source-feasibility"
    resumed = _invoke("resume", project_id)
    assert resumed["execution_state"] == "queued"
    cancelled = _invoke(
        "cancel",
        project_id,
        "--reason",
        "Owner ended the queued work without changing the evidence phase.",
    )
    assert cancelled["execution_state"] == "idle"
    assert cancelled["active_contract_id"] == contract_id


def test_owner_can_reject_and_replace_an_exploration_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic-only owner rejection fixture")
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Owner protocol",
        "--locator",
        "owner:protocol",
        "--provider",
        "owner",
        "--access-mode",
        "owner_provided",
    )
    pack = _invoke(
        "sources",
        "freeze",
        project_id,
        "--source-id",
        str(source["source_id"]),
    )
    answers = (
        "--answer",
        "chart_construction=synthetic_only",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    first = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        *answers,
    )
    first_contract = cast(dict[str, object], first["contract"])
    rejected = _invoke(
        "reject",
        "exploration",
        project_id,
        str(first_contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "The owner requires a replacement contract.",
    )
    rejected_case = cast(dict[str, object], rejected["case"])
    assert rejected_case["exploration_review"]["state"] == "rejected"  # type: ignore[index]
    assert rejected_case["responsibility"] == "owner"

    replacement = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        "chart_construction=synthetic_only",
        "--answer",
        "event_availability=neckline_breakout_confirmed",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    replacement_contract = cast(dict[str, object], replacement["contract"])
    assert replacement_contract["contract_id"] != first_contract["contract_id"]
    replacement_case = cast(dict[str, object], replacement["case"])
    assert replacement_case["phase"] == "exploration_review"
    assert replacement_case["exploration_review"]["state"] == "pending"  # type: ignore[index]


def test_rejected_exploration_can_close_and_reopen_one_pre_d2_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "SPY double bottom pre-D2 revision fixture")
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Revision protocol",
        "--locator",
        "owner:revision-protocol",
        "--provider",
        "owner",
        "--access-mode",
        "owner_provided",
    )
    pack = _invoke(
        "sources",
        "freeze",
        project_id,
        "--source-id",
        str(source["source_id"]),
    )
    answers = (
        "--answer",
        "chart_construction=spy_rth_60m_four_hour_window",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        *answers,
    )
    contract = cast(dict[str, object], drafted["contract"])
    _invoke(
        "reject",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "The protocol needs one bounded pre-D2 revision.",
    )
    closed = _invoke(
        "decide",
        project_id,
        "--outcome",
        "INVALID",
        "--disposition",
        "revise",
        "--actor",
        "owner",
        "--reason",
        "Reject this protocol without opening D2, then revise it.",
    )
    assert cast(dict[str, object], closed["case"])["phase"] == "closed"

    revised = _invoke(
        "revise",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        *answers,
        "--actor",
        "owner",
        "--reason",
        "Reopen one immutable child while the original D2 boundary is still sealed.",
    )
    revised_contract = cast(dict[str, object], revised["contract"])
    revised_case = cast(dict[str, object], revised["case"])
    assert revised_contract["parent_contract_id"] == contract["contract_id"]
    assert revised_case["phase"] == "exploration_review"
    assert revised_case["active_contract_id"] == revised_contract["contract_id"]
    assert revised_case["d2_state"] == "sealed"
    assert (
        revised_contract["payload"]["protocol"]["evidence_topology"]["D2"][  # type: ignore[index]
            "relation_to_prior"
        ]
        == "unopened_sealed_reuse"
    )

    replay = _invoke(
        "revise",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        *answers,
        "--actor",
        "owner",
        "--reason",
        "Reopen one immutable child while the original D2 boundary is still sealed.",
    )
    assert (
        cast(dict[str, object], replay["contract"])["contract_id"]
        == revised_contract["contract_id"]
    )


def test_draft_rejects_cross_project_source_pack_before_persisting_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    first = cast(dict[str, object], _invoke("capture", "First synthetic case")["project"])
    second = cast(dict[str, object], _invoke("capture", "Second synthetic case")["project"])
    source = _invoke(
        "sources",
        "add",
        str(first["project_id"]),
        "--title",
        "First project source",
        "--locator",
        "owner:first",
        "--provider",
        "owner",
        "--access-mode",
        "owner_provided",
    )
    pack = _invoke(
        "sources",
        "freeze",
        str(first["project_id"]),
        "--source-id",
        str(source["source_id"]),
    )
    before = _invoke("status", str(second["project_id"]))
    failed = runner.invoke(
        app,
        [
            "research",
            "draft",
            str(second["project_id"]),
            "--source-pack-id",
            str(pack["pack_id"]),
            "--answer",
            "chart_construction=synthetic_only",
            "--answer",
            "event_availability=second_trough_confirmable",
            "--answer",
            "primary_outcome=four_trading_hour_return_25bp",
            "--json",
        ],
    )
    assert failed.exit_code != 0
    assert "must belong" in failed.output
    after = _invoke("status", str(second["project_id"]))
    assert after["active_contract_id"] == before["active_contract_id"]


def test_deep_and_confirmation_runs_remain_gated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "A generic synthetic research idea")
    project = captured["project"]
    assert isinstance(project, dict)
    project_id = str(project["project_id"])

    for phase, gate in (
        ("deep", "deep_research phase"),
        ("confirm", "sealed_confirmation phase"),
    ):
        result = runner.invoke(
            app,
            ["research", "run", phase, project_id, "--json"],
        )
        assert result.exit_code != 0
        assert gate in result.output


def test_postlaunch_v1_project_attaches_to_research_through_public_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    control_dir = tmp_path / "control"
    control_dir.mkdir()
    database = control_dir / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            hypothesis TEXT NOT NULL,
            falsification_criterion TEXT NOT NULL,
            status TEXT NOT NULL,
            current_version_id TEXT,
            current_experiment_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        ) STRICT;
        PRAGMA user_version = 1;
        """
    )
    project_id = "f03802b8-df35-4f19-a90c-0b3437aa587d"
    connection.execute(
        "INSERT INTO projects VALUES (?, ?, ?, ?, 'active', NULL, NULL, ?, ?)",
        (
            project_id,
            "Migrated postlaunch research project",
            "SPY double bottoms may precede positive four-hour returns.",
            "Reject when the registered effect is absent.",
            "2026-08-06T00:00:00.000000Z",
            "2026-08-06T00:00:00.000000Z",
        ),
    )
    connection.commit()
    connection.close()

    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Migrated protocol source",
        "--locator",
        "owner:migrated-source",
        "--provider",
        "owner",
        "--access-mode",
        "owner_provided",
    )
    pack = _invoke(
        "sources",
        "freeze",
        project_id,
        "--source-id",
        str(source["source_id"]),
    )
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        "chart_construction=spy_rth_60m_four_hour_window",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    case = cast(dict[str, object], drafted["case"])
    assert case["phase"] == "exploration_review"
    assert case["responsibility"] == "owner"


@pytest.mark.parametrize(
    ("idea", "chart", "availability"),
    [
        (
            "A generic owner research event may predict returns",
            "spy_rth_60m_four_hour_window",
            "second_trough_confirmable",
        ),
        (
            "SPY double bottom neckline variants may predict returns",
            "spy_rth_60m_four_hour_window",
            "neckline_breakout_confirmed",
        ),
        (
            "SPY double bottom literal extended-hours variant",
            "spy_extended_fixed_4h",
            "second_trough_confirmable",
        ),
    ],
)
def test_gate1_unavailable_contracts_cannot_be_approved_or_attempted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    idea: str,
    chart: str,
    availability: str,
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", idea)
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Unsupported D0 fixture protocol",
        locator="owner:unsupported-d0",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        f"chart_construction={chart}",
        "--answer",
        f"event_availability={availability}",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    contract = cast(dict[str, object], drafted["contract"])
    payload = cast(dict[str, object], contract["payload"])
    case = cast(dict[str, object], drafted["case"])
    assert payload["approval_ready"] is False
    assert cast(dict[str, object], payload["gate1_availability"])["state"] == "UNAVAILABLE"
    assert case["phase"] == "exploration_review"
    assert case["responsibility"] == "owner"
    assert "rejects and closes" in str(case["next_action"])

    failed = runner.invoke(
        app,
        [
            "research",
            "approve",
            "exploration",
            project_id,
            str(contract["contract_id"]),
            "--actor",
            "owner",
            "--reason",
            "Unavailable operators cannot enter the pilot phase.",
            "--json",
        ],
    )
    assert failed.exit_code != 0
    assert "approval_ready=true" in failed.output
    status = _invoke("status", project_id)
    assert status["phase"] == "exploration_review"
    assert status["execution_state"] == "idle"
    assert status["attempt_count"] == 0
    assert not (tmp_path / "runs").exists()


def test_pilot_rejects_implementation_drift_before_reserving_a_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic double bottom implementation drift fixture")
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Synthetic implementation fingerprint protocol",
        locator="owner:synthetic-implementation-drift",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        "chart_construction=spy_rth_60m_four_hour_window",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    contract = cast(dict[str, object], drafted["contract"])
    _invoke(
        "approve",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "Approve the exact implementation fingerprint fixture.",
    )
    current = research_cmds._implementation_hashes()
    monkeypatch.setattr(
        research_cmds,
        "_implementation_hashes",
        lambda: {**current, "code": "0" * 64},
    )

    rejected = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
    assert rejected.exit_code != 0
    assert "implementation fingerprints no longer match" in rejected.output
    case = _invoke("status", project_id)
    assert case["execution_state"] == "idle"
    assert case["attempt_count"] == 0
    database = sqlite3.connect(tmp_path / "control" / "workstation.sqlite3")
    assert database.execute("SELECT COUNT(*) FROM research_launch_reservations").fetchone() == (0,)
    database.close()


@pytest.mark.parametrize("error_type", [DataError, RuntimeError, OSError])
def test_pilot_failures_checkpoint_and_stop_after_two_safe_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic double bottom detector retry fixture")
    project = captured["project"]
    assert isinstance(project, dict)
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Synthetic fixture protocol",
        locator="owner:synthetic-fixture",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        "chart_construction=spy_rth_60m_four_hour_window",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    contract = drafted["contract"]
    assert isinstance(contract, dict)
    _invoke(
        "approve",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "Approve the bounded retry fixture.",
    )

    def fail_pilot(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise error_type("planted fixture calibration failed")

    monkeypatch.setattr(research_cmds, "run_synthetic_pilot", fail_pilot)
    for attempt_number in range(1, 4):
        failed = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
        assert failed.exit_code != 0
        assert "failed and was checkpointed" in failed.output
        case = _invoke("status", project_id)
        assert case["attempt_count"] == attempt_number
        assert case["terminal_attempt_count"] == attempt_number
        assert case["unfinalized_launch_count"] == 0
        assert case["elapsed_budget"] == {
            "source_requests": 0,
            "variants": 3 * attempt_number,
            "wall_seconds": attempt_number,
        }
        assert case["checkpoint"] == f"d0:failed:{attempt_number}"
        assert case["execution_state"] == ("blocked" if attempt_number == 3 else "failed")
        assert case["phase"] == ("research_decision" if attempt_number == 3 else "pilot")
        if attempt_number < 3:
            resumed = _invoke("resume", project_id)
            assert resumed["execution_state"] == "queued"

    exhausted = runner.invoke(app, ["research", "resume", project_id, "--json"])
    assert exhausted.exit_code != 0
    assert "terminal research decision state" in exhausted.output
    terminal = _invoke("status", project_id)
    assert terminal["execution_state"] == "blocked"
    assert terminal["d2_state"] == "sealed"

    closed = _invoke(
        "decide",
        project_id,
        "--outcome",
        "INVALID",
        "--disposition",
        "park",
        "--actor",
        "owner",
        "--reason",
        "The synthetic evaluator exhausted its safe retry budget.",
    )
    closed_case = closed["case"]
    assert isinstance(closed_case, dict)
    assert closed_case["phase"] == "closed"
    assert closed_case["execution_state"] == "idle"
    assert closed_case["d2_state"] == "sealed"
    packet = _invoke("report", project_id)
    assert packet["report_schema"] == "ResearchGatePacketV1"
    assert packet["terminal"] is True
    assert packet["scientific_outcome"] == "INVALID"
    assert packet["recommended_disposition"] == "park"
    layers = packet["layers"]
    assert isinstance(layers, dict)
    conclusion = layers["conclusion_90_seconds"]
    assert isinstance(conclusion, dict)
    assert conclusion["evidence_basis"] == "NO_TYPED_NON_SYNTHETIC_EVIDENCE"


def test_store_failure_after_successful_pilot_never_fabricates_a_failed_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A completed pilot whose attempt write fails must not be recorded as a pilot failure."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic double bottom attempt-recording fixture")
    project = captured["project"]
    assert isinstance(project, dict)
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Synthetic fixture protocol",
        locator="owner:synthetic-fixture",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        "chart_construction=spy_rth_60m_four_hour_window",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    contract = drafted["contract"]
    assert isinstance(contract, dict)
    _invoke(
        "approve",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "Approve the attempt-recording fixture.",
    )

    original_record = ControlStore.record_research_attempt

    def flaky_record(
        self: ControlStore, project_id: str, contract_id: str, **kwargs: object
    ) -> dict[str, object]:
        if kwargs.get("status") == "completed":
            raise DataError("injected: attempt store write failed after the pilot succeeded")
        return original_record(self, project_id, contract_id, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(ControlStore, "record_research_attempt", flaky_record)
    result = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
    assert result.exit_code != 0
    assert "completed and published immutable run" in result.output
    monkeypatch.setattr(ControlStore, "record_research_attempt", original_record)

    # The immutable run was genuinely published.
    run_dirs = [path for path in (tmp_path / "runs").iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    manifest = json.loads((run_dirs[0] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "research_pilot"

    # The consumed launch stays counted (crash-consumes rule), but no attempt record of any
    # status was fabricated and the reservation stays visibly unfinalized.
    case = _invoke("status", project_id)
    assert case["attempt_count"] == 1
    assert case["terminal_attempt_count"] == 0
    assert case["unfinalized_launch_count"] == 1
    assert case["execution_state"] == "running"

    # The documented recovery path works: resume, re-run, and the identical immutable run
    # republishes idempotently while the interrupted reservation stays consumed.
    resumed = _invoke("resume", project_id, "--acknowledge-orphaned-process")
    assert resumed["execution_state"] == "queued"
    recovered = _invoke("run", "pilot", project_id)
    recovered_manifest = recovered["manifest"]
    recovered_case = recovered["case"]
    assert isinstance(recovered_manifest, dict) and isinstance(recovered_case, dict)
    assert recovered_manifest["run_id"] == manifest["run_id"]
    assert recovered_case["attempt_count"] == 2
    assert recovered_case["terminal_attempt_count"] == 1
    assert recovered_case["phase"] == "deep_research"
    assert recovered_case["remaining_launches"] == 1


def test_hard_crashes_consume_launch_slots_budget_and_deny_a_fourth_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic double bottom hard-crash reservation fixture")
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Synthetic hard-crash protocol",
        locator="owner:synthetic-hard-crash",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        "chart_construction=spy_rth_60m_four_hour_window",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    contract = cast(dict[str, object], drafted["contract"])
    _invoke(
        "approve",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "Approve the crash durability fixture.",
    )

    def hard_crash(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise KeyboardInterrupt

    monkeypatch.setattr(research_cmds, "run_synthetic_pilot", hard_crash)
    for launch_number in range(1, 4):
        crashed = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
        assert crashed.exit_code != 0
        case = _invoke("status", project_id)
        assert case["execution_state"] == "running"
        assert case["attempt_count"] == launch_number
        assert case["terminal_attempt_count"] == 0
        assert case["unfinalized_launch_count"] == launch_number
        assert case["latest_launch_number"] == launch_number
        assert case["elapsed_budget"] == {
            "source_requests": 0,
            "variants": 3 * launch_number,
            "wall_seconds": launch_number,
        }
        if launch_number < 3:
            resumed = _invoke("resume", project_id, "--acknowledge-orphaned-process")
            assert resumed["execution_state"] == "queued"

    denied = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
    assert denied.exit_code != 0
    assert "revision or disposition is required" in denied.output
    denied_resume = runner.invoke(
        app,
        [
            "research",
            "resume",
            project_id,
            "--acknowledge-orphaned-process",
            "--json",
        ],
    )
    assert denied_resume.exit_code != 0
    assert "retry limit is exhausted" in denied_resume.output

    database = sqlite3.connect(tmp_path / "control" / "workstation.sqlite3")
    assert database.execute("SELECT COUNT(*) FROM research_launch_reservations").fetchone() == (3,)
    assert database.execute("SELECT COUNT(*) FROM research_launch_attempt_links").fetchone() == (0,)
    database.close()

    _invoke("cancel", project_id, "--reason", "Stop after the exhausted crash budget.")
    _invoke(
        "decide",
        project_id,
        "--outcome",
        "INVALID",
        "--disposition",
        "park",
        "--actor",
        "owner",
        "--reason",
        "Three hard crashes exhausted the durable launch budget.",
    )
    packet = _invoke("report", project_id)
    layers = cast(dict[str, object], packet["layers"])
    appendix = cast(dict[str, object], layers["technical_appendix"])
    assert len(cast(list[object], appendix["launch_reservation_ledger"])) == 3
    assert appendix["launch_attempt_link_ledger"] == []
    budget_ledger = cast(list[dict[str, object]], appendix["budget_ledger"])
    assert budget_ledger[0]["used"] == {
        "source_requests": 0,
        "variants": 9,
        "wall_seconds": 3,
    }


def test_completed_pilot_is_adopted_after_crash_without_duplicate_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic double bottom crash-recovery fixture")
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Synthetic recovery protocol",
        locator="owner:synthetic-recovery",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        "chart_construction=spy_rth_60m_four_hour_window",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    contract = cast(dict[str, object], drafted["contract"])
    _invoke(
        "approve",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "Approve the deterministic crash-recovery fixture.",
    )

    original_transition = ControlStore.transition_research_execution
    crashed = False

    def crash_after_attempt(
        self: ControlStore, *args: object, **kwargs: object
    ) -> dict[str, object]:
        nonlocal crashed
        if kwargs.get("to_state") == "idle" and not crashed:
            crashed = True
            raise DataError("simulated process loss after attempt insertion")
        return original_transition(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(ControlStore, "transition_research_execution", crash_after_attempt)
    interrupted = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
    assert interrupted.exit_code != 0
    assert "simulated process loss" in interrupted.output
    monkeypatch.setattr(ControlStore, "transition_research_execution", original_transition)

    stranded = _invoke("status", project_id)
    assert stranded["execution_state"] == "running"
    assert stranded["attempt_count"] == 1
    run_id = stranded["latest_run_id"]
    unsafe_resume = runner.invoke(app, ["research", "resume", project_id, "--json"])
    assert unsafe_resume.exit_code != 0
    assert _invoke("status", project_id)["execution_state"] == "running"
    resumed = _invoke("resume", project_id, "--acknowledge-orphaned-process")
    assert resumed["execution_state"] == "queued"

    recovered = _invoke("run", "pilot", project_id)
    recovered_case = cast(dict[str, object], recovered["case"])
    assert recovered_case["phase"] == "deep_research"
    assert recovered_case["responsibility"] == "codex"
    assert recovered_case["next_action"] == (
        "Launch `alpha research run deep` to execute the frozen analysis plan on D1."
    )
    assert recovered_case["attempt_count"] == 1
    assert recovered_case["latest_run_id"] == run_id


def test_legacy_compare_still_ranks_engine_strategies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=400)

    payload = _invoke("compare", "SPY")

    assert payload["symbol"] == "SPY"
    assert payload["n_bars"] == 400
    ranked = payload["ranked"]
    assert isinstance(ranked, list)
    assert len(ranked) == 4
    returns = [row["total_return"] for row in ranked if row["total_return"] is not None]
    assert returns == sorted(returns, reverse=True)


def test_legacy_compare_subset_and_missing_data_behavior_remain_compatible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=400)
    subset = runner.invoke(
        app,
        ["research", "compare", "SPY", "--strategies", "ma_crossover"],
    )
    assert subset.exit_code == 0
    assert "ma_crossover" in subset.stdout

    missing = runner.invoke(app, ["research", "compare", "NOPE", "--json"])
    assert missing.exit_code != 0


def test_research_list_projects_bounded_backlog_rows_newest_activity_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    first = _invoke("capture", "Gold rallies after triple witching expiries", "--name", "Gold")
    second = _invoke("capture", "SPY drifts upward into month-end rebalancing", "--name", "SPY")
    first_case = cast(dict[str, object], first["case"])
    second_case = cast(dict[str, object], second["case"])
    first_id = str(cast(dict[str, object], first["project"])["project_id"])
    second_id = str(cast(dict[str, object], second["project"])["project_id"])
    assert first_case["phase"] == "triage" and second_case["phase"] == "triage"

    page = _invoke("list")
    assert set(page) == {"items", "limit", "offset", "has_more"}
    assert page["limit"] == 50 and page["offset"] == 0 and page["has_more"] is False
    items = page["items"]
    assert isinstance(items, list) and len(items) == 2
    row = cast(dict[str, object], items[0])
    assert set(row) == {
        "case_id",
        "title",
        "original_idea",
        "phase",
        "execution_state",
        "outcome",
        "disposition",
        "next_action",
        "responsibility",
        "latest_finding",
        "blocker",
        "recovery_action",
        "completed_milestones",
        "total_milestones",
        "owner_pinned",
        "priority",
        "budget",
        "updated_at",
    }
    # Newest research activity first: the second capture leads.
    assert [cast(dict[str, object], item)["case_id"] for item in items] == [second_id, first_id]
    assert row["title"] == "SPY"
    assert row["original_idea"] == "SPY drifts upward into month-end rebalancing"
    assert row["phase"] == "triage"
    assert row["execution_state"] == "idle"
    assert row["outcome"] is None and row["disposition"] is None
    assert row["responsibility"] == "owner"
    assert (
        row["recovery_action"]
        == "Answer the single bounded question batch; Codex handles technical defaults."
    )
    assert row["completed_milestones"] == 2  # captured + triage phase events
    assert row["total_milestones"] == 9  # the nine research phases
    # The advisory priority rubric is not yet scored; the projection says so honestly.
    assert row["owner_pinned"] is False
    assert row["priority"] == {
        "falsifiability": 0,
        "data_readiness": 0,
        "novelty": 0,
        "information_gain_per_cost": 0,
    }
    budget = cast(dict[str, object], row["budget"])
    assert set(budget) == {"approved_units", "consumed_units", "unit"}
    assert budget["unit"] == "minutes"
    assert isinstance(row["updated_at"], str) and row["updated_at"]

    bounded = _invoke("list", "--limit", "1")
    assert bounded["has_more"] is True
    assert len(cast(list[object], bounded["items"])) == 1
    offset_page = _invoke("list", "--limit", "1", "--offset", "1")
    assert [
        cast(dict[str, object], item)["case_id"]
        for item in cast(list[object], offset_page["items"])
    ] == [first_id]

    rejected = runner.invoke(app, ["research", "list", "--limit", "0", "--json"])
    assert rejected.exit_code != 0


def test_context_packets_notes_protocols_and_brief_cli_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "SPY drifts upward into month-end rebalancing")
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])

    protocols = _invoke("protocols", "list")
    entries = cast(list[dict[str, object]], protocols["protocols"])
    assert len(entries) == 13
    assert entries[0]["id"] == "new-idea-intake"
    shown = _invoke("protocols", "show", "new-idea-intake")
    assert isinstance(shown["content"], str) and "no trading rules" in str(shown["purpose"])

    built = _invoke(
        "context",
        "build",
        project_id,
        "--kind",
        "research_case",
        "--protocol",
        "new-idea-intake",
    )
    packet_id = str(built["packet_id"])
    assert packet_id.startswith("cp_")
    assert built["protocol_id"] == "new-idea-intake"
    assert str(built["protocol_content_hash"]) == str(entries[0]["sha256"])
    payload = cast(dict[str, object], built["payload"])
    assert payload["packet_kind"] == "research_case"

    listed = _invoke("context", "list", project_id)
    assert [row["packet_id"] for row in cast(list[dict[str, object]], listed["items"])] == [
        packet_id
    ]
    shown_packet = _invoke("context", "show", packet_id)
    assert shown_packet["payload"] == payload

    note = _invoke(
        "note",
        "add",
        project_id,
        "--kind",
        "critique",
        "--body",
        "The volatility-regime confounder is not yet matched.",
        "--author",
        "codex",
        "--author-kind",
        "agent",
        "--packet",
        packet_id,
    )
    assert str(note["note_id"]).startswith("rn_")
    notes = _invoke("note", "list", project_id)
    assert [row["note_id"] for row in cast(list[dict[str, object]], notes["items"])] == [
        note["note_id"]
    ]

    brief = _invoke("brief", project_id)
    assert brief["brief_schema"] == "ResearchBriefV1"
    assert str(brief["packet_id"]).startswith("cp_")
    changes = cast(dict[str, object], brief["changes"])
    assert set(changes) == {"phase_events", "execution_events", "attempts", "decisions"}


def test_new_research_commands_report_human_fallbacks_and_fail_loud_on_unknown_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Gold rallies after triple witching expiries")
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])

    listing = runner.invoke(app, ["research", "list"])
    assert listing.exit_code == 0 and project_id in listing.output
    hub = runner.invoke(app, ["research", "evidence-hub", project_id])
    assert hub.exit_code == 0 and "evidence hub sections" in hub.output
    empty_context = runner.invoke(app, ["research", "context", "list", project_id])
    assert empty_context.exit_code == 0 and "no packets recorded" in empty_context.output
    empty_notes = runner.invoke(app, ["research", "note", "list", project_id])
    assert empty_notes.exit_code == 0 and "no notes recorded" in empty_notes.output
    protocols_text = runner.invoke(app, ["research", "protocols", "list"])
    assert protocols_text.exit_code == 0 and "new-idea-intake" in protocols_text.output
    protocol_text = runner.invoke(app, ["research", "protocols", "show", "research-critic"])
    assert protocol_text.exit_code == 0 and "Research Critic" in protocol_text.output
    built = runner.invoke(app, ["research", "context", "build", project_id, "--kind", "validation"])
    assert built.exit_code == 0 and "recorded packet cp_" in built.output
    noted = runner.invoke(
        app,
        [
            "research",
            "note",
            "add",
            project_id,
            "--kind",
            "synthesis",
            "--body",
            "Established: nothing yet.",
        ],
    )
    assert noted.exit_code == 0 and "recorded note rn_" in noted.output
    briefed = runner.invoke(app, ["research", "brief", project_id])
    assert briefed.exit_code == 0 and "brief recorded as cp_" in briefed.output
    shown = runner.invoke(app, ["research", "context", "list", project_id])
    assert shown.exit_code == 0 and "validation" in shown.output

    unknown = "00000000-0000-4000-8000-000000000000"
    for args in (
        ["research", "evidence-hub", unknown, "--json"],
        ["research", "context", "build", unknown, "--kind", "research_case", "--json"],
        ["research", "context", "show", "cp_" + "9" * 64, "--json"],
        ["research", "context", "list", unknown, "--json"],
        ["research", "note", "add", unknown, "--kind", "critique", "--body", "x", "--json"],
        ["research", "note", "list", unknown, "--json"],
        ["research", "protocols", "show", "unknown-protocol", "--json"],
        ["research", "brief", unknown, "--json"],
        ["research", "status", unknown, "--json"],
    ):
        rejected = runner.invoke(app, args)
        assert rejected.exit_code != 0, args


def _pull_and_snapshot_aapl(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.integration.test_data_cli import _FakeAdapter

    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"fake": _FakeAdapter})
    pull = runner.invoke(
        app,
        [
            "data",
            "pull",
            "AAPL",
            "--source",
            "fake",
            "--start",
            "2020-08-28",
            "--end",
            "2020-09-02",
        ],
    )
    assert pull.exit_code == 0, pull.output
    snapped = runner.invoke(app, ["data", "snapshot", "snap1", "AAPL", "--source", "fake"])
    assert snapped.exit_code == 0, snapped.output


def test_research_dataset_register_list_and_audit_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _pull_and_snapshot_aapl(monkeypatch)
    captured = _invoke("capture", "AAPL drifts after gap days")
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])

    registered = _invoke(
        "data",
        "register",
        "AAPL",
        "--kind",
        "snapshot",
        "--snapshot-id",
        "snap1",
        "--start",
        "2020-08-28",
        "--end",
        "2020-09-02",
    )
    ref_id = str(registered["ref_id"])
    assert ref_id.startswith("rd_")
    assert registered["research_only"] is True
    assert registered["provider"] == "fake"
    origin = cast(dict[str, object], registered["origin"])
    assert origin["snapshot_id"] == "snap1"
    assert len(str(origin["manifest_sha256"])) == 64

    slice_registered = _invoke(
        "data",
        "register",
        "AAPL",
        "--kind",
        "store-slice",
        "--start",
        "2020-08-28",
        "--end",
        "2020-09-02",
    )
    assert str(slice_registered["ref_id"]).startswith("rd_")
    assert "provenance_sha256" in cast(dict[str, object], slice_registered["origin"])

    listed = _invoke("data", "list")
    assert len(cast(list[object], listed["items"])) == 2
    filtered = _invoke("data", "list", "--symbol", "AAPL")
    assert len(cast(list[object], filtered["items"])) == 2

    audited = _invoke("data", "audit", project_id, ref_id)
    manifest = cast(dict[str, object], audited["manifest"])
    assert manifest["command"] == "research_data_audit"
    assert manifest["watermark"] == "EXPLORATORY"
    assert manifest["real_market_evidence"] is False
    assert manifest["eligible_for_holdout_or_execution"] is False
    assert manifest["research_data_audit_method_version"] == "ar1-conservative-cap-v2"
    audit = cast(dict[str, object], audited["audit"])
    summary = cast(dict[str, object], audit["summary"])
    assert summary["audit_schema"] == "ResearchDataAuditV1"
    assert summary["method_version"] == "ar1-conservative-cap-v2"
    # A four-bar dataset is honestly blocking: far below any usable sample.
    assert cast(int, summary["blocking_count"]) >= 1
    assert audit["project_id"] == project_id

    enriched = _invoke("data", "list")
    rows = cast(list[dict[str, object]], enriched["items"])
    audited_row = next(row for row in rows if row["ref_id"] == ref_id)
    assert audited_row["latest_audit"] is not None


def test_research_dataset_registration_fails_closed_without_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=50)  # bars without provenance

    unknown_snapshot = runner.invoke(
        app,
        [
            "research",
            "data",
            "register",
            "SPY",
            "--kind",
            "snapshot",
            "--snapshot-id",
            "missing",
            "--start",
            "2020-01-01",
            "--end",
            "2020-06-01",
            "--json",
        ],
    )
    assert unknown_snapshot.exit_code != 0

    no_provenance = runner.invoke(
        app,
        [
            "research",
            "data",
            "register",
            "SPY",
            "--kind",
            "store-slice",
            "--start",
            "2020-01-01",
            "--end",
            "2020-06-01",
            "--json",
        ],
    )
    assert no_provenance.exit_code != 0
    assert "provenance" in no_provenance.output.casefold()


def test_quantpad_receipt_registration_and_corrupt_snapshot_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps({"receipt_id": "a" * 32, "response_sha256": "b" * 64}), encoding="utf-8"
    )
    registered = _invoke(
        "data",
        "register",
        "AAPL",
        "--kind",
        "quantpad",
        "--receipt",
        str(receipt_path),
        "--start",
        "2026-01-01",
        "--end",
        "2026-02-01",
        "--bar-minutes",
        "60",
    )
    assert registered["dataset_kind"] == "quantpad_receipt"
    assert registered["provider"] == "quantpad"
    assert registered["bar_duration_minutes"] == 60

    missing_receipt = runner.invoke(
        app,
        [
            "research",
            "data",
            "register",
            "AAPL",
            "--kind",
            "quantpad",
            "--start",
            "2026-01-01",
            "--end",
            "2026-02-01",
            "--json",
        ],
    )
    assert missing_receipt.exit_code != 0
    malformed = tmp_path / "bad-receipt.json"
    malformed.write_text("[]", encoding="utf-8")
    bad_receipt = runner.invoke(
        app,
        [
            "research",
            "data",
            "register",
            "AAPL",
            "--kind",
            "quantpad",
            "--receipt",
            str(malformed),
            "--start",
            "2026-01-01",
            "--end",
            "2026-02-01",
            "--json",
        ],
    )
    assert bad_receipt.exit_code != 0

    corrupt = tmp_path / "snapshots" / "broken"
    corrupt.mkdir(parents=True)
    (corrupt / "manifest.json").write_text("{not json", encoding="utf-8")
    listing = runner.invoke(app, ["data", "snapshots", "--json"])
    assert listing.exit_code != 0
    unknown_audit = runner.invoke(
        app,
        [
            "research",
            "data",
            "audit",
            "00000000-0000-4000-8000-000000000000",
            "rd_" + "0" * 64,
            "--json",
        ],
    )
    assert unknown_audit.exit_code != 0


def _register_daily_dataset(tmp_path: Path, symbol: str, lows: list[float] | None = None) -> str:
    """Snapshot planted Tiingo-shaped daily bars and register them via the CLI."""
    from datetime import UTC, datetime, timedelta

    from alpha_data.snapshot import create_snapshot
    from alpha_data.store import ParquetStore
    from tests.unit.test_research_gate4_lane import _daily_frame, _daily_lows

    if lows is None:
        lows = _daily_lows()
    store = ParquetStore(tmp_path / "store")
    store.write_bars(symbol, _daily_frame(lows))
    snapshot_id = f"gate4-{symbol.lower()}"
    create_snapshot(
        store,
        tmp_path / "snapshots",
        snapshot_id,
        [symbol],
        source="tiingo",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    end_day = datetime(2020, 1, 6, tzinfo=UTC) + timedelta(days=len(lows) - 1)
    registered = _invoke(
        "data",
        "register",
        symbol,
        "--kind",
        "snapshot",
        "--snapshot-id",
        snapshot_id,
        "--start",
        "2020-01-06",
        "--end",
        end_day.date().isoformat(),
        "--bar-minutes",
        "1440",
    )
    return str(registered["ref_id"])


def _daily_draft_args(project_id: str, pack_id: str) -> list[str]:
    return [
        "draft",
        project_id,
        "--source-pack-id",
        pack_id,
        "--answer",
        "chart_construction=tiingo_daily_fallback",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=next_regular_session_return_50bp",
    ]


def test_empirical_daily_draft_binds_the_registered_dataset_and_reaches_deep_research(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R6a (ADR-0026): the Gate-4 daily lane freezes an empirical exploration boundary."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    ref_id = _register_daily_dataset(tmp_path, "SPY")
    captured = _invoke("capture", "SPY bounces after double bottoms on the daily chart")
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])
    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Technical trading revisited",
        "--locator",
        "doi:10.0000/example",
        "--provider",
        "crossref",
        "--access-mode",
        "metadata_only",
    )
    pack = _invoke("sources", "freeze", project_id, "--source-id", str(source["source_id"]))
    drafted = _invoke(
        *_daily_draft_args(project_id, str(pack["pack_id"])),
        "--dataset",
        ref_id,
    )
    payload = cast(dict[str, object], cast(dict[str, object], drafted["contract"])["payload"])
    assert payload["approval_ready"] is True
    assert payload["blocking_questions"] == []
    hashes = cast(dict[str, object], payload["hashes"])
    data_hash = hashes["data"]
    assert isinstance(data_hash, str) and len(data_hash) == 64
    protocol = cast(dict[str, object], payload["protocol"])
    assert protocol["boundary_authority"] == {
        "kind": "empirical_dataset",
        "real_market_evidence": True,
        "empirical_confirmation_authorized": True,
    }
    empirical = cast(dict[str, object], protocol["empirical_dataset"])
    assert empirical["ref_id"] == ref_id
    assert empirical["content_sha256"] == data_hash
    assert empirical["instrument"] == "SPY"
    assert empirical["provider"] == "tiingo"
    assert cast(int, empirical["session_group_count"]) >= 100
    topology = cast(dict[str, object], protocol["evidence_topology"])
    d2 = cast(dict[str, object], topology["D2"])
    assert d2["share"] == 0.2
    boundary_hash = d2["boundary_hash"]
    assert isinstance(boundary_hash, str) and len(boundary_hash) == 64
    operator = cast(dict[str, object], protocol["d0_operator"])
    fixture = cast(dict[str, object], operator["fixture"])
    assert fixture["fixture_id"] == "spy_session_daily_double_bottom_v1"

    frozen_id = str(cast(dict[str, object], drafted["contract"])["contract_id"])
    _invoke(
        "approve",
        "exploration",
        project_id,
        frozen_id,
        "--actor",
        "owner",
        "--reason",
        "The registered daily dataset and bounded plan suit empirical D1 exploration.",
    )
    pilot = _invoke("run", "pilot", project_id)
    pilot_case = cast(dict[str, object], pilot["case"])
    assert pilot_case["phase"] == "deep_research"
    manifest = cast(dict[str, object], pilot["manifest"])
    assert manifest["watermark"] == "EXPLORATORY"
    assert manifest["real_market_evidence"] is False  # the D0 pilot itself stays synthetic

    # R6b (ADR-0026): the governed deep run executes on the registered daily dataset.
    deep = _invoke("run", "deep", project_id)
    deep_manifest = cast(dict[str, object], deep["manifest"])
    assert deep_manifest["evidence_zone"] == "D1"
    assert deep_manifest["real_market_evidence"] is True
    assert deep_manifest["watermark"] == "EXPLORATORY"
    assert deep_manifest["eligible_for_holdout_or_execution"] is False
    assert deep_manifest["dataset_hash"] == data_hash  # the approval-frozen dataset bytes
    deep_attempt = cast(dict[str, object], deep["attempt"])
    assert deep_attempt["status"] == "completed"
    assert deep_attempt["kind"] == "d1-deep-research"
    deep_case = cast(dict[str, object], deep["case"])
    assert deep_case["phase"] == "deep_research"


def _varied_daily_lows(blocks: int = 50) -> list[float]:
    """Planted daily motifs with heterogeneous post-confirmation rises (non-degenerate CI)."""
    from tests.unit.test_research_gate4_lane import _MOTIF

    lows: list[float] = []
    for block in range(blocks):
        lows.extend(_MOTIF)
        level = _MOTIF[-1]
        rise = 8.0 + 0.5 * (block % 5)
        for day in range(1):
            level = level + rise if day == 0 else level
            lows.append(level)
        lows.extend([100.0] * (block % 3))
    return lows


def _approved_empirical_daily_project(
    tmp_path: Path, lows: list[float] | None = None
) -> tuple[str, str]:
    """Register the daily SPY dataset and drive one empirical case into deep_research."""
    ref_id = _register_daily_dataset(tmp_path, "SPY", lows)
    captured = _invoke("capture", "SPY bounces after double bottoms on the daily chart")
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])
    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Technical trading revisited",
        "--locator",
        "doi:10.0000/example",
        "--provider",
        "crossref",
        "--access-mode",
        "metadata_only",
    )
    pack = _invoke("sources", "freeze", project_id, "--source-id", str(source["source_id"]))
    drafted = _invoke(
        *_daily_draft_args(project_id, str(pack["pack_id"])),
        "--dataset",
        ref_id,
    )
    contract = cast(dict[str, object], drafted["contract"])
    payload = cast(dict[str, object], contract["payload"])
    data_hash = str(cast(dict[str, object], payload["hashes"])["data"])
    _invoke(
        "approve",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "The registered daily dataset and bounded plan suit empirical D1 exploration.",
    )
    pilot = _invoke("run", "pilot", project_id)
    assert cast(dict[str, object], pilot["case"])["phase"] == "deep_research"
    return project_id, data_hash


def test_confirmation_drafting_freezes_the_one_shot_family_from_d1_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R6c (ADR-0026): the confirmation contract is frozen mechanically from admitted D1."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id, data_hash = _approved_empirical_daily_project(tmp_path, lows=_varied_daily_lows())
    _invoke("run", "deep", project_id)

    drafted = _invoke("draft-confirmation", project_id)
    contract = cast(dict[str, object], drafted["contract"])
    payload = cast(dict[str, object], contract["payload"])
    assert contract["scope"] == "confirmation"
    parent_id = str(contract["parent_contract_id"])
    assert parent_id.startswith("rc_")
    confirmation = cast(dict[str, object], payload["confirmation"])
    assert confirmation["variant_count"] == 1
    assert confirmation["multiplicity_count"] == 1
    assert confirmation["familywise_alpha"] == 0.05
    assert confirmation["target_power"] == 0.90
    power_report = cast(dict[str, object], confirmation["power_report"])
    assert 0.90 <= cast(float, power_report["achieved_power"]) <= 1.0
    assert power_report["seed"] == 7
    assert str(power_report["source_run_id"])
    fingerprints = cast(dict[str, object], confirmation["fingerprints"])
    assert isinstance(fingerprints.get("data"), str)
    hashes = cast(dict[str, object], payload["hashes"])
    assert hashes["data"] == data_hash
    plan = cast(dict[str, object], payload["analysis_plan"])
    families = cast(list[dict[str, object]], plan["families"])
    assert [entry["family"] for entry in families] == ["event_study"]
    assert families[0]["multiplicity"] == "primary"
    case = cast(dict[str, object], drafted["case"])
    assert case["phase"] == "confirmation_review"
    assert case["d2_state"] == "sealed"

    store = ControlStore(tmp_path)
    parent = store.get_research_contract(parent_id)
    parent_payload = cast(dict[str, object], parent["payload"])

    def _boundary_hash(value: dict[str, object]) -> str:
        protocol = cast(dict[str, object], value["protocol"])
        topology = cast(dict[str, object], protocol["evidence_topology"])
        return str(cast(dict[str, object], topology["D2"])["boundary_hash"])

    assert _boundary_hash(payload) == _boundary_hash(parent_payload)


def _confirmation_ready_project(tmp_path: Path) -> tuple[str, str, str]:
    """Drive one empirical case through D1 and freeze its confirmation contract."""
    project_id, data_hash = _approved_empirical_daily_project(tmp_path, lows=_varied_daily_lows())
    _invoke("run", "deep", project_id)
    drafted = _invoke("draft-confirmation", project_id)
    contract_id = str(cast(dict[str, object], drafted["contract"])["contract_id"])
    return project_id, contract_id, data_hash


def test_one_shot_confirmation_consumes_d2_and_routes_to_owner_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R6d (ADR-0026): approve -> sealed_confirmation -> one governed one-shot D2 run."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id, contract_id, data_hash = _confirmation_ready_project(tmp_path)
    approved = _approve_confirmation(project_id, contract_id)
    approved_case = cast(dict[str, object], approved["case"])
    assert approved_case["phase"] == "sealed_confirmation"
    assert approved_case["d2_state"] == "authorized"

    confirm = _invoke("run", "confirm", project_id)
    manifest = cast(dict[str, object], confirm["manifest"])
    assert manifest["command"] == "research_confirm"
    assert manifest["evidence_zone"] == "D2"
    assert manifest["watermark"] == "REGISTERED CONFIRMATORY"
    assert manifest["real_market_evidence"] is True
    assert manifest["eligible_for_holdout_or_execution"] is False
    assert manifest["dataset_hash"] == data_hash
    attempt = cast(dict[str, object], confirm["attempt"])
    assert attempt["kind"] == "sealed-confirmation"
    assert attempt["status"] == "completed"
    case = cast(dict[str, object], confirm["case"])
    assert case["phase"] == "research_decision"
    assert case["d2_state"] == "consumed"
    assert case["execution_state"] == "idle"

    run_id = str(manifest["run_id"])
    evidence = json.loads(
        (tmp_path / "runs" / run_id / "research_gate_evidence.json").read_text(encoding="utf-8")
    )
    assert evidence["confirmation_classification"] == "SUPPORTED"

    # The sealed share is spent: a second invocation recovers the same immutable run and
    # records no new attempt, execution, or data read.
    second = _invoke("run", "confirm", project_id)
    assert cast(dict[str, object], second["manifest"])["run_id"] == run_id
    assert cast(dict[str, object], second["attempt"])["attempt_id"] == attempt["attempt_id"]

    # The owner decision is bound to the mechanical classification.
    contradicted = runner.invoke(
        app,
        [
            "research",
            "decide",
            project_id,
            "--outcome",
            "CONTRADICTED",
            "--disposition",
            "reject",
            "--actor",
            "owner",
            "--reason",
            "An owner claim against the mechanical classification must fail.",
            "--json",
        ],
    )
    assert contradicted.exit_code != 0
    assert "mechanical D2 classification" in contradicted.output
    decided = _invoke(
        "decide",
        project_id,
        "--outcome",
        "SUPPORTED",
        "--disposition",
        "advance_to_strategy",
        "--actor",
        "owner",
        "--reason",
        "The mechanically confirmed effect advances to strategy work.",
    )
    assert cast(dict[str, object], decided["decision"])["outcome"] == "SUPPORTED"


def _approve_confirmation(project_id: str, contract_id: str) -> dict[str, object]:
    return _invoke(
        "approve",
        "confirmation",
        project_id,
        contract_id,
        "--actor",
        "owner",
        "--reason",
        "Confirm the exact one-shot family.",
    )


def test_confirmation_contaminates_d2_on_sealed_dataset_integrity_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pre-flight integrity failure spends the sealed share: INVALID is the only exit."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id, contract_id, _ = _confirmation_ready_project(tmp_path)
    _approve_confirmation(project_id, contract_id)
    parquets = sorted((tmp_path / "snapshots" / "gate4-spy").rglob("*.parquet"))
    assert parquets
    for parquet in parquets:
        parquet.write_bytes(parquet.read_bytes() + b"tampered")

    blocked = runner.invoke(app, ["research", "run", "confirm", project_id, "--json"])
    assert blocked.exit_code != 0
    assert "contaminated" in blocked.output
    case = _invoke("status", project_id)
    assert case["d2_state"] == "contaminated"
    assert case["phase"] == "research_decision"

    # The spent share can never be re-run, and no attempt or run was recorded.
    rerun = runner.invoke(app, ["research", "run", "confirm", project_id, "--json"])
    assert rerun.exit_code != 0
    assert "contaminated" in rerun.output
    assert case["attempt_count"] == 2  # D0 pilot + D1 deep only

    # SUPPORTED and advance are unreachable from a contaminated share.
    advance = runner.invoke(
        app,
        [
            "research",
            "decide",
            project_id,
            "--outcome",
            "SUPPORTED",
            "--disposition",
            "advance_to_strategy",
            "--actor",
            "owner",
            "--reason",
            "A contaminated share cannot support the claim.",
            "--json",
        ],
    )
    assert advance.exit_code != 0
    assert "INVALID" in advance.output
    closed = _invoke(
        "decide",
        project_id,
        "--outcome",
        "INVALID",
        "--disposition",
        "park",
        "--actor",
        "owner",
        "--reason",
        "The sealed confirmation dataset failed integrity before the one-shot read.",
    )
    closed_case = cast(dict[str, object], closed["case"])
    assert closed_case["phase"] == "closed"
    assert closed_case["d2_state"] == "contaminated"


def test_confirmation_crash_checkpoints_and_recovers_with_exact_reexecution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A runtime crash checkpoints honestly and never contaminates the sealed share."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id, contract_id, data_hash = _confirmation_ready_project(tmp_path)
    _approve_confirmation(project_id, contract_id)

    from alpha_cli.research_d2 import run_confirmation as real_run_confirmation

    def crash(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise DataError("simulated executor crash")

    monkeypatch.setattr(research_cmds, "run_confirmation", crash)
    failed = runner.invoke(app, ["research", "run", "confirm", project_id, "--json"])
    assert failed.exit_code != 0
    assert "checkpointed" in failed.output
    case = _invoke("status", project_id)
    assert case["execution_state"] == "failed"
    assert case["checkpoint"] == "d2:failed:1"
    assert case["d2_state"] == "authorized"
    assert case["phase"] == "sealed_confirmation"

    monkeypatch.setattr(research_cmds, "run_confirmation", real_run_confirmation)
    resumed = _invoke("resume", project_id)
    assert resumed["execution_state"] == "queued"
    confirm = _invoke("run", "confirm", project_id)
    manifest = cast(dict[str, object], confirm["manifest"])
    assert manifest["dataset_hash"] == data_hash
    attempt = cast(dict[str, object], confirm["attempt"])
    assert attempt["status"] == "completed"
    recovered_case = cast(dict[str, object], confirm["case"])
    assert recovered_case["phase"] == "research_decision"
    assert recovered_case["d2_state"] == "consumed"
    assert recovered_case["checkpoint"] == "d2:complete"


def test_confirmation_retries_exhaust_to_blocked_without_touching_the_share(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id, contract_id, _ = _confirmation_ready_project(tmp_path)
    _approve_confirmation(project_id, contract_id)

    def crash(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise DataError("simulated executor crash")

    monkeypatch.setattr(research_cmds, "run_confirmation", crash)
    for attempt_number in range(1, 4):
        failed = runner.invoke(app, ["research", "run", "confirm", project_id, "--json"])
        assert failed.exit_code != 0
        case = _invoke("status", project_id)
        assert case["checkpoint"] == f"d2:failed:{attempt_number}"
        assert case["execution_state"] == ("blocked" if attempt_number == 3 else "failed")
        assert case["d2_state"] == "authorized"
        if attempt_number < 3:
            assert _invoke("resume", project_id)["execution_state"] == "queued"

    # The initial attempt plus two safe retries are spent: the cap holds even after resume.
    assert _invoke("resume", project_id)["execution_state"] == "queued"
    capped = runner.invoke(app, ["research", "run", "confirm", project_id, "--json"])
    assert capped.exit_code != 0
    assert "revision" in capped.output


def test_confirmation_drafting_fails_closed_without_authority_or_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    synthetic_project = _approved_deep_ready_project()
    blocked = runner.invoke(app, ["research", "draft-confirmation", synthetic_project, "--json"])
    assert blocked.exit_code != 0
    assert "cannot authorize D2" in blocked.output


def test_confirmation_drafting_requires_a_completed_clearing_d1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id, _ = _approved_empirical_daily_project(tmp_path, lows=_varied_daily_lows())
    blocked = runner.invoke(app, ["research", "draft-confirmation", project_id, "--json"])
    assert blocked.exit_code != 0
    assert "deep-research" in blocked.output  # "…requires a completed D1 deep-research attempt"


def test_confirmation_drafting_fails_loud_on_degenerate_discovery_intervals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Perfectly uniform planted outcomes cannot fabricate confirmation certainty."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id, _ = _approved_empirical_daily_project(tmp_path)  # uniform rises
    _invoke("run", "deep", project_id)
    blocked = runner.invoke(app, ["research", "draft-confirmation", project_id, "--json"])
    assert blocked.exit_code != 0
    assert "non-degenerate" in blocked.output


def test_empirical_deep_run_fails_closed_on_drifted_dataset_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A registered dataset that no longer reproduces the frozen data hash cannot run."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id, _ = _approved_empirical_daily_project(tmp_path)

    from alpha_cli.research_d1 import registered_synthetic_d1_bars

    monkeypatch.setattr(
        research_cmds,
        "load_registered_research_bars",
        lambda *args, **kwargs: registered_synthetic_d1_bars(),
    )
    blocked = runner.invoke(app, ["research", "run", "deep", project_id, "--json"])
    assert blocked.exit_code != 0
    assert "approval-frozen data hash" in blocked.output


def test_empirical_daily_draft_fails_closed_on_missing_or_mismatched_datasets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "SPY bounces after double bottoms on the daily chart")
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])
    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Technical trading revisited",
        "--locator",
        "doi:10.0000/example",
        "--provider",
        "crossref",
        "--access-mode",
        "metadata_only",
    )
    pack_id = str(
        _invoke("sources", "freeze", project_id, "--source-id", str(source["source_id"]))["pack_id"]
    )

    no_dataset = runner.invoke(app, ["research", *_daily_draft_args(project_id, pack_id), "--json"])
    assert no_dataset.exit_code != 0
    assert "registered" in no_dataset.output and "dataset" in no_dataset.output

    unknown_ref = runner.invoke(
        app,
        [
            "research",
            *_daily_draft_args(project_id, pack_id),
            "--dataset",
            "rd_" + "0" * 64,
            "--json",
        ],
    )
    assert unknown_ref.exit_code != 0

    wrong_instrument_ref = _register_daily_dataset(tmp_path, "AAPL")
    mismatched = runner.invoke(
        app,
        [
            "research",
            *_daily_draft_args(project_id, pack_id),
            "--dataset",
            wrong_instrument_ref,
            "--json",
        ],
    )
    assert mismatched.exit_code != 0
    assert "instrument" in mismatched.output.casefold()

    spy_ref = _register_daily_dataset(tmp_path, "SPY")
    synthetic_with_dataset = runner.invoke(
        app,
        [
            "research",
            "draft",
            project_id,
            "--source-pack-id",
            pack_id,
            "--answer",
            "chart_construction=spy_rth_60m_four_hour_window",
            "--answer",
            "event_availability=second_trough_confirmable",
            "--answer",
            "primary_outcome=four_trading_hour_return_25bp",
            "--dataset",
            spy_ref,
            "--json",
        ],
    )
    assert synthetic_with_dataset.exit_code != 0
    assert "synthetic" in synthetic_with_dataset.output.casefold()


def test_approval_payload_rejects_inconsistent_empirical_bindings() -> None:
    """Provider and session-group integrity hold even for hand-built dataset bindings."""
    from alpha_cli.research_intake import draft_exploration_contract
    from alpha_cli.research_runtime import _GENERATION_60M, _bars

    preview = draft_exploration_contract(
        "SPY bounces after double bottoms on the daily chart",
        resolutions={
            "chart_construction": "tiingo_daily_fallback",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "next_regular_session_return_50bp",
        },
    )
    hourly_bars = _bars(_GENERATION_60M, [100.0 + i for i in range(25)], "d0-planted", "e" * 64)
    ref: dict[str, object] = {
        "ref_id": "rd_" + "f" * 64,
        "instrument": "SPY",
        "provider": "yfinance",
        "start_ts": "2020-01-01",
        "end_ts": "2020-06-01",
    }
    with pytest.raises(DataError, match="provider"):
        research_cmds._approval_payload(
            preview,
            source_pack_id="sp_" + "a" * 64,
            empirical_dataset=research_cmds._EmpiricalDataset(ref=ref, bars=hourly_bars),
        )
    # 25 hourly bars share calendar dates: duplicate session groups must fail closed.
    with pytest.raises(DataError, match="duplicate session groups"):
        research_cmds._approval_payload(
            preview,
            source_pack_id="sp_" + "a" * 64,
            empirical_dataset=research_cmds._EmpiricalDataset(
                ref={**ref, "provider": "tiingo"}, bars=hourly_bars
            ),
        )
    assert research_cmds._implementation_drifted(["not", "a", "mapping"]) is True


def test_claim_lifecycle_drafts_screens_and_feeds_the_literature_dimension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "SPY drifts upward into month-end rebalancing")
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])
    contract_id = str(cast(dict[str, object], captured["case"])["active_contract_id"])

    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Calendar effects in index returns",
        "--locator",
        "doi:10.0000/calendar",
        "--provider",
        "crossref",
        "--access-mode",
        "metadata_only",
        "--doi",
        "10.0000/Calendar",
        "--year",
        "2015",
        "--author",
        "A. Author",
        "--author",
        "B. Author",
    )
    source_id = str(source["source_id"])
    assert source["doi"] == "10.0000/calendar"
    assert source["authors"] == ["A. Author", "B. Author"]

    found = _invoke("sources", "search", "calendar effects")
    assert [row["source_id"] for row in cast(list[dict[str, object]], found["items"])] == [
        source_id
    ]

    drafted = _invoke(
        "sources",
        "claim",
        "add",
        project_id,
        "--source-id",
        source_id,
        "--contract-id",
        contract_id,
        "--text",
        "Month-end index drift is positive and statistically detectable pre-2010.",
        "--direction",
        "supports",
        "--strength",
        "moderate",
        "--method",
        "Calendar-day regression with Newey-West errors.",
        "--sample",
        "US index returns 1970-2010.",
        "--market",
        "US_EQUITY",
        "--limitations",
        "Post-publication decay is not addressed.",
    )
    claim_id = str(drafted["claim_id"])
    assert claim_id.startswith("sc_")
    assert drafted["status"] == "draft"
    assert drafted["author_kind"] == "agent"

    # A draft claim never moves the scorecard's literature dimension.
    status_before = _invoke("status", project_id)
    scorecard_before = cast(dict[str, object], status_before["scorecard"])
    literature_before = next(
        cast(dict[str, object], row)
        for row in cast(list[object], scorecard_before["dimensions"])
        if cast(dict[str, object], row)["dimension_id"] == "literature"
    )
    assert literature_before["state"] == "insufficient"

    screened = _invoke("sources", "claim", "screen", project_id, claim_id, "--actor", "owner")
    assert screened["status"] == "screened"
    listed = _invoke("sources", "claim", "list", project_id)
    rows = cast(list[dict[str, object]], listed["items"])
    assert [(row["claim_id"], row["status"]) for row in rows] == [(claim_id, "screened")]

    status_after = _invoke("status", project_id)
    scorecard_after = cast(dict[str, object], status_after["scorecard"])
    literature_after = next(
        cast(dict[str, object], row)
        for row in cast(list[object], scorecard_after["dimensions"])
        if cast(dict[str, object], row)["dimension_id"] == "literature"
    )
    assert literature_after["state"] == "supporting"

    hub = _invoke("evidence-hub", project_id)
    literature_section = cast(
        dict[str, object], cast(dict[str, object], hub["sections"])["literature"]
    )
    hub_claims = cast(list[dict[str, object]], literature_section["claims"])
    assert [row["claim_id"] for row in hub_claims] == [claim_id]
    assert hub_claims[0]["status"] == "screened"


def test_sources_fetch_drives_the_isolated_worker_with_closed_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "SECRET_SENTINEL")
    monkeypatch.setenv("SHELL", "/secret/interactive-shell")
    captured_argv: list[list[str]] = []
    captured_kwargs: list[dict[str, object]] = []

    class _Completed:
        returncode = 0
        stdout = json.dumps(
            {
                "final_url": "https://arxiv.org/pdf/1234v1",
                "media_type": "application/pdf",
                "byte_count": 10,
                "sha256": "a" * 64,
                "trust_label": "UNTRUSTED_SOURCE",
                "object_path": "/objects/aa",
                "receipt_path": "/objects/aa.receipt.json",
            }
        )
        stderr = ""

    def fake_run(argv: list[str], **kwargs: object) -> _Completed:
        captured_argv.append(argv)
        captured_kwargs.append(kwargs)
        return _Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)
    fetched = _invoke("sources", "fetch", "https://arxiv.org/pdf/1234v1")
    assert fetched["trust_label"] == "UNTRUSTED_SOURCE"
    assert "object_path" not in fetched and "receipt_path" not in fetched
    assert len(captured_argv) == 1
    argv = captured_argv[0]
    assert Path(argv[0]).name == "uv"
    assert argv[1:4] == ["run", "--project", argv[3]]
    assert argv[3].endswith("workers/literature")
    assert argv[4:7] == ["literature-worker", "fetch", "--url"]
    assert argv[7] == "https://arxiv.org/pdf/1234v1"
    assert "--objects-dir" in argv
    child_env = cast(dict[str, str], captured_kwargs[0]["env"])
    assert "ALPHA_TIINGO_API_KEY" not in child_env
    assert "SHELL" not in child_env
    assert "HOME" not in child_env
    assert set(child_env) == {"LANG", "LC_ALL", "PATH", "UV_NO_CONFIG", "UV_OFFLINE"}
    assert captured_kwargs[0]["start_new_session"] is True
    assert callable(captured_kwargs[0]["preexec_fn"])

    class _Failed(_Completed):
        returncode = 1
        stdout = ""
        stderr = json.dumps({"error": "research source hostname is not allowlisted"})

    monkeypatch.setattr(subprocess, "run", lambda argv, **kwargs: _Failed())
    rejected = runner.invoke(
        app, ["research", "sources", "fetch", "https://evil.example.com/x", "--json"]
    )
    assert rejected.exit_code != 0
    assert "not allowlisted" in rejected.output


def test_literature_discovery_acquisition_and_extraction_link_end_to_end_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id = str(
        cast(dict[str, object], _invoke("capture", "SPY pattern literature workflow")["project"])[
            "project_id"
        ]
    )
    discovery_id = "ld_" + "1" * 64
    candidate_id = "lc_" + "2" * 64
    source_sha = hashlib.sha256(b"%PDF-offline-fixture").hexdigest()
    extraction_id = "rx_" + "3" * 64
    discovery = {
        "schema": "LiteratureDiscoveryV1",
        "discovery_id": discovery_id,
        "query": "SPY pattern",
        "candidates": [
            {
                "candidate_id": candidate_id,
                "provider": "arxiv",
                "title": "SPY pattern evidence",
                "doi": None,
                "year": 2024,
                "authors": ["A. Author"],
                "open_access_url": "https://arxiv.org/pdf/1234.5678",
                "access_state": "direct_pdf",
                "relevance_explanation": "matched title concepts: pattern.",
                "matched_concepts": ["pattern"],
                "retracted": None,
                "dedup_key": "content:" + "4" * 32,
                "trust_label": "UNTRUSTED_SOURCE",
            }
        ],
        "receipt": {
            "receipt_id": discovery_id,
            "budget": {"max_candidates": 20, "max_full_texts": 5},
            "trust_label": "UNTRUSTED_SOURCE",
        },
    }
    extraction = {
        "schema": "ResearchDocumentTextV1",
        "extraction_id": extraction_id,
        "source_sha256": source_sha,
        "parser": "pypdf",
        "parser_version": "6.14.2",
        "config_hash": "5" * 64,
        "normalization": "NFC_LF_RSTRIP_V1",
        "status": "image_only",
        "pages": [
            {
                "page": 1,
                "text": "",
                "character_count": 0,
                "text_sha256": hashlib.sha256(b"").hexdigest(),
            }
        ],
        "page_count": 1,
        "character_count": 0,
        "warnings": ["No extractable text; OCR is out of scope."],
        "trust_label": "UNTRUSTED_SOURCE",
    }
    outputs: Iterator[dict[str, object]] = iter(
        [
            cast(dict[str, object], discovery),
            {
                "final_url": "https://arxiv.org/pdf/1234.5678",
                "media_type": "application/pdf",
                "byte_count": 20,
                "sha256": source_sha,
                "trust_label": "UNTRUSTED_SOURCE",
                "object_path": str(tmp_path / "research" / "objects" / source_sha),
                "receipt_path": str(
                    tmp_path / "research" / "objects" / f"{source_sha}.receipt.json"
                ),
            },
            extraction,
        ]
    )

    class _Completed:
        returncode = 0
        stderr = ""

        def __init__(self, payload: dict[str, object]) -> None:
            self.stdout = json.dumps(payload)

    monkeypatch.setattr(subprocess, "run", lambda argv, **kwargs: _Completed(next(outputs)))
    discovered = _invoke(
        "sources",
        "discover",
        project_id,
        "--query",
        "SPY pattern",
        "--unpaywall-email",
        "owner@example.com",
    )
    assert discovered["discovery_id"] == discovery_id
    acquired = _invoke("sources", "acquire", project_id, discovery_id, candidate_id)
    assert cast(dict[str, object], acquired["document"])["status"] == "image_only"
    assert "artifact_relpath" not in cast(dict[str, object], acquired["document"])
    sources = ControlStore(tmp_path).list_research_sources(project_id)
    assert sources[0]["extraction_status"] == "image_only"


def _approved_deep_ready_project() -> str:
    """Capture → sources → draft → approve → D0 pilot, landing in deep_research."""
    captured = _invoke(
        "capture",
        "I notice the S&P500 bounces after double bottoms on the 4h time frame",
    )
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])
    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Technical trading revisited",
        "--locator",
        "doi:10.0000/example",
        "--provider",
        "crossref",
        "--access-mode",
        "metadata_only",
    )
    pack = _invoke("sources", "freeze", project_id, "--source-id", str(source["source_id"]))
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        "chart_construction=spy_rth_60m_four_hour_window",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    frozen_id = str(cast(dict[str, object], drafted["contract"])["contract_id"])
    _invoke(
        "approve",
        "exploration",
        project_id,
        frozen_id,
        "--actor",
        "owner",
        "--reason",
        "The bounded protocol, plan, and source pack suit D0/D1 exploration.",
    )
    pilot = _invoke("run", "pilot", project_id)
    pilot_case = cast(dict[str, object], pilot["case"])
    assert pilot_case["phase"] == "deep_research"
    assert "run deep" in str(pilot_case["next_action"])
    return project_id


def test_run_deep_is_open_by_default_but_stays_phase_governed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-0025 opened D1 admission; every other governance rail still applies."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "A generic idea that has not completed D0")
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])
    blocked = runner.invoke(app, ["research", "run", "deep", project_id, "--json"])
    assert blocked.exit_code != 0
    assert "deep_research phase" in blocked.output


def test_run_deep_executes_the_frozen_plan_as_a_governed_durable_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id = _approved_deep_ready_project()

    deep = _invoke("run", "deep", project_id)
    manifest = cast(dict[str, object], deep["manifest"])
    attempt = cast(dict[str, object], deep["attempt"])
    case = cast(dict[str, object], deep["case"])
    assert manifest["command"] == "research_deep"
    assert manifest["evidence_zone"] == "D1"
    assert manifest["watermark"] == "EXPLORATORY"
    assert manifest["real_market_evidence"] is False
    assert manifest["eligible_for_holdout_or_execution"] is False
    assert attempt["kind"] == "d1-deep-research"
    assert attempt["status"] == "completed"
    assert attempt["budget_used"] == {"variants": 6}
    assert case["phase"] == "deep_research"
    assert case["execution_state"] == "idle"
    assert case["latest_run_id"] == manifest["run_id"]

    store = ControlStore(tmp_path)
    jobs = store.list_jobs()
    research_jobs = [job for job in jobs if job["kind"] == "research:event-study"]
    assert len(research_jobs) == 1
    assert research_jobs[0]["status"] == "succeeded"
    assert research_jobs[0]["result_run_id"] == manifest["run_id"]

    # The synthetic registered fixture is null by construction: it must never look like a
    # discovered edge.
    evidence_path = tmp_path / "runs" / str(manifest["run_id"]) / "research_gate_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["primary_result"]["practical_magnitude"]["status"] != "CLEARS_HURDLE"

    recovered = _invoke("run", "deep", project_id)
    assert cast(dict[str, object], recovered["manifest"])["run_id"] == manifest["run_id"]

    # The Evidence Hub and scorecard go live from the admitted D1 evidence — no terminal
    # packet is required for an open case.
    hub = _invoke("evidence-hub", project_id)
    sections = cast(dict[str, object], hub["sections"])
    exploration = cast(dict[str, object], sections["exploration"])
    assert exploration["status"] == "TESTED"
    robustness = cast(dict[str, object], sections["robustness"])
    assert robustness["status"] == "RECORDED"
    finding_ids = {
        str(cast(dict[str, object], finding)["finding_id"])
        for section in ("evidence_for", "evidence_against")
        for finding in cast(list[object], cast(dict[str, object], sections[section])["findings"])
    }
    assert finding_ids  # live D1 findings are partitioned into for/against
    status = _invoke("status", project_id)
    dimensions = {
        str(cast(dict[str, object], entry)["dimension_id"]): str(
            cast(dict[str, object], entry)["state"]
        )
        for entry in cast(list[object], cast(dict[str, object], status["scorecard"])["dimensions"])
    }
    assert dimensions["effect_existence"] == "mixed"  # exploratory only, honestly capped
    assert dimensions["falsification"] != "not_tested"


def test_run_deep_failures_checkpoint_and_exact_reexecution_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id = _approved_deep_ready_project()

    def _boom(*args: object, **kwargs: object) -> dict[str, object]:
        raise DataError("simulated mid-plan crash")

    monkeypatch.setattr(research_cmds, "run_deep_research", _boom)
    failed = runner.invoke(app, ["research", "run", "deep", project_id, "--json"])
    assert failed.exit_code != 0
    assert "checkpointed" in failed.output

    store = ControlStore(tmp_path)
    case = store.research_case_summary(project_id)
    assert case["execution_state"] == "failed"
    assert str(case["checkpoint"]).startswith("d1:failed:")
    failed_jobs = [job for job in store.list_jobs() if job["kind"] == "research:event-study"]
    assert failed_jobs and failed_jobs[0]["status"] == "failed"

    monkeypatch.undo()
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _invoke("resume", project_id)
    resumed = _invoke("run", "deep", project_id)
    manifest = cast(dict[str, object], resumed["manifest"])
    attempt = cast(dict[str, object], resumed["attempt"])
    assert manifest["evidence_zone"] == "D1"
    assert attempt["status"] == "completed"
    assert cast(dict[str, object], attempt["details"])["attempt_number"] == 2

"""Research-contract authority and schema-v2 migration invariants."""

from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

import alpha_cli.control_store as control_store_module
from alpha_cli import _artifacts
from alpha_cli.artifact_contract import artifact_metadata
from alpha_cli.control_store import SCHEMA_VERSION, ControlStore
from alpha_cli.research_intake import draft_exploration_contract
from alpha_cli.research_runtime import (
    _d0_acceptance_payload,
    _recomputed_d0_measurements,
    d0_execution_fingerprint,
    registered_d0_operator,
)
from alpha_core import DataError
from alpha_research import ResearchChartFingerprintV1, ResearchD2BoundaryV1
from tests.fixtures.control_store_fixtures import mark_project_as_migrated_legacy

PROJECT_ID = "9e4908b1-a9cd-4c13-a47e-740d92175680"
LEGACY_PROJECT_ID = "bf09e202-a02a-45c5-904e-1dbda4bf298e"
START = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _enable_future_empirical_state_machine_for_unit_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise future gates without exposing them through the production default."""

    monkeypatch.setattr(control_store_module, "_UNRELEASED_EMPIRICAL_RESEARCH_ENABLED", True)


def _project(store: ControlStore, project_id: str = PROJECT_ID) -> None:
    store.create_project(
        name="SPY four-hour double bottom",
        hypothesis="Confirmed double bottoms precede positive forward returns.",
        falsification_criterion="Reject when matched-control effects are non-positive.",
        project_id=project_id,
        at=START,
    )


def _source_pack(store: ControlStore) -> str:
    source = store.create_research_source(
        PROJECT_ID,
        title="Technical patterns and subsequent returns",
        locator="doi:10.0000/example",
        provider="crossref",
        access_mode="metadata_only",
        metadata={"doi": "10.0000/example", "screening": "include"},
        at=START + timedelta(minutes=1),
    )
    pack = store.create_research_source_pack(
        PROJECT_ID,
        source_ids=[str(source["source_id"])],
        definition={"queries": ["double bottom forward returns"], "frozen": True},
        at=START + timedelta(minutes=2),
    )
    return str(pack["pack_id"])


def _boundary(seed: str, *, synthetic: bool = True) -> ResearchD2BoundaryV1:
    chart = (
        ResearchChartFingerprintV1(
            instrument="SYNTHETIC_SPY",
            provider="alpha_synthetic_fixture",
            venue="SYNTHETIC",
            timezone="UTC",
            session="synthetic_equal_duration",
            bar_construction=(
                "fixed_60_trading_minute_bars_with_240_trading_minute_pattern_window"
            ),
            bar_duration_seconds=3_600,
            anchor="SYNTHETIC_EPOCH",
            adjustment_basis="synthetic_not_applicable",
            timestamp_semantics="bar_end_available",
        )
        if synthetic
        else ResearchChartFingerprintV1(
            instrument="SPY",
            provider="licensed-test-provider",
            venue="ARCX",
            timezone="America/New_York",
            session="regular_hours",
            bar_construction="fixed_60_trading_minute_bars",
            bar_duration_seconds=3_600,
            anchor="09:30 America/New_York",
            adjustment_basis="point_in_time_split_and_dividend",
            timestamp_semantics="bar_close_available",
        )
    )
    return ResearchD2BoundaryV1.from_eligible_groups(
        dataset_fingerprint=hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        eligible_groups=tuple(f"{seed}|2026-01-{day:02d}|RTH" for day in range(1, 11)),
        chart_fingerprint=chart,
        event_formula="confirmable second trough within 0.5 percent of first trough",
        event_availability_timestamp="second_trough_bar_close",
        primary_endpoint="event_minus_matched_control_arithmetic_return",
        primary_horizon="240_trading_minutes",
        outcome_overlap_embargo_groups=1,
    )


def _payload(
    pack_id: str,
    *,
    confirmation: bool = False,
    boundary_seed: str = "baseline-boundary",
    relation_to_prior: str | None = None,
) -> dict[str, object]:
    boundary = _boundary(boundary_seed)
    event_definition: dict[str, object] = {
        "name": "double_bottom",
        "availability": "second_trough_confirmable",
        "records_both_trough_times": True,
        "fires_only_when_confirmable": True,
        "right_pivot_moves_event_forward": True,
        "neckline_is_separate_variant": True,
        "overlapping_outcomes": "purge",
    }
    primary_claim: dict[str, object] = {
        "estimand": "event_minus_matched_control_arithmetic_return",
        "endpoint": "forward_arithmetic_return",
        "horizon_trading_minutes": 240,
        "direction": "positive",
        "minimum_effect_return": 0.0025,
    }
    protocol_chart_fingerprint = boundary.chart_fingerprint.to_dict()
    chart_fingerprint = (
        protocol_chart_fingerprint
        if confirmation
        else {
            "provider": "alpha_synthetic_fixture",
            "timezone": "UTC",
            "timestamp_semantics": "bar_end_available",
            "adjustment_basis": "synthetic_not_applicable",
            "instrument": "SYNTHETIC_SPY",
            "venue": "SYNTHETIC",
            "session": "synthetic_equal_duration",
            "bar_duration_minutes": 60,
            "pattern_window_trading_minutes": 240,
            "anchor": "SYNTHETIC_EPOCH",
            "label": "synthetic SPY-like 60-minute D0 fixture with a four-hour pattern window",
        }
    )
    d2: dict[str, object] = {
        "state": "sealed",
        "share": 0.20,
        "boundary_hash": boundary.boundary_sha256,
    }
    if relation_to_prior is not None:
        d2["relation_to_prior"] = relation_to_prior
    payload: dict[str, object] = {
        "schema": "ResearchContractV1",
        "scope": "exploration" if not confirmation else "confirmation",
        "approval_ready": True,
        "blocking_questions": [],
        "resolved_material_choices": {
            "chart_construction": "spy_rth_60m_four_hour_window",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "four_trading_hour_return_25bp",
        },
        "chart_fingerprint": chart_fingerprint,
        "event_definition": event_definition,
        "primary_claim": primary_claim,
        "thesis": {"primary_claims": [primary_claim]},
        "protocol": {
            "event": "causal confirmed double bottom",
            "event_definition": event_definition,
            "outcome": "forward return in elapsed trading minutes",
            "chart_fingerprint": protocol_chart_fingerprint,
            "primary_claims": [primary_claim],
            "boundary_authority": (
                {
                    "kind": "empirical_dataset",
                    "real_market_evidence": True,
                    "empirical_confirmation_authorized": True,
                }
                if confirmation
                else {
                    "kind": "synthetic_acceptance_fixture",
                    "real_market_evidence": False,
                    "empirical_confirmation_authorized": False,
                }
            ),
            "evidence_topology": {
                "boundary": boundary.to_dict(),
                "D0": {"share": 0.0},
                "D1": {"share": 0.60},
                "D2": d2,
                "D3": {"state": "sealed", "share": 0.20},
            },
        },
        "source_pack_id": pack_id,
        "budget": {"wall_seconds": 14_400, "source_requests": 60, "variants": 128},
        "hashes": {
            "code": "git:a1b2c3d4e5f60718",
            "environment": "uv-lock:1234abcd5678ef90",
            "evaluator": "event-study-v1.0.0",
            "data": "sha256:1234abcd5678ef901234abcd5678ef90" if confirmation else None,
        },
    }
    if confirmation:
        payload["confirmation"] = {
            "variant_count": 128,
            "multiplicity_count": 128,
            "familywise_alpha": 0.05,
            "target_power": 0.90,
            "power_report": {"achieved_power": 0.92},
            "fingerprints": {
                "detector": "double-bottom-v1.0.0",
                "variant_family": "variant-family-a1b2c3d4",
                "statistics": "event-study-stats-v1",
            },
        }
    else:
        protocol = cast(dict[str, object], payload["protocol"])
        protocol["d0_operator"] = registered_d0_operator(payload)
    return payload


def _approved_contracts(
    store: ControlStore,
    *,
    outcome: str = "SUPPORTED",
    disposition: str = "advance_to_strategy",
    record_confirmation_evidence: bool = True,
    record_decision: bool = True,
    d2_state: str = "consumed",
    transition_to_decision: bool = True,
) -> tuple[str, str]:
    pack_id = _source_pack(store)
    exploration = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=_payload(pack_id),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    exploration_id = str(exploration["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="triage",
        contract_id=exploration_id,
        actor="codex",
        reason="The captured idea is ready for triage.",
        next_action="Prepare the exploration review.",
        responsibility="codex",
        at=START + timedelta(minutes=4),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="exploration_review",
        contract_id=exploration_id,
        actor="codex",
        reason="The exploration contract is ready for owner review.",
        next_action="Approve or reject exploration.",
        responsibility="owner",
        at=START + timedelta(minutes=5),
    )
    store.review_research_contract(
        PROJECT_ID,
        exploration_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="D1 protocol is suitable for bounded exploration.",
        at=START + timedelta(minutes=6),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=exploration_id,
        actor="codex",
        reason="Exploration was approved.",
        next_action="Run the bounded pilot.",
        responsibility="codex",
        at=START + timedelta(minutes=7),
    )
    _record_completed_d0(
        store,
        exploration_id,
        _payload(pack_id),
        at=START + timedelta(minutes=7, seconds=30),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="deep_research",
        contract_id=exploration_id,
        actor="codex",
        reason="The pilot completed.",
        next_action="Freeze the confirmation child.",
        responsibility="codex",
        at=START + timedelta(minutes=8),
    )
    confirmation_payload = _payload(pack_id, confirmation=True)
    confirmation = store.create_research_contract(
        PROJECT_ID,
        scope="confirmation",
        parent_contract_id=exploration_id,
        payload=confirmation_payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=9),
    )
    confirmation_id = str(confirmation["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="confirmation_review",
        contract_id=confirmation_id,
        actor="codex",
        reason="The confirmation child is ready for owner review.",
        next_action="Approve or reject D2 authorization.",
        responsibility="owner",
        at=START + timedelta(minutes=10),
    )
    store.review_research_contract(
        PROJECT_ID,
        confirmation_id,
        scope="confirmation",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="The frozen confirmation family may consume D2 once.",
        at=START + timedelta(minutes=11),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="sealed_confirmation",
        contract_id=confirmation_id,
        actor="codex",
        reason="Confirmation was approved.",
        next_action="Consume D2 once.",
        responsibility="codex",
        at=START + timedelta(minutes=12),
    )
    store.transition_research_d2_state(
        PROJECT_ID,
        confirmation_id,
        to_state=d2_state,  # type: ignore[arg-type]
        actor="system",
        reason=f"The sealed confirmation boundary became {d2_state}.",
        at=START + timedelta(minutes=13),
    )
    if record_confirmation_evidence and d2_state == "consumed":
        gate_evidence = _confirmation_evidence(outcome)
        gate_evidence_bytes = json.dumps(
            gate_evidence,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        run_id = _write_research_run(
            store._data_dir,
            run_id=hashlib.sha256(confirmation_id.encode()).hexdigest()[:16],
            contract_id=confirmation_id,
            payload=confirmation_payload,
            evidence_zone="D2",
            gate_evidence=gate_evidence,
        )
        store.record_research_attempt(
            PROJECT_ID,
            confirmation_id,
            kind="sealed-confirmation",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={
                "evidence_zone": "D2",
                "real_market_evidence": True,
                "gate_packet_evidence_ref": {
                    "artifact": "research_gate_evidence.json",
                    "content_sha256": hashlib.sha256(gate_evidence_bytes).hexdigest(),
                },
            },
            run_id=run_id,
            at=START + timedelta(minutes=13, seconds=30),
        )
    if transition_to_decision:
        store.transition_research_phase(
            PROJECT_ID,
            to_phase="research_decision",
            contract_id=confirmation_id,
            actor="codex",
            reason="Confirmation results are complete.",
            next_action="Record the owner research decision.",
            responsibility="owner",
            at=START + timedelta(minutes=14),
        )
    if record_decision:
        assert transition_to_decision
        store.record_research_decision(
            PROJECT_ID,
            confirmation_id,
            outcome=outcome,  # type: ignore[arg-type]
            disposition=disposition,  # type: ignore[arg-type]
            actor="owner",
            actor_kind="human",
            reason="The owner accepts the mechanical frozen-confirmation classification.",
            at=START + timedelta(minutes=15),
        )
    return exploration_id, confirmation_id


def _confirmation_evidence(outcome: str) -> dict[str, object]:
    claim: dict[str, object] | None = {
        "direction": "positive",
        "minimum_effect": 0.0005,
        "adjusted_p_value": 0.01,
        "alpha": 0.05,
    }
    if outcome == "SUPPORTED":
        primary: dict[str, object] = {
            "status": "TESTED",
            "estimate": 0.003,
            "unit": "return",
            "sample_size": 60,
            "effective_sample_size": 45.0,
            "uncertainty": {
                "lower": 0.001,
                "upper": 0.005,
                "level": 0.95,
                "method": "cluster bootstrap",
            },
            "practical_magnitude": {
                "status": "CLEARS_HURDLE",
                "value": 0.003,
                "unit": "return",
                "interpretation": "The interval clears the registered hurdle.",
            },
        }
        checks = {
            "corrected_primary_test_passed": True,
            "interval_registered_direction": True,
            "economic_hurdle_cleared": True,
            "interval_wholly_against_direction": False,
        }
    elif outcome == "CONTRADICTED":
        primary = {
            "status": "TESTED",
            "estimate": -0.003,
            "unit": "return",
            "sample_size": 60,
            "effective_sample_size": 45.0,
            "uncertainty": {
                "lower": -0.005,
                "upper": -0.001,
                "level": 0.95,
                "method": "cluster bootstrap",
            },
            "practical_magnitude": {
                "status": "BELOW_HURDLE",
                "value": -0.003,
                "unit": "return",
                "interpretation": "The interval lies against the registered direction.",
            },
        }
        checks = {
            "corrected_primary_test_passed": False,
            "interval_registered_direction": False,
            "economic_hurdle_cleared": False,
            "interval_wholly_against_direction": True,
        }
        claim = dict(claim or {}, adjusted_p_value=0.6)
    elif outcome == "INVALID":
        primary = {"status": "NOT_TESTED"}
        checks = {
            "corrected_primary_test_passed": False,
            "interval_registered_direction": False,
            "economic_hurdle_cleared": False,
            "interval_wholly_against_direction": False,
        }
        claim = None
    else:
        primary = {
            "status": "TESTED",
            "estimate": 0.001,
            "unit": "return",
            "sample_size": 60,
            "effective_sample_size": 45.0,
            "uncertainty": {
                "lower": -0.001,
                "upper": 0.003,
                "level": 0.95,
                "method": "cluster bootstrap",
            },
            "practical_magnitude": {
                "status": "INCONCLUSIVE",
                "value": 0.001,
                "unit": "return",
                "interpretation": "The interval does not clear the registered hurdle.",
            },
        }
        checks = {
            "corrected_primary_test_passed": False,
            "interval_registered_direction": False,
            "economic_hurdle_cleared": False,
            "interval_wholly_against_direction": False,
        }
        claim = dict(claim or {}, adjusted_p_value=0.2)
    evidence: dict[str, object] = {
        "schema": "ResearchGateEvidenceV1",
        "evidence_zone": "D2",
        "primary_result": primary,
        "confirmation_classification": outcome,
        "confirmation_checks": checks,
    }
    if claim is not None:
        evidence["confirmation_claim"] = claim
    return evidence


def _approved_pilot(store: ControlStore) -> tuple[str, dict[str, object]]:
    pack_id = _source_pack(store)
    payload = _payload(pack_id)
    contract = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    contract_id = str(contract["contract_id"])
    for minute, phase, responsibility in (
        (4, "triage", "codex"),
        (5, "exploration_review", "owner"),
    ):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase=phase,  # type: ignore[arg-type]
            contract_id=contract_id,
            actor="codex",
            reason=f"Advance the fixture to {phase}.",
            next_action="Continue the governed pilot fixture.",
            responsibility=responsibility,  # type: ignore[arg-type]
            at=START + timedelta(minutes=minute),
        )
    store.review_research_contract(
        PROJECT_ID,
        contract_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Approve the exact pilot fixture.",
        at=START + timedelta(minutes=6),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=contract_id,
        actor="owner",
        reason="The pilot fixture is approved.",
        next_action="Run D0 only.",
        responsibility="codex",
        at=START + timedelta(minutes=7),
    )
    return contract_id, payload


def _write_research_run(
    data_dir: Path,
    *,
    run_id: str,
    contract_id: str,
    payload: dict[str, object],
    override: tuple[str, object] | None = None,
    evidence_zone: str = "D0",
    gate_evidence: dict[str, object] | None = None,
) -> str:
    contract_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    hashes = payload["hashes"]
    assert isinstance(hashes, dict)
    dataset_hash: str | None = None
    if evidence_zone == "D0":
        protocol = payload["protocol"]
        assert isinstance(protocol, dict)
        operator = protocol["d0_operator"]
        assert isinstance(operator, dict)
        fixture = operator["fixture"]
        assert isinstance(fixture, dict)
        dataset_hash = str(fixture["definition_fingerprint"])
        run_identity = {
            "command": "research_pilot",
            "project_id": PROJECT_ID,
            "research_contract_id": contract_id,
            "contract_hash": contract_hash,
            "dataset_hash": dataset_hash,
            "execution_fingerprint": "a" * 64,
        }
        run_id = hashlib.sha256(
            json.dumps(run_identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
    manifest: dict[str, object] = {
        "run_id": run_id,
        "run_identity_version": 3,
        "command": "research_confirm" if evidence_zone == "D2" else "research_pilot",
        "kind": "research",
        "project_id": PROJECT_ID,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "source_pack_id": payload["source_pack_id"],
        "research_fingerprints": hashes,
        "evidence_zone": evidence_zone,
        "eligible_for_holdout_or_execution": False,
        "places_orders": False,
        "snapshot_id": None,
        "snapshot_hash": None,
        "execution_fingerprint": "a" * 64,
        "strategy_fingerprint": None,
        "source_fingerprint": contract_hash,
    }
    if evidence_zone == "D0":
        assert dataset_hash is not None
        manifest["dataset_hash"] = dataset_hash
        protocol = payload["protocol"]
        assert isinstance(protocol, dict)
        operator = protocol["d0_operator"]
        assert isinstance(operator, dict)
        manifest["d0_operator"] = operator
        manifest["d0_operator_fingerprint"] = operator["fingerprint"]
        manifest["d0_acceptance_artifact"] = "d0_acceptance.json"
    if override is not None:
        field, value = override
        if field.startswith("research_fingerprints."):
            fingerprints = dict(hashes)
            fingerprints[field.partition(".")[2]] = value
            manifest["research_fingerprints"] = fingerprints
        else:
            manifest[field] = value
    rdir = _artifacts.run_dir(data_dir, run_id)
    rdir.mkdir(parents=True)
    if evidence_zone == "D0":
        operator_fingerprint = manifest["d0_operator_fingerprint"]
        assert isinstance(operator_fingerprint, str)
        assert dataset_hash is not None
        measurements = _recomputed_d0_measurements()
        sidecars: dict[str, bytes] = {
            "events.json": b'[{"confirmation_index":8,"second_trough_index":6}]',
            "topology.json": b'{"schema_version":2}',
            "power.json": b'{"known_sigma_fixture_only":true}',
            "chart-data.json": b'{"watermark":"EXPLORATORY"}',
            "detector-validity.png": b"synthetic-d0-chart",
            "report.md": b"# D0 synthetic acceptance\n",
            "d0_acceptance.json": json.dumps(
                _d0_acceptance_payload(
                    run_id=run_id,
                    project_id=PROJECT_ID,
                    contract_id=contract_id,
                    contract_hash=contract_hash,
                    dataset_hash=dataset_hash,
                    execution_fingerprint="a" * 64,
                    d0_operator_fingerprint=operator_fingerprint,
                    measurements=measurements,
                ),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8"),
        }
        for filename, content in sidecars.items():

            def write_sidecar(target: Path, *, body: bytes = content) -> None:
                target.write_bytes(body)

            _artifacts.publish_artifact(rdir / filename, write_sidecar)
    if gate_evidence is not None:
        content = json.dumps(
            gate_evidence,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

        def write_gate_evidence(target: Path) -> None:
            target.write_bytes(content)

        _artifacts.publish_artifact(rdir / "research_gate_evidence.json", write_gate_evidence)
    _artifacts.write_manifest(rdir, manifest)
    return run_id


def _run_only_payload() -> dict[str, object]:
    return {
        "source_pack_id": "sp_" + "1" * 64,
        "hashes": {
            "code": "git:a1b2c3d4e5f60718",
            "environment": "uv-lock:1234abcd5678ef90",
            "evaluator": "event-study-v1.0.0",
            "data": None,
        },
        "protocol": {
            "d0_operator": {
                "schema": "TestRegisteredOperatorV1",
                "fingerprint": "4" * 64,
                "fixture": {"definition_fingerprint": "5" * 64},
            }
        },
    }


def _record_completed_d0(
    store: ControlStore,
    contract_id: str,
    payload: dict[str, object],
    *,
    at: datetime,
) -> str:
    run_id = _write_research_run(
        store._data_dir,
        run_id="ignored-content-derived-id",
        contract_id=contract_id,
        payload=payload,
    )
    store.record_research_attempt(
        PROJECT_ID,
        contract_id,
        kind="d0-synthetic-pilot",
        status="completed",
        config_fingerprint="a" * 64,
        budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
        details={
            "evidence_zone": "D0",
            "d0_acceptance_ref": _d0_acceptance_ref(store._data_dir, run_id),
        },
        run_id=run_id,
        at=at,
    )
    return run_id


def _d0_acceptance_ref(data_dir: Path, run_id: str) -> dict[str, object]:
    manifest = _artifacts.read_manifest(data_dir / "runs" / run_id)
    artifacts = cast(dict[str, object], manifest["artifacts"])
    metadata = cast(dict[str, object], artifacts["d0_acceptance.json"])
    return {
        "artifact": "d0_acceptance.json",
        "content_sha256": metadata["sha256"],
    }


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


def test_schema_v1_migrates_additively_and_preserves_legacy_projection(tmp_path: Path) -> None:
    root = tmp_path / "control"
    root.mkdir()
    database = root / "workstation.sqlite3"
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
        """
    )
    expected = {
        "project_id": LEGACY_PROJECT_ID,
        "name": "Legacy project",
        "hypothesis": "Legacy hypothesis",
        "falsification_criterion": "Legacy criterion",
        "status": "active",
        "current_version_id": None,
        "current_experiment_id": None,
        "created_at": "2026-08-05T23:59:00.000000Z",
        "updated_at": "2026-08-05T23:59:00.000000Z",
    }
    post_launch_project_id = "a9fe8545-ac44-48d5-bb01-5517b96002c9"
    post_launch = {
        **expected,
        "project_id": post_launch_project_id,
        "name": "Post-launch v1 project",
        "created_at": "2026-08-06T00:00:00.000000Z",
        "updated_at": "2026-08-06T00:00:00.000000Z",
    }
    connection.execute(
        "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(expected.values())
    )
    connection.execute(
        "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(post_launch.values())
    )
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()

    assert SCHEMA_VERSION == 2
    assert ControlStore(tmp_path).list_projects() == [post_launch, expected]
    migrated = sqlite3.connect(database)
    governance = {
        str(row[0]): (int(row[1]), str(row[2]))
        for row in migrated.execute(
            "SELECT project_id, research_required, origin FROM project_research_governance"
        )
    }
    assert migrated.execute("PRAGMA user_version").fetchone() == (2,)
    tables = {
        str(row[0])
        for row in migrated.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    migrated.close()
    assert {
        "research_contracts",
        "research_contract_review_events",
        "research_phase_events",
        "research_execution_events",
        "research_source_records",
        "research_source_packs",
        "research_attempt_records",
        "research_launch_reservations",
        "research_launch_attempt_links",
    } <= tables
    assert governance == {
        LEGACY_PROJECT_ID: (0, "legacy_import"),
        post_launch_project_id: (1, "strategy_development"),
    }
    assert (root / "workstation.sqlite3.v1.bak").is_file()

    legacy_version = ControlStore(tmp_path).create_strategy_version(
        LEGACY_PROJECT_ID,
        strategy_name="legacy_mean_reversion",
        source_fingerprint="git:legacy-migration",
        definition={"window": 20},
        parameter_space={"window": [20]},
        at=START,
    )
    assert "research_contract_id" not in legacy_version
    with pytest.raises(DataError, match="research_contract_id"):
        ControlStore(tmp_path).create_strategy_version(
            post_launch_project_id,
            strategy_name="must_be_research_governed",
            source_fingerprint="git:post-launch-v1",
            definition={},
            parameter_space={},
            at=START,
        )


def test_schema_v1_migration_failure_rolls_back_all_ddl_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "control"
    root.mkdir()
    database = root / "workstation.sqlite3"
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
    expected = (
        LEGACY_PROJECT_ID,
        "Interrupted v1 project",
        "Interrupted migration preserves this hypothesis.",
        "Reject if a partial schema survives rollback.",
        "active",
        None,
        None,
        "2026-08-05T23:59:00.000000Z",
        "2026-08-05T23:59:00.000000Z",
    )
    connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", expected)
    connection.commit()
    connection.close()

    schema_v2 = control_store_module._SCHEMA_V2
    monkeypatch.setattr(
        control_store_module,
        "_SCHEMA_V2",
        schema_v2 + "\nTHIS IS AN INJECTED MIGRATION FAILURE;",
    )
    with pytest.raises(DataError, match="cannot initialize control store"):
        ControlStore(tmp_path).list_projects()

    backup = root / "workstation.sqlite3.v1.bak"
    source = sqlite3.connect(database)
    retained_backup = sqlite3.connect(backup)
    try:
        assert source.execute("PRAGMA user_version").fetchone() == (1,)
        assert retained_backup.execute("PRAGMA user_version").fetchone() == (1,)
        assert control_store_module._logical_database_fingerprint(
            source
        ) == control_store_module._logical_database_fingerprint(retained_backup)
    finally:
        source.close()
        retained_backup.close()

    monkeypatch.setattr(control_store_module, "_SCHEMA_V2", schema_v2)
    assert ControlStore(tmp_path).list_projects()[0]["project_id"] == LEGACY_PROJECT_ID
    migrated = sqlite3.connect(database)
    try:
        assert migrated.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
    finally:
        migrated.close()


def _migration_v1_database(tmp_path: Path) -> tuple[Path, tuple[object, ...]]:
    root = tmp_path / "control"
    root.mkdir()
    database = root / "workstation.sqlite3"
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
    legacy_row: tuple[object, ...] = (
        LEGACY_PROJECT_ID,
        "Migration guard project",
        "Migration preserves the exact locked v1 state.",
        "Reject if backup validation or transactional DDL fails.",
        "active",
        None,
        None,
        "2026-08-05T23:59:00.000000Z",
        "2026-08-05T23:59:00.000000Z",
    )
    connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", legacy_row)
    connection.commit()
    connection.close()
    return database, legacy_row


@pytest.mark.parametrize(
    ("backup_kind", "message"),
    [
        pytest.param("symlink", "must not be a symlink", id="symlink"),
        pytest.param("directory", "is not a file", id="non-file"),
        pytest.param("invalid", "backup is invalid", id="invalid-sqlite"),
    ],
)
def test_schema_v1_migration_rejects_unsafe_existing_backup(
    tmp_path: Path,
    backup_kind: str,
    message: str,
) -> None:
    database, legacy_row = _migration_v1_database(tmp_path)
    backup = database.with_name(f"{database.name}.v1.bak")
    if backup_kind == "symlink":
        target = database.with_name("untrusted-backup-target")
        target.write_text("not a database", encoding="utf-8")
        backup.symlink_to(target)
    elif backup_kind == "directory":
        backup.mkdir()
    else:
        invalid = sqlite3.connect(backup)
        invalid.close()

    with pytest.raises(DataError, match=message):
        ControlStore(tmp_path).list_projects()

    source = sqlite3.connect(database)
    try:
        assert source.execute("PRAGMA user_version").fetchone() == (1,)
        assert source.execute("SELECT * FROM projects").fetchall() == [legacy_row]
    finally:
        source.close()


def test_new_schema_v1_backup_rejects_invalid_snapshot_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _ = _migration_v1_database(tmp_path)
    source = sqlite3.connect(database, isolation_level=None)
    source.execute("PRAGMA journal_mode = WAL")
    source.execute("BEGIN IMMEDIATE")
    original_connect = sqlite3.connect

    class CorruptingSnapshot:
        def __init__(self, delegate: sqlite3.Connection) -> None:
            self.delegate = delegate

        @property
        def in_transaction(self) -> bool:
            return self.delegate.in_transaction

        def execute(self, statement: str) -> sqlite3.Cursor:
            return self.delegate.execute(statement)

        def backup(self, target: sqlite3.Connection) -> None:
            self.delegate.backup(target)
            target.execute("PRAGMA user_version = 0")
            target.commit()

        def rollback(self) -> None:
            self.delegate.rollback()

        def close(self) -> None:
            self.delegate.close()

    def corrupt_snapshot_connect(path: Any, *args: Any, **kwargs: Any) -> Any:
        connected = original_connect(path, *args, **kwargs)
        if Path(path) == database:
            return CorruptingSnapshot(connected)
        return connected

    monkeypatch.setattr(sqlite3, "connect", corrupt_snapshot_connect)
    try:
        with pytest.raises(DataError, match="cannot verify control store v1 migration backup"):
            control_store_module._verified_v1_backup(source, database)
    finally:
        source.rollback()
        source.close()

    assert not database.with_name(f"{database.name}.v1.bak").exists()
    assert list(database.parent.glob(f".{database.name}.v1.bak.*.tmp")) == []


def test_new_schema_v1_backup_rejects_fingerprint_mismatch_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _ = _migration_v1_database(tmp_path)
    source = sqlite3.connect(database, isolation_level=None)
    source.execute("PRAGMA journal_mode = WAL")
    source.execute("BEGIN IMMEDIATE")
    original_fingerprint = control_store_module._logical_database_fingerprint
    fingerprint_calls = 0

    def mismatch_first_fingerprint(connection: sqlite3.Connection) -> str:
        nonlocal fingerprint_calls
        fingerprint_calls += 1
        fingerprint = original_fingerprint(connection)
        return "f" * 64 if fingerprint_calls == 1 else fingerprint

    monkeypatch.setattr(
        control_store_module, "_logical_database_fingerprint", mismatch_first_fingerprint
    )
    try:
        with pytest.raises(DataError, match="backup does not match the current database"):
            control_store_module._verified_v1_backup(source, database)
    finally:
        source.rollback()
        source.close()

    assert fingerprint_calls == 2
    assert not database.with_name(f"{database.name}.v1.bak").exists()
    assert list(database.parent.glob(f".{database.name}.v1.bak.*.tmp")) == []


def test_static_schema_helpers_fail_closed_and_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = sqlite3.connect(tmp_path / "helpers.sqlite3", isolation_level=None)
    try:
        with pytest.raises(sqlite3.OperationalError, match="active transaction"):
            control_store_module._apply_schema_v2_locked(connection)

        connection.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="incomplete static"):
            control_store_module._execute_static_sql_script(
                connection, "CREATE TABLE incomplete (value TEXT"
            )
        connection.rollback()

        monkeypatch.setattr(
            control_store_module,
            "_SCHEMA_V2",
            "CREATE TABLE rolled_back (value TEXT);\nTHIS IS INVALID SQL;",
        )
        with pytest.raises(sqlite3.OperationalError):
            control_store_module._apply_schema_v2(connection)
        assert connection.in_transaction is False
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'rolled_back'"
            ).fetchone()
            is None
        )
        assert connection.execute("PRAGMA user_version").fetchone() == (0,)
    finally:
        connection.close()


def test_locked_v1_migration_rejects_unsupported_version_and_rolls_back(tmp_path: Path) -> None:
    database = tmp_path / "unsupported.sqlite3"
    connection = sqlite3.connect(database, isolation_level=None)
    connection.execute("PRAGMA user_version = 3")
    with pytest.raises(DataError, match="unsupported control store schema version 3"):
        control_store_module._migrate_schema_v1(connection, database)
    assert connection.in_transaction is False
    assert connection.execute("PRAGMA user_version").fetchone() == (3,)
    connection.close()


@pytest.mark.parametrize(
    ("budget", "require_minimum", "message"),
    [
        pytest.param("not-an-object", False, "must be a JSON object", id="not-object"),
        pytest.param({}, True, "requires wall_seconds", id="missing-minimums"),
        pytest.param({"wall_seconds": -1}, False, "non-negative", id="negative"),
        pytest.param({"wall_seconds": float("inf")}, False, "finite JSON", id="infinite"),
    ],
)
def test_research_budget_validation_fails_closed(
    budget: object,
    require_minimum: bool,
    message: str,
) -> None:
    with pytest.raises(DataError, match=message):
        control_store_module._budget_values(budget, require_minimum=require_minimum)


def test_schema_v1_backup_and_migration_hold_one_writer_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "control"
    root.mkdir()
    database = root / "workstation.sqlite3"
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
    legacy_row = (
        LEGACY_PROJECT_ID,
        "Locked legacy project",
        "The backup and migration share one serialized legacy snapshot.",
        "Reject if a writer can enter after backup creation.",
        "active",
        None,
        None,
        "2026-08-05T23:59:00.000000Z",
        "2026-08-05T23:59:00.000000Z",
    )
    connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", legacy_row)
    connection.commit()
    expected_fingerprint = control_store_module._logical_database_fingerprint(connection)
    connection.close()

    backup_ready = threading.Event()
    release_migration = threading.Event()
    original_backup = control_store_module._verified_v1_backup

    def hold_after_backup(locked: sqlite3.Connection, path: Path) -> None:
        original_backup(locked, path)
        backup_ready.set()
        if not release_migration.wait(timeout=5):
            raise AssertionError("timed out waiting to release the migration lock")

    monkeypatch.setattr(control_store_module, "_verified_v1_backup", hold_after_backup)
    migration_errors: list[BaseException] = []
    concurrent_migration_errors: list[BaseException] = []
    concurrent_initial_versions: list[int] = []
    concurrent_begin = threading.Event()

    def migrate() -> None:
        try:
            ControlStore(tmp_path).list_projects()
        except BaseException as exc:  # pragma: no cover - asserted below for thread handoff.
            migration_errors.append(exc)

    def concurrent_migrate() -> None:
        connection = sqlite3.connect(database, timeout=5.0, isolation_level=None)
        try:
            version = connection.execute("PRAGMA user_version").fetchone()
            concurrent_initial_versions.append(int(version[0]))

            def observe_transaction(
                action: int,
                _arg1: str | None,
                _arg2: str | None,
                _database_name: str | None,
                _trigger_name: str | None,
            ) -> int:
                if action == sqlite3.SQLITE_TRANSACTION:
                    concurrent_begin.set()
                return sqlite3.SQLITE_OK

            connection.set_authorizer(observe_transaction)
            control_store_module._migrate_schema_v1(connection, database)
        except BaseException as exc:  # pragma: no cover - asserted below for thread handoff.
            concurrent_migration_errors.append(exc)
        finally:
            connection.close()

    migrator = threading.Thread(target=migrate)
    second_migrator = threading.Thread(target=concurrent_migrate)
    migrator.start()
    try:
        assert backup_ready.wait(timeout=5)
        writer = sqlite3.connect(database, timeout=0.05, isolation_level=None)
        try:
            writer.execute("PRAGMA busy_timeout = 50")
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                writer.execute("BEGIN IMMEDIATE")
        finally:
            writer.close()
        second_migrator.start()
        assert concurrent_begin.wait(timeout=5)
    finally:
        release_migration.set()
        migrator.join(timeout=5)
        if second_migrator.ident is not None:
            second_migrator.join(timeout=5)

    assert not migrator.is_alive()
    assert not second_migrator.is_alive()
    assert migration_errors == []
    assert concurrent_migration_errors == []
    assert concurrent_initial_versions == [1]
    migrated = sqlite3.connect(database)
    backup = sqlite3.connect(root / "workstation.sqlite3.v1.bak")
    try:
        assert migrated.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
        assert control_store_module._logical_database_fingerprint(backup) == expected_fingerprint
        assert backup.execute("SELECT * FROM projects").fetchall() == [legacy_row]
    finally:
        migrated.close()
        backup.close()


def test_existing_schema_v2_reopen_adds_launch_reservation_tables(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    database = tmp_path / "control" / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    assert connection.execute("PRAGMA user_version").fetchone() == (2,)
    connection.execute("DROP TABLE research_launch_attempt_links")
    connection.execute("DROP TABLE research_launch_reservations")
    connection.commit()
    connection.close()

    assert ControlStore(tmp_path).get_project(PROJECT_ID)["project_id"] == PROJECT_ID
    reopened = sqlite3.connect(database)
    tables = {
        str(row[0])
        for row in reopened.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    reopened.close()
    assert {"research_launch_reservations", "research_launch_attempt_links"} <= tables


def test_new_projects_require_research_and_legacy_import_is_migration_only(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    store.create_project(
        name="Fresh strategy project",
        hypothesis="A fresh strategy hypothesis.",
        falsification_criterion="Reject when confirmation is not economically meaningful.",
        project_id=PROJECT_ID,
        at=START,
    )
    with pytest.raises(DataError, match="research_contract_id"):
        store.create_strategy_version(
            PROJECT_ID,
            strategy_name="ungoverned_attempt",
            source_fingerprint="git:must-not-bypass",
            definition={},
            parameter_space={},
            at=START + timedelta(minutes=1),
        )

    with pytest.raises(DataError, match="unsupported project research origin"):
        store.create_project(
            name="Backdated fake legacy project",
            hypothesis="This record did not predate the research program.",
            falsification_criterion="Reject the forged grandfathering claim.",
            research_origin="legacy_import",  # type: ignore[arg-type]
            project_id=LEGACY_PROJECT_ID,
            at=datetime(2026, 8, 5, 23, 59, tzinfo=UTC),
        )
    store.create_project(
        name="Backdated governed project",
        hypothesis="A caller-controlled timestamp must not change governance.",
        falsification_criterion="Reject if a strategy can bypass research.",
        project_id=LEGACY_PROJECT_ID,
        at=datetime(2026, 8, 5, 23, 59, tzinfo=UTC),
    )
    with pytest.raises(DataError, match="research_contract_id"):
        store.create_strategy_version(
            LEGACY_PROJECT_ID,
            strategy_name="backdated_bypass_attempt",
            source_fingerprint="git:must-still-be-governed",
            definition={},
            parameter_space={},
            at=START + timedelta(minutes=2),
        )


def test_lost_governance_row_is_not_silently_recreated_on_reopen(tmp_path: Path) -> None:
    """A missing governance row must stay missing; reopen must not re-derive it from created_at."""
    store = ControlStore(tmp_path)
    store.create_project(
        name="Backdated governed project",
        hypothesis="Reopening the store must not re-derive governance from created_at.",
        falsification_criterion="Reject if schema scripts recreate governance rows.",
        project_id=PROJECT_ID,
        at=datetime(2026, 8, 5, 23, 59, tzinfo=UTC),
    )
    database = tmp_path / "control" / control_store_module.DATABASE_NAME
    connection = sqlite3.connect(database)
    try:
        deleted = connection.execute(
            "DELETE FROM project_research_governance WHERE project_id = ?", (PROJECT_ID,)
        )
        assert deleted.rowcount == 1
        connection.commit()
    finally:
        connection.close()

    with contextlib.suppress(DataError):
        ControlStore(tmp_path).list_projects()

    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            "SELECT research_required, origin FROM project_research_governance"
            " WHERE project_id = ?",
            (PROJECT_ID,),
        ).fetchall()
    finally:
        connection.close()
    assert rows == []


def test_read_projection_does_not_take_the_writer_lock_at_open(tmp_path: Path) -> None:
    """Steady-state opens must issue no write-bearing statement, so reads never contend."""
    store = ControlStore(tmp_path)
    _project(store)
    database = tmp_path / "control" / control_store_module.DATABASE_NAME
    writer = sqlite3.connect(database)
    try:
        writer.execute("BEGIN IMMEDIATE")
        projects = ControlStore(tmp_path).list_projects()
    finally:
        writer.close()
    assert [row["project_id"] for row in projects] == [PROJECT_ID]


@pytest.mark.parametrize(
    "fault_label",
    ["project", "governance", "scope", "contract", "captured", "execution", "d2", "triage"],
)
def test_research_capture_is_atomic_and_retry_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault_label: str
) -> None:
    store = ControlStore(tmp_path)
    payload = draft_exploration_contract(
        "SPY double bottoms may precede positive four-hour returns."
    )
    kwargs = {
        "name": "Atomic capture fixture",
        "hypothesis": "SPY double bottoms may precede positive four-hour returns.",
        "falsification_criterion": "Reject when registered controls do not support the claim.",
        "draft_payload": payload,
        "created_by": "codex",
        "next_action": "Owner answers the material question batch.",
        "responsibility": "owner",
        "blocker": "The chart, event time, and outcome are unresolved.",
        "recovery": "Answer the bounded question batch.",
    }
    original = ControlStore._capture_fault_checkpoint

    def fail_at(label: str) -> None:
        if label == fault_label:
            raise DataError(f"fault after {label}")

    monkeypatch.setattr(ControlStore, "_capture_fault_checkpoint", staticmethod(fail_at))
    with pytest.raises(DataError, match=f"fault after {fault_label}"):
        store.capture_research_case(**kwargs)  # type: ignore[arg-type]
    assert store.list_projects() == []
    # Row-level proof of atomicity: no partial write survives in ANY capture-touched table.
    database = tmp_path / "control" / control_store_module.DATABASE_NAME
    connection = sqlite3.connect(database)
    try:
        for table in (
            "projects",
            "project_research_governance",
            "project_scope_events",
            "research_contracts",
            "research_phase_events",
            "research_execution_events",
            "research_d2_events",
        ):
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # noqa: S608
            assert count == (0,), f"partial {table} row survived the {fault_label} fault"
    finally:
        connection.close()

    monkeypatch.setattr(ControlStore, "_capture_fault_checkpoint", staticmethod(original))
    first = store.capture_research_case(**kwargs)  # type: ignore[arg-type]
    replay = store.capture_research_case(**kwargs)  # type: ignore[arg-type]
    assert replay == first
    assert len(store.list_projects()) == 1
    assert cast(dict[str, object], first["case"])["phase"] == "triage"


def test_schema_v1_migration_rejects_a_stale_valid_backup(tmp_path: Path) -> None:
    root = tmp_path / "control"
    root.mkdir()
    database = root / "workstation.sqlite3"
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
    first = (
        LEGACY_PROJECT_ID,
        "Original v1 project",
        "Original hypothesis",
        "Original falsifier",
        "active",
        None,
        None,
        "2026-08-05T23:58:00.000000Z",
        "2026-08-05T23:58:00.000000Z",
    )
    connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", first)
    connection.commit()
    connection.close()
    backup = root / "workstation.sqlite3.v1.bak"
    shutil.copyfile(database, backup)

    connection = sqlite3.connect(database)
    second = (
        PROJECT_ID,
        "Later committed v1 project",
        "Later hypothesis",
        "Later falsifier",
        "active",
        None,
        None,
        "2026-08-05T23:59:00.000000Z",
        "2026-08-05T23:59:00.000000Z",
    )
    connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", second)
    connection.commit()
    connection.close()

    with pytest.raises(DataError, match="backup does not match the current database"):
        ControlStore(tmp_path).list_projects()

    source = sqlite3.connect(database)
    retained_backup = sqlite3.connect(backup)
    try:
        assert source.execute("PRAGMA user_version").fetchone() == (1,)
        assert source.execute("SELECT COUNT(*) FROM projects").fetchone() == (2,)
        assert retained_backup.execute("SELECT COUNT(*) FROM projects").fetchone() == (1,)
    finally:
        source.close()
        retained_backup.close()


def test_sources_contracts_reuse_content_ids_and_owner_reviews_fail_closed(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    pack_id = _source_pack(store)
    contract = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=_payload(pack_id),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    reused = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=_payload(pack_id),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=30),
    )
    contract_id = str(contract["contract_id"])
    assert reused == contract
    assert contract_id.startswith("rc_")
    assert pack_id.startswith("sp_")

    with pytest.raises(DataError, match="owner review requires a human actor"):
        store.review_research_contract(
            PROJECT_ID,
            contract_id,
            scope="exploration",
            decision="approve",
            actor="codex",
            actor_kind="agent",
            reason="Agents cannot approve themselves.",
        )
    with pytest.raises(DataError, match="approved exploration parent"):
        store.create_research_contract(
            PROJECT_ID,
            scope="confirmation",
            parent_contract_id=contract_id,
            payload=_payload(pack_id, confirmation=True),
            created_by="codex",
            author_kind="agent",
        )

    store.transition_research_phase(
        PROJECT_ID,
        to_phase="triage",
        contract_id=contract_id,
        actor="codex",
        reason="The idea is ready for triage.",
        next_action="Prepare the review packet.",
        responsibility="codex",
        at=START + timedelta(minutes=31),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="exploration_review",
        contract_id=contract_id,
        actor="codex",
        reason="The review packet is complete.",
        next_action="Approve or reject exploration.",
        responsibility="owner",
        at=START + timedelta(minutes=32),
    )
    review = store.review_research_contract(
        PROJECT_ID,
        contract_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Approved for exploration.",
        at=START + timedelta(minutes=33),
    )
    assert review["decision"] == "approve"
    assert store.get_research_contract(contract_id)["review_state"] == "approved"


def test_phase_confirmation_and_d2_state_machines_are_distinct(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    pack_id = _source_pack(store)
    payload = _payload(pack_id)
    exploration = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    exploration_id = str(exploration["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="triage",
        contract_id=exploration_id,
        actor="codex",
        reason="The idea has enough detail for triage.",
        next_action="Check data and literature feasibility.",
        responsibility="codex",
        at=START + timedelta(minutes=4),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="exploration_review",
        contract_id=exploration_id,
        actor="codex",
        reason="The exploration protocol is ready for owner review.",
        next_action="Approve or reject the exploration contract.",
        responsibility="owner",
        at=START + timedelta(minutes=5),
    )
    with pytest.raises(DataError, match="exploration approval"):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase="pilot",
            contract_id=exploration_id,
            actor="codex",
            reason="Must not skip D1 approval.",
            next_action="Run the pilot.",
            responsibility="codex",
        )
    store.review_research_contract(
        PROJECT_ID,
        exploration_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Exploration approved.",
        at=START + timedelta(minutes=6),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=exploration_id,
        actor="codex",
        reason="Advance to pilot.",
        next_action="Execute pilot work.",
        responsibility="codex",
        at=START + timedelta(minutes=7),
    )
    _record_completed_d0(
        store,
        exploration_id,
        _payload(pack_id),
        at=START + timedelta(minutes=7, seconds=30),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="deep_research",
        contract_id=exploration_id,
        actor="codex",
        reason="Advance to deep_research.",
        next_action="Execute deep_research work.",
        responsibility="codex",
        at=START + timedelta(minutes=8),
    )
    confirmation_payload = _payload(pack_id, confirmation=True)
    confirmation = store.create_research_contract(
        PROJECT_ID,
        scope="confirmation",
        parent_contract_id=exploration_id,
        payload=confirmation_payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=9),
    )
    confirmation_id = str(confirmation["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="confirmation_review",
        contract_id=confirmation_id,
        actor="codex",
        reason="The child confirmation contract is frozen for review.",
        next_action="Approve or reject D2 consumption.",
        responsibility="owner",
        at=START + timedelta(minutes=10),
    )
    summary = store.research_case_summary(PROJECT_ID)
    assert summary["d2_state"] == "sealed"
    assert summary["confirmation_review"]["state"] == "pending"  # type: ignore[index]

    store.review_research_contract(
        PROJECT_ID,
        confirmation_id,
        scope="confirmation",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Authorize the exact child contract, without consuming D2 yet.",
        at=START + timedelta(minutes=11),
    )
    assert store.research_case_summary(PROJECT_ID)["d2_state"] == "authorized"
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="sealed_confirmation",
        contract_id=confirmation_id,
        actor="codex",
        reason="The child contract is approved and D2 remains sealed until execution.",
        next_action="Run the sealed confirmation once.",
        responsibility="codex",
        at=START + timedelta(minutes=12),
    )
    with pytest.raises(DataError, match="D2 must be consumed"):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase="research_decision",
            contract_id=confirmation_id,
            actor="codex",
            reason="Cannot decide before confirmation executes.",
            next_action="Draft the research decision.",
            responsibility="codex",
        )
    store.transition_research_d2_state(
        PROJECT_ID,
        confirmation_id,
        to_state="consumed",
        actor="system",
        reason="The exact sealed confirmation job started.",
        at=START + timedelta(minutes=13),
    )
    gate_evidence = _confirmation_evidence("SUPPORTED")
    gate_evidence_bytes = json.dumps(
        gate_evidence,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    run_id = _write_research_run(
        tmp_path,
        run_id="e500000000000005",
        contract_id=confirmation_id,
        payload=confirmation_payload,
        evidence_zone="D2",
        gate_evidence=gate_evidence,
    )
    store.record_research_attempt(
        PROJECT_ID,
        confirmation_id,
        kind="sealed-confirmation",
        status="completed",
        config_fingerprint="a" * 64,
        budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
        details={
            "evidence_zone": "D2",
            "real_market_evidence": True,
            "gate_packet_evidence_ref": {
                "artifact": "research_gate_evidence.json",
                "content_sha256": hashlib.sha256(gate_evidence_bytes).hexdigest(),
            },
        },
        run_id=run_id,
        at=START + timedelta(minutes=13, seconds=30),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="research_decision",
        contract_id=confirmation_id,
        actor="codex",
        reason="Confirmation results are ready for a decision.",
        next_action="Owner accepts, rejects, or revises the research conclusion.",
        responsibility="owner",
        at=START + timedelta(minutes=14),
    )
    final = store.research_case_summary(PROJECT_ID)
    assert final["phase"] == "research_decision"
    assert final["d2_state"] == "consumed"
    assert final["d3_state"] == "not_sealed"
    assert final["next_action"] == ("Owner accepts, rejects, or revises the research conclusion.")
    assert final["responsibility"] == "owner"


def test_execution_attempts_and_budget_projection_are_independent(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    pack_id = _source_pack(store)
    payload = _payload(pack_id)
    exploration = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    exploration_id = str(exploration["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="triage",
        contract_id=exploration_id,
        actor="codex",
        reason="The idea is ready for triage.",
        next_action="Prepare exploration review.",
        responsibility="codex",
        at=START + timedelta(minutes=4),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="exploration_review",
        contract_id=exploration_id,
        actor="codex",
        reason="The contract is ready for review.",
        next_action="Approve or reject exploration.",
        responsibility="owner",
        at=START + timedelta(minutes=5),
    )
    store.review_research_contract(
        PROJECT_ID,
        exploration_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Approve the bounded pilot.",
        at=START + timedelta(minutes=6),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=exploration_id,
        actor="codex",
        reason="Exploration was approved.",
        next_action="Run the pilot.",
        responsibility="codex",
        at=START + timedelta(minutes=7),
    )
    store.transition_research_execution(
        PROJECT_ID,
        to_state="queued",
        contract_id=exploration_id,
        actor="codex",
        reason="The approved pilot is queued.",
        next_action="Acquire the research worker.",
        responsibility="codex",
        checkpoint="pilot:queued",
        at=START + timedelta(minutes=8),
    )
    store.transition_research_execution(
        PROJECT_ID,
        to_state="running",
        contract_id=exploration_id,
        actor="system",
        reason="The pilot worker started.",
        next_action="Evaluate the registered variants.",
        responsibility="codex",
        checkpoint="pilot:variant-1",
        at=START + timedelta(minutes=9),
    )
    run_id = _write_research_run(
        tmp_path,
        run_id="d000000000000001",
        contract_id=exploration_id,
        payload=payload,
    )
    attempt = store.record_research_attempt(
        PROJECT_ID,
        exploration_id,
        kind="d0-synthetic-pilot",
        status="completed",
        config_fingerprint="a" * 64,
        budget_used={"wall_seconds": 600, "source_requests": 4, "variants": 8},
        details={
            "effect": 0.0012,
            "evidence_zone": "D0",
            "d0_acceptance_ref": _d0_acceptance_ref(tmp_path, run_id),
        },
        run_id=run_id,
        at=START + timedelta(minutes=10),
    )
    assert str(attempt["attempt_id"]).startswith("ra_")
    store.transition_research_execution(
        PROJECT_ID,
        to_state="paused",
        contract_id=exploration_id,
        actor="codex",
        reason="Pause at the deterministic checkpoint for owner input.",
        next_action="Review the pilot confounder table.",
        responsibility="owner",
        checkpoint="pilot:variant-8",
        blocker="The weekday control changes the effect sign.",
        recovery="Owner chooses whether the mechanism remains plausible.",
        at=START + timedelta(minutes=11),
    )
    summary = store.research_case_summary(PROJECT_ID)
    assert summary["execution_state"] == "paused"
    assert summary["checkpoint"] == "pilot:variant-8"
    assert summary["blocker"] == "The weekday control changes the effect sign."
    assert summary["elapsed_budget"] == {
        "source_requests": 4,
        "variants": 8,
        "wall_seconds": 600,
    }
    assert summary["remaining_budget"] == {
        "source_requests": 56,
        "variants": 120,
        "wall_seconds": 13_800,
    }
    assert isinstance(summary["milestones"], list)


def test_governed_strategy_and_experiment_bind_exact_confirmation_contract(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(store)
    with pytest.raises(DataError, match="research_contract_id"):
        store.create_strategy_version(
            PROJECT_ID,
            strategy_name="double_bottom",
            source_fingerprint="git:3333333",
            definition={"detector": "causal-double-bottom-v1"},
            parameter_space={"tolerance": [0.005, 0.01]},
            at=START + timedelta(minutes=7),
        )
    version = store.create_strategy_version(
        PROJECT_ID,
        strategy_name="double_bottom",
        source_fingerprint="git:3333333",
        definition={"detector": "causal-double-bottom-v1"},
        parameter_space={"tolerance": [0.005, 0.01]},
        research_contract_id=confirmation_id,
        at=START + timedelta(minutes=7),
    )
    assert version["research_contract_id"] == confirmation_id
    version_id = str(version["version_id"])
    with pytest.raises(DataError, match="matching research_contract_id"):
        store.create_experiment_spec(
            PROJECT_ID,
            strategy_version_id=version_id,
            snapshot_id="snapshot-spy",
            universe=["SPY"],
            split_policy={"train": 504, "test": 63},
            costs={"fee_bps": 1},
            seeds={"master": 7},
        )
    experiment = store.create_experiment_spec(
        PROJECT_ID,
        strategy_version_id=version_id,
        snapshot_id="snapshot-spy",
        universe=["SPY"],
        split_policy={"train": 504, "test": 63},
        costs={"fee_bps": 1},
        seeds={"master": 7},
        research_contract_id=confirmation_id,
        at=START + timedelta(minutes=8),
    )
    assert experiment["research_contract_id"] == confirmation_id

    store.create_project(
        name="Grandfathered mean reversion",
        hypothesis="Large daily deviations mean-revert after costs.",
        falsification_criterion="Reject when locked OOS Sharpe is non-positive.",
        project_id=LEGACY_PROJECT_ID,
        at=datetime(2026, 8, 5, 23, 59, tzinfo=UTC),
    )
    mark_project_as_migrated_legacy(store, LEGACY_PROJECT_ID)
    legacy = store.create_strategy_version(
        LEGACY_PROJECT_ID,
        strategy_name="mean_reversion",
        source_fingerprint="git:legacy",
        definition={"window": 20},
        parameter_space={"window": [20]},
        at=START + timedelta(minutes=9),
    )
    identity = {
        "schema_version": 1,
        "strategy_name": "mean_reversion",
        "source_fingerprint": "git:legacy",
        "definition": {"window": 20},
        "parameter_space": {"window": [20]},
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False)
    expected_id = f"sv_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
    assert legacy["version_id"] == expected_id
    assert "research_contract_id" not in legacy


def test_incomplete_draft_cannot_cross_exploration_review(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    draft = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload={
            "schema": "ResearchContractV1",
            "approval_ready": False,
            "blocking_questions": ["What exactly counts as a bounce?"],
            "thesis": {"raw_idea": "SPY double bottoms bounce"},
            "source_pack_id": None,
        },
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=1),
    )
    contract_id = str(draft["contract_id"])
    for minute, phase in ((2, "triage"), (3, "exploration_review")):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase=phase,  # type: ignore[arg-type]
            contract_id=contract_id,
            actor="codex",
            reason=f"Move the draft to {phase}.",
            next_action="Resolve the blocking questions.",
            responsibility="owner",
            at=START + timedelta(minutes=minute),
        )
    with pytest.raises(DataError, match="approval_ready=true"):
        store.review_research_contract(
            PROJECT_ID,
            contract_id,
            scope="exploration",
            decision="approve",
            actor="owner",
            actor_kind="human",
            reason="An incomplete draft must not be approvable.",
        )
    summary = store.research_case_summary(PROJECT_ID)
    assert summary["exploration_review"]["state"] == "pending"  # type: ignore[index]
    assert summary["d2_state"] == "sealed"


@pytest.mark.parametrize("mutation", ["hash", "dataset", "share", "chart"])
def test_approval_recomputes_canonical_d2_boundary_semantics(tmp_path: Path, mutation: str) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    payload = _payload(_source_pack(store))
    protocol = cast(dict[str, object], payload["protocol"])
    topology = cast(dict[str, object], protocol["evidence_topology"])
    d2 = cast(dict[str, object], topology["D2"])
    boundary = cast(dict[str, object], topology["boundary"])
    if mutation == "hash":
        d2["boundary_hash"] = "f" * 64
    elif mutation == "dataset":
        boundary["dataset_fingerprint"] = "f" * 64
    elif mutation == "share":
        cast(dict[str, object], topology["D1"])["share"] = 0.50
    else:
        chart = cast(dict[str, object], protocol["chart_fingerprint"])
        chart["instrument"] = "ES"
    contract = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    contract_id = str(contract["contract_id"])
    for minute, phase in ((4, "triage"), (5, "exploration_review")):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase=phase,  # type: ignore[arg-type]
            contract_id=contract_id,
            actor="codex",
            reason=f"Advance to {phase}.",
            next_action="Validate the canonical boundary.",
            responsibility="owner" if phase == "exploration_review" else "codex",
            at=START + timedelta(minutes=minute),
        )
    with pytest.raises(DataError, match="boundary|share|chart"):
        store.review_research_contract(
            PROJECT_ID,
            contract_id,
            scope="exploration",
            decision="approve",
            actor="owner",
            actor_kind="human",
            reason="A mutated boundary must fail closed.",
        )


def test_production_gate_hard_disables_unreleased_empirical_research(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(control_store_module, "_UNRELEASED_EMPIRICAL_RESEARCH_ENABLED", False)
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    _record_completed_d0(
        store,
        contract_id,
        payload,
        at=START + timedelta(minutes=7, seconds=30),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="deep_research",
        contract_id=contract_id,
        actor="codex",
        reason="D0 is complete.",
        next_action="Stop because D1 is not shipped.",
        responsibility="codex",
        at=START + timedelta(minutes=8),
    )
    with pytest.raises(DataError, match="empirical D1/D2 attempts remain hard-disabled"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="event-study",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1},
        )
    with pytest.raises(DataError, match="D2 access remains hard-disabled"):
        store.transition_research_d2_state(
            PROJECT_ID,
            contract_id,
            to_state="consumed",
            actor="system",
            reason="This must never open D2 in Gate 1.",
        )

    confirmation = store.create_research_contract(
        PROJECT_ID,
        scope="confirmation",
        payload=_payload(str(payload["source_pack_id"]), confirmation=True),
        created_by="codex",
        author_kind="agent",
        parent_contract_id=contract_id,
        at=START + timedelta(minutes=9),
    )
    confirmation_id = str(confirmation["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="confirmation_review",
        contract_id=confirmation_id,
        actor="codex",
        reason="Present the frozen child while Gate 3 remains disabled.",
        next_action="Do not approve until the empirical authority exists.",
        responsibility="owner",
        at=START + timedelta(minutes=10),
    )
    with pytest.raises(DataError, match="confirmation approval remains hard-disabled"):
        store.review_research_contract(
            PROJECT_ID,
            confirmation_id,
            scope="confirmation",
            decision="approve",
            actor="owner",
            actor_kind="human",
            reason="This production-disabled action must fail.",
            at=START + timedelta(minutes=11),
        )


def test_early_inconclusive_decision_keeps_d2_sealed_and_cannot_advance(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    pack_id = _source_pack(store)
    exploration = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=_payload(pack_id),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    contract_id = str(exploration["contract_id"])
    for minute, phase, responsibility in (
        (4, "triage", "codex"),
        (5, "exploration_review", "owner"),
    ):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase=phase,  # type: ignore[arg-type]
            contract_id=contract_id,
            actor="codex",
            reason=f"Advance to {phase}.",
            next_action="Complete the current gate.",
            responsibility=responsibility,  # type: ignore[arg-type]
            at=START + timedelta(minutes=minute),
        )
    store.review_research_contract(
        PROJECT_ID,
        contract_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Approve the pilot only.",
        at=START + timedelta(minutes=6),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=contract_id,
        actor="codex",
        reason="The pilot is authorized.",
        next_action="Run the power diagnostic.",
        responsibility="codex",
        at=START + timedelta(minutes=7),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="research_decision",
        contract_id=contract_id,
        actor="codex",
        reason="The pilot cannot reach the preregistered power target.",
        next_action="Park the idea or obtain more qualified data.",
        responsibility="owner",
        blocker="Insufficient independent events for target power.",
        recovery="Acquire more history without opening D2 or park the idea.",
        at=START + timedelta(minutes=8),
    )
    decision = store.record_research_decision(
        PROJECT_ID,
        contract_id,
        outcome="INCONCLUSIVE",
        disposition="park",
        actor="owner",
        actor_kind="human",
        reason="Power is insufficient; D2 remains sealed.",
        at=START + timedelta(minutes=9),
    )
    assert decision["outcome"] == "INCONCLUSIVE"
    summary = store.research_case_summary(PROJECT_ID)
    assert summary["d2_state"] == "sealed"
    assert summary["confirmation_contract_id"] is None
    with pytest.raises(DataError, match="approved confirmation contract"):
        store.create_strategy_version(
            PROJECT_ID,
            strategy_name="double_bottom",
            source_fingerprint="git:abcdef123456",
            definition={"detector": "v1"},
            parameter_space={},
            research_contract_id=contract_id,
        )


def test_evidence_free_and_d0_only_paths_cannot_claim_contradicted(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, _ = _approved_pilot(store)

    with pytest.raises(DataError, match="only as INCONCLUSIVE or INVALID"):
        store.close_early_research_case(
            PROJECT_ID,
            outcome="CONTRADICTED",
            disposition="reject",
            actor="owner",
            reason="No typed non-synthetic evidence exists.",
            at=START + timedelta(minutes=8),
        )

    store.transition_research_phase(
        PROJECT_ID,
        to_phase="research_decision",
        contract_id=contract_id,
        actor="system",
        reason="Stop before any empirical evidence is available.",
        next_action="Owner records an inconclusive or invalid early disposition.",
        responsibility="owner",
        at=START + timedelta(minutes=9),
    )
    with pytest.raises(DataError, match="typed non-synthetic evidence"):
        store.record_research_decision(
            PROJECT_ID,
            contract_id,
            outcome="CONTRADICTED",
            disposition="reject",
            actor="owner",
            actor_kind="human",
            reason="D0 cannot contradict a market thesis.",
            at=START + timedelta(minutes=10),
        )

    summary = store.research_case_summary(PROJECT_ID)
    assert summary["research_decision"] is None
    assert summary["d2_state"] == "sealed"


def test_generic_research_jobs_remain_reserved(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="reserved"):
        ControlStore(tmp_path).create_job(kind="research:event-study", request={})


def test_confirmation_decision_requires_one_mechanically_classified_d2_attempt(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(
        store,
        record_confirmation_evidence=False,
        record_decision=False,
        transition_to_decision=False,
    )

    with pytest.raises(DataError, match="typed D2 evidence"):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase="research_decision",
            contract_id=confirmation_id,
            actor="owner",
            reason="A consumed boundary alone cannot establish support.",
            next_action="Do not present an evidence-free decision.",
            responsibility="owner",
            at=START + timedelta(minutes=15),
        )


def test_confirmation_decision_cannot_override_mechanical_d2_classification(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(
        store,
        outcome="INCONCLUSIVE",
        disposition="park",
        record_decision=False,
    )

    with pytest.raises(DataError, match="mechanical D2 classification"):
        store.record_research_decision(
            PROJECT_ID,
            confirmation_id,
            outcome="SUPPORTED",
            disposition="advance_to_strategy",
            actor="owner",
            actor_kind="human",
            reason="The owner cannot relabel an inconclusive result as support.",
            at=START + timedelta(minutes=15),
        )


def test_contaminated_confirmation_can_close_only_as_invalid(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(
        store,
        record_confirmation_evidence=False,
        record_decision=False,
        d2_state="contaminated",
    )

    decision = store.record_research_decision(
        PROJECT_ID,
        confirmation_id,
        outcome="INVALID",
        disposition="park",
        actor="owner",
        actor_kind="human",
        reason="The contaminated lineage cannot answer the claim.",
        at=START + timedelta(minutes=15),
    )
    assert decision["outcome"] == "INVALID"


def test_research_attempt_accepts_only_exact_contract_bound_run(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    run_id = _write_research_run(
        tmp_path,
        run_id="a100000000000001",
        contract_id=contract_id,
        payload=payload,
    )

    attempt = store.record_research_attempt(
        PROJECT_ID,
        contract_id,
        kind="d0-synthetic-pilot",
        status="completed",
        config_fingerprint="a" * 64,
        budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
        details={
            "evidence_zone": "D0",
            "d0_acceptance_ref": _d0_acceptance_ref(tmp_path, run_id),
        },
        run_id=run_id,
        at=START + timedelta(minutes=8),
    )

    assert attempt["run_id"] == run_id


def test_research_run_admission_rejects_legacy_manifest_downgrade(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    contract_id = "rc_" + "2" * 64
    payload = _run_only_payload()
    run_id = _write_research_run(
        tmp_path,
        run_id="a100000000000002",
        contract_id=contract_id,
        payload=payload,
    )
    manifest_path = tmp_path / "runs" / run_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    manifest["run_identity_version"] = 1
    manifest.pop("artifact_contract_version")
    manifest.pop("artifacts")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    with pytest.raises(DataError, match="immutable v3"):
        store._require_research_run(
            run_id,
            project_id=PROJECT_ID,
            contract_id=contract_id,
            contract_payload=payload,
            phase="pilot",
            config_fingerprint="a" * 64,
        )


def test_research_run_admission_rejects_self_consistent_but_underived_run_id(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    contract_id = "rc_" + "6" * 64
    payload = _run_only_payload()
    derived_run_id = _write_research_run(
        tmp_path,
        run_id="ignored-content-derived-id",
        contract_id=contract_id,
        payload=payload,
    )
    forged_run_id = "f" * 16
    assert forged_run_id != derived_run_id
    source = tmp_path / "runs" / derived_run_id
    target = tmp_path / "runs" / forged_run_id
    source.rename(target)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["run_id"] = forged_run_id
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    with pytest.raises(DataError, match="content-derived identity"):
        store._require_research_run(
            forged_run_id,
            project_id=PROJECT_ID,
            contract_id=contract_id,
            contract_payload=payload,
            phase="pilot",
            config_fingerprint="a" * 64,
        )


def test_generic_evidence_ledger_rejects_research_runs(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    contract_id = "rc_" + "3" * 64
    payload = _run_only_payload()
    run_id = _write_research_run(
        tmp_path,
        run_id="a100000000000003",
        contract_id=contract_id,
        payload=payload,
    )

    with pytest.raises(DataError, match="research runs cannot enter the generic evidence ledger"):
        store.create_evidence(
            claim="Synthetic double-bottom acceptance predicts real SPY returns.",
            assets=["SPY"],
            frozen_universe=["SPY"],
            timeframe="4h",
            method="synthetic_fixture",
            knowledge_at=START + timedelta(minutes=8),
            author="codex",
            author_kind="agent",
            source_run_id=run_id,
            source_artifact="manifest.json",
            source_field="outcomes.planted_pattern.passed",
            at=START + timedelta(minutes=8),
        )

    assert store.list_evidence() == []


def test_pilot_rejects_typed_d1_evidence_without_linking_an_attempt(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    run_id = _write_research_run(
        tmp_path,
        run_id="d100000000000001",
        contract_id=contract_id,
        payload=payload,
    )
    manifest = _artifacts.read_manifest(tmp_path / "runs" / run_id)
    acceptance_metadata = manifest["artifacts"]["d0_acceptance.json"]

    with pytest.raises(DataError, match="D0 pilot cannot carry typed D1 or D2"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={
                "evidence_zone": "D0",
                "gate_packet_evidence_ref": {
                    "artifact": "d0_acceptance.json",
                    "content_sha256": acceptance_metadata["sha256"],
                },
            },
            run_id=run_id,
            at=START + timedelta(minutes=8),
        )
    assert store.research_case_summary(PROJECT_ID)["attempt_count"] == 0


def test_pilot_cannot_forge_completion_or_advance_without_passing_run(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    with pytest.raises(DataError, match="exactly one completed immutable D0"):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase="deep_research",
            contract_id=contract_id,
            actor="codex",
            reason="A direct transition must fail.",
            next_action="Keep D1 closed.",
            responsibility="codex",
        )
    with pytest.raises(DataError, match="only the registered d0-synthetic-pilot"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="arbitrary-pilot",
            status="failed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1},
            details={"evidence_zone": "D0"},
            error="expected fixture rejection",
        )
    with pytest.raises(DataError, match="immutable run_id"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1},
            details={"evidence_zone": "D0"},
        )

    run_id = _write_research_run(
        tmp_path,
        run_id="d100000000000002",
        contract_id=contract_id,
        payload=payload,
    )
    run_dir = tmp_path / "runs" / run_id
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
    manifest["outcomes"] = {
        "planted_pattern": {"passed": True},
        "monotonic_null": {"passed": True},
        "single_trough_null": {"passed": True},
        "prospective_power_fixture": {"passed": True},
    }
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    with pytest.raises(DataError, match="exact deterministic recomputation"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1},
            details={"evidence_zone": "D0"},
            run_id=run_id,
        )
    assert store.research_case_summary(PROJECT_ID)["attempt_count"] == 0


def test_post_admission_d0_rewrite_fails_recovery_summary_and_packet_reads(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    run_id = _record_completed_d0(
        store,
        contract_id,
        payload,
        at=START + timedelta(minutes=8),
    )
    before = store.research_case_summary(PROJECT_ID)
    attempt_id = cast(str, before["latest_attempt_id"])

    store.transition_research_phase(
        PROJECT_ID,
        to_phase="research_decision",
        contract_id=contract_id,
        actor="system",
        reason="Simulate recovery after the completed D0 attempt was recorded.",
        next_action="Owner records an evidence-bounded disposition.",
        responsibility="owner",
        at=START + timedelta(minutes=9),
    )
    store.record_research_decision(
        PROJECT_ID,
        contract_id,
        outcome="INCONCLUSIVE",
        disposition="park",
        actor="owner",
        actor_kind="human",
        reason="D0 alone cannot answer the market claim.",
        at=START + timedelta(minutes=10),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="closed",
        contract_id=contract_id,
        actor="owner",
        reason="Close the synthetic-only case.",
        next_action="Revise only through a new immutable lineage.",
        responsibility="owner",
        at=START + timedelta(minutes=11),
    )

    database = sqlite3.connect(tmp_path / "control" / "workstation.sqlite3")
    stored_details = cast(
        str,
        database.execute(
            "SELECT details_json FROM research_attempt_records WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()[0],
    )
    mismatched_details = json.loads(stored_details)
    mismatched_details["d0_acceptance_ref"]["content_sha256"] = "f" * 64
    database.execute(
        "UPDATE research_attempt_records SET details_json = ? WHERE attempt_id = ?",
        (
            json.dumps(mismatched_details, sort_keys=True, separators=(",", ":")),
            attempt_id,
        ),
    )
    database.commit()
    with pytest.raises(DataError, match="exact typed acceptance artifact provenance"):
        store.verified_research_attempt(PROJECT_ID, attempt_id)
    database.execute(
        "UPDATE research_attempt_records SET details_json = ? WHERE attempt_id = ?",
        (stored_details, attempt_id),
    )
    database.commit()
    database.close()

    _rewrite_d0_acceptance_and_manifest(tmp_path, run_id)

    with pytest.raises(DataError, match="exact deterministic recomputation"):
        store.verified_research_attempt(PROJECT_ID, attempt_id)
    with pytest.raises(DataError, match="exact deterministic recomputation"):
        store.research_case_summary(PROJECT_ID)
    with pytest.raises(DataError, match="exact deterministic recomputation"):
        store.research_gate_packet_inputs(PROJECT_ID)


def test_pilot_advancement_requires_idle_execution_after_passing_run(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    _record_completed_d0(
        store,
        contract_id,
        payload,
        at=START + timedelta(minutes=8),
    )
    store.transition_research_execution(
        PROJECT_ID,
        to_state="queued",
        contract_id=contract_id,
        actor="codex",
        reason="Keep the worker active during the adversarial transition.",
        next_action="Do not advance while work is queued.",
        responsibility="codex",
        checkpoint="d0:complete",
        at=START + timedelta(minutes=9),
    )
    with pytest.raises(DataError, match="requires idle execution"):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase="deep_research",
            contract_id=contract_id,
            actor="codex",
            reason="A queued worker cannot advance authority.",
            next_action="Return execution to idle first.",
            responsibility="codex",
            at=START + timedelta(minutes=10),
        )


def test_confirmation_attempt_rejects_inline_or_missing_evidence_artifacts(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(
        store,
        record_confirmation_evidence=False,
        record_decision=False,
        transition_to_decision=False,
    )
    contract = store.get_research_contract(confirmation_id)
    payload = cast(dict[str, object], contract["payload"])
    evidence = _confirmation_evidence("SUPPORTED")
    run_id = _write_research_run(
        tmp_path,
        run_id="c300000000000003",
        contract_id=confirmation_id,
        payload=payload,
        evidence_zone="D2",
        gate_evidence=evidence,
    )
    with pytest.raises(DataError, match="inline gate_packet_evidence"):
        store.record_research_attempt(
            PROJECT_ID,
            confirmation_id,
            kind="sealed-confirmation",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={"evidence_zone": "D2", "gate_packet_evidence": evidence},
            run_id=run_id,
            at=START + timedelta(minutes=14),
        )

    missing_run_id = _write_research_run(
        tmp_path,
        run_id="d400000000000004",
        contract_id=confirmation_id,
        payload=payload,
        evidence_zone="D2",
    )
    with pytest.raises(DataError, match="declared immutable artifact"):
        store.record_research_attempt(
            PROJECT_ID,
            confirmation_id,
            kind="sealed-confirmation",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={
                "evidence_zone": "D2",
                "gate_packet_evidence_ref": {
                    "artifact": "research_gate_evidence.json",
                    "content_sha256": "f" * 64,
                },
            },
            run_id=missing_run_id,
            at=START + timedelta(minutes=14),
        )


def test_confirmation_decision_reverifies_evidence_artifact_bytes(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(store, record_decision=False)
    run_id = hashlib.sha256(confirmation_id.encode()).hexdigest()[:16]
    evidence_path = tmp_path / "runs" / run_id / "research_gate_evidence.json"
    evidence_path.write_text("{}", encoding="utf-8")

    with pytest.raises(DataError, match="artifact"):
        store.record_research_decision(
            PROJECT_ID,
            confirmation_id,
            outcome="SUPPORTED",
            disposition="advance_to_strategy",
            actor="owner",
            actor_kind="human",
            reason="Tampered analytical evidence must fail closed.",
            at=START + timedelta(minutes=15),
        )


def test_identical_research_attempt_replay_is_idempotent_before_budget_debit(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    run_id = _write_research_run(
        tmp_path,
        run_id="d000000000000002",
        contract_id=contract_id,
        payload=payload,
    )
    kwargs = {
        "kind": "d0-synthetic-pilot",
        "status": "completed",
        "config_fingerprint": "a" * 64,
        "budget_used": {"wall_seconds": 14_400, "source_requests": 60, "variants": 128},
        "details": {
            "evidence_zone": "D0",
            "d0_acceptance_ref": _d0_acceptance_ref(tmp_path, run_id),
        },
        "run_id": run_id,
    }

    first = store.record_research_attempt(
        PROJECT_ID,
        contract_id,
        **kwargs,  # type: ignore[arg-type]
        at=START + timedelta(minutes=8),
    )
    replay = store.record_research_attempt(
        PROJECT_ID,
        contract_id,
        **kwargs,  # type: ignore[arg-type]
        at=START + timedelta(minutes=9),
    )
    assert replay == first


def test_reserved_d0_terminalization_debits_once_and_blocks_unlinked_bypass(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    store.transition_research_execution(
        PROJECT_ID,
        to_state="queued",
        contract_id=contract_id,
        actor="codex",
        reason="Queue the reserved D0 fixture.",
        next_action="Reserve before computing.",
        responsibility="codex",
        checkpoint="d0:queued",
        at=START + timedelta(minutes=8),
    )
    fingerprint = d0_execution_fingerprint(payload)
    reservation = store.reserve_d0_research_launch(
        PROJECT_ID,
        contract_id,
        config_fingerprint=fingerprint,
        at=START + timedelta(minutes=9),
    )
    assert reservation["launch_number"] == 1
    reserved = store.research_case_summary(PROJECT_ID)
    assert reserved["attempt_count"] == 1
    assert reserved["terminal_attempt_count"] == 0
    assert reserved["unfinalized_launch_count"] == 1
    assert reserved["elapsed_budget"] == {
        "source_requests": 0,
        "variants": 3,
        "wall_seconds": 1,
    }

    with pytest.raises(DataError, match="requires its durable launch reservation"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="failed",
            config_fingerprint=fingerprint,
            budget_used={"wall_seconds": 1},
            details={"attempt_number": 1, "evidence_zone": "D0"},
            error="unlinked terminal bypass",
            at=START + timedelta(minutes=10),
        )

    attempt = store.record_research_attempt(
        PROJECT_ID,
        contract_id,
        kind="d0-synthetic-pilot",
        status="failed",
        config_fingerprint=fingerprint,
        budget_used={},
        details={"attempt_number": 1, "evidence_zone": "D0"},
        error="registered D0 failure",
        launch_reservation_id=str(reservation["reservation_id"]),
        at=START + timedelta(minutes=10),
    )
    assert attempt["budget_used"] == {}
    linked = store.research_case_summary(PROJECT_ID)
    assert linked["attempt_count"] == 1
    assert linked["terminal_attempt_count"] == 1
    assert linked["unfinalized_launch_count"] == 0
    assert linked["elapsed_budget"] == reserved["elapsed_budget"]


def test_unreserved_legacy_d0_attempts_are_capped_at_three(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, _ = _approved_pilot(store)
    recorded: list[dict[str, object]] = []
    for attempt_number in range(1, 4):
        recorded.append(
            store.record_research_attempt(
                PROJECT_ID,
                contract_id,
                kind="d0-synthetic-pilot",
                status="failed",
                config_fingerprint=str(attempt_number) * 64,
                budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
                details={"attempt_number": attempt_number, "evidence_zone": "D0"},
                error=f"legacy direct failure {attempt_number}",
                at=START + timedelta(minutes=7 + attempt_number),
            )
        )
    with pytest.raises(DataError, match="initial attempt and two safe retries"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="failed",
            config_fingerprint="4" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={"attempt_number": 4, "evidence_zone": "D0"},
            error="forbidden fourth direct failure",
            at=START + timedelta(minutes=12),
        )
    assert (
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="failed",
            config_fingerprint="3" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={"attempt_number": 3, "evidence_zone": "D0"},
            error="legacy direct failure 3",
            at=START + timedelta(minutes=20),
        )
        == recorded[-1]
    )


def test_running_reconciliation_requires_explicit_orphan_acknowledgement(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, _ = _approved_pilot(store)
    for state in ("queued", "running"):
        store.transition_research_execution(
            PROJECT_ID,
            to_state=state,
            contract_id=contract_id,
            actor="codex",
            reason=f"Move fixture to {state}.",
            next_action="Continue the deterministic pilot.",
            responsibility="codex",
            checkpoint="d0:prepared",
            at=START + timedelta(minutes=8),
        )

    with pytest.raises(DataError, match="orphan reconciliation acknowledgement"):
        store.transition_research_execution(
            PROJECT_ID,
            to_state="queued",
            contract_id=contract_id,
            actor="owner",
            reason="The prior process was killed.",
            next_action="Retry from the durable checkpoint.",
            responsibility="codex",
            checkpoint="d0:prepared",
            at=START + timedelta(minutes=9),
        )
    reconciled = store.transition_research_execution(
        PROJECT_ID,
        to_state="queued",
        contract_id=contract_id,
        actor="owner",
        reason="The owner verified that the prior process is gone.",
        next_action="Retry from the durable checkpoint.",
        responsibility="codex",
        checkpoint="d0:prepared",
        reconcile_running=True,
        at=START + timedelta(minutes=9),
    )
    assert reconciled["state"] == "queued"


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("project_id", LEGACY_PROJECT_ID),
        ("research_contract_id", "rc_" + "f" * 64),
        ("contract_hash", "b" * 64),
        ("source_pack_id", "sp_" + "e" * 64),
        ("research_fingerprints.code", "wrong-code-fingerprint"),
        ("research_fingerprints.environment", "wrong-environment-fingerprint"),
        ("research_fingerprints.evaluator", "wrong-evaluator-fingerprint"),
        ("research_fingerprints.data", "wrong-dataset-fingerprint"),
        ("evidence_zone", "D1"),
        ("eligible_for_holdout_or_execution", True),
        ("places_orders", True),
    ],
)
def test_research_attempt_rejects_wrong_run_lineage_or_authority(
    tmp_path: Path, field: str, wrong_value: object
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    run_id = _write_research_run(
        tmp_path,
        run_id="b200000000000002",
        contract_id=contract_id,
        payload=payload,
        override=(field, wrong_value),
    )

    with pytest.raises(DataError, match="research run"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={"evidence_zone": "D0"},
            run_id=run_id,
            at=START + timedelta(minutes=8),
        )


def test_gate_packet_inputs_are_complete_deterministic_and_public(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    exploration_id, confirmation_id = _approved_contracts(store)
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="closed",
        contract_id=confirmation_id,
        actor="codex",
        reason="The owner decision is recorded and the research case is closed.",
        next_action="Create a strategy only through the governed linkage.",
        responsibility="owner",
        at=START + timedelta(minutes=16),
    )

    packet = store.research_gate_packet_inputs(PROJECT_ID)
    assert packet == store.research_gate_packet_inputs(PROJECT_ID)
    assert packet["phase"] == "closed"
    assert packet["lineage_contract_ids"] == [exploration_id, confirmation_id]
    contracts = packet["contracts"]
    sources = packet["sources"]
    source_packs = packet["source_packs"]
    review_events = packet["review_events"]
    d2_events = packet["d2_events"]
    decision_events = packet["decision_events"]
    assert isinstance(contracts, list)
    assert isinstance(sources, list)
    assert isinstance(source_packs, list)
    assert isinstance(review_events, list)
    assert isinstance(d2_events, list)
    assert isinstance(decision_events, list)
    assert [contract["contract_id"] for contract in contracts] == [
        exploration_id,
        confirmation_id,
    ]
    assert len(sources) == 1
    assert len(source_packs) == 1
    assert [event["scope"] for event in review_events] == [
        "exploration",
        "confirmation",
    ]
    assert [event["state"] for event in d2_events][-2:] == [
        "authorized",
        "consumed",
    ]
    assert decision_events[0]["disposition"] == "advance_to_strategy"
    with pytest.raises(DataError, match="ledger_limit"):
        store.research_gate_packet_inputs(PROJECT_ID, ledger_limit=1)
    for invalid_limit in (True, 1.5, "10"):
        with pytest.raises(DataError, match="ledger_limit"):
            store.research_gate_packet_inputs(PROJECT_ID, ledger_limit=cast(int, invalid_limit))


def test_revise_reopens_with_new_d2_boundary_without_erasing_consumed_history(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    exploration_id, confirmation_id = _approved_contracts(
        store, outcome="INCONCLUSIVE", disposition="revise"
    )
    old_contract = store.get_research_contract(exploration_id)
    old_payload = old_contract["payload"]
    assert isinstance(old_payload, dict)
    pack_id = str(old_payload["source_pack_id"])

    overlapping = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        parent_contract_id=exploration_id,
        payload=_payload(
            pack_id,
            boundary_seed="baseline-boundary",
            relation_to_prior="non_overlapping_future",
        ),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=16),
    )
    with pytest.raises(DataError, match="distinct D2 boundary"):
        store.reopen_research_revision(
            PROJECT_ID,
            str(overlapping["contract_id"]),
            actor="codex",
            reason="This revision accidentally reuses consumed observations.",
            next_action="Reject the overlapping revision.",
            at=START + timedelta(minutes=17),
        )

    revision_payload = _payload(
        pack_id,
        boundary_seed="future-2027-boundary",
        relation_to_prior="non_overlapping_future",
    )
    revision = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        parent_contract_id=exploration_id,
        payload=revision_payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=18),
    )
    revision_id = str(revision["contract_id"])
    reopened = store.reopen_research_revision(
        PROJECT_ID,
        revision_id,
        actor="codex",
        reason="The owner requested a revised protocol on future observations.",
        next_action="Approve or reject the revised exploration contract.",
        at=START + timedelta(minutes=19),
    )
    assert reopened["phase"] == "exploration_review"
    assert reopened["contract_id"] == revision_id

    summary = store.research_case_summary(PROJECT_ID)
    assert summary["phase"] == "exploration_review"
    assert summary["d2_state"] == "sealed"
    assert summary["d2_boundary_hash"] == _boundary("future-2027-boundary").boundary_sha256
    history = summary["d2_history"]
    assert isinstance(history, list)
    assert {
        "contract_id": confirmation_id,
        "state": "consumed",
        "boundary_hash": _boundary("baseline-boundary").boundary_sha256,
    } in [
        {
            "contract_id": event["contract_id"],
            "state": event["state"],
            "boundary_hash": event["boundary_hash"],
        }
        for event in history
    ]
    store.review_research_contract(
        PROJECT_ID,
        revision_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="The future observation boundary is acceptable.",
        at=START + timedelta(minutes=20),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=revision_id,
        actor="codex",
        reason="Advance the revised study to pilot.",
        next_action="Run the revised D0 pilot.",
        responsibility="codex",
        at=START + timedelta(minutes=21),
    )
    _record_completed_d0(
        store,
        revision_id,
        revision_payload,
        at=START + timedelta(minutes=21, seconds=30),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="deep_research",
        contract_id=revision_id,
        actor="codex",
        reason="Advance the revised study to deep_research.",
        next_action="Prepare the revised confirmation child.",
        responsibility="codex",
        at=START + timedelta(minutes=22),
    )
    overlapping_confirmation = store.create_research_contract(
        PROJECT_ID,
        scope="confirmation",
        parent_contract_id=revision_id,
        payload=_payload(
            pack_id,
            confirmation=True,
            boundary_seed="baseline-boundary",
        ),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=23),
    )
    overlapping_confirmation_id = str(overlapping_confirmation["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="confirmation_review",
        contract_id=overlapping_confirmation_id,
        actor="codex",
        reason="Present the mistakenly overlapping child for fail-closed review.",
        next_action="Reject the mismatched confirmation boundary.",
        responsibility="owner",
        at=START + timedelta(minutes=24),
    )
    with pytest.raises(DataError, match="must match its approved exploration"):
        store.review_research_contract(
            PROJECT_ID,
            overlapping_confirmation_id,
            scope="confirmation",
            decision="approve",
            actor="owner",
            actor_kind="human",
            reason="This must fail because it recycles the prior D2 boundary.",
            at=START + timedelta(minutes=25),
        )

    parked_store = ControlStore(tmp_path / "parked")
    _project(parked_store)
    parked_exploration_id, parked_confirmation_id = _approved_contracts(
        parked_store, outcome="INCONCLUSIVE", disposition="park"
    )
    parked_store.transition_research_phase(
        PROJECT_ID,
        to_phase="closed",
        contract_id=parked_confirmation_id,
        actor="codex",
        reason="The owner parked and closed this research case.",
        next_action="Keep the case closed unless a new idea is captured separately.",
        responsibility="owner",
        at=START + timedelta(minutes=16),
    )
    parked_contract = parked_store.get_research_contract(parked_exploration_id)
    parked_payload = parked_contract["payload"]
    assert isinstance(parked_payload, dict)
    parked_revision = parked_store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        parent_contract_id=parked_exploration_id,
        payload=_payload(
            str(parked_payload["source_pack_id"]),
            boundary_seed="external-replication-boundary",
            relation_to_prior="external_replication",
        ),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=17),
    )
    with pytest.raises(DataError, match="owner disposition 'revise'"):
        parked_store.reopen_research_revision(
            PROJECT_ID,
            str(parked_revision["contract_id"]),
            actor="codex",
            reason="Parked research must remain closed.",
            next_action="Do not reopen.",
            at=START + timedelta(minutes=18),
        )


def _captured_case(store: ControlStore, index: int, *, at: datetime) -> str:
    """Capture one distinct research case and return its project id."""

    result = store.capture_research_case(
        name=f"Backlog case {index}",
        hypothesis=f"Observation {index} may precede positive four-hour returns.",
        falsification_criterion="Reject when registered controls do not support the claim.",
        draft_payload=draft_exploration_contract(
            f"Observation {index} may precede positive four-hour returns."
        ),
        created_by="codex",
        next_action="Owner answers the material question batch.",
        responsibility="owner",
        blocker="The chart, event time, and outcome are unresolved.",
        recovery="Answer the bounded question batch.",
        at=at,
    )
    case = result["case"]
    assert isinstance(case, dict)
    return str(case["project_id"])


def test_list_research_cases_is_bounded_newest_activity_first(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_ids = [
        _captured_case(store, index, at=START + timedelta(minutes=index)) for index in range(3)
    ]
    # A strategy-only project without a research case never appears in the backlog.
    store.create_project(
        name="Strategy-only project",
        hypothesis="Not a research case.",
        falsification_criterion="Not applicable.",
        project_id=LEGACY_PROJECT_ID,
        at=START + timedelta(minutes=30),
    )

    rows = store.list_research_cases()
    assert [cast(dict[str, object], row["case"])["project_id"] for row in rows] == list(
        reversed(project_ids)
    )
    for row in rows:
        assert set(row) == {"case", "updated_at"}
        case = row["case"]
        assert isinstance(case, dict)
        # The per-case shape is byte-identical to the canonical single-case summary.
        assert case == store.research_case_summary(str(case["project_id"]))
        assert isinstance(row["updated_at"], str) and row["updated_at"]

    # Later research activity (an execution transition) moves that case to the front.
    oldest = project_ids[0]
    summary = store.research_case_summary(oldest)
    store.transition_research_execution(
        oldest,
        to_state="blocked",
        contract_id=str(summary["active_contract_id"]),
        actor="owner",
        reason="Owner paused triage pending data access.",
        next_action="Restore data access before continuing triage.",
        responsibility="owner",
        blocker="Data access is unavailable.",
        recovery="Restore data access.",
        at=START + timedelta(hours=1),
    )
    reordered = store.list_research_cases()
    assert str(cast(dict[str, object], reordered[0]["case"])["project_id"]) == oldest

    # Bounded paging with the documented research limit.
    assert store.list_research_cases(limit=1) == reordered[:1]
    assert store.list_research_cases(limit=1, offset=1) == reordered[1:2]
    assert store.list_research_cases(limit=1, offset=99) == []
    with pytest.raises(DataError, match="limit"):
        store.list_research_cases(limit=0)
    with pytest.raises(DataError, match="limit"):
        store.list_research_cases(limit=201)
    with pytest.raises(DataError, match="offset"):
        store.list_research_cases(offset=-1)


def test_context_packet_build_is_content_addressed_append_only_and_deterministic(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    project_id = _captured_case(store, 0, at=START)

    first = store.build_research_context_packet(
        project_id,
        kind="research_case",
        created_by="codex",
        at=START + timedelta(minutes=5),
    )
    packet_id = str(first["packet_id"])
    assert packet_id.startswith("cp_") and len(packet_id) == 3 + 64
    assert first["packet_kind"] == "research_case"
    assert first["protocol_id"] is None and first["protocol_content_hash"] is None
    payload = first["payload"]
    assert isinstance(payload, dict)
    assert payload["packet_schema"] == "ResearchContextPacketV1"
    assert payload["project_id"] == project_id
    assert payload["packet_kind"] == "research_case"
    # Bounded collections carry explicit truncation flags — no invisible context dumps.
    assert payload["attempts_truncated"] is False
    assert payload["sources_truncated"] is False
    assert payload["notes_truncated"] is False
    # Identical inputs produce the identical content-addressed packet (idempotent record).
    replay = store.build_research_context_packet(
        project_id,
        kind="research_case",
        created_by="codex",
        at=START + timedelta(minutes=9),
    )
    assert replay["packet_id"] == packet_id
    assert replay["payload"] == payload
    assert len(store.list_research_context_packets(project_id)) == 1

    # A different kind is a different packet; recording is visibility.
    validation = store.build_research_context_packet(
        project_id,
        kind="validation",
        created_by="codex",
        protocol_id="research-critic",
        protocol_content_hash="c" * 64,
        at=START + timedelta(minutes=10),
    )
    assert validation["packet_id"] != packet_id
    assert validation["protocol_id"] == "research-critic"
    assert validation["protocol_content_hash"] == "c" * 64
    listed = store.list_research_context_packets(project_id)
    assert [row["packet_id"] for row in listed] == [validation["packet_id"], packet_id]
    fetched = store.get_research_context_packet(str(validation["packet_id"]))
    assert fetched == validation

    with pytest.raises(DataError, match="packet kind"):
        store.build_research_context_packet(project_id, kind="chat", created_by="codex")
    with pytest.raises(DataError, match="symbol"):
        store.build_research_context_packet(project_id, kind="asset", created_by="codex")
    with pytest.raises(DataError, match="unknown research context packet"):
        store.get_research_context_packet("cp_" + "0" * 64)


def test_research_notes_are_append_only_and_structurally_outside_evidence(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    project_id = _captured_case(store, 0, at=START)
    packet = store.build_research_context_packet(
        project_id, kind="research_case", created_by="codex", at=START + timedelta(minutes=1)
    )
    before = json.dumps(
        store.research_gate_packet_inputs(project_id), sort_keys=True, allow_nan=False
    )

    critique = store.add_research_note(
        project_id,
        note_kind="critique",
        body="The volatility-regime confounder is not yet matched.",
        author="codex",
        author_kind="agent",
        context_packet_id=str(packet["packet_id"]),
        at=START + timedelta(minutes=2),
    )
    assert str(critique["note_id"]).startswith("rn_")
    assert critique["author_kind"] == "agent"
    assert critique["context_packet_id"] == packet["packet_id"]
    synthesis = store.add_research_note(
        project_id,
        note_kind="synthesis",
        body="Established: nothing. Speculative: everything pre-D1.",
        author="owner",
        author_kind="owner",
        at=START + timedelta(minutes=3),
    )
    notes = store.list_research_notes(project_id)
    assert [row["note_id"] for row in notes] == [synthesis["note_id"], critique["note_id"]]

    # Structural evidence exclusion: the gate-packet inputs are byte-identical with notes.
    after = json.dumps(
        store.research_gate_packet_inputs(project_id), sort_keys=True, allow_nan=False
    )
    assert after == before

    with pytest.raises(DataError, match="note kind"):
        store.add_research_note(
            project_id, note_kind="evidence", body="x", author="codex", author_kind="agent"
        )
    with pytest.raises(DataError, match="author kind"):
        store.add_research_note(
            project_id, note_kind="critique", body="x", author="codex", author_kind="human"
        )
    with pytest.raises(DataError, match="unknown research context packet"):
        store.add_research_note(
            project_id,
            note_kind="critique",
            body="x",
            author="codex",
            author_kind="agent",
            context_packet_id="cp_" + "1" * 64,
        )


def test_research_brief_reports_only_deltas_since_the_previous_brief(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_id = _captured_case(store, 0, at=START)

    first = store.research_brief(project_id, created_by="codex", at=START + timedelta(minutes=4))
    assert first["brief_schema"] == "ResearchBriefV1"
    case = first["case"]
    assert isinstance(case, dict) and case["project_id"] == project_id
    changes = first["changes"]
    assert isinstance(changes, dict)
    # The first brief reports the complete history as new.
    assert len(cast(list[object], changes["phase_events"])) == 2  # captured + triage
    assert len(cast(list[object], changes["execution_events"])) == 1  # initial idle
    assert changes["attempts"] == [] and changes["decisions"] == []
    assert isinstance(first["packet_id"], str) and str(first["packet_id"]).startswith("cp_")

    summary = store.research_case_summary(project_id)
    store.transition_research_execution(
        project_id,
        to_state="blocked",
        contract_id=str(summary["active_contract_id"]),
        actor="owner",
        reason="Owner paused triage pending data access.",
        next_action="Restore data access before continuing triage.",
        responsibility="owner",
        blocker="Data access is unavailable.",
        recovery="Restore data access.",
        at=START + timedelta(minutes=6),
    )
    second = store.research_brief(project_id, created_by="codex", at=START + timedelta(minutes=7))
    second_changes = second["changes"]
    assert isinstance(second_changes, dict)
    assert second_changes["phase_events"] == []
    execution_events = cast(list[dict[str, object]], second_changes["execution_events"])
    assert len(execution_events) == 1
    assert execution_events[0]["state"] == "blocked"
    assert second["packet_id"] != first["packet_id"]

    third = store.research_brief(project_id, created_by="codex", at=START + timedelta(minutes=8))
    third_changes = third["changes"]
    assert isinstance(third_changes, dict)
    assert all(third_changes[key] == [] for key in third_changes)


def test_research_dataset_registration_is_fail_closed_and_content_addressed(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    ref = store.register_research_dataset(
        dataset_kind="snapshot",
        instrument="AAPL",
        provider="fake",
        start_ts="2020-08-28",
        end_ts="2020-09-02",
        bar_duration_minutes=None,
        origin={"snapshot_id": "snap-a", "manifest_sha256": "a" * 64},
        registered_by="owner",
        at=START,
    )
    ref_id = str(ref["ref_id"])
    assert ref_id.startswith("rd_") and len(ref_id) == 3 + 64
    assert ref["research_only"] is True
    assert ref["dataset_kind"] == "snapshot"
    # Idempotent re-registration of identical bytes.
    replay = store.register_research_dataset(
        dataset_kind="snapshot",
        instrument="AAPL",
        provider="fake",
        start_ts="2020-08-28",
        end_ts="2020-09-02",
        bar_duration_minutes=None,
        origin={"snapshot_id": "snap-a", "manifest_sha256": "a" * 64},
        registered_by="owner",
        at=START + timedelta(minutes=5),
    )
    assert replay["ref_id"] == ref_id
    rows = store.list_research_datasets()
    assert [row["ref_id"] for row in rows] == [ref_id]
    assert rows[0]["latest_audit"] is None
    assert store.get_research_dataset(ref_id)["origin"] == {
        "snapshot_id": "snap-a",
        "manifest_sha256": "a" * 64,
    }
    assert store.list_research_datasets(instrument="AAPL") == rows
    assert store.list_research_datasets(instrument="SPY") == []

    # Fail-closed origins: a registration without its exact binding is refused.
    with pytest.raises(DataError, match="manifest_sha256"):
        store.register_research_dataset(
            dataset_kind="snapshot",
            instrument="AAPL",
            provider="fake",
            start_ts="2020-08-28",
            end_ts="2020-09-02",
            bar_duration_minutes=None,
            origin={"snapshot_id": "snap-a"},
            registered_by="owner",
        )
    with pytest.raises(DataError, match="provenance_sha256"):
        store.register_research_dataset(
            dataset_kind="store_slice",
            instrument="AAPL",
            provider="fake",
            start_ts="2020-08-28",
            end_ts="2020-09-02",
            bar_duration_minutes=None,
            origin={},
            registered_by="owner",
        )
    with pytest.raises(DataError, match="receipt"):
        store.register_research_dataset(
            dataset_kind="quantpad_receipt",
            instrument="AAPL",
            provider="quantpad",
            start_ts="2020-08-28",
            end_ts="2020-09-02",
            bar_duration_minutes=60,
            origin={"response_sha256": "b" * 64},
            registered_by="owner",
        )
    with pytest.raises(DataError, match="dataset kind"):
        store.register_research_dataset(
            dataset_kind="csv_upload",
            instrument="AAPL",
            provider="fake",
            start_ts="2020-08-28",
            end_ts="2020-09-02",
            bar_duration_minutes=None,
            origin={},
            registered_by="owner",
        )


def test_research_dataset_audits_bind_ref_project_and_run(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_id = _captured_case(store, 0, at=START)
    ref = store.register_research_dataset(
        dataset_kind="store_slice",
        instrument="AAPL",
        provider="fake",
        start_ts="2020-08-28",
        end_ts="2020-09-02",
        bar_duration_minutes=None,
        origin={"provenance_sha256": "c" * 64},
        registered_by="owner",
        at=START,
    )
    ref_id = str(ref["ref_id"])
    audit = store.record_research_dataset_audit(
        ref_id,
        project_id=project_id,
        run_id="deadbeefdeadbeef",
        summary={
            "audit_schema": "ResearchDataAuditV1",
            "blocking_count": 0,
            "limiting_count": 1,
            "notes": ["One calendar gap over a holiday."],
        },
        at=START + timedelta(minutes=10),
    )
    assert audit["ref_id"] == ref_id and audit["project_id"] == project_id
    listed = store.list_research_dataset_audits(ref_id)
    assert [row["run_id"] for row in listed] == ["deadbeefdeadbeef"]
    enriched = store.list_research_datasets()
    latest = enriched[0]["latest_audit"]
    assert isinstance(latest, dict)
    assert latest["summary"]["limiting_count"] == 1

    with pytest.raises(DataError, match="unknown research dataset"):
        store.record_research_dataset_audit(
            "rd_" + "0" * 64,
            project_id=project_id,
            run_id="deadbeefdeadbeef",
            summary={
                "audit_schema": "ResearchDataAuditV1",
                "blocking_count": 0,
                "limiting_count": 0,
                "notes": [],
            },
        )
    with pytest.raises(DataError, match="audit summary"):
        store.record_research_dataset_audit(
            ref_id,
            project_id=project_id,
            run_id="deadbeefdeadbeef",
            summary={"blocking_count": 0},
        )


def test_data_audit_refuses_drifted_bytes_and_unsupported_kinds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The audit loader is fail-closed: registered hashes must still match the disk."""
    from alpha_cli.research_data_audit import run_data_audit

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id = _captured_case(ControlStore(tmp_path), 0, at=START)

    def _ref(kind: str, origin: dict[str, object]) -> dict[str, object]:
        return {
            "ref_id": "rd_" + "1" * 64,
            "dataset_kind": kind,
            "instrument": "AAPL",
            "provider": "fake",
            "start_ts": "2020-01-01",
            "end_ts": "2020-06-01",
            "bar_duration_minutes": None,
            "origin": origin,
        }

    with pytest.raises(DataError, match="canonical project_id"):
        run_data_audit(tmp_path, project_id="not-a-uuid", ref=_ref("snapshot", {}))
    with pytest.raises(DataError, match="registered dataset ref"):
        run_data_audit(tmp_path, project_id=project_id, ref={"ref_id": "nope"})
    with pytest.raises(DataError, match="missing its manifest"):
        run_data_audit(
            tmp_path,
            project_id=project_id,
            ref=_ref("snapshot", {"snapshot_id": "ghost", "manifest_sha256": "a" * 64}),
        )
    snapshot_dir = tmp_path / "snapshots" / "snap-x"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="no longer matches its registered manifest hash"):
        run_data_audit(
            tmp_path,
            project_id=project_id,
            ref=_ref("snapshot", {"snapshot_id": "snap-x", "manifest_sha256": "a" * 64}),
        )
    with pytest.raises(DataError, match="no provenance sidecar"):
        run_data_audit(
            tmp_path,
            project_id=project_id,
            ref=_ref("store_slice", {"provenance_sha256": "b" * 64}),
        )
    with pytest.raises(DataError, match="qualified-loading lane"):
        run_data_audit(
            tmp_path,
            project_id=project_id,
            ref=_ref("quantpad_receipt", {"receipt_id": "c" * 32, "response_sha256": "d" * 64}),
        )
    with pytest.raises(DataError, match="end at or after"):
        bad_range = _ref("snapshot", {"snapshot_id": "snap-x", "manifest_sha256": "a" * 64})
        bad_range["start_ts"] = "2021-01-01"
        bad_range["end_ts"] = "2020-01-01"
        run_data_audit(tmp_path, project_id=project_id, ref=bad_range)


def test_source_records_gain_typed_doi_year_authors_columns(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    source = store.create_research_source(
        PROJECT_ID,
        title="Technical patterns and subsequent returns",
        locator="doi:10.0000/example",
        provider="crossref",
        access_mode="metadata_only",
        doi="10.0000/EXAMPLE",
        year=2019,
        authors=["A. Author", "B. Author"],
        at=START,
    )
    # The DOI normalizes to lowercase; authors round-trip as a typed list.
    assert source["doi"] == "10.0000/example"
    assert source["year"] == 2019
    assert source["authors"] == ["A. Author", "B. Author"]
    fetched = store.get_research_source(str(source["source_id"]))
    assert fetched["doi"] == "10.0000/example"
    assert fetched["year"] == 2019
    assert fetched["authors"] == ["A. Author", "B. Author"]

    with pytest.raises(DataError, match="year"):
        store.create_research_source(
            PROJECT_ID,
            title="Bad year",
            locator="doi:10.0000/bad",
            provider="crossref",
            access_mode="metadata_only",
            year=99,
        )
    with pytest.raises(DataError, match="authors"):
        store.create_research_source(
            PROJECT_ID,
            title="Bad authors",
            locator="doi:10.0000/bad2",
            provider="crossref",
            access_mode="metadata_only",
            authors=["", "ok"],
        )


def test_source_claims_are_append_only_and_owner_screened(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_id = _captured_case(store, 0, at=START)
    summary = store.research_case_summary(project_id)
    contract_id = str(summary["active_contract_id"])
    source = store.create_research_source(
        project_id,
        title="Technical patterns and subsequent returns",
        locator="doi:10.0000/example",
        provider="crossref",
        access_mode="metadata_only",
        doi="10.0000/example",
        year=2019,
        at=START + timedelta(minutes=1),
    )
    source_id = str(source["source_id"])

    claim = store.draft_source_claim(
        project_id,
        source_id=source_id,
        contract_id=contract_id,
        claim_text="Double-bottom patterns show small positive drift pre-2005 that decays.",
        direction="supports",
        strength="weak",
        method_summary="Event study over daily US equities with matched controls.",
        sample_summary="1962-2004, ~2,000 events.",
        markets=["US_EQUITY"],
        limitations="Pre-decimalization microstructure; publication-era decay likely.",
        author="codex",
        author_kind="agent",
        at=START + timedelta(minutes=2),
    )
    claim_id = str(claim["claim_id"])
    assert claim_id.startswith("sc_")
    assert claim["status"] == "draft"
    assert claim["revision"] == 1

    # Screening appends a new revision; the draft row survives unchanged (append-only).
    screened = store.screen_source_claim(
        project_id,
        claim_id=claim_id,
        actor="owner",
        at=START + timedelta(minutes=3),
    )
    assert screened["status"] == "screened"
    assert screened["revision"] == 2
    assert screened["screened_by"] == "owner"
    rows = store.list_source_claims(project_id)
    assert [(row["claim_id"], row["revision"], row["status"]) for row in rows] == [
        (claim_id, 2, "screened"),
    ]
    history = store.list_source_claims(project_id, include_history=True)
    assert [(row["revision"], row["status"]) for row in history if row["claim_id"] == claim_id] == [
        (2, "screened"),
        (1, "draft"),
    ]

    with pytest.raises(DataError, match="already screened"):
        store.screen_source_claim(project_id, claim_id=claim_id, actor="owner")
    with pytest.raises(DataError, match="claim direction"):
        store.draft_source_claim(
            project_id,
            source_id=source_id,
            contract_id=contract_id,
            claim_text="x",
            direction="proves",
            strength="weak",
            method_summary="m",
            sample_summary="s",
            markets=[],
            limitations="l",
            author="codex",
            author_kind="agent",
        )
    with pytest.raises(DataError, match="unknown research source"):
        store.draft_source_claim(
            project_id,
            source_id="rs_" + "0" * 64,
            contract_id=contract_id,
            claim_text="x",
            direction="supports",
            strength="weak",
            method_summary="m",
            sample_summary="s",
            markets=[],
            limitations="l",
            author="codex",
            author_kind="agent",
        )


def test_source_search_is_bounded_and_local_only(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    for index, title in enumerate(
        ("Momentum everywhere", "Double bottoms revisited", "Double tops and bottoms")
    ):
        store.create_research_source(
            PROJECT_ID,
            title=title,
            locator=f"doi:10.0000/s{index}",
            provider="crossref",
            access_mode="metadata_only",
            doi=f"10.0000/s{index}",
            at=START + timedelta(minutes=index),
        )
    hits = store.search_research_sources("double bottom")
    assert [row["title"] for row in hits] == [
        "Double bottoms revisited",
        "Double tops and bottoms",
    ]
    by_doi = store.search_research_sources("10.0000/s0")
    assert [row["title"] for row in by_doi] == ["Momentum everywhere"]
    assert store.search_research_sources("nonexistent topic") == []
    with pytest.raises(DataError, match="query"):
        store.search_research_sources("")


def test_source_record_columns_heal_on_a_pre_r4_store(tmp_path: Path) -> None:
    """A schema-v2 store predating the typed columns gains them idempotently on open."""
    store = ControlStore(tmp_path)
    _project(store)
    database = tmp_path / "control" / control_store_module.DATABASE_NAME
    connection = sqlite3.connect(database)
    try:
        for column in ("doi", "year", "authors_json"):
            connection.execute(f"ALTER TABLE research_source_records DROP COLUMN {column}")
        connection.commit()
        present = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(research_source_records)")
        }
        assert "doi" not in present
    finally:
        connection.close()

    healed = ControlStore(tmp_path)
    source = healed.create_research_source(
        PROJECT_ID,
        title="Post-heal typed source",
        locator="doi:10.0000/healed",
        provider="crossref",
        access_mode="metadata_only",
        doi="10.0000/healed",
        year=2020,
        authors=["A. Author"],
        at=START,
    )
    assert source["doi"] == "10.0000/healed"
    assert healed.get_research_source(str(source["source_id"]))["year"] == 2020

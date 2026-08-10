"""The preregistered D1 deep-research executor (spec §9.3, ADR-0025).

End-to-end over registered synthetic fixtures: planted-pattern recovery, planted-confounder
rejection, null-stays-null after Holm, honest insufficient-event packets, deterministic
re-publication, and mechanical evidence re-verification (producer flags never authority).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from alpha_cli.research_analysis_plan import default_analysis_plan
from alpha_cli.research_d1 import (
    D1_ANALYSES_ARTIFACT,
    D1_EVIDENCE_ARTIFACT,
    d1_execution_fingerprint,
    derive_d1_findings,
    research_bars_from_lows,
    run_deep_research,
    validate_d1_evidence_artifacts,
)
from alpha_core import DataError

PROJECT_ID = "9e4908b1-a9cd-4c13-a47e-740d92175680"
CONTRACT_ID = "rc_" + "a" * 64
_MOTIF = (105.0, 103.0, 100.0, 95.0, 99.0, 101.0, 100.0, 95.5, 99.0, 101.0)
_MONDAY = datetime(2020, 1, 6, 0, 0, tzinfo=UTC)  # a Monday


def _contract(*, horizon_bars: int = 4) -> dict[str, Any]:
    primary_claim = {
        "estimand": "event_minus_matched_control_arithmetic_return",
        "endpoint": "forward_arithmetic_return",
        "horizon_trading_minutes": 240,
        "direction": "positive",
        "minimum_effect_return": 0.0025,
    }
    return {
        "schema": "ResearchContractV1",
        "scope": "exploration",
        "approval_ready": True,
        "blocking_questions": [],
        "raw_idea": "double bottoms bounce",
        "primary_claim": primary_claim,
        "thesis": {"primary_claims": [primary_claim]},
        "confounders": ["calendar and day of week", "trend and volatility state"],
        "statistical_policy": {"familywise_alpha": 0.05},
        "analysis_plan": default_analysis_plan(horizon_bars=horizon_bars),
        "budget": {"wall_seconds": 8_400, "source_requests": 40, "variants": 64},
        "source_pack_id": "sp_" + "b" * 64,
        "hashes": {
            "code": "git:a1b2c3d4e5f60718",
            "environment": "uv-lock:1234abcd5678ef90",
            "evaluator": "event-study-v1.0.0",
            "data": None,
        },
        "protocol": {
            "boundary_authority": {
                "kind": "synthetic_acceptance_fixture",
                "real_market_evidence": False,
                "empirical_confirmation_authorized": False,
            },
            "d0_operator": {
                "operator": {
                    "spec": {
                        "pivot_left": 1,
                        "pivot_right": 2,
                        "min_separation": 3,
                        "max_separation": 6,
                        "trough_tolerance": 0.03,
                        "min_rebound": 0.05,
                    }
                }
            },
        },
    }


def _weekly_lows(mode: str, *, weeks: int = 8) -> list[float]:
    """One planted motif per Monday over hourly bars starting at a Monday midnight.

    ``recovery`` rises sharply after each confirmation (a real planted edge).
    ``confounder`` drifts the WHOLE Monday geometrically, so events and same-weekday
    controls share the move and matching must reject the naive read.
    ``null`` wobbles around the motif's closing level with a mean-zero pattern.
    """
    lows: list[float] = []
    for week in range(weeks):
        for day in range(7):
            if day != 0:
                lows.extend([100.0] * 24)
                continue
            lows.extend(_MOTIF)
            level = _MOTIF[-1]
            for hour in range(14):
                if mode == "recovery":
                    level = level + 1.5 if hour < 6 else level
                elif mode == "confounder":
                    level *= 1.0142  # geometric: % moves match across the whole Monday
                else:
                    wobble = 0.3 if week % 2 else -0.3
                    level = _MOTIF[-1] + (wobble if hour % 2 else 0.0)
                lows.append(level)
    return lows


def _run(tmp_path: Path, lows: list[float], contract: dict[str, Any]) -> dict[str, Any]:
    bars = research_bars_from_lows(
        lows,
        dataset_id="d1-fixture",
        content_sha256="c" * 64,
        start=_MONDAY,
        bar_duration=timedelta(hours=1),
    )
    return run_deep_research(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
    )


def _evidence(tmp_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    path = run_dir / D1_EVIDENCE_ARTIFACT
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_planted_pattern_is_recovered_end_to_end(tmp_path: Path) -> None:
    contract = _contract()
    manifest = _run(tmp_path, _weekly_lows("recovery"), contract)
    assert manifest["command"] == "research_deep"
    assert manifest["evidence_zone"] == "D1"
    assert manifest["watermark"] == "EXPLORATORY"
    assert manifest["real_market_evidence"] is False
    assert manifest["eligible_for_holdout_or_execution"] is False
    assert manifest["places_orders"] is False
    evidence = _evidence(tmp_path, manifest)
    assert evidence["schema"] == "ResearchGateEvidenceV1"
    assert evidence["evidence_zone"] == "D1"
    primary = evidence["primary_result"]
    assert primary["status"] == "TESTED"
    assert float(primary["estimate"]) > 0.0025
    assert primary["practical_magnitude"]["status"] == "CLEARS_HURDLE"
    assert evidence["negative_controls"]["status"] == "PASSED"
    assert evidence["mechanism"]["status"] == "NOT_TESTED"  # honest: D1 computes no mechanism
    assert "confirmation_classification" not in evidence  # D1 never carries D2 keys


def test_planted_weekday_confounder_is_rejected_by_matching(tmp_path: Path) -> None:
    contract = _contract()
    manifest = _run(tmp_path, _weekly_lows("confounder"), contract)
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    analyses = json.loads((run_dir / D1_ANALYSES_ARTIFACT).read_text(encoding="utf-8"))
    cell = analyses["measurements"]["families"]["event_study"]["cells"][0]
    assert float(cell["unadjusted"]["estimate"]) > 0.0025  # the naive read looks like an edge
    evidence = _evidence(tmp_path, manifest)
    assert evidence["primary_result"]["practical_magnitude"]["status"] != "CLEARS_HURDLE"
    assert "calendar and day of week" in evidence["confounders"]["resolved"]


def test_pure_null_stays_null_after_holm(tmp_path: Path) -> None:
    contract = _contract()
    manifest = _run(tmp_path, _weekly_lows("null"), contract)
    evidence = _evidence(tmp_path, manifest)
    assert evidence["primary_result"]["practical_magnitude"]["status"] != "CLEARS_HURDLE"
    multiplicity = evidence["multiplicity"]
    assert multiplicity["status"] in {"PASSED", "INCONCLUSIVE"}
    assert "0 direction-consistent" in str(multiplicity["summary"])


def test_insufficient_events_produce_an_honest_not_tested_packet(tmp_path: Path) -> None:
    contract = _contract()
    manifest = _run(tmp_path, [100.0 + 0.1 * i for i in range(600)], contract)
    evidence = _evidence(tmp_path, manifest)
    assert evidence["primary_result"]["status"] == "NOT_TESTED"
    assert evidence["untested_work"]  # the skipped families are declared, never hidden


def test_reruns_republish_identically_and_future_poison_changes_nothing(tmp_path: Path) -> None:
    contract = _contract()
    lows = _weekly_lows("recovery")
    manifest = _run(tmp_path, lows, contract)
    again = _run(tmp_path, lows, contract)
    assert again == manifest  # deterministic idempotent republication

    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    clean_analyses = (run_dir / D1_ANALYSES_ARTIFACT).read_bytes()
    discovery_stop = int(json.loads(clean_analyses)["measurements"]["topology"]["discovery_stop"])
    poisoned = [*lows[:discovery_stop], *([999.0, 1.0] * ((len(lows) - discovery_stop + 1) // 2))]
    poisoned = poisoned[: len(lows)]
    poisoned_manifest = _run(tmp_path / "poisoned", poisoned, contract)
    poisoned_dir = tmp_path / "poisoned" / "runs" / str(poisoned_manifest["run_id"])
    assert (poisoned_dir / D1_ANALYSES_ARTIFACT).read_bytes() == clean_analyses


@pytest.mark.bias_guard
def test_d1_executor_never_reads_beyond_the_discovery_share(tmp_path: Path) -> None:
    """Rewriting confirmation/holdout bars must not change any D1 measurement."""
    contract = _contract()
    lows = _weekly_lows("recovery")
    manifest = _run(tmp_path, lows, contract)
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    clean = (run_dir / D1_ANALYSES_ARTIFACT).read_bytes()
    stop = int(json.loads(clean)["measurements"]["topology"]["discovery_stop"])
    poisoned_lows = [*lows[:stop], *([5000.0] * (len(lows) - stop))]
    poisoned_manifest = _run(tmp_path / "b", poisoned_lows, contract)
    poisoned_dir = tmp_path / "b" / "runs" / str(poisoned_manifest["run_id"])
    assert (poisoned_dir / D1_ANALYSES_ARTIFACT).read_bytes() == clean


def test_mechanical_verification_rejects_flipped_producer_flags(tmp_path: Path) -> None:
    contract = _contract()
    manifest = _run(tmp_path, _weekly_lows("recovery"), contract)
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    verified = validate_d1_evidence_artifacts(
        run_dir,
        manifest,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
    )
    assert verified["primary_result"]["status"] == "TESTED"

    analyses = json.loads((run_dir / D1_ANALYSES_ARTIFACT).read_text(encoding="utf-8"))
    cell = analyses["measurements"]["families"]["event_study"]["cells"][0]
    cell["matched"]["ci_lower"] = -1.0  # rewrite a raw measurement under the same evidence
    (run_dir / D1_ANALYSES_ARTIFACT).write_text(
        json.dumps(analyses, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    with pytest.raises(DataError):
        validate_d1_evidence_artifacts(
            run_dir,
            manifest,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
        )


def test_execution_fingerprint_freezes_the_plan_and_operator(tmp_path: Path) -> None:
    contract = _contract()
    fingerprint = d1_execution_fingerprint(contract)
    assert fingerprint == d1_execution_fingerprint(_contract())
    changed = _contract()
    plan = cast(dict[str, Any], changed["analysis_plan"])
    families = cast(list[dict[str, Any]], plan["families"])
    families[0] = {**families[0], "grid": {"horizon_bars": [5]}}
    assert d1_execution_fingerprint(changed) != fingerprint
    with pytest.raises(DataError, match="analysis_plan"):
        d1_execution_fingerprint({**_contract(), "analysis_plan": None})


def test_findings_derivation_is_pure_and_direction_aware() -> None:
    contract = _contract()
    claim = {
        "direction": "positive",
        "minimum_effect_return": 0.0025,
        "alpha": 0.05,
        "confounders": contract["confounders"],
    }
    measurements = {
        "topology": {
            "total_observations": 100,
            "discovery_stop": 60,
            "embargo": 4,
        },
        "events": {"detected": 0, "eligible": 0, "embargoed": 0, "rows": []},
        "families": {},
        "skipped_families": [
            {"family": "event_study", "reason": "no eligible events were detected"}
        ],
        "budget": {"variants_used": 0},
    }
    findings = derive_d1_findings(measurements, claim=claim)
    assert findings["schema"] == "ResearchGateEvidenceV1"
    assert findings["primary_result"]["status"] == "NOT_TESTED"
    assert findings["stability"]["transportability"]["status"] == "NOT_TESTED"
    assert findings == derive_d1_findings(measurements, claim=claim)


def test_mixed_passed_and_inconclusive_controls_are_inconclusive() -> None:
    claim = {
        "direction": "positive",
        "minimum_effect_return": 0.01,
        "alpha": 0.05,
        "confounders": [],
        "required_families": ["event_study", "shuffled_event_null", "leadlag_leakage"],
        "required_falsifiers": ["shuffled_event_null", "leadlag_leakage"],
    }
    measurements = {
        "families": {
            "event_study": {
                "cells": [
                    {
                        "matched": {
                            "estimate": 0.002,
                            "ci_lower": 0.001,
                            "ci_upper": 0.004,
                            "confidence": 0.95,
                            "sample_size": 40,
                            "effective_event_count": 12,
                            "low_cluster_count": False,
                        }
                    }
                ]
            },
            "shuffled_event_null": {"cells": [{"placebo_p_upper": 0.5, "placebo_p_lower": 0.5}]},
            "leadlag_leakage": {
                "cells": [
                    {
                        "profile": [
                            {"lag": -1, "n": 20, "correlation": 0.1},
                            {"lag": 1, "n": 20, "correlation": 0.2},
                        ]
                    }
                ]
            },
        },
        "skipped_families": [],
    }

    findings = derive_d1_findings(measurements, claim=claim)

    assert findings["negative_controls"]["status"] == "INCONCLUSIVE"
    assert findings["confirmation_readiness"]["state"] == "blocked"
    assert "required_falsifier_not_passed" in {
        blocker["code"] for blocker in findings["confirmation_readiness"]["blockers"]
    }

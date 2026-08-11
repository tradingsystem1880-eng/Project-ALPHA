"""Fail-loud error paths of the D1 experiment engine (spec §9, ADR-0025).

Every branch here is a fail-closed guarantee: malformed inputs, drifted contracts, and
tampered artifacts must raise typed ``DataError``s — never degrade to silent defaults.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from alpha_cli.research_analysis_plan import default_analysis_plan, validate_analysis_plan
from alpha_cli.research_d1 import (
    D1_ANALYSES_ARTIFACT,
    D1_EVIDENCE_ARTIFACT,
    derive_d1_findings,
    research_bars_from_lows,
    run_deep_research,
    validate_d1_evidence_artifacts,
)
from alpha_cli.research_intake import draft_exploration_contract
from alpha_core import DataError
from alpha_research import (
    conditional_return_summary,
    difference_in_means,
    leadlag_profile,
    leakage_diagnostic,
    quantile_breakdown,
    rank_ic,
    rolling_rank_ic,
    subsample_consistency,
)

PROJECT_ID = "9e4908b1-a9cd-4c13-a47e-740d92175680"
CONTRACT_ID = "rc_" + "a" * 64
_MOTIF = (105.0, 103.0, 100.0, 95.0, 99.0, 101.0, 100.0, 95.5, 99.0, 101.0)
_MONDAY = datetime(2020, 1, 6, 0, 0, tzinfo=UTC)


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
        "confounders": ["calendar and day of week"],
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


def _recovery_lows(*, weeks: int = 8) -> list[float]:
    lows: list[float] = []
    for week in range(weeks):
        # Vary the second-trough depth and recovery slope per week so the rebound signal
        # and forward outcomes are non-constant (rank IC needs real variance).
        motif = list(_MOTIF)
        motif[7] = 95.5 - 0.05 * week
        slope = 1.5 + 0.1 * week
        for day in range(7):
            if day != 0:
                lows.extend([100.0] * 24)
                continue
            lows.extend(motif)
            level = motif[-1]
            for hour in range(14):
                level = level + slope if hour < 6 else level
                lows.append(level)
    return lows


def _bars(lows: list[float]) -> Any:
    return research_bars_from_lows(
        lows,
        dataset_id="d1-fixture",
        content_sha256="c" * 64,
        start=_MONDAY,
        bar_duration=timedelta(hours=1),
    )


def _run(tmp_path: Path, contract: dict[str, Any]) -> dict[str, Any]:
    return run_deep_research(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=_bars(_recovery_lows()),
    )


# --- pure D1 analysis modules -------------------------------------------------------------


def test_pure_modules_reject_malformed_inputs() -> None:
    with pytest.raises(DataError, match="one-dimensional"):
        rank_ic([[1.0, 2.0], [3.0, 4.0]], [[1.0, 2.0], [3.0, 4.0]])  # type: ignore[list-item]
    with pytest.raises(DataError, match="finite"):
        rank_ic([1.0, float("nan"), 2.0], [1.0, 2.0, 3.0])
    with pytest.raises(DataError, match="share one length"):
        rank_ic([1.0, 2.0, 3.0], [1.0, 2.0])
    with pytest.raises(DataError, match="at least three"):
        rank_ic([1.0, 2.0], [1.0, 2.0])
    with pytest.raises(DataError, match="window must be an integer"):
        rolling_rank_ic([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], window=2)
    with pytest.raises(DataError, match="share one length"):
        rolling_rank_ic([1.0, 2.0, 3.0], [1.0, 2.0], window=3)
    with pytest.raises(DataError, match="at least one group"):
        conditional_return_summary({})
    with pytest.raises(DataError, match="zero pooled variance"):
        difference_in_means([1.0, 1.0], [1.0, 1.0])
    with pytest.raises(DataError, match="share one length"):
        quantile_breakdown([1.0, 2.0, 3.0], [1.0, 2.0], quantiles=2)
    with pytest.raises(DataError, match="needs at least"):
        quantile_breakdown([1.0, 2.0], [1.0, 2.0], quantiles=3)
    with pytest.raises(DataError, match="max_lag must be a positive integer"):
        leadlag_profile([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], max_lag=0)
    with pytest.raises(DataError, match="share one length"):
        leadlag_profile([1.0, 2.0, 3.0], [1.0, 2.0], max_lag=1)
    with pytest.raises(DataError, match="fewer than three pairs"):
        leadlag_profile([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], max_lag=1)
    with pytest.raises(DataError, match="non-empty lead-lag profile"):
        leakage_diagnostic([])
    with pytest.raises(DataError, match="n_splits >= 2"):
        subsample_consistency([1.0, 2.0, 3.0, 4.0], n_splits=1)


# --- analysis-plan validation -------------------------------------------------------------


def test_analysis_plan_rejects_malformed_shapes() -> None:
    plan = default_analysis_plan(horizon_bars=4)
    with pytest.raises(DataError, match="positive grid-cell budget"):
        validate_analysis_plan(plan, max_grid_cells=0)
    with pytest.raises(DataError, match="unsupported fields"):
        validate_analysis_plan({**plan, "extra": 1}, max_grid_cells=64)
    bad_grid = json.loads(json.dumps(plan))
    bad_grid["families"][0]["grid"] = []
    with pytest.raises(DataError, match="JSON object of axes"):
        validate_analysis_plan(bad_grid, max_grid_cells=64)
    bad_multiplicity = json.loads(json.dumps(plan))
    bad_multiplicity["families"][1]["multiplicity"] = "bonferroni"
    with pytest.raises(DataError, match="multiplicity must be one of"):
        validate_analysis_plan(bad_multiplicity, max_grid_cells=64)
    with pytest.raises(DataError, match="positive integer horizon"):
        default_analysis_plan(horizon_bars=0)


def test_intake_rejects_malformed_ideas_and_resolutions() -> None:
    with pytest.raises(DataError, match="safe characters"):
        draft_exploration_contract("   ")
    with pytest.raises(DataError, match="unknown research intake resolution"):
        draft_exploration_contract("real idea", resolutions={"bogus": "x"})
    with pytest.raises(DataError, match="unsupported chart_construction"):
        draft_exploration_contract("real idea", resolutions={"chart_construction": "nope"})


# --- contract validation at the D1 boundary -----------------------------------------------


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda c: c.__setitem__("schema", "OtherV1"), "requires ResearchContractV1"),
        (lambda c: c.__setitem__("scope", "confirmation"), "exploration contract"),
        (lambda c: c.__setitem__("approval_ready", False), "approval_ready"),
        (lambda c: c.__setitem__("blocking_questions", ["q"]), "no blocking questions"),
        (
            lambda c: c["protocol"]["boundary_authority"].__setitem__("kind", "other"),
            "boundary authority kind",
        ),
        (lambda c: c.__delitem__("hashes"), "frozen contract fingerprints"),
        (
            lambda c: c["protocol"]["boundary_authority"].__delitem__("real_market_evidence"),
            "declare real_market_evidence",
        ),
        (lambda c: c.__delitem__("primary_claim"), "one resolved primary claim"),
        (
            lambda c: c["primary_claim"].__setitem__("direction", "sideways"),
            "positive or negative",
        ),
        (
            lambda c: c["primary_claim"].__setitem__("minimum_effect_return", -0.1),
            "non-negative minimum_effect_return",
        ),
        (
            lambda c: c["statistical_policy"].__setitem__("familywise_alpha", 0.7),
            "alpha must lie",
        ),
        (lambda c: c.__setitem__("confounders", [1]), "list of strings"),
        (lambda c: c.__delitem__("analysis_plan"), "frozen analysis_plan"),
        (
            lambda c: c["budget"].__setitem__("variants", 0),
            "positive integer variants budget",
        ),
        (
            lambda c: c["protocol"]["d0_operator"]["operator"].__setitem__("spec", {}),
            "frozen registered detector spec",
        ),
    ],
)
def test_run_deep_rejects_drifted_contracts(tmp_path: Path, mutate: Any, match: str) -> None:
    contract = _contract()
    mutate(contract)
    with pytest.raises(DataError, match=match):
        _run(tmp_path, contract)


def test_run_deep_rejects_malformed_identities(tmp_path: Path) -> None:
    contract = _contract()
    bars = _bars(_recovery_lows())
    with pytest.raises(DataError, match="canonical project_id"):
        run_deep_research(
            tmp_path, project_id="nope", contract_id=CONTRACT_ID, contract=contract, bars=bars
        )
    with pytest.raises(DataError, match="content-addressed contract_id"):
        run_deep_research(
            tmp_path, project_id=PROJECT_ID, contract_id="rc_zz", contract=contract, bars=bars
        )
    with pytest.raises(DataError, match="at least one low value"):
        research_bars_from_lows([], dataset_id="d", content_sha256="c" * 64, start=_MONDAY)


# --- registered secondary families beyond the default plan --------------------------------


def test_rank_ic_and_quantile_families_execute_with_a_multi_cell_grid(
    tmp_path: Path,
) -> None:
    contract = _contract()
    contract["analysis_plan"] = {
        "schema": "ResearchAnalysisPlanV1",
        "families": [
            {
                "family": "event_study",
                "multiplicity": "primary",
                "rationale": "Primary event-conditioned contrast over two horizons.",
                "grid": {"horizon_bars": [4, 8]},
            },
            {
                "family": "rank_ic",
                "multiplicity": "secondary_holm",
                "rationale": "Rebound depth should rank forward returns monotonically.",
                "grid": {},
            },
            {
                "family": "quantile_breakdown",
                "multiplicity": "secondary_holm",
                "rationale": "The association must not concentrate in one signal bucket.",
                "grid": {"quantiles": [2]},
            },
        ],
    }
    result = _run(tmp_path, contract)
    analyses = json.loads(
        (tmp_path / "runs" / str(result["run_id"]) / D1_ANALYSES_ARTIFACT).read_bytes()
    )
    families = analyses["measurements"]["families"]
    assert "rank_ic" in families and families["rank_ic"]["cells"]
    assert "quantile_breakdown" in families and families["quantile_breakdown"]["cells"]
    assert len(families["event_study"]["cells"]) == 2
    evidence = json.loads(
        (tmp_path / "runs" / str(result["run_id"]) / D1_EVIDENCE_ARTIFACT).read_bytes()
    )
    # Two agreeing grid cells light the parameter-neighborhood dimension.
    assert evidence["stability"]["parameter"]["status"] == "STABLE"


def test_negative_direction_claim_reuses_the_same_mechanical_hurdle(
    tmp_path: Path,
) -> None:
    result = _run(tmp_path, _contract())
    analyses = json.loads(
        (tmp_path / "runs" / str(result["run_id"]) / D1_ANALYSES_ARTIFACT).read_bytes()
    )
    measurements = analyses["measurements"]
    claim = {
        "direction": "negative",
        "minimum_effect_return": 0.0025,
        "alpha": 0.05,
        "confounders": [],
    }
    findings = derive_d1_findings(measurements, claim=claim)
    # The planted recovery is positive, so a negative claim fails its own hurdle.
    assert findings["primary_result"]["practical_magnitude"]["status"] == "BELOW_HURDLE"
    with pytest.raises(DataError, match="registered claim direction"):
        derive_d1_findings(measurements, claim={**claim, "direction": "sideways"})
    with pytest.raises(DataError, match="hurdle, alpha, and confounders"):
        derive_d1_findings(measurements, claim={**claim, "alpha": None})


# --- tamper-evident admission (post-publication rewrites fail closed) ---------------------


def _published(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    result = _run(tmp_path, _contract())
    run_dir = tmp_path / "runs" / str(result["run_id"])
    manifest = json.loads((run_dir / "manifest.json").read_text())
    return run_dir, manifest


def test_admission_rejects_manifest_identity_drift(tmp_path: Path) -> None:
    run_dir, manifest = _published(tmp_path)
    contract = _contract()

    with pytest.raises(DataError, match="research_deep D1 manifest"):
        validate_d1_evidence_artifacts(
            run_dir,
            {**manifest, "command": "backtest"},
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
        )
    with pytest.raises(DataError, match="project does not match"):
        validate_d1_evidence_artifacts(
            run_dir,
            {**manifest, "project_id": "0" * 8},
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
        )
    with pytest.raises(DataError, match="contract does not match"):
        validate_d1_evidence_artifacts(
            run_dir,
            manifest,
            project_id=PROJECT_ID,
            contract_id="rc_" + "f" * 64,
            contract=contract,
        )
    with pytest.raises(DataError, match="typed evidence artifact"):
        validate_d1_evidence_artifacts(
            run_dir,
            {**manifest, "d1_evidence_artifact": "other.json"},
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
        )
    stripped = json.loads(json.dumps(manifest))
    del stripped["artifacts"][D1_ANALYSES_ARTIFACT]
    with pytest.raises(DataError, match="declare immutable artifact"):
        validate_d1_evidence_artifacts(
            run_dir,
            stripped,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
        )


def test_admission_rejects_rewritten_artifact_bytes(tmp_path: Path) -> None:
    run_dir, manifest = _published(tmp_path)
    contract = _contract()
    tampered = tmp_path / "tampered"

    for artifact, match in (
        (D1_ANALYSES_ARTIFACT, "analyses artifact does not match"),
        (D1_EVIDENCE_ARTIFACT, "evidence artifact does not match"),
    ):
        shutil.rmtree(tampered, ignore_errors=True)
        shutil.copytree(run_dir, tampered)
        path = tampered / artifact
        payload = json.loads(path.read_bytes())
        payload["schema"] = "Doctored"
        path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        with pytest.raises(DataError, match=match):
            validate_d1_evidence_artifacts(
                tampered,
                manifest,
                project_id=PROJECT_ID,
                contract_id=CONTRACT_ID,
                contract=contract,
            )


def test_admission_rejects_non_canonical_and_non_object_artifacts(tmp_path: Path) -> None:
    import hashlib

    run_dir, manifest = _published(tmp_path)
    contract = _contract()

    for raw, match in (
        (b'{ "schema": "ResearchD1AnalysesV1" }', "canonical JSON bytes"),
        (b"[]", "must contain a JSON object"),
        (b"not json", "valid UTF-8 JSON"),
    ):
        tampered = tmp_path / "tampered"
        shutil.rmtree(tampered, ignore_errors=True)
        shutil.copytree(run_dir, tampered)
        (tampered / D1_ANALYSES_ARTIFACT).write_bytes(raw)
        doctored = json.loads(json.dumps(manifest))
        doctored["artifacts"][D1_ANALYSES_ARTIFACT]["sha256"] = hashlib.sha256(raw).hexdigest()
        with pytest.raises(DataError, match=match):
            validate_d1_evidence_artifacts(
                tampered,
                doctored,
                project_id=PROJECT_ID,
                contract_id=CONTRACT_ID,
                contract=contract,
            )

    symlinked = tmp_path / "symlinked"
    shutil.copytree(run_dir, symlinked)
    target = symlinked / D1_ANALYSES_ARTIFACT
    moved = symlinked / "moved.json"
    target.rename(moved)
    target.symlink_to(moved)
    with pytest.raises(DataError, match="regular immutable file"):
        validate_d1_evidence_artifacts(
            symlinked,
            manifest,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=_contract(),
        )


def test_admission_rejects_forged_findings_and_broken_links(tmp_path: Path) -> None:
    import hashlib

    run_dir, manifest = _published(tmp_path)
    contract = _contract()

    def _republish(mutate: Any) -> tuple[Path, dict[str, Any]]:
        tampered = tmp_path / "tampered"
        shutil.rmtree(tampered, ignore_errors=True)
        shutil.copytree(run_dir, tampered)
        payload = json.loads((tampered / D1_EVIDENCE_ARTIFACT).read_bytes())
        mutate(payload)
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        (tampered / D1_EVIDENCE_ARTIFACT).write_bytes(raw)
        doctored = json.loads(json.dumps(manifest))
        doctored["artifacts"][D1_EVIDENCE_ARTIFACT]["sha256"] = hashlib.sha256(raw).hexdigest()
        return tampered, doctored

    tampered, doctored = _republish(
        lambda p: p["primary_result"]["practical_magnitude"].__setitem__("status", "FORGED")
    )
    with pytest.raises(DataError, match="exact mechanical recomputation"):
        validate_d1_evidence_artifacts(
            tampered,
            doctored,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
        )

    tampered, doctored = _republish(lambda p: p.__setitem__("artifact_links", []))
    with pytest.raises(DataError, match="link its immutable measurement artifacts"):
        validate_d1_evidence_artifacts(
            tampered,
            doctored,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
        )

    def _repoint_analyses_link(payload: dict[str, Any]) -> None:
        # Keep a valid-looking link, but aim it at a different declared artifact so the
        # per-link checks pass while the raw-measurements link itself is missing.
        other = next(
            name
            for name in manifest["artifacts"]
            if name not in {D1_ANALYSES_ARTIFACT, D1_EVIDENCE_ARTIFACT}
        )
        for link in payload["artifact_links"]:
            if link["artifact_id"] == D1_ANALYSES_ARTIFACT:
                link["artifact_id"] = other
                link["content_sha256"] = manifest["artifacts"][other]["sha256"]

    tampered, doctored = _republish(_repoint_analyses_link)
    with pytest.raises(DataError, match="link the raw measurements artifact"):
        validate_d1_evidence_artifacts(
            tampered,
            doctored,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
        )

    def _break_link_run(payload: dict[str, Any]) -> None:
        payload["artifact_links"][0]["run_id"] = "0" * 16

    tampered, doctored = _republish(_break_link_run)
    with pytest.raises(DataError, match="bind their own run"):
        validate_d1_evidence_artifacts(
            tampered,
            doctored,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
        )

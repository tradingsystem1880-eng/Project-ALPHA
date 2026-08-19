"""One-shot D2 runtime for the registered Bybit BTCUSDT crowding operator."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final, cast

from alpha_cli import _artifacts
from alpha_cli.research_crypto_runtime import (
    ZoneSpec,
    canonical,
    crypto_evaluation_payload,
    sha,
    validate_crypto_d0_contract,
    validate_crypto_execution_inputs,
    validate_zone_evidence,
)
from alpha_cli.research_readiness import derive_research_readiness
from alpha_core import DataError
from alpha_research import (
    ClaimDirection,
    ConfirmationEvidence,
    CryptoCrowdingEvaluationV1,
    CryptoCrowdingObservationV1,
    ResearchChartData,
    ResearchChartPoint,
    ResearchChartSeries,
    ResearchD2BoundaryV2,
    classify_confirmation,
    evaluate_crypto_crowding,
    registered_crypto_crowding_plan,
    render_research_line_chart,
)

D2_ANALYSES_ARTIFACT: Final = "d2_analyses.json"
D2_EVIDENCE_ARTIFACT: Final = "research_gate_evidence.json"
_RUNTIME_VERSION: Final = 1
_MAX_ARTIFACT_BYTES: Final = 4 * 1024 * 1024
_PROJECT_ID: Final = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_CONTRACT_ID: Final = re.compile(r"rc_[0-9a-f]{64}")
_VALUE_LABEL: Final = "crypto D2 value"


def _canonical(value: object) -> str:
    return canonical(value, label=_VALUE_LABEL)


def _sha(value: object) -> str:
    return sha(value, label=_VALUE_LABEL)


def _validate_contract(contract: Mapping[str, object]) -> None:
    validate_crypto_d0_contract(contract)
    if (
        contract.get("schema") != "ResearchContractV1"
        or contract.get("scope") != "confirmation"
        or contract.get("approval_ready") is not True
        or contract.get("blocking_questions") != []
    ):
        raise DataError("crypto D2 requires an approval-ready confirmation contract")
    confirmation = contract.get("confirmation")
    plan = registered_crypto_crowding_plan()
    if (
        not isinstance(confirmation, Mapping)
        or confirmation.get("variant_count") != 1
        or confirmation.get("multiplicity_count") != 1
        or confirmation.get("familywise_alpha") != 0.05
        or confirmation.get("minimum_confirmation_events") != plan.minimum_confirmation_events
    ):
        raise DataError("crypto D2 confirmation policy does not match the registered operator")


def crypto_d2_execution_fingerprint(contract: Mapping[str, object]) -> str:
    _validate_contract(contract)
    return _sha(
        {
            "runtime": "alpha_cli.research_crypto_d2.one_shot_confirmation",
            "runtime_version": _RUNTIME_VERSION,
            "operator": registered_crypto_crowding_plan().to_dict(),
            "confirmation": contract["confirmation"],
        }
    )


def _findings(result: CryptoCrowdingEvaluationV1) -> dict[str, object]:
    estimate = result.primary_estimate
    plan = registered_crypto_crowding_plan()
    if estimate is None or result.status != "EVALUATED":
        evidence: dict[str, object] = {
            "schema": "ResearchGateEvidenceV1",
            "evidence_zone": "D2",
            "primary_result": {
                "status": "NOT_TESTED",
                "event_count": result.primary_event_count,
                "blockers": list(result.blockers),
            },
            "confirmation_classification": "INCONCLUSIVE",
            "confirmation_checks": {
                "corrected_primary_test_passed": False,
                "interval_registered_direction": False,
                "economic_hurdle_cleared": False,
                "interval_wholly_against_direction": False,
            },
            "strongest_support": None,
            "strongest_contradiction": (
                "The sealed D2 share did not meet the registered ten-event admission floor."
            ),
            "power": {"status": "INCONCLUSIVE", "summary": "; ".join(result.blockers)},
        }
    else:
        numeric = ConfirmationEvidence(
            direction=ClaimDirection.NEGATIVE,
            estimate=estimate.estimate,
            ci_lower=estimate.ci_lower,
            ci_upper=estimate.ci_upper,
            adjusted_p_value=estimate.p_value,
            alpha=0.05,
            minimum_effect=abs(plan.practical_hurdle_return),
            reliability_passed=not estimate.low_cluster_count,
        )
        classification = classify_confirmation(numeric).status.name
        checks = {
            "corrected_primary_test_passed": numeric.adjusted_p_value <= numeric.alpha,
            "interval_registered_direction": numeric.ci_upper < 0.0,
            "economic_hurdle_cleared": numeric.ci_upper < plan.practical_hurdle_return,
            "interval_wholly_against_direction": numeric.ci_lower > 0.0,
        }
        magnitude = (
            "CLEARS_HURDLE"
            if checks["economic_hurdle_cleared"]
            else (
                "BELOW_HURDLE"
                if estimate.ci_lower > plan.practical_hurdle_return
                else "INCONCLUSIVE"
            )
        )
        evidence = {
            "schema": "ResearchGateEvidenceV1",
            "evidence_zone": "D2",
            "primary_result": {
                "status": "TESTED",
                "estimate": estimate.estimate,
                "unit": "mark_return_minus_index_return",
                "sample_size": estimate.matched_pairs,
                "effective_sample_size": float(estimate.effective_week_clusters),
                "uncertainty": {
                    "lower": estimate.ci_lower,
                    "upper": estimate.ci_upper,
                    "level": 0.95,
                    "method": "UTC_week_cluster_bootstrap_percentile",
                },
                "practical_magnitude": {
                    "status": magnitude,
                    "value": estimate.estimate,
                    "unit": "mark_return_minus_index_return",
                },
            },
            "confirmation_classification": classification,
            "confirmation_checks": checks,
            "confirmation_claim": {
                "direction": "negative",
                "minimum_effect": abs(plan.practical_hurdle_return),
                "adjusted_p_value": estimate.p_value,
                "alpha": 0.05,
            },
            "strongest_support": (
                "The one-shot D2 interval clears the registered 5 bp underperformance hurdle."
                if classification == "SUPPORTED"
                else None
            ),
            "strongest_contradiction": (
                "The sealed D2 interval lies wholly against the registered direction."
                if classification == "CONTRADICTED"
                else (
                    "The sealed D2 estimate is statistically or economically inconclusive."
                    if classification != "SUPPORTED"
                    else None
                )
            ),
            "power": {
                "status": "INCONCLUSIVE" if estimate.low_cluster_count else "PASSED",
                "summary": (f"{estimate.effective_week_clusters} effective UTC-week clusters."),
            },
        }
    evidence.update(
        {
            "mechanism": {"status": "NOT_TESTED", "summary": None},
            "stability": {
                "parameter": {"status": "NOT_TESTED", "summary": None},
                "temporal": {"status": "NOT_TESTED", "summary": None},
                "transportability": {"status": "NOT_TESTED", "summary": None},
            },
            "multiplicity": {
                "status": "PASSED",
                "summary": "Exactly one frozen primary hypothesis was executed.",
            },
            "negative_controls": {"status": "NOT_TESTED", "summary": None},
            "confounders": {
                "resolved": list(plan.matching_covariates),
                "unresolved": ["cross-dataset transportability"],
            },
            "untested_work": ["D3 holdout", "cross-dataset transportability"],
            "what_would_change_conclusion": [
                "evidence that the sealed D2 membership was visible before authorization",
                "a materially different result on later non-overlapping data",
            ],
        }
    )
    evidence.update(derive_research_readiness(evidence))
    return evidence


def _payloads(
    *,
    run_id: str,
    contract: Mapping[str, object],
    observations: tuple[CryptoCrowdingObservationV1, ...],
    boundary: ResearchD2BoundaryV2,
) -> tuple[dict[str, object], dict[str, object], CryptoCrowdingEvaluationV1]:
    _, start, stop = validate_crypto_execution_inputs(
        contract, observations, boundary, evidence_zone="D2"
    )
    result = evaluate_crypto_crowding(
        observations,
        evidence_zone="D2",
        admission_start=start,
        admission_stop=stop,
    )
    analyses = {
        "schema": "CryptoCrowdingD2AnalysesV1",
        "schema_version": 1,
        "admission": {
            "start_index": start,
            "stop_index": stop,
            "outcome_overlap_embargo_groups": boundary.outcome_overlap_embargo_groups,
            "boundary_sha256": boundary.boundary_sha256,
        },
        "measurements": {"evaluation": crypto_evaluation_payload(result)},
    }
    evidence = {
        **_findings(result),
        "artifact_links": [
            {
                "run_id": run_id,
                "artifact_id": D2_ANALYSES_ARTIFACT,
                "content_sha256": hashlib.sha256(_canonical(analyses).encode()).hexdigest(),
                "media_type": "application/json",
            }
        ],
    }
    return analyses, evidence, result


def _publish(path: Path, payload: object) -> None:
    _artifacts.publish_artifact(
        path,
        lambda target: target.write_text(_canonical(payload), encoding="utf-8"),
    )


def run_crypto_crowding_confirmation(
    data_dir: Path,
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
    observations: tuple[CryptoCrowdingObservationV1, ...],
    boundary: ResearchD2BoundaryV2,
    on_checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Execute the exact primary once against only the outcome-safe D2 membership."""
    if _PROJECT_ID.fullmatch(project_id) is None or _CONTRACT_ID.fullmatch(contract_id) is None:
        raise DataError("crypto D2 requires canonical project and contract ids")
    _validate_contract(contract)
    dataset_hash, start, stop = validate_crypto_execution_inputs(
        contract, observations, boundary, evidence_zone="D2"
    )
    execution_fingerprint = crypto_d2_execution_fingerprint(contract)
    contract_hash = _sha(contract)
    run_identity = {
        "command": "research_confirm",
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "dataset_hash": dataset_hash,
        "execution_fingerprint": execution_fingerprint,
    }
    run_id = _sha(run_identity)[:16]
    run_dir = _artifacts.run_dir(data_dir, run_id)
    analyses, evidence, result = _payloads(
        run_id=run_id,
        contract=contract,
        observations=observations,
        boundary=boundary,
    )
    if on_checkpoint is not None:
        on_checkpoint("d2:sealed-share-verified")
    _publish(run_dir / D2_ANALYSES_ARTIFACT, analyses)
    _publish(run_dir / D2_EVIDENCE_ARTIFACT, evidence)

    admitted = observations[start:stop]
    series = ResearchChartSeries(
        series_id="d2-mark-minus-index",
        label="Mark minus index return",
        unit="return",
        points=tuple(
            ResearchChartPoint(
                ts=item.exit_time,
                value=(item.exit_mark / item.entry_mark - 1)
                - (item.exit_index / item.entry_index - 1),
            )
            for item in admitted
        ),
    )
    chart = ResearchChartData(
        chart_id="crypto-crowding-d2-confirmation",
        title="D2 Bybit crowding confirmation",
        x_label="Outcome availability (UTC)",
        y_label="Mark minus index return",
        evidence_phase="confirmatory",
        dataset_sha256=dataset_hash,
        protocol_sha256=contract_hash,
        question="Does the frozen crowding contrast hold on the sealed confirmation share?",
        plain_language_answer=str(
            evidence["strongest_support"] or evidence["strongest_contradiction"]
        ),
        sample_size=len(admitted),
        effective_sample_size=float(max(1, result.primary_event_count)),
        uncertainty="UTC-week clustered bootstrap; see the immutable evidence artifact.",
        caveat="REGISTERED CONFIRMATORY D2 only; D3 remains sealed and no authority is granted.",
        run_id=run_id,
        artifact_id="crypto-crowding-d2-series",
        artifact_sha256=_sha(series.to_dict()),
        series=(series,),
    )
    _artifacts.publish_artifact(
        run_dir / "chart-data.json",
        lambda target: target.write_text(
            json.dumps(chart.to_dict(), sort_keys=True, indent=2, allow_nan=False),
            encoding="utf-8",
        ),
    )
    _artifacts.publish_artifact(
        run_dir / "d2-one-shot-confirmation.png",
        lambda target: target.write_bytes(render_research_line_chart(chart)),
    )
    _artifacts.publish_artifact(
        run_dir / "report.md",
        lambda target: target.write_text(
            "# D2 Crypto Crowding Confirmation\n\n"
            "**REGISTERED CONFIRMATORY — ONE-SHOT SEALED-SHARE EVIDENCE**\n\n"
            f"The exact primary classified {evidence['confirmation_classification']}. "
            "D3 was not admitted and this run grants no execution authority.\n",
            encoding="utf-8",
        ),
    )
    if on_checkpoint is not None:
        on_checkpoint("d2:one-shot-family-complete")
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "run_identity_version": 3,
        "command": "research_confirm",
        "kind": "research",
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "source_pack_id": contract.get("source_pack_id"),
        "research_fingerprints": dict(cast(Mapping[str, object], contract["hashes"])),
        "evidence_zone": "D2",
        "watermark": "REGISTERED CONFIRMATORY",
        "real_market_evidence": True,
        "eligible_for_holdout_or_execution": False,
        "places_orders": False,
        "snapshot_id": None,
        "snapshot_hash": None,
        "execution_fingerprint": execution_fingerprint,
        "strategy_fingerprint": None,
        "source_fingerprint": contract_hash,
        "dataset_hash": dataset_hash,
        "d2_evidence_artifact": D2_EVIDENCE_ARTIFACT,
        "d2_analyses_artifact": D2_ANALYSES_ARTIFACT,
    }
    _artifacts.write_manifest(run_dir, manifest)
    return _artifacts.read_manifest(run_dir)


_D2_ZONE: Final = ZoneSpec(
    command="research_confirm",
    zone="D2",
    label="crypto D2",
    analyses_artifact=D2_ANALYSES_ARTIFACT,
    evidence_artifact=D2_EVIDENCE_ARTIFACT,
    analyses_manifest_key="d2_analyses_artifact",
    evidence_manifest_key="d2_evidence_artifact",
    fingerprint=crypto_d2_execution_fingerprint,
    payloads=lambda run_id, contract, observations, boundary: _payloads(
        run_id=run_id, contract=contract, observations=observations, boundary=boundary
    ),
    max_artifact_bytes=_MAX_ARTIFACT_BYTES,
)


def validate_crypto_d2_evidence_artifacts(
    run_dir: Path,
    manifest: Mapping[str, object],
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
    observations: tuple[CryptoCrowdingObservationV1, ...],
    boundary: ResearchD2BoundaryV2,
) -> dict[str, object]:
    """Recompute the one-shot classification from exact frozen inputs."""
    return validate_zone_evidence(
        run_dir,
        manifest,
        zone=_D2_ZONE,
        project_id=project_id,
        contract_id=contract_id,
        contract=contract,
        observations=observations,
        boundary=boundary,
    )


__all__ = [
    "D2_ANALYSES_ARTIFACT",
    "D2_EVIDENCE_ARTIFACT",
    "crypto_d2_execution_fingerprint",
    "run_crypto_crowding_confirmation",
    "validate_crypto_d2_evidence_artifacts",
]

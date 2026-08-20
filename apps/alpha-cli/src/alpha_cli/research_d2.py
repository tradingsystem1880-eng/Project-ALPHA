"""The one-shot sealed D2 confirmation executor (spec §10, ADR-0026).

Executes ONLY the approval-frozen single primary event-study family of a confirmation
contract, strictly inside the confirmation (D2) share of the evidence topology, and
publishes one immutable v3 run carrying raw measurements (``d2_analyses.json``), the typed
``ResearchGateEvidenceV1`` artifact with its mechanically bound ``confirmation_claim`` and
``confirmation_checks``, and REGISTERED CONFIRMATORY chart data.

Authority model (the D0/D1 pattern): ``d2_analyses.json`` holds RAW measurements only;
the confirmation classification is recomputed from those numbers via
:func:`alpha_research.classify_confirmation` by :func:`derive_d2_findings` — the ONE
mechanical classifier shared by the write path and by
:func:`validate_d2_evidence_artifacts` at admission, so producer pass-flags are never
authority. The whole computation is deterministic (protocol-frozen bootstrap seed, same
policy as D0/D1 — NEVER derived from ``AlphaSettings.random_seed``), so crash recovery is
exact re-execution: an interrupted launch republishes byte-identical artifacts under the
same run identity. The final holdout (D3) is never materialized into the executable view.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final, cast

from alpha_cli import _artifacts
from alpha_cli.research_readiness import derive_research_readiness
from alpha_core import DataError
from alpha_research import (
    ClaimDirection,
    ConfirmationEvidence,
    DoubleBottomSpec,
    EqualDurationResearchBars,
    EventStudyObservation,
    PreEventCovariate,
    ResearchChartData,
    ResearchChartPoint,
    ResearchChartSeries,
    ResearchD2Boundary,
    ResearchEvidenceTopology,
    classify_confirmation,
    detect_double_bottom_events,
    evaluate_event_association,
    evaluate_matched_association,
    match_event_controls,
    render_research_line_chart,
)

D2_EVIDENCE_ARTIFACT: Final = "research_gate_evidence.json"
D2_ANALYSES_ARTIFACT: Final = "d2_analyses.json"
_D2_ANALYSES_SCHEMA: Final = "ResearchD2AnalysesV1"
_D2_RUNTIME_VERSION: Final = 1
# SEED POLICY (the D0/D1 deviation, deliberately repeated): the cluster-bootstrap seed is
# a protocol-frozen literal so admission-time recomputation is machine-independent.
_D2_SEED: Final = 7
_D2_CONFIDENCE: Final = 0.95
_D2_RESAMPLES: Final = 2_000
_MATCHING_COVARIATES: Final = ("weekday",)
_WEEKDAY_CONFOUNDER: Final = "calendar and day of week"
_MAX_EVENT_ROWS: Final = 200
_MAX_ARTIFACT_BYTES: Final = 4 * 1024 * 1024
_PROJECT_ID_RE: Final = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_CONTRACT_ID_RE: Final = re.compile(r"rc_[0-9a-f]{64}")
_SHA256_RE: Final = re.compile(r"[0-9a-f]{64}")


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DataError("D2 research values must be finite and JSON-compatible") from exc


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _fmt(value: float) -> str:
    return format(float(value), ".6g")


def _detector_spec(contract: Mapping[str, object]) -> DoubleBottomSpec:
    protocol = contract.get("protocol")
    operator = None if not isinstance(protocol, Mapping) else protocol.get("d0_operator")
    inner = None if not isinstance(operator, Mapping) else operator.get("operator")
    spec = None if not isinstance(inner, Mapping) else inner.get("spec")
    if not isinstance(spec, Mapping) or set(spec) != {
        "pivot_left",
        "pivot_right",
        "min_separation",
        "max_separation",
        "trough_tolerance",
        "min_rebound",
    }:
        raise DataError("D2 execution requires the frozen registered detector spec")
    return DoubleBottomSpec(
        pivot_left=int(spec["pivot_left"]),
        pivot_right=int(spec["pivot_right"]),
        min_separation=int(spec["min_separation"]),
        max_separation=int(spec["max_separation"]),
        trough_tolerance=float(spec["trough_tolerance"]),
        min_rebound=float(spec["min_rebound"]),
    )


def _claim(contract: Mapping[str, object]) -> dict[str, Any]:
    primary = contract.get("primary_claim")
    if not isinstance(primary, Mapping):
        raise DataError("D2 execution requires one resolved primary claim")
    direction = primary.get("direction")
    if direction not in {"positive", "negative"}:
        raise DataError("D2 primary claim direction must be positive or negative")
    minimum = primary.get("minimum_effect_return")
    if isinstance(minimum, bool) or not isinstance(minimum, int | float) or minimum < 0:
        raise DataError("D2 primary claim requires a non-negative minimum_effect_return")
    confirmation = contract.get("confirmation")
    alpha = None if not isinstance(confirmation, Mapping) else confirmation.get("familywise_alpha")
    if isinstance(alpha, bool) or not isinstance(alpha, int | float) or not 0 < alpha < 0.5:
        raise DataError("D2 familywise alpha must lie in (0, 0.5)")
    confounders = contract.get("confounders", [])
    if not isinstance(confounders, list) or not all(isinstance(item, str) for item in confounders):
        raise DataError("D2 contract confounders must be a list of strings")
    return {
        "direction": direction,
        "minimum_effect_return": float(minimum),
        "alpha": float(alpha),
        "confounders": list(confounders),
    }


def _confirmation_horizon(contract: Mapping[str, object]) -> int:
    plan = contract.get("analysis_plan")
    families = None if not isinstance(plan, Mapping) else plan.get("families")
    if not isinstance(families, list) or len(families) != 1:
        raise DataError("D2 execution requires the frozen single primary family plan")
    entry = families[0]
    if (
        not isinstance(entry, Mapping)
        or entry.get("family") != "event_study"
        or entry.get("multiplicity") != "primary"
    ):
        raise DataError("D2 execution requires one frozen primary event_study family")
    grid = entry.get("grid")
    horizons = None if not isinstance(grid, Mapping) else grid.get("horizon_bars")
    if (
        not isinstance(horizons, list)
        or len(horizons) != 1
        or isinstance(horizons[0], bool)
        or not isinstance(horizons[0], int)
        or horizons[0] < 1
    ):
        raise DataError("D2 execution requires exactly one frozen primary horizon")
    return int(horizons[0])


def _validate_contract(contract: Mapping[str, object]) -> None:
    if contract.get("schema") != "ResearchContractV1":
        raise DataError("D2 execution requires ResearchContractV1")
    if contract.get("scope") != "confirmation":
        raise DataError("D2 execution requires an approved confirmation contract")
    if contract.get("approval_ready") is not True:
        raise DataError("D2 execution requires approval_ready=true")
    if contract.get("blocking_questions") != []:
        raise DataError("D2 execution requires no blocking questions")
    protocol = contract.get("protocol")
    boundary = None if not isinstance(protocol, Mapping) else protocol.get("boundary_authority")
    if (
        not isinstance(boundary, Mapping)
        or boundary.get("kind") != "empirical_dataset"
        or boundary.get("real_market_evidence") is not True
        or boundary.get("empirical_confirmation_authorized") is not True
    ):
        raise DataError("synthetic acceptance boundaries cannot authorize D2 confirmation")
    confirmation = contract.get("confirmation")
    if not isinstance(confirmation, Mapping):
        raise DataError("D2 execution requires the frozen confirmation object")
    if confirmation.get("variant_count") != 1 or confirmation.get("multiplicity_count") != 1:
        raise DataError("D2 execution requires the frozen one-variant confirmation family")
    alpha = confirmation.get("familywise_alpha")
    target = confirmation.get("target_power")
    if (
        isinstance(alpha, bool)
        or not isinstance(alpha, int | float)
        or not math.isclose(float(alpha), 0.05, abs_tol=1e-12)
        or isinstance(target, bool)
        or not isinstance(target, int | float)
        or not math.isclose(float(target), 0.90, abs_tol=1e-12)
    ):
        raise DataError("D2 execution requires the frozen 0.05 alpha and 0.90 target power")
    hashes = contract.get("hashes")
    frozen_data = None if not isinstance(hashes, Mapping) else hashes.get("data")
    if not isinstance(frozen_data, str) or _SHA256_RE.fullmatch(frozen_data) is None:
        raise DataError("D2 execution requires the approval-frozen dataset hash")


def d2_execution_fingerprint(contract: Mapping[str, object]) -> str:
    """Fingerprint the exact D2 runtime, frozen family, and registered detector."""
    _validate_contract(contract)
    spec = _detector_spec(contract)
    return _sha(
        {
            "runtime": "alpha_cli.research_d2.sealed_confirmation",
            "runtime_version": _D2_RUNTIME_VERSION,
            "seed": _D2_SEED,
            "confidence": _D2_CONFIDENCE,
            "n_resamples": _D2_RESAMPLES,
            "horizon_bars": _confirmation_horizon(contract),
            "detector_spec": {
                "pivot_left": spec.pivot_left,
                "pivot_right": spec.pivot_right,
                "min_separation": spec.min_separation,
                "max_separation": spec.max_separation,
                "trough_tolerance": spec.trough_tolerance,
                "min_rebound": spec.min_rebound,
            },
        }
    )


class _D2Data:
    """The confirmation-share view: the ONLY data the one-shot test may read.

    Bars at or beyond the confirmation stop (the final D3 holdout) are never
    materialized into this view, and eligible events are anchored strictly inside the
    confirmation share with outcomes that complete before D3.
    """

    def __init__(
        self,
        bars: EqualDurationResearchBars,
        spec: DoubleBottomSpec,
        horizon: int,
    ) -> None:
        n = len(bars.bars)
        self.topology = ResearchEvidenceTopology.for_observations(
            n, forward_outcome_observations=horizon
        )
        self.discovery_stop = self.topology.discovery.stop
        self.confirmation_stop = self.topology.confirmation.stop
        self.horizon = horizon
        self.bars = EqualDurationResearchBars(bars.dataset, bars.bars[: self.confirmation_stop])
        self.closes = [bar.close for bar in self.bars.bars]
        self.events = detect_double_bottom_events(self.bars, spec)
        self.eligible_stop = self.topology.eligible_event_window("confirmation").stop
        self.eligible_events = tuple(
            event
            for event in self.events
            if self.discovery_stop <= event.confirmation_index < self.eligible_stop
        )
        self.spec = spec
        self.as_of = self.bars.bars[-1].available_at

    def _forward_return(self, index: int) -> float | None:
        settle = index + self.horizon
        if settle >= self.confirmation_stop:
            return None
        anchor_close = self.closes[index]
        return (self.closes[settle] - anchor_close) / anchor_close

    def _observation(self, index: int, *, is_event: bool, outcome: float) -> EventStudyObservation:
        anchor = self.bars.bars[index]
        settle = self.bars.bars[index + self.horizon]
        return EventStudyObservation(
            observation_id=f"{'event' if is_event else 'control'}-{index}",
            is_event=is_event,
            event_at=anchor.end,
            event_available_at=anchor.available_at,
            outcome_start_at=anchor.end,
            outcome_end_at=settle.end,
            outcome_available_at=settle.available_at,
            outcome=outcome,
            cluster_id=anchor.start.date().isoformat(),
            covariates=(
                PreEventCovariate(
                    name="weekday",
                    value=anchor.start.weekday(),
                    observed_at=anchor.start,
                    available_at=anchor.start,
                ),
            ),
        )

    def observations(
        self,
    ) -> tuple[tuple[EventStudyObservation, ...], tuple[EventStudyObservation, ...]]:
        excluded: set[int] = set()
        for event in self.events:
            span_start = max(0, event.first_trough_index - self.spec.pivot_left)
            excluded.update(range(span_start, event.confirmation_index + self.horizon + 1))
        events = tuple(
            self._observation(event.confirmation_index, is_event=True, outcome=float(value))
            for event in self.eligible_events
            if (value := self._forward_return(event.confirmation_index)) is not None
        )
        controls = tuple(
            self._observation(index, is_event=False, outcome=float(value))
            for index in range(self.discovery_stop, self.eligible_stop)
            if index not in excluded and (value := self._forward_return(index)) is not None
        )
        return events, controls


def _estimate_record(estimate: Any) -> dict[str, object]:
    return {
        "estimate": float(estimate.estimate),
        "ci_lower": float(estimate.ci_lower),
        "ci_upper": float(estimate.ci_upper),
        "p_value": float(estimate.p_value),
        "confidence": float(estimate.confidence),
        "sample_size": int(estimate.sample_size),
        "effective_event_count": int(estimate.effective_event_count),
        "low_cluster_count": bool(estimate.low_cluster_count),
    }


def _not_tested() -> dict[str, object]:
    return {"status": "NOT_TESTED", "summary": None}


def derive_d2_findings(
    measurements: Mapping[str, object], *, claim: Mapping[str, object]
) -> dict[str, Any]:
    """Mechanically derive the one-shot D2 evidence from raw measurements — the classifier.

    Every check boolean and the confirmation classification are recomputed from the
    matched numbers via :func:`classify_confirmation`; an honest insufficient-events run
    produces a NOT_TESTED primary with an INCONCLUSIVE classification and no claim.
    """
    direction = claim.get("direction")
    minimum = claim.get("minimum_effect_return")
    alpha = claim.get("alpha")
    confounders = claim.get("confounders", [])
    if direction not in {"positive", "negative"}:
        raise DataError("D2 findings require a registered claim direction")
    if (
        isinstance(minimum, bool)
        or not isinstance(minimum, int | float)
        or isinstance(alpha, bool)
        or not isinstance(alpha, int | float)
        or not isinstance(confounders, list)
    ):
        raise DataError("D2 findings require the frozen claim hurdle, alpha, and confounders")

    matched = measurements.get("matched")
    findings: dict[str, Any] = {
        "schema": "ResearchGateEvidenceV1",
        "evidence_zone": "D2",
        "mechanism": _not_tested(),
        "stability": {
            "parameter": _not_tested(),
            "temporal": _not_tested(),
            "transportability": _not_tested(),
        },
        "negative_controls": _not_tested(),
        "multiplicity": {
            "status": "PASSED",
            "summary": (
                "The frozen family contains exactly one primary hypothesis; the adjusted "
                "p-value equals the raw p-value."
            ),
        },
        "untested_work": [
            "mechanism analysis",
            "cross-dataset transportability",
            "parameter neighborhood beyond the frozen primary cell",
        ],
        "what_would_change_conclusion": [
            "evidence the sealed confirmation share was visible before the freeze",
            "a materially different estimate on later non-overlapping data",
            "an unresolved confounder shown to reproduce the conditional effect",
        ],
    }
    if not isinstance(matched, Mapping):
        findings["primary_result"] = {"status": "NOT_TESTED"}
        findings["confirmation_classification"] = "INCONCLUSIVE"
        findings["confirmation_checks"] = {
            "corrected_primary_test_passed": False,
            "interval_registered_direction": False,
            "economic_hurdle_cleared": False,
            "interval_wholly_against_direction": False,
        }
        findings["strongest_support"] = None
        findings["strongest_contradiction"] = (
            "The sealed confirmation share produced no eligible events to test the claim."
        )
        findings["confounders"] = {
            "resolved": [],
            "unresolved": [str(item) for item in confounders],
        }
        findings["power"] = _not_tested()
        findings.update(derive_research_readiness(findings))
        return findings

    estimate = float(cast(float, matched["estimate"]))
    ci_lower = float(cast(float, matched["ci_lower"]))
    ci_upper = float(cast(float, matched["ci_upper"]))
    p_value = float(cast(float, matched["p_value"]))
    numeric = ConfirmationEvidence(
        direction=ClaimDirection(str(direction)),
        estimate=estimate,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        adjusted_p_value=p_value,
        alpha=float(alpha),
        minimum_effect=float(minimum),
        reliability_passed=not bool(matched.get("low_cluster_count")),
    )
    low_cluster_count = not numeric.reliability_passed
    classification = classify_confirmation(numeric).status.name
    positive = numeric.direction is ClaimDirection.POSITIVE
    checks = {
        "corrected_primary_test_passed": numeric.adjusted_p_value <= numeric.alpha,
        "interval_registered_direction": (
            numeric.ci_lower > 0.0 if positive else numeric.ci_upper < 0.0
        ),
        "economic_hurdle_cleared": (
            numeric.ci_lower > numeric.minimum_effect
            if positive
            else numeric.ci_upper < -numeric.minimum_effect
        ),
        "interval_wholly_against_direction": (
            numeric.ci_upper < 0.0 if positive else numeric.ci_lower > 0.0
        ),
    }
    if positive:
        if ci_lower > float(minimum):
            magnitude_status = "CLEARS_HURDLE"
        elif ci_upper < float(minimum):
            magnitude_status = "BELOW_HURDLE"
        else:
            magnitude_status = "INCONCLUSIVE"
    elif ci_upper < -float(minimum):
        magnitude_status = "CLEARS_HURDLE"
    elif ci_lower > -float(minimum):
        magnitude_status = "BELOW_HURDLE"
    else:
        magnitude_status = "INCONCLUSIVE"
    findings["primary_result"] = {
        "status": "TESTED",
        "estimate": estimate,
        "unit": "arithmetic_return",
        "sample_size": int(cast(int, matched["sample_size"])),
        "effective_sample_size": float(int(cast(int, matched["effective_event_count"]))),
        "uncertainty": {
            "lower": ci_lower,
            "upper": ci_upper,
            "level": float(cast(float, matched["confidence"])),
            "method": "cluster_bootstrap_percentile",
        },
        "practical_magnitude": {
            "status": magnitude_status,
            "value": estimate,
            "unit": "arithmetic_return",
            "interpretation": (
                f"One-shot matched confirmation estimate {_fmt(estimate)} against the "
                f"registered minimum effect {_fmt(float(minimum))}."
            ),
        },
    }
    findings["confirmation_classification"] = classification
    findings["confirmation_checks"] = checks
    findings["confirmation_claim"] = {
        "direction": str(direction),
        "minimum_effect": float(minimum),
        "adjusted_p_value": p_value,
        "alpha": float(alpha),
    }
    findings["strongest_support"] = (
        (
            f"The one-shot matched confirmation estimate {_fmt(estimate)} clears the "
            "registered hurdle on sealed data."
        )
        if classification == "SUPPORTED"
        else None
    )
    if classification == "CONTRADICTED":
        findings["strongest_contradiction"] = (
            "The sealed confirmation interval lies wholly against the registered claim."
        )
    elif classification != "SUPPORTED":
        findings["strongest_contradiction"] = (
            "The sealed confirmation evidence is statistically or economically too imprecise."
        )
    else:
        findings["strongest_contradiction"] = None
    findings["confounders"] = {
        "resolved": [_WEEKDAY_CONFOUNDER],
        "unresolved": [str(item) for item in confounders if str(item) != _WEEKDAY_CONFOUNDER],
    }
    if low_cluster_count:
        findings["power"] = {
            "status": "INCONCLUSIVE",
            "summary": (
                f"Only {int(cast(int, matched['effective_event_count']))} effective event "
                "clusters — below the ten-cluster reliability floor."
            ),
        }
    else:
        findings["power"] = {
            "status": "PASSED",
            "summary": (
                f"{int(cast(int, matched['effective_event_count']))} effective event "
                "clusters support the interval."
            ),
        }
    findings.update(derive_research_readiness(findings))
    return findings


def _publish_text(path: Path, content: str) -> None:
    _publish_bytes(path, content.encode("utf-8"))


def _publish_bytes(path: Path, content: bytes) -> None:
    def write(target: Path) -> None:
        target.write_bytes(content)

    _artifacts.publish_artifact(path, write)


def run_confirmation(
    data_dir: Path,
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
    bars: EqualDurationResearchBars,
    boundary: ResearchD2Boundary,
    on_checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Execute the frozen one-shot confirmation on the sealed D2 share and publish one run."""
    if _PROJECT_ID_RE.fullmatch(project_id) is None:
        raise DataError("D2 execution requires a canonical project_id")
    if _CONTRACT_ID_RE.fullmatch(contract_id) is None:
        raise DataError("D2 execution requires a content-addressed contract_id")
    _validate_contract(contract)
    spec = _detector_spec(contract)
    claim = _claim(contract)
    horizon = _confirmation_horizon(contract)
    dataset_hash = bars.dataset.content_sha256
    if _SHA256_RE.fullmatch(dataset_hash) is None:
        raise DataError("D2 execution requires a content-addressed dataset hash")
    hashes = contract.get("hashes")
    frozen_data = None if not isinstance(hashes, Mapping) else hashes.get("data")
    if frozen_data != dataset_hash:
        raise DataError(
            "loaded dataset bytes do not reproduce the approval-frozen confirmation data hash"
        )
    if boundary.dataset_fingerprint != dataset_hash:
        raise DataError(
            "sealed boundary dataset fingerprint does not match the loaded research dataset"
        )
    groups = [bar.start.date().isoformat() for bar in bars.bars]
    if not boundary.verify_eligible_groups(groups):
        raise DataError(
            "loaded session groups do not reproduce the sealed boundary's eligible groups"
        )
    data = _D2Data(bars, spec, horizon)
    if (
        data.discovery_stop != boundary.d1.stop_index
        or data.confirmation_stop != boundary.d2.stop_index
    ):
        raise DataError(
            "the executable confirmation share does not align with the sealed boundary's D2 zone"
        )
    if on_checkpoint is not None:
        on_checkpoint("d2:sealed-share-verified")

    events, controls = data.observations()
    measurements: dict[str, object] = {
        "topology": {
            "total_observations": data.topology.total_observations,
            "discovery_stop": data.discovery_stop,
            "confirmation_stop": data.confirmation_stop,
            "eligible_event_stop": data.eligible_stop,
            "embargo": horizon,
            "contract_hash": data.topology.contract_hash,
        },
        "events": {
            "detected_in_view": len(data.events),
            "eligible": len(data.eligible_events),
            "rows": [
                {
                    "first_trough_index": event.first_trough_index,
                    "second_trough_index": event.second_trough_index,
                    "confirmation_index": event.confirmation_index,
                    "rebound": event.rebound,
                    "trough_difference": event.trough_difference,
                }
                for event in data.eligible_events[:_MAX_EVENT_ROWS]
            ],
        },
        "counts": {"events": len(events), "controls": len(controls)},
    }
    if events and len(controls) >= 1:
        try:
            unadjusted = evaluate_event_association(
                events,
                as_of=data.as_of,
                confidence=_D2_CONFIDENCE,
                n_resamples=_D2_RESAMPLES,
                seed=_D2_SEED,
            )
            matched_study = match_event_controls(
                (*events, *controls),
                covariate_names=_MATCHING_COVARIATES,
                as_of=data.as_of,
            )
            matched = evaluate_matched_association(
                matched_study,
                confidence=_D2_CONFIDENCE,
                n_resamples=_D2_RESAMPLES,
                seed=_D2_SEED,
            )
        except DataError as exc:
            # The D1 skipped-family pattern: an uncomputable frozen statistic is recorded
            # honestly (NOT_TESTED / INCONCLUSIVE), never hidden and never fabricated.
            measurements["unadjusted"] = None
            measurements["matched"] = None
            measurements["matched_pairs"] = 0
            measurements["statistic_error"] = str(exc)[:2_000]
        else:
            measurements["unadjusted"] = _estimate_record(unadjusted)
            measurements["matched"] = _estimate_record(matched)
            measurements["matched_pairs"] = len(matched_study.pairs)
    else:
        measurements["unadjusted"] = None
        measurements["matched"] = None
        measurements["matched_pairs"] = 0
    if on_checkpoint is not None:
        on_checkpoint("d2:one-shot-family-complete")

    findings = derive_d2_findings(measurements, claim=claim)
    contract_hash = _sha(contract)
    execution_fingerprint = d2_execution_fingerprint(contract)
    run_identity = {
        "command": "research_confirm",
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "dataset_hash": dataset_hash,
        "execution_fingerprint": execution_fingerprint,
    }
    run_id = _sha(run_identity)[:16]
    run_dir = _artifacts.run_dir(Path(data_dir), run_id)

    analyses_payload = {
        "schema": _D2_ANALYSES_SCHEMA,
        "schema_version": 1,
        "measurements": measurements,
    }
    analyses_bytes = _canonical(analyses_payload).encode("utf-8")
    analyses_sha = hashlib.sha256(analyses_bytes).hexdigest()

    chart_points = tuple(
        ResearchChartPoint(ts=bar.end, value=bar.close)
        for bar in data.bars.bars[data.discovery_stop :]
    )
    chart_series = ResearchChartSeries(
        series_id="confirmation-close",
        label="Confirmation-share close",
        unit="price",
        points=chart_points,
    )
    chart_series_sha = _sha(chart_series.to_dict())
    classification = str(findings["confirmation_classification"])
    chart = ResearchChartData(
        chart_id="d2-one-shot-confirmation",
        title="D2 sealed-share prices and the one-shot confirmation",
        x_label="Session close (UTC)",
        y_label="Close",
        evidence_phase="confirmatory",
        dataset_sha256=dataset_hash,
        protocol_sha256=contract_hash,
        question="Does the frozen primary contrast hold on the sealed confirmation share?",
        plain_language_answer=str(
            findings["strongest_support"] or findings["strongest_contradiction"]
        ),
        sample_size=len(chart_points),
        effective_sample_size=float(max(1, len(data.eligible_events))),
        uncertainty="Cluster-bootstrap percentile interval; see the evidence artifact.",
        caveat=(
            "One-shot REGISTERED CONFIRMATORY evidence; the final holdout (D3) remains "
            "sealed and this is never execution authority."
        ),
        run_id=run_id,
        artifact_id="d2-one-shot-confirmation-series",
        artifact_sha256=chart_series_sha,
        series=(chart_series,),
    )
    evidence = {
        **findings,
        "artifact_links": [
            {
                "run_id": run_id,
                "artifact_id": D2_ANALYSES_ARTIFACT,
                "content_sha256": analyses_sha,
                "media_type": "application/json",
            }
        ],
    }

    _publish_bytes(run_dir / D2_ANALYSES_ARTIFACT, analyses_bytes)
    _publish_text(run_dir / D2_EVIDENCE_ARTIFACT, _canonical(evidence))
    _publish_text(
        run_dir / "chart-data.json",
        json.dumps(chart.to_dict(), sort_keys=True, indent=2, allow_nan=False),
    )
    _publish_bytes(run_dir / "d2-one-shot-confirmation.png", render_research_line_chart(chart))
    _publish_text(
        run_dir / "report.md",
        "# D2 Sealed Confirmation\n\n"
        "**REGISTERED CONFIRMATORY — ONE-SHOT SEALED-SHARE EVIDENCE**\n\n"
        f"The frozen primary family executed once on the sealed confirmation share and "
        f"classified {classification}. The final holdout (D3) was never read. The "
        "classification is mechanically re-derived from raw measurements at every "
        "admission and read.\n",
    )
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "run_identity_version": 3,
        "command": "research_confirm",
        "kind": "research",
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "source_pack_id": contract.get("source_pack_id"),
        "research_fingerprints": dict(cast(Mapping[str, object], contract.get("hashes", {}))),
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


def _read_canonical_json(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise DataError(f"{label} is not a regular immutable file")
    raw = path.read_bytes()
    if len(raw) > _MAX_ARTIFACT_BYTES:
        raise DataError(f"{label} exceeds the bounded JSON size")
    try:
        parsed: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise DataError(f"{label} must contain a JSON object")
    if raw != _canonical(parsed).encode("utf-8"):
        raise DataError(f"{label} must use canonical JSON bytes")
    return parsed


def _manifest_artifact_sha(manifest: Mapping[str, object], name: str) -> str:
    artifacts = manifest.get("artifacts")
    metadata = None if not isinstance(artifacts, Mapping) else artifacts.get(name)
    sha = None if not isinstance(metadata, Mapping) else metadata.get("sha256")
    if not isinstance(sha, str) or _SHA256_RE.fullmatch(sha) is None:
        raise DataError(f"D2 run manifest does not declare immutable artifact {name!r}")
    return sha


def validate_d2_evidence_artifacts(
    run_dir: Path,
    manifest: Mapping[str, object],
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
) -> dict[str, Any]:
    """Re-verify one D2 run's typed evidence by exact mechanical recomputation.

    Producer classification and check booleans are never authority: everything is
    re-derived from the raw measurements artifact via the same classifier the writer
    used, and any divergence — including a post-admission rewrite — fails closed.
    """
    if manifest.get("command") != "research_confirm" or manifest.get("evidence_zone") != "D2":
        raise DataError("D2 evidence verification requires a research_confirm D2 manifest")
    if manifest.get("project_id") != project_id:
        raise DataError("D2 evidence verification project does not match the manifest")
    if manifest.get("research_contract_id") != contract_id:
        raise DataError("D2 evidence verification contract does not match the manifest")
    if manifest.get("d2_evidence_artifact") != D2_EVIDENCE_ARTIFACT:
        raise DataError("D2 manifest does not select its typed evidence artifact")

    analyses_sha = _manifest_artifact_sha(manifest, D2_ANALYSES_ARTIFACT)
    evidence_sha = _manifest_artifact_sha(manifest, D2_EVIDENCE_ARTIFACT)
    analyses_path = run_dir / D2_ANALYSES_ARTIFACT
    evidence_path = run_dir / D2_EVIDENCE_ARTIFACT
    analyses_bytes = analyses_path.read_bytes() if analyses_path.is_file() else b""
    evidence_bytes = evidence_path.read_bytes() if evidence_path.is_file() else b""
    if hashlib.sha256(analyses_bytes).hexdigest() != analyses_sha:
        raise DataError("D2 analyses artifact does not match its immutable manifest hash")
    if hashlib.sha256(evidence_bytes).hexdigest() != evidence_sha:
        raise DataError("D2 evidence artifact does not match its immutable manifest hash")

    analyses = _read_canonical_json(analyses_path, "D2 analyses artifact")
    evidence = _read_canonical_json(evidence_path, "D2 evidence artifact")
    if analyses.get("schema") != _D2_ANALYSES_SCHEMA:
        raise DataError("D2 analyses artifact has an unsupported schema")
    measurements = analyses.get("measurements")
    if not isinstance(measurements, Mapping):
        raise DataError("D2 analyses artifact has no raw measurements")

    expected = derive_d2_findings(measurements, claim=_claim(contract))
    produced = {key: value for key, value in evidence.items() if key != "artifact_links"}
    legacy_expected = {
        key: value
        for key, value in expected.items()
        if key not in {"confirmation_readiness", "promotion_readiness"}
    }
    if _canonical(produced) not in {_canonical(expected), _canonical(legacy_expected)}:
        raise DataError(
            "D2 evidence findings fail exact mechanical recomputation from raw measurements"
        )
    links = evidence.get("artifact_links")
    if not isinstance(links, list) or not links:
        raise DataError("D2 evidence must link its immutable measurement artifacts")
    linked_analyses = False
    for link in links:
        if not isinstance(link, Mapping):
            raise DataError("D2 evidence artifact links must be objects")
        artifact_id = link.get("artifact_id")
        if not isinstance(artifact_id, str):
            raise DataError("D2 evidence artifact links must name their artifacts")
        if link.get("run_id") != manifest.get("run_id"):
            raise DataError("D2 evidence artifact links must bind their own run")
        if link.get("content_sha256") != _manifest_artifact_sha(manifest, artifact_id):
            raise DataError("D2 evidence artifact link hash does not match the manifest")
        if artifact_id == D2_ANALYSES_ARTIFACT:
            linked_analyses = True
    if not linked_analyses:
        raise DataError("D2 evidence must link the raw measurements artifact")
    return evidence


__all__ = [
    "D2_ANALYSES_ARTIFACT",
    "D2_EVIDENCE_ARTIFACT",
    "d2_execution_fingerprint",
    "derive_d2_findings",
    "run_confirmation",
    "validate_d2_evidence_artifacts",
]

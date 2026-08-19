"""The preregistered D1 deep-research executor (spec §9.3, ADR-0025).

Executes the frozen ``analysis_plan`` of an approved exploration contract over registered
research-only bars, strictly inside the discovery (D1) share of the evidence topology, and
publishes one immutable v3 run carrying raw measurements (``d1_analyses.json``), the typed
``ResearchGateEvidenceV1`` artifact, and EXPLORATORY-watermarked chart data.

Authority model (the D0 pattern): ``d1_analyses.json`` holds RAW measurements only; every
finding status in the evidence artifact is recomputed from those measurements by
:func:`derive_d1_findings` — the ONE mechanical classifier shared by the write path and by
:func:`validate_d1_evidence_artifacts` at admission, so producer pass-flags are never
authority. A research run has no orders, fills, sizing, or costs; economic magnitude enters
only as the registered minimum-effect hurdle. The whole computation is deterministic
(protocol-frozen bootstrap seed, like the D0 power seed — NEVER derived from
``AlphaSettings.random_seed``), so crash recovery is exact re-execution: an interrupted
launch republishes byte-identical artifacts under the same run identity.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final, cast

from alpha_cli import _artifacts
from alpha_cli.research_analysis_plan import validate_analysis_plan
from alpha_cli.research_readiness import derive_research_readiness
from alpha_core import DataError
from alpha_research import (
    DoubleBottomSpec,
    EqualDurationResearchBars,
    EventStudyObservation,
    FrozenSecondaryFamily,
    PreEventCovariate,
    ResearchBar,
    ResearchChartData,
    ResearchChartPoint,
    ResearchChartSeries,
    ResearchD2Boundary,
    ResearchDatasetRef,
    ResearchEvidenceTopology,
    SecondaryHypothesis,
    detect_double_bottom_events,
    evaluate_event_association,
    evaluate_matched_association,
    holm_adjust_secondary_family,
    match_event_controls,
    render_research_line_chart,
)
from alpha_research.conditional_returns import (
    conditional_return_summary,
    difference_in_means,
    forward_returns,
    quantile_breakdown,
)
from alpha_research.ic import rank_ic
from alpha_research.leadlag import leadlag_profile, leakage_diagnostic
from alpha_research.stability import subsample_consistency, temporal_split_effects

D1_EVIDENCE_ARTIFACT: Final = "research_gate_evidence.json"
D1_ANALYSES_ARTIFACT: Final = "d1_analyses.json"
_D1_ANALYSES_SCHEMA: Final = "ResearchD1AnalysesV1"
_D1_RUNTIME_VERSION: Final = 1
# SEED POLICY (the D0 deviation, deliberately repeated): the cluster-bootstrap seed is a
# protocol-frozen literal so admission-time recomputation is machine-independent; deriving
# it from AlphaSettings.random_seed would make verification depend on the reader's config.
_D1_SEED: Final = 7
_D1_CONFIDENCE: Final = 0.95
_D1_RESAMPLES: Final = 2_000
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
        raise DataError("D1 research values must be finite and JSON-compatible") from exc


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _fmt(value: float) -> str:
    return format(float(value), ".6g")


def research_bars_from_lows(
    lows: Sequence[float],
    *,
    dataset_id: str,
    content_sha256: str,
    start: datetime,
    bar_duration: timedelta = timedelta(hours=1),
) -> EqualDurationResearchBars:
    """Deterministic research bars from a low series (the registered synthetic geometry)."""
    if not lows:
        raise DataError("research bars require at least one low value")
    minutes = int(bar_duration.total_seconds()) // 60
    dataset = ResearchDatasetRef(
        dataset_id=dataset_id,
        provider="alpha_synthetic_fixture",
        provider_symbol="SYNTHETIC_SPY",
        symbol="SPY",
        venue="SYNTHETIC",
        timeframe=f"{minutes}m",
        timezone="UTC",
        session="synthetic_equal_duration",
        content_sha256=content_sha256,
    )
    bars = tuple(
        ResearchBar(
            dataset_id=dataset_id,
            start=start + index * bar_duration,
            end=start + (index + 1) * bar_duration,
            available_at=start + (index + 1) * bar_duration,
            open=low + 1.0,
            high=low + 6.0,
            low=low,
            close=low + 2.0,
            volume=1_000.0 + index,
        )
        for index, low in enumerate(lows)
    )
    return EqualDurationResearchBars(dataset, bars)


_DAILY_BAR_MINUTES: Final = 1_440


def load_registered_research_bars(
    data_dir: Path, *, ref: Mapping[str, object]
) -> EqualDurationResearchBars:
    """Load a registered dataset as research bars — the Gate-4 Tiingo-daily fallback lane.

    ADR-0020 acceptance: only the fixed session-daily (1440-minute) representation is
    loadable; duplicates, disorder, incoherent OHLC, or a non-daily registration fail
    loud. Qualified intraday loading (the QuantPad lane) requires approved retention and
    licensing evidence and is explicitly unavailable here (ADR-0023).
    """
    if ref.get("dataset_kind") == "quantpad_receipt":
        raise DataError(
            "qualified intraday research loading requires approved QuantPad retention and "
            "licensing evidence (ADR-0023); only the registered Tiingo-daily fallback lane "
            "is loadable"
        )
    duration = ref.get("bar_duration_minutes")
    if duration is not None and duration != _DAILY_BAR_MINUTES:
        raise DataError(
            "only the registered Tiingo-daily fallback lane is loadable; this dataset "
            f"registers {duration!r}-minute bars"
        )
    from alpha_cli.research_data_audit import load_registered_dataset_frame

    frame = load_registered_dataset_frame(Path(data_dir), ref=ref)
    if frame.height == 0:
        raise DataError("registered research dataset holds no bars in its range")
    ref_id = str(ref.get("ref_id"))
    instrument = str(ref.get("instrument", ""))
    rows = frame.to_dicts()
    previous_ts: datetime | None = None
    bars: list[ResearchBar] = []
    for row in rows:
        ts = row["ts"]
        if not isinstance(ts, datetime):
            raise DataError("registered research dataset bars must carry datetime timestamps")
        if previous_ts is not None and ts <= previous_ts:
            raise DataError(
                "registered research dataset bars must be strictly ordered without duplicates"
            )
        previous_ts = ts
        end = ts + timedelta(minutes=_DAILY_BAR_MINUTES)
        bars.append(
            ResearchBar(
                dataset_id=ref_id,
                start=ts,
                end=end,
                available_at=end,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
        )
    content_sha = _sha(
        {
            "schema": "AlphaResearchDailyBarsV1",
            "instrument": instrument,
            "rows": [
                {
                    "ts": bar.start.isoformat(),
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
                for bar in bars
            ],
        }
    )
    dataset = ResearchDatasetRef(
        dataset_id=ref_id,
        provider=str(ref.get("provider", "")) or "unknown",
        provider_symbol=instrument,
        symbol=instrument,
        venue="RESEARCH_DAILY",
        timeframe="1d",
        timezone="UTC",
        session="regular_session_daily",
        content_sha256=content_sha,
    )
    return EqualDurationResearchBars(dataset, tuple(bars))


# The registered synthetic D1 fixture: detectable planted motifs with a mean-zero
# post-confirmation wobble. It exercises the complete pipeline WITHOUT manufacturing a
# supporting result — synthetic D1 evidence must never look like a discovered edge.
_D1_SYNTHETIC_MOTIF: Final = (105.0, 103.0, 100.0, 95.0, 99.0, 101.0, 100.0, 95.5, 99.0, 101.0)
_D1_SYNTHETIC_WEEKS: Final = 8
_D1_SYNTHETIC_START: Final = "2020-01-06T00:00:00+00:00"  # a Monday


def registered_synthetic_d1_lows() -> list[float]:
    lows: list[float] = []
    for week in range(_D1_SYNTHETIC_WEEKS):
        for day in range(7):
            if day != 0:
                lows.extend([100.0] * 24)
                continue
            lows.extend(_D1_SYNTHETIC_MOTIF)
            base = _D1_SYNTHETIC_MOTIF[-1]
            wobble = 0.3 if week % 2 else -0.3
            for hour in range(14):
                lows.append(base + (wobble if hour % 2 else 0.0))
    return lows


def registered_synthetic_d1_bars() -> EqualDurationResearchBars:
    """The one registered synthetic D1 dataset (content-addressed, null by construction)."""
    lows = registered_synthetic_d1_lows()
    return research_bars_from_lows(
        lows,
        dataset_id="d1-synthetic-null",
        content_sha256=_sha(
            {
                "schema": "AlphaSyntheticD1FixtureV1",
                "start": _D1_SYNTHETIC_START,
                "lows": lows,
            }
        ),
        start=datetime.fromisoformat(_D1_SYNTHETIC_START),
    )


def _plan(contract: Mapping[str, object]) -> dict[str, Any]:
    plan = contract.get("analysis_plan")
    budget = contract.get("budget")
    variants = None if not isinstance(budget, Mapping) else budget.get("variants")
    if isinstance(variants, bool) or not isinstance(variants, int) or variants < 1:
        raise DataError("D1 execution requires a positive integer variants budget")
    if not isinstance(plan, Mapping):
        raise DataError(
            "D1 execution requires the frozen analysis_plan registered at exploration approval"
        )
    return validate_analysis_plan(plan, max_grid_cells=variants)


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
        raise DataError("D1 execution requires the frozen registered detector spec")
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
        raise DataError("D1 execution requires one resolved primary claim")
    direction = primary.get("direction")
    if direction not in {"positive", "negative"}:
        raise DataError("D1 primary claim direction must be positive or negative")
    minimum = primary.get("minimum_effect_return")
    if isinstance(minimum, bool) or not isinstance(minimum, int | float) or minimum < 0:
        raise DataError("D1 primary claim requires a non-negative minimum_effect_return")
    policy = contract.get("statistical_policy")
    alpha = 0.05 if not isinstance(policy, Mapping) else policy.get("familywise_alpha", 0.05)
    if isinstance(alpha, bool) or not isinstance(alpha, int | float) or not 0 < alpha < 0.5:
        raise DataError("D1 familywise alpha must lie in (0, 0.5)")
    confounders = contract.get("confounders", [])
    if not isinstance(confounders, list) or not all(isinstance(item, str) for item in confounders):
        raise DataError("D1 contract confounders must be a list of strings")
    plan = contract.get("analysis_plan")
    plan_families = [] if not isinstance(plan, Mapping) else plan.get("families", [])
    if not isinstance(plan_families, list):
        raise DataError("D1 contract analysis_plan families must be a list")
    required_families = [
        str(entry["family"])
        for entry in plan_families
        if isinstance(entry, Mapping) and isinstance(entry.get("family"), str)
    ]
    required_falsifiers = [
        str(entry["family"])
        for entry in plan_families
        if isinstance(entry, Mapping)
        and isinstance(entry.get("family"), str)
        and entry.get("multiplicity") == "falsification"
    ]
    return {
        "direction": direction,
        "minimum_effect_return": float(minimum),
        "alpha": float(alpha),
        "confounders": list(confounders),
        "required_families": required_families,
        "required_falsifiers": required_falsifiers,
    }


def _validate_contract(contract: Mapping[str, object]) -> None:
    if contract.get("schema") != "ResearchContractV1":
        raise DataError("D1 execution requires ResearchContractV1")
    if contract.get("scope") != "exploration":
        raise DataError("D1 execution requires an exploration contract")
    if contract.get("approval_ready") is not True:
        raise DataError("D1 execution requires approval_ready=true")
    if contract.get("blocking_questions") != []:
        raise DataError("D1 execution requires no blocking questions")
    protocol = contract.get("protocol")
    boundary = None if not isinstance(protocol, Mapping) else protocol.get("boundary_authority")
    kind = None if not isinstance(boundary, Mapping) else boundary.get("kind")
    if kind not in {"synthetic_acceptance_fixture", "empirical_dataset"}:
        raise DataError("D1 execution requires a registered boundary authority kind")
    hashes = contract.get("hashes")
    if not isinstance(hashes, Mapping):
        raise DataError("D1 execution requires frozen contract fingerprints")


def _real_market_evidence(contract: Mapping[str, object]) -> bool:
    protocol = contract.get("protocol")
    boundary = None if not isinstance(protocol, Mapping) else protocol.get("boundary_authority")
    value = None if not isinstance(boundary, Mapping) else boundary.get("real_market_evidence")
    if not isinstance(value, bool):
        raise DataError("D1 boundary authority must declare real_market_evidence")
    return value


def d1_execution_fingerprint(contract: Mapping[str, object]) -> str:
    """Fingerprint the exact D1 runtime, frozen plan, and registered detector."""
    _validate_contract(contract)
    plan = _plan(contract)
    spec = _detector_spec(contract)
    return _sha(
        {
            "runtime": "alpha_cli.research_d1.deep_research",
            "runtime_version": _D1_RUNTIME_VERSION,
            "seed": _D1_SEED,
            "confidence": _D1_CONFIDENCE,
            "n_resamples": _D1_RESAMPLES,
            "analysis_plan": plan,
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


def _grid_cells(grid: Mapping[str, object]) -> list[dict[str, int | float]]:
    axes = sorted(grid)
    if not axes:
        return [{}]
    values: list[list[int | float]] = []
    for axis in axes:
        axis_values = grid[axis]
        if not isinstance(axis_values, list):
            raise DataError(f"analysis grid axis {axis!r} must be a list")
        values.append([value for value in axis_values if isinstance(value, int | float)])
    cells: list[dict[str, int | float]] = []
    for combo in itertools.product(*values):
        cells.append(dict(zip(axes, combo, strict=True)))
    return cells


def _int_param(cell: Mapping[str, object], name: str, default: int) -> int:
    value = cell.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int | float) or int(value) != value:
        raise DataError(f"analysis grid parameter {name!r} must be an integer")
    return int(value)


class _D1Data:
    """The discovery-share view: the ONLY data any D1 family may read."""

    def __init__(
        self,
        bars: EqualDurationResearchBars,
        spec: DoubleBottomSpec,
        embargo: int,
    ) -> None:
        n = len(bars.bars)
        self.topology = ResearchEvidenceTopology.for_observations(
            n, forward_outcome_observations=embargo
        )
        stop = self.topology.discovery.stop
        self.discovery_stop = stop
        self.embargo = embargo
        self.bars = EqualDurationResearchBars(bars.dataset, bars.bars[:stop])
        self.closes = [bar.close for bar in self.bars.bars]
        self.events = detect_double_bottom_events(self.bars, spec)
        self.eligible_stop = self.topology.eligible_event_window("discovery").stop
        self.eligible_events = tuple(
            event for event in self.events if event.confirmation_index < self.eligible_stop
        )
        self.spec = spec
        self.as_of = self.bars.bars[-1].available_at

    def outcomes(self, horizon: int) -> list[float | None]:
        return forward_returns(self.closes, horizon=horizon)

    def event_anchor_indices(self) -> list[int]:
        return [event.confirmation_index for event in self.eligible_events]

    def _observation(
        self, index: int, *, horizon: int, is_event: bool, outcome: float
    ) -> EventStudyObservation:
        anchor = self.bars.bars[index]
        settle = self.bars.bars[index + horizon]
        return EventStudyObservation(
            observation_id=f"{'event' if is_event else 'control'}-{index}",
            is_event=is_event,
            event_at=anchor.end,
            event_available_at=anchor.available_at,
            outcome_start_at=anchor.end,
            outcome_end_at=settle.end,
            outcome_available_at=settle.available_at,
            outcome=outcome,
            # The bar START owns the session day: a bar closing exactly at midnight (the
            # last hourly bar, or a whole daily session) must not be relabelled tomorrow.
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
        self, horizon: int
    ) -> tuple[tuple[EventStudyObservation, ...], tuple[EventStudyObservation, ...]]:
        outcomes = self.outcomes(horizon)
        excluded: set[int] = set()
        for event in self.events:
            span_start = max(0, event.first_trough_index - self.spec.pivot_left)
            excluded.update(range(span_start, event.confirmation_index + horizon + 1))
        event_anchors = set(self.event_anchor_indices())
        events = tuple(
            self._observation(index, horizon=horizon, is_event=True, outcome=float(value))
            for index in sorted(event_anchors)
            if index + horizon < self.discovery_stop and (value := outcomes[index]) is not None
        )
        controls = tuple(
            self._observation(index, horizon=horizon, is_event=False, outcome=float(value))
            for index in range(self.eligible_stop)
            if index not in excluded
            and index + horizon < self.discovery_stop
            and (value := outcomes[index]) is not None
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


def _family_event_study(data: _D1Data, cell: Mapping[str, object]) -> dict[str, object]:
    horizon = _int_param(cell, "horizon_bars", data.embargo)
    events, controls = data.observations(horizon)
    if not events:
        raise DataError("no eligible events were detected in the discovery share")
    unadjusted = evaluate_event_association(
        events,
        as_of=data.as_of,
        confidence=_D1_CONFIDENCE,
        n_resamples=_D1_RESAMPLES,
        seed=_D1_SEED,
    )
    matched_study = match_event_controls(
        (*events, *controls),
        covariate_names=_MATCHING_COVARIATES,
        as_of=data.as_of,
    )
    matched = evaluate_matched_association(
        matched_study,
        confidence=_D1_CONFIDENCE,
        n_resamples=_D1_RESAMPLES,
        seed=_D1_SEED,
    )
    return {
        "params": dict(cell),
        "counts": {
            "events_detected": len(data.events),
            "events_eligible": len(events),
            "events_embargoed": len(data.events) - len(data.eligible_events),
            "controls": len(controls),
            "matched_pairs": len(matched_study.pairs),
            "unmatched_events": len(matched_study.unmatched_event_ids),
        },
        "unadjusted": _estimate_record(unadjusted),
        "matched": _estimate_record(matched),
    }


def _family_conditional_returns(data: _D1Data, cell: Mapping[str, object]) -> dict[str, object]:
    horizon = _int_param(cell, "horizon_bars", data.embargo)
    events, controls = data.observations(horizon)
    if len(events) < 2 or len(controls) < 2:
        raise DataError("conditional returns require at least two events and two controls")
    event_outcomes = [item.outcome for item in events]
    baseline_outcomes = [item.outcome for item in controls]
    baseline_mean = sum(baseline_outcomes) / len(baseline_outcomes)
    centered = tuple(
        EventStudyObservation(
            observation_id=item.observation_id,
            is_event=True,
            event_at=item.event_at,
            event_available_at=item.event_available_at,
            outcome_start_at=item.outcome_start_at,
            outcome_end_at=item.outcome_end_at,
            outcome_available_at=item.outcome_available_at,
            outcome=item.outcome - baseline_mean,
            cluster_id=item.cluster_id,
            covariates=item.covariates,
        )
        for item in events
    )
    contrast = evaluate_event_association(
        centered,
        as_of=data.as_of,
        confidence=_D1_CONFIDENCE,
        n_resamples=_D1_RESAMPLES,
        seed=_D1_SEED,
    )
    return {
        "params": dict(cell),
        "summary": conditional_return_summary(
            {"event": event_outcomes, "baseline": baseline_outcomes}
        ),
        "difference": difference_in_means(event_outcomes, baseline_outcomes),
        "centered_estimate": float(contrast.estimate),
        "centered_p_value": float(contrast.p_value),
    }


def _event_outcome_values(data: _D1Data) -> list[float]:
    events, _ = data.observations(data.embargo)
    return [item.outcome for item in events]


def _family_temporal_stability(data: _D1Data, cell: Mapping[str, object]) -> dict[str, object]:
    values = _event_outcome_values(data)
    n_periods = _int_param(cell, "n_periods", 2)
    return {"params": dict(cell), "periods": temporal_split_effects(values, n_periods=n_periods)}


def _family_subsample_consistency(data: _D1Data, cell: Mapping[str, object]) -> dict[str, object]:
    values = _event_outcome_values(data)
    n_splits = _int_param(cell, "n_splits", 4)
    return {"params": dict(cell), "result": subsample_consistency(values, n_splits=n_splits)}


def _family_rank_ic(data: _D1Data, cell: Mapping[str, object]) -> dict[str, object]:
    events, _ = data.observations(data.embargo)
    by_anchor = {event.confirmation_index: event for event in data.eligible_events}
    signals: list[float] = []
    outcomes: list[float] = []
    for observation in events:
        index = int(observation.observation_id.split("-", 1)[1])
        signals.append(float(by_anchor[index].rebound))
        outcomes.append(observation.outcome)
    return {"params": dict(cell), "rank_ic": rank_ic(signals, outcomes)}


def _family_quantile_breakdown(data: _D1Data, cell: Mapping[str, object]) -> dict[str, object]:
    events, _ = data.observations(data.embargo)
    by_anchor = {event.confirmation_index: event for event in data.eligible_events}
    signals: list[float] = []
    outcomes: list[float] = []
    for observation in events:
        index = int(observation.observation_id.split("-", 1)[1])
        signals.append(float(by_anchor[index].rebound))
        outcomes.append(observation.outcome)
    quantiles = _int_param(cell, "quantiles", 4)
    return {
        "params": dict(cell),
        "rows": quantile_breakdown(signals, outcomes, quantiles=quantiles),
    }


def _family_shuffled_event_null(data: _D1Data, cell: Mapping[str, object]) -> dict[str, object]:
    shuffles = _int_param(cell, "shuffles", 200)
    if shuffles < 10:
        raise DataError("shuffled-event null requires at least ten registered shuffles")
    anchors = data.event_anchor_indices()
    if not anchors:
        raise DataError("no eligible events were detected in the discovery share")
    outcomes = data.outcomes(data.embargo)
    span = data.eligible_stop
    observed_values = [v for a in anchors if (v := outcomes[a]) is not None]
    observed = sum(observed_values) / len(observed_values)
    placebo_means: list[float] = []
    for k in range(1, shuffles + 1):
        offset = max(1, round(k * span / (shuffles + 1)))
        shifted = sorted({(anchor + offset) % span for anchor in anchors})
        values = [v for index in shifted if (v := outcomes[index]) is not None]
        if values:
            placebo_means.append(sum(values) / len(values))
    if not placebo_means:
        raise DataError("shuffled-event null produced no valid placebo anchors")
    at_least = sum(1 for mean in placebo_means if mean >= observed)
    at_most = sum(1 for mean in placebo_means if mean <= observed)
    return {
        "params": dict(cell),
        "observed_mean": float(observed),
        "placebo_count": len(placebo_means),
        "placebo_mean": float(sum(placebo_means) / len(placebo_means)),
        "placebo_p_upper": (at_least + 1) / (len(placebo_means) + 1),
        "placebo_p_lower": (at_most + 1) / (len(placebo_means) + 1),
    }


def _family_leadlag_leakage(data: _D1Data, cell: Mapping[str, object]) -> dict[str, object]:
    max_lag = _int_param(cell, "max_lag", 3)
    horizon = data.embargo
    outcomes = data.outcomes(horizon)
    anchors = set(data.event_anchor_indices())
    indicator: list[float] = []
    strided_outcomes: list[float] = []
    for start in range(0, data.eligible_stop - horizon + 1, horizon):
        value = outcomes[start]
        if value is None:  # pragma: no cover - eligible anchors always have outcomes.
            continue
        indicator.append(
            1.0 if any(index in anchors for index in range(start, start + horizon)) else 0.0
        )
        strided_outcomes.append(float(value))
    # Lag units are whole non-overlapping outcome windows, so adjacent-window overlap can
    # never masquerade as leakage.
    return {
        "params": dict(cell),
        "stride_bars": horizon,
        "profile": leadlag_profile(indicator, strided_outcomes, max_lag=max_lag),
    }


_FAMILY_RUNNERS: Final[dict[str, Callable[[_D1Data, Mapping[str, object]], dict[str, object]]]] = {
    "event_study": _family_event_study,
    "conditional_returns": _family_conditional_returns,
    "temporal_stability": _family_temporal_stability,
    "subsample_consistency": _family_subsample_consistency,
    "rank_ic": _family_rank_ic,
    "quantile_breakdown": _family_quantile_breakdown,
    "shuffled_event_null": _family_shuffled_event_null,
    "leadlag_leakage": _family_leadlag_leakage,
}


def _not_tested() -> dict[str, object]:
    return {"status": "NOT_TESTED", "summary": None}


def _magnitude_status(*, direction: str, ci_lower: float, ci_upper: float, minimum: float) -> str:
    if direction == "positive":
        if ci_lower > minimum:
            return "CLEARS_HURDLE"
        if ci_upper < minimum:
            return "BELOW_HURDLE"
        return "INCONCLUSIVE"
    if ci_upper < -minimum:
        return "CLEARS_HURDLE"
    if ci_lower > -minimum:
        return "BELOW_HURDLE"
    return "INCONCLUSIVE"


def _first_cell(measurements: Mapping[str, object], family: str) -> Mapping[str, object] | None:
    families = measurements.get("families")
    record = None if not isinstance(families, Mapping) else families.get(family)
    cells = None if not isinstance(record, Mapping) else record.get("cells")
    if isinstance(cells, list) and cells and isinstance(cells[0], Mapping):
        return cells[0]
    return None


def _all_cells(measurements: Mapping[str, object], family: str) -> list[Mapping[str, object]]:
    families = measurements.get("families")
    record = None if not isinstance(families, Mapping) else families.get(family)
    cells = None if not isinstance(record, Mapping) else record.get("cells")
    if not isinstance(cells, list):
        return []
    return [cell for cell in cells if isinstance(cell, Mapping)]


def derive_d1_findings(
    measurements: Mapping[str, object], *, claim: Mapping[str, object]
) -> dict[str, Any]:
    """Mechanically derive every D1 finding from raw measurements — the one classifier."""
    direction = claim.get("direction")
    minimum = claim.get("minimum_effect_return")
    alpha = claim.get("alpha")
    confounders = claim.get("confounders", [])
    if direction not in {"positive", "negative"}:
        raise DataError("D1 findings require a registered claim direction")
    if (
        isinstance(minimum, bool)
        or not isinstance(minimum, int | float)
        or isinstance(alpha, bool)
        or not isinstance(alpha, int | float)
        or not isinstance(confounders, list)
    ):
        raise DataError("D1 findings require the frozen claim hurdle, alpha, and confounders")
    sign = 1.0 if direction == "positive" else -1.0

    primary_cell = _first_cell(measurements, "event_study")
    matched = None if primary_cell is None else primary_cell.get("matched")
    primary: dict[str, Any]
    magnitude_status = "NOT_TESTED"
    if isinstance(matched, Mapping):
        estimate = float(matched["estimate"])
        ci_lower = float(matched["ci_lower"])
        ci_upper = float(matched["ci_upper"])
        magnitude_status = _magnitude_status(
            direction=str(direction),
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            minimum=float(minimum),
        )
        primary = {
            "status": "TESTED",
            "estimate": estimate,
            "unit": "arithmetic_return",
            "sample_size": int(matched["sample_size"]),
            "effective_sample_size": float(int(matched["effective_event_count"])),
            "uncertainty": {
                "lower": ci_lower,
                "upper": ci_upper,
                "level": float(matched["confidence"]),
                "method": "cluster_bootstrap_percentile",
            },
            "practical_magnitude": {
                "status": magnitude_status,
                "value": estimate,
                "unit": "arithmetic_return",
                "interpretation": (
                    f"Matched event-minus-control estimate {_fmt(estimate)} against the "
                    f"registered minimum effect {_fmt(float(minimum))}."
                ),
            },
        }
    else:
        primary = {"status": "NOT_TESTED"}

    temporal_cell = _first_cell(measurements, "temporal_stability")
    subsample_cell = _first_cell(measurements, "subsample_consistency")
    if temporal_cell is None and subsample_cell is None:
        temporal_finding = _not_tested()
    elif not isinstance(matched, Mapping):
        temporal_finding = {
            "status": "INCONCLUSIVE",
            "summary": "No established primary effect exists to stabilize.",
        }
    else:
        raw_periods = [] if temporal_cell is None else temporal_cell.get("periods", [])
        period_rows = (
            [row for row in raw_periods if isinstance(row, Mapping)]
            if isinstance(raw_periods, list)
            else []
        )
        period_means = [float(row["mean"]) for row in period_rows]
        periods_consistent = bool(period_means) and all(mean * sign > 0.0 for mean in period_means)
        subsample_result = None if subsample_cell is None else subsample_cell.get("result")
        positive_fraction = (
            None
            if not isinstance(subsample_result, Mapping)
            else float(subsample_result["positive_fraction"])
        )
        subsample_consistent = positive_fraction is not None and (
            positive_fraction >= 0.75 if sign > 0 else positive_fraction <= 0.25
        )
        checks = [
            value
            for value in (
                periods_consistent if period_means else None,
                subsample_consistent if positive_fraction is not None else None,
            )
            if value is not None
        ]
        summary = (
            "Period means: "
            + (", ".join(_fmt(mean) for mean in period_means) or "none")
            + "; subsample positive fraction: "
            + ("untested" if positive_fraction is None else _fmt(positive_fraction))
            + "."
        )
        if not checks:
            temporal_finding = {"status": "INCONCLUSIVE", "summary": summary}
        elif all(checks):
            temporal_finding = {"status": "STABLE", "summary": summary}
        else:
            temporal_finding = {"status": "UNSTABLE", "summary": summary}

    event_cells = _all_cells(measurements, "event_study")
    matched_estimates: list[float] = []
    for cell in event_cells:
        cell_matched = cell.get("matched")
        if isinstance(cell_matched, Mapping):
            matched_estimates.append(float(cast(float, cell_matched["estimate"])))
    if len(matched_estimates) < 2:
        parameter_finding = _not_tested()
    elif all(estimate * sign > 0.0 for estimate in matched_estimates):
        parameter_finding = {
            "status": "STABLE",
            "summary": (
                "All registered grid cells agree in direction: "
                + ", ".join(_fmt(value) for value in matched_estimates)
                + "."
            ),
        }
    else:
        parameter_finding = {
            "status": "UNSTABLE",
            "summary": (
                "Registered grid cells disagree in direction: "
                + ", ".join(_fmt(value) for value in matched_estimates)
                + "."
            ),
        }

    hypotheses: list[SecondaryHypothesis] = []
    directions: dict[str, float] = {}
    for index, cell in enumerate(_all_cells(measurements, "conditional_returns")):
        p_value = cell.get("centered_p_value")
        estimate_value = cell.get("centered_estimate")
        if isinstance(p_value, int | float) and isinstance(estimate_value, int | float):
            hypothesis_id = f"conditional_returns:{index}"
            hypotheses.append(
                SecondaryHypothesis(hypothesis_id=hypothesis_id, p_value=float(p_value))
            )
            directions[hypothesis_id] = float(estimate_value)
    if hypotheses:
        adjusted = holm_adjust_secondary_family(
            FrozenSecondaryFamily(
                family_id="d1-secondary",
                hypotheses=tuple(hypotheses),
                alpha=float(alpha),
            )
        )
        survivors = sum(
            1 for item in adjusted if item.rejected and directions[item.hypothesis_id] * sign > 0.0
        )
        multiplicity_finding = {
            "status": "PASSED",
            "summary": (
                f"Holm over {len(adjusted)} secondary hypotheses; {survivors} "
                "direction-consistent survivors."
            ),
        }
    else:
        multiplicity_finding = {
            "status": "INCONCLUSIVE",
            "summary": (
                "No registered secondary hypothesis produced a p-value; "
                "0 direction-consistent survivors."
            ),
        }

    if not isinstance(matched, Mapping):
        power_finding = _not_tested()
    elif bool(matched.get("low_cluster_count")):
        power_finding = {
            "status": "INCONCLUSIVE",
            "summary": (
                f"Only {int(matched['effective_event_count'])} effective event clusters — "
                "below the ten-cluster reliability floor."
            ),
        }
    else:
        power_finding = {
            "status": "PASSED",
            "summary": (
                f"{int(matched['effective_event_count'])} effective event clusters "
                "support the interval."
            ),
        }

    control_statuses: list[str] = []
    control_notes: list[str] = []
    shuffle_cell = _first_cell(measurements, "shuffled_event_null")
    if shuffle_cell is not None:
        p_upper = float(cast(float, shuffle_cell["placebo_p_upper"]))
        p_lower = float(cast(float, shuffle_cell["placebo_p_lower"]))
        placebo_p = p_upper if sign > 0 else p_lower
        if placebo_p <= float(alpha):
            control_statuses.append("PASSED")
            control_notes.append(
                f"shuffled-event placebo p={_fmt(placebo_p)} does not reproduce the effect"
            )
        elif magnitude_status == "CLEARS_HURDLE":
            control_statuses.append("FAILED")
            control_notes.append(
                f"shuffled-event placebo p={_fmt(placebo_p)} reproduces the claimed effect"
            )
        else:
            control_statuses.append("INCONCLUSIVE")
            control_notes.append(
                f"shuffled-event placebo p={_fmt(placebo_p)} with no claimed effect"
            )
    leadlag_cell = _first_cell(measurements, "leadlag_leakage")
    if leadlag_cell is not None:
        profile = leadlag_cell.get("profile")
        if not isinstance(profile, list):
            raise DataError("lead-lag measurements are missing their profile rows")
        diagnosis = leakage_diagnostic([dict(row) for row in profile])
        if bool(diagnosis["suspicious"]):
            control_statuses.append("FAILED")
            control_notes.append(f"lead-lag leakage screen: {diagnosis['reason']}")
        else:
            control_statuses.append("PASSED")
            control_notes.append("lead-lag leakage screen found no negative-lag dominance")
    if not control_statuses:
        negative_controls: dict[str, object] = _not_tested()
    elif "FAILED" in control_statuses:
        negative_controls = {"status": "FAILED", "summary": "; ".join(control_notes) + "."}
    elif "INCONCLUSIVE" in control_statuses:
        negative_controls = {"status": "INCONCLUSIVE", "summary": "; ".join(control_notes) + "."}
    else:
        negative_controls = {"status": "PASSED", "summary": "; ".join(control_notes) + "."}

    resolved = [_WEEKDAY_CONFOUNDER] if isinstance(matched, Mapping) else []
    unresolved = [str(item) for item in confounders if str(item) not in resolved]

    untested: list[str] = ["mechanism analysis", "cross-dataset transportability"]
    if len(matched_estimates) < 2:
        untested.append("parameter neighborhood beyond the single registered cell")
    skipped = measurements.get("skipped_families")
    if isinstance(skipped, list):
        for item in skipped:
            if isinstance(item, Mapping):
                untested.append(f"{item.get('family')}: {item.get('reason')}")

    strongest_support = (
        (
            f"Matched event-minus-control estimate {_fmt(float(matched['estimate']))} "
            "clears the registered hurdle."
        )
        if isinstance(matched, Mapping) and magnitude_status == "CLEARS_HURDLE"
        else None
    )
    if negative_controls["status"] == "FAILED":
        strongest_contradiction: str | None = str(negative_controls["summary"])
    elif isinstance(matched, Mapping) and magnitude_status != "CLEARS_HURDLE":
        strongest_contradiction = (
            "The matched estimate does not clear the registered minimum effect."
        )
    else:
        strongest_contradiction = None

    findings: dict[str, Any] = {
        "schema": "ResearchGateEvidenceV1",
        "evidence_zone": "D1",
        "primary_result": primary,
        "mechanism": _not_tested(),
        "strongest_support": strongest_support,
        "strongest_contradiction": strongest_contradiction,
        "confounders": {"resolved": resolved, "unresolved": unresolved},
        "stability": {
            "parameter": parameter_finding,
            "temporal": temporal_finding,
            "transportability": _not_tested(),
        },
        "multiplicity": multiplicity_finding,
        "power": power_finding,
        "negative_controls": negative_controls,
        "untested_work": untested,
        "what_would_change_conclusion": [
            "a failed negative control or leakage screen on the exact pipeline",
            "a materially different matched estimate on later non-overlapping data",
            "an unresolved confounder shown to reproduce the conditional effect",
        ],
    }
    required_families = claim.get("required_families", [])
    required_falsifiers = claim.get("required_falsifiers", [])
    skipped_families = (
        [
            str(item.get("family"))
            for item in skipped
            if isinstance(item, Mapping) and isinstance(item.get("family"), str)
        ]
        if isinstance(skipped, list)
        else []
    )
    skipped_required = (
        [family for family in skipped_families if family in required_families]
        if isinstance(required_families, list)
        else skipped_families
    )
    findings.update(
        derive_research_readiness(
            findings,
            required_falsifiers=(
                [str(item) for item in required_falsifiers]
                if isinstance(required_falsifiers, list)
                else ()
            ),
            skipped_required_families=skipped_required,
        )
    )
    return findings


def _publish_text(path: Path, content: str) -> None:
    _publish_bytes(path, content.encode("utf-8"))


def _publish_bytes(path: Path, content: bytes) -> None:
    def write(target: Path) -> None:
        target.write_bytes(content)

    _artifacts.publish_artifact(path, write)


def run_deep_research(
    data_dir: Path,
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
    bars: EqualDurationResearchBars,
    boundary: ResearchD2Boundary | None = None,
    on_checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Execute the frozen analysis plan on the discovery share and publish one immutable run.

    When the sealed ``boundary`` is supplied (the empirical lane), the loaded dataset, its
    session groups, and the executable discovery cut are verified against the approval-time
    commitment before any family runs.
    """
    if _PROJECT_ID_RE.fullmatch(project_id) is None:
        raise DataError("D1 execution requires a canonical project_id")
    if _CONTRACT_ID_RE.fullmatch(contract_id) is None:
        raise DataError("D1 execution requires a content-addressed contract_id")
    _validate_contract(contract)
    plan = _plan(contract)
    spec = _detector_spec(contract)
    claim = _claim(contract)
    real_market = _real_market_evidence(contract)
    dataset_hash = bars.dataset.content_sha256
    if _SHA256_RE.fullmatch(dataset_hash) is None:
        raise DataError("D1 execution requires a content-addressed dataset hash")
    if boundary is not None:
        if boundary.dataset_fingerprint != dataset_hash:
            raise DataError(
                "sealed boundary dataset fingerprint does not match the loaded research dataset"
            )
        groups = [bar.start.date().isoformat() for bar in bars.bars]
        if not boundary.verify_eligible_groups(groups):
            raise DataError(
                "loaded session groups do not reproduce the sealed boundary's eligible groups"
            )

    horizons = [
        int(value)
        for entry in plan["families"]
        for value in entry["grid"].get("horizon_bars", [])
        if isinstance(value, int | float) and not isinstance(value, bool)
    ]
    embargo = max(horizons) if horizons else 1
    data = _D1Data(bars, spec, embargo)
    if boundary is not None and (
        data.discovery_stop != boundary.d1.stop_index
        or data.topology.confirmation.stop != boundary.d2.stop_index
    ):
        raise DataError(
            "the executable discovery share does not align with the sealed boundary's D1 zone"
        )

    families: dict[str, object] = {}
    skipped: list[dict[str, object]] = []
    variants_used = 0
    for ordinal, entry in enumerate(plan["families"], start=1):
        family = str(entry["family"])
        runner = _FAMILY_RUNNERS.get(family)
        if runner is None:  # pragma: no cover - the plan validator pins the registry.
            raise DataError(f"analysis family {family!r} has no registered runner")
        cells: list[dict[str, object]] = []
        try:
            for cell in _grid_cells(entry["grid"]):
                cells.append(runner(data, cell))
                variants_used += 1
        except DataError as exc:
            skipped.append({"family": family, "reason": str(exc)})
        else:
            families[family] = {"cells": cells}
        if on_checkpoint is not None:
            on_checkpoint(f"d1:{family}:{ordinal}")

    measurements: dict[str, object] = {
        "topology": {
            "total_observations": data.topology.total_observations,
            "discovery_stop": data.discovery_stop,
            "eligible_event_stop": data.eligible_stop,
            "embargo": embargo,
            "contract_hash": data.topology.contract_hash,
        },
        "events": {
            "detected": len(data.events),
            "eligible": len(data.eligible_events),
            "embargoed": len(data.events) - len(data.eligible_events),
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
        "families": families,
        "skipped_families": skipped,
        "budget": {"variants_used": variants_used},
    }
    findings = derive_d1_findings(measurements, claim=claim)

    contract_hash = _sha(contract)
    execution_fingerprint = d1_execution_fingerprint(contract)
    run_identity = {
        "command": "research_deep",
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "dataset_hash": dataset_hash,
        "execution_fingerprint": execution_fingerprint,
    }
    run_id = _sha(run_identity)[:16]
    run_dir = _artifacts.run_dir(Path(data_dir), run_id)

    analyses_payload = {
        "schema": _D1_ANALYSES_SCHEMA,
        "schema_version": 1,
        "measurements": measurements,
    }
    analyses_bytes = _canonical(analyses_payload).encode("utf-8")
    analyses_sha = hashlib.sha256(analyses_bytes).hexdigest()

    chart_points = tuple(ResearchChartPoint(ts=bar.end, value=bar.close) for bar in data.bars.bars)
    chart_series = ResearchChartSeries(
        series_id="discovery-close",
        label="Discovery-share close",
        unit="synthetic price units" if not real_market else "price",
        points=chart_points,
    )
    chart_series_sha = _sha(chart_series.to_dict())
    chart = ResearchChartData(
        chart_id="d1-primary-association",
        title="D1 discovery-share prices and event anchors",
        x_label="Bar end (UTC)",
        y_label="Close",
        evidence_phase="exploratory",
        dataset_sha256=dataset_hash,
        protocol_sha256=contract_hash,
        question="Do confirmed events precede forward returns beyond matched controls?",
        plain_language_answer=str(
            findings["strongest_support"]
            or findings["strongest_contradiction"]
            or "No eligible events were available to test the claim."
        ),
        sample_size=len(data.bars.bars),
        effective_sample_size=float(max(1, len(data.eligible_events))),
        uncertainty="Cluster-bootstrap percentile intervals; see the evidence artifact.",
        caveat="EXPLORATORY D1 discovery-share evidence; never holdout or execution authority.",
        run_id=run_id,
        artifact_id="d1-primary-association-series",
        artifact_sha256=chart_series_sha,
        series=(chart_series,),
    )
    evidence = {
        **findings,
        "artifact_links": [
            {
                "run_id": run_id,
                "artifact_id": D1_ANALYSES_ARTIFACT,
                "content_sha256": analyses_sha,
                "media_type": "application/json",
            }
        ],
    }

    _publish_bytes(run_dir / D1_ANALYSES_ARTIFACT, analyses_bytes)
    _publish_text(run_dir / D1_EVIDENCE_ARTIFACT, _canonical(evidence))
    _publish_text(
        run_dir / "chart-data.json",
        json.dumps(chart.to_dict(), sort_keys=True, indent=2, allow_nan=False),
    )
    _publish_bytes(run_dir / "d1-primary-association.png", render_research_line_chart(chart))
    _publish_text(
        run_dir / "report.md",
        "# D1 Deep Research\n\n"
        "**EXPLORATORY — DISCOVERY-SHARE EVIDENCE ONLY**\n\n"
        "The frozen analysis plan executed inside the discovery (D1) share; D2 and D3 were "
        "never read. Findings are mechanically derived from raw measurements and re-verified "
        "at admission.\n",
    )
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "run_identity_version": 3,
        "command": "research_deep",
        "kind": "research",
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "source_pack_id": contract.get("source_pack_id"),
        "research_fingerprints": dict(cast(Mapping[str, object], contract.get("hashes", {}))),
        "evidence_zone": "D1",
        "watermark": "EXPLORATORY",
        "real_market_evidence": real_market,
        "eligible_for_holdout_or_execution": False,
        "places_orders": False,
        "snapshot_id": None,
        "snapshot_hash": None,
        "execution_fingerprint": execution_fingerprint,
        "strategy_fingerprint": None,
        "source_fingerprint": contract_hash,
        "dataset_hash": dataset_hash,
        "d1_evidence_artifact": D1_EVIDENCE_ARTIFACT,
        "d1_analyses_artifact": D1_ANALYSES_ARTIFACT,
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
        raise DataError(f"D1 run manifest does not declare immutable artifact {name!r}")
    return sha


def validate_d1_evidence_artifacts(
    run_dir: Path,
    manifest: Mapping[str, object],
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
) -> dict[str, Any]:
    """Re-verify one D1 run's typed evidence by exact mechanical recomputation.

    Producer finding statuses are never authority: every status is re-derived from the raw
    measurements artifact via the same classifier the writer used, and any divergence —
    including a post-admission rewrite of either artifact — fails closed.
    """
    if manifest.get("command") != "research_deep" or manifest.get("evidence_zone") != "D1":
        raise DataError("D1 evidence verification requires a research_deep D1 manifest")
    if manifest.get("project_id") != project_id:
        raise DataError("D1 evidence verification project does not match the manifest")
    if manifest.get("research_contract_id") != contract_id:
        raise DataError("D1 evidence verification contract does not match the manifest")
    if manifest.get("d1_evidence_artifact") != D1_EVIDENCE_ARTIFACT:
        raise DataError("D1 manifest does not select its typed evidence artifact")

    analyses_sha = _manifest_artifact_sha(manifest, D1_ANALYSES_ARTIFACT)
    evidence_sha = _manifest_artifact_sha(manifest, D1_EVIDENCE_ARTIFACT)
    analyses_path = run_dir / D1_ANALYSES_ARTIFACT
    evidence_path = run_dir / D1_EVIDENCE_ARTIFACT
    analyses_bytes = analyses_path.read_bytes() if analyses_path.is_file() else b""
    evidence_bytes = evidence_path.read_bytes() if evidence_path.is_file() else b""
    if hashlib.sha256(analyses_bytes).hexdigest() != analyses_sha:
        raise DataError("D1 analyses artifact does not match its immutable manifest hash")
    if hashlib.sha256(evidence_bytes).hexdigest() != evidence_sha:
        raise DataError("D1 evidence artifact does not match its immutable manifest hash")

    analyses = _read_canonical_json(analyses_path, "D1 analyses artifact")
    evidence = _read_canonical_json(evidence_path, "D1 evidence artifact")
    if analyses.get("schema") != _D1_ANALYSES_SCHEMA:
        raise DataError("D1 analyses artifact has an unsupported schema")
    measurements = analyses.get("measurements")
    if not isinstance(measurements, Mapping):
        raise DataError("D1 analyses artifact has no raw measurements")

    expected = derive_d1_findings(measurements, claim=_claim(contract))
    produced = {key: value for key, value in evidence.items() if key != "artifact_links"}
    legacy_expected = {
        key: value
        for key, value in expected.items()
        if key not in {"confirmation_readiness", "promotion_readiness"}
    }
    if _canonical(produced) not in {_canonical(expected), _canonical(legacy_expected)}:
        raise DataError(
            "D1 evidence findings fail exact mechanical recomputation from raw measurements"
        )
    links = evidence.get("artifact_links")
    if not isinstance(links, list) or not links:
        raise DataError("D1 evidence must link its immutable measurement artifacts")
    linked_analyses = False
    for link in links:
        if not isinstance(link, Mapping):
            raise DataError("D1 evidence artifact links must be objects")
        artifact_id = link.get("artifact_id")
        if not isinstance(artifact_id, str):
            raise DataError("D1 evidence artifact links must name their artifacts")
        if link.get("run_id") != manifest.get("run_id"):
            raise DataError("D1 evidence artifact links must bind their own run")
        if link.get("content_sha256") != _manifest_artifact_sha(manifest, artifact_id):
            raise DataError("D1 evidence artifact link hash does not match the manifest")
        if artifact_id == D1_ANALYSES_ARTIFACT:
            linked_analyses = True
    if not linked_analyses:
        raise DataError("D1 evidence must link the raw measurements artifact")
    return evidence


__all__ = [
    "D1_ANALYSES_ARTIFACT",
    "D1_EVIDENCE_ARTIFACT",
    "d1_execution_fingerprint",
    "derive_d1_findings",
    "load_registered_research_bars",
    "registered_synthetic_d1_bars",
    "registered_synthetic_d1_lows",
    "research_bars_from_lows",
    "run_deep_research",
    "validate_d1_evidence_artifacts",
]

"""Point-in-time contracts and evaluation for the registered BTCUSDT crowding question."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

from alpha_core import DataError
from alpha_research.event_study import (
    EventStudyObservation,
    PreEventCovariate,
    evaluate_matched_association,
    match_event_controls,
)
from alpha_research.multiple_testing import (
    FrozenSecondaryFamily,
    SecondaryHypothesis,
    holm_adjust_secondary_family,
)

type CryptoEvidenceZone = Literal["D1", "D2"]
type CryptoCrowdingStatus = Literal["EVALUATED", "INCONCLUSIVE"]

_PLAN_SCHEMA: Final = "CryptoCrowdingResearchPlanV1"
_OBSERVATION_SCHEMA: Final = "CryptoCrowdingObservationV1"
_RESULT_SCHEMA: Final = "CryptoCrowdingEvaluationV1"
_REQUIRED_FAMILIES: Final = (
    "funding",
    "open_interest",
    "premium_bars",
    "mark_bars",
    "index_bars",
    "derivative_bars",
    "instrument_catalog",
)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DataError(f"crypto crowding {label} must be timezone-aware")
    return value.astimezone(UTC)


def _finite(value: float, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise DataError(f"crypto crowding {label} must be finite")
    result = float(value)
    if positive and result <= 0:
        raise DataError(f"crypto crowding {label} must be positive")
    return result


@dataclass(frozen=True)
class CryptoCrowdingResearchPlanV1:
    bundle_id: str = "bybit_btcusdt_crowding_reversal_v1"
    provider: str = "bybit"
    venue: str = "BYBIT"
    market_type: str = "linear"
    instrument: str = "BTCUSDT"
    base_asset: str = "BTC"
    quote_asset: str = "USDT"
    required_families: tuple[str, ...] = _REQUIRED_FAMILIES
    confounder_family: str = "long_short_ratio"
    history_observations: int = 365
    primary_percentile: float = 0.95
    sensitivity_percentiles: tuple[float, float] = (0.9, 0.975)
    sensitivity_multiplicity: str = "holm_v1"
    percentile_method: str = "linear_type7_v1"
    open_interest_lookback_hours: int = 24
    entry_delay_hours: int = 1
    practical_hurdle_return: float = -0.0005
    minimum_effective_events: int = 50
    minimum_confirmation_events: int = 10
    uncertainty_cluster: str = "UTC_week"
    matching_covariates: tuple[str, str, str] = (
        "utc_funding_slot",
        "recent_trend_tercile",
        "recent_volatility_tercile",
    )
    bootstrap_resamples: int = 2_000
    bootstrap_seed: int = 7
    shifted_placebo_days: tuple[int, ...] = (1, 3, 5, 7, 9, 11, 13, 15, 17, 19)
    topology: str = "group_atomic_60_20_20"
    schema: str = _PLAN_SCHEMA
    schema_version: Literal[1] = 1

    def __post_init__(self) -> None:
        if (
            self.bundle_id != "bybit_btcusdt_crowding_reversal_v1"
            or self.provider != "bybit"
            or self.venue != "BYBIT"
            or self.market_type != "linear"
            or self.instrument != "BTCUSDT"
            or self.base_asset != "BTC"
            or self.quote_asset != "USDT"
            or self.required_families != _REQUIRED_FAMILIES
            or self.confounder_family != "long_short_ratio"
            or self.history_observations != 365
            or self.primary_percentile != 0.95
            or self.sensitivity_percentiles != (0.9, 0.975)
            or self.sensitivity_multiplicity != "holm_v1"
            or self.percentile_method != "linear_type7_v1"
            or self.open_interest_lookback_hours != 24
            or self.entry_delay_hours != 1
            or self.practical_hurdle_return != -0.0005
            or self.minimum_effective_events != 50
            or self.minimum_confirmation_events != 10
            or self.uncertainty_cluster != "UTC_week"
            or self.matching_covariates
            != ("utc_funding_slot", "recent_trend_tercile", "recent_volatility_tercile")
            or self.bootstrap_resamples != 2_000
            or self.bootstrap_seed != 7
            or self.shifted_placebo_days != (1, 3, 5, 7, 9, 11, 13, 15, 17, 19)
            or self.topology != "group_atomic_60_20_20"
            or self.schema != _PLAN_SCHEMA
            or self.schema_version != 1
        ):
            raise DataError("crypto crowding plan is not the registered generation")

    def _identity_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "bundle_id": self.bundle_id,
            "provider": self.provider,
            "venue": self.venue,
            "market_type": self.market_type,
            "instrument": self.instrument,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "required_families": list(self.required_families),
            "confounder_family": self.confounder_family,
            "history_observations": self.history_observations,
            "primary_percentile": self.primary_percentile,
            "sensitivity_percentiles": list(self.sensitivity_percentiles),
            "sensitivity_multiplicity": self.sensitivity_multiplicity,
            "percentile_method": self.percentile_method,
            "open_interest_lookback_hours": self.open_interest_lookback_hours,
            "entry_delay_hours": self.entry_delay_hours,
            "practical_hurdle_return": self.practical_hurdle_return,
            "minimum_effective_events": self.minimum_effective_events,
            "minimum_confirmation_events": self.minimum_confirmation_events,
            "uncertainty_cluster": self.uncertainty_cluster,
            "matching_covariates": list(self.matching_covariates),
            "bootstrap_resamples": self.bootstrap_resamples,
            "bootstrap_seed": self.bootstrap_seed,
            "shifted_placebo_days": list(self.shifted_placebo_days),
            "topology": self.topology,
        }

    @property
    def operator_fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self._identity_dict())).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {**self._identity_dict(), "operator_fingerprint": self.operator_fingerprint}


@dataclass(frozen=True)
class CryptoCrowdingObservationV1:
    funding_time: datetime
    funding_available_at: datetime
    funding_rate: float
    open_interest: float
    open_interest_available_at: datetime
    premium: float
    premium_available_at: datetime
    entry_time: datetime
    entry_available_at: datetime
    entry_mark: float
    entry_index: float
    exit_time: datetime
    exit_available_at: datetime
    exit_mark: float
    exit_index: float
    long_short_ratio: float | None
    recent_trend: float
    recent_volatility: float
    regime: str
    diagnostics_available_at: datetime
    correction_lineage: tuple[str, ...] = ()
    schema: str = _OBSERVATION_SCHEMA
    schema_version: Literal[1] = 1

    def __post_init__(self) -> None:
        for field in (
            "funding_time",
            "funding_available_at",
            "open_interest_available_at",
            "premium_available_at",
            "entry_time",
            "entry_available_at",
            "exit_time",
            "exit_available_at",
            "diagnostics_available_at",
        ):
            object.__setattr__(self, field, _utc(getattr(self, field), field))
        for field in ("funding_rate", "premium", "recent_trend", "recent_volatility"):
            object.__setattr__(self, field, _finite(getattr(self, field), field))
        for field in ("open_interest", "entry_mark", "entry_index", "exit_mark", "exit_index"):
            object.__setattr__(self, field, _finite(getattr(self, field), field, positive=True))
        if self.long_short_ratio is not None:
            object.__setattr__(
                self,
                "long_short_ratio",
                _finite(self.long_short_ratio, "long_short_ratio", positive=True),
            )
        if not isinstance(self.regime, str) or not self.regime.strip():
            raise DataError("crypto crowding regime must be a non-empty string")
        if not isinstance(self.correction_lineage, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.correction_lineage
        ):
            raise DataError("crypto crowding correction lineage is invalid")
        if self.schema != _OBSERVATION_SCHEMA or self.schema_version != 1:
            raise DataError("crypto crowding observation schema is invalid")
        if (
            max(
                self.funding_available_at,
                self.open_interest_available_at,
                self.premium_available_at,
                self.diagnostics_available_at,
            )
            > self.funding_time
        ):
            raise DataError("crypto crowding event input is not point-in-time available")
        if self.entry_time != self.funding_time + timedelta(hours=1):
            raise DataError("crypto crowding entry is not the first complete hourly bar")
        if self.entry_available_at > self.entry_time or self.exit_available_at > self.exit_time:
            raise DataError("crypto crowding price input is not point-in-time available")
        if self.exit_time <= self.entry_time:
            raise DataError("crypto crowding outcome boundary is invalid")


@dataclass(frozen=True)
class CryptoCrowdingEventV1:
    observation_index: int
    funding_time: datetime
    entry_time: datetime
    exit_time: datetime
    funding_rate: float
    funding_threshold: float
    percentile: float
    open_interest_change_24h: float
    premium: float
    mark_minus_index_return: float
    clears_practical_hurdle: bool


@dataclass(frozen=True)
class CryptoCrowdingEstimateV1:
    estimate: float
    ci_lower: float
    ci_upper: float
    p_value: float
    matched_pairs: int
    unmatched_events: int
    effective_week_clusters: int
    low_cluster_count: bool


@dataclass(frozen=True)
class CryptoCrowdingSensitivityV1:
    percentile: float
    event_count: int
    p_value: float | None
    adjusted_p_value: float | None
    rejected: bool | None


@dataclass(frozen=True)
class CryptoCrowdingShiftedPlaceboV1:
    shift_count: int
    observed_mean: float
    placebo_mean: float
    two_sided_p_value: float


@dataclass(frozen=True)
class CryptoCrowdingLongShortDiagnosticV1:
    event_mean: float
    non_event_mean: float
    event_count: int
    non_event_count: int
    missing_count: int


@dataclass(frozen=True)
class CryptoCrowdingRegimeDiagnosticV1:
    regime: str
    event_count: int
    mean_outcome: float


@dataclass(frozen=True)
class CryptoCrowdingEvaluationV1:
    evidence_zone: CryptoEvidenceZone
    plan_fingerprint: str
    status: CryptoCrowdingStatus
    primary_events: tuple[CryptoCrowdingEventV1, ...]
    sensitivity_event_counts: tuple[tuple[float, int], ...]
    blockers: tuple[str, ...]
    primary_estimate: CryptoCrowdingEstimateV1 | None = None
    sensitivity_results: tuple[CryptoCrowdingSensitivityV1, ...] = ()
    shifted_date_placebo: CryptoCrowdingShiftedPlaceboV1 | None = None
    long_short_diagnostic: CryptoCrowdingLongShortDiagnosticV1 | None = None
    regime_diagnostics: tuple[CryptoCrowdingRegimeDiagnosticV1, ...] = ()
    schema: str = _RESULT_SCHEMA
    schema_version: Literal[1] = 1

    @property
    def primary_event_count(self) -> int:
        return len(self.primary_events)


@dataclass(frozen=True)
class CryptoCrowdingD0AcceptanceV1:
    operator_fingerprint: str
    fixture_definition_sha256: str
    planted_event_count: int
    null_event_count: int
    confounded_event_count: int
    confounder_recorded: bool
    future_poison_rejected: bool
    missing_required_suppressed: bool
    correction_lineage_preserved: bool
    correction_changes_result: bool
    insufficient_sample_blocker: bool
    schema: str = "CryptoCrowdingD0AcceptanceV1"
    schema_version: Literal[1] = 1

    @property
    def passed(self) -> bool:
        return (
            self.planted_event_count == 1
            and self.null_event_count == 0
            and self.confounded_event_count == 1
            and self.confounder_recorded
            and self.future_poison_rejected
            and self.missing_required_suppressed
            and self.correction_lineage_preserved
            and self.correction_changes_result
            and self.insufficient_sample_blocker
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "operator_fingerprint": self.operator_fingerprint,
            "fixture_definition_sha256": self.fixture_definition_sha256,
            "planted_event_count": self.planted_event_count,
            "null_event_count": self.null_event_count,
            "confounded_event_count": self.confounded_event_count,
            "confounder_recorded": self.confounder_recorded,
            "future_poison_rejected": self.future_poison_rejected,
            "missing_required_suppressed": self.missing_required_suppressed,
            "correction_lineage_preserved": self.correction_lineage_preserved,
            "correction_changes_result": self.correction_changes_result,
            "insufficient_sample_blocker": self.insufficient_sample_blocker,
            "passed": self.passed,
            "evidence_zone": "D0",
            "real_market_evidence": False,
            "eligible_for_holdout_or_execution": False,
        }


def registered_crypto_crowding_plan() -> CryptoCrowdingResearchPlanV1:
    """Return the one immutable operator generation admitted by ADR-0033."""
    return CryptoCrowdingResearchPlanV1()


def _d0_observations(
    *,
    event_index: int | None,
    confounded: bool = False,
) -> tuple[CryptoCrowdingObservationV1, ...]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    rows: list[CryptoCrowdingObservationV1] = []
    for index in range(420):
        funding_time = start + timedelta(hours=8 * index)
        is_event = index == event_index
        rows.append(
            CryptoCrowdingObservationV1(
                funding_time=funding_time,
                funding_available_at=funding_time,
                funding_rate=0.02 if is_event else 0.001 + index * 0.000001,
                open_interest=120.0 + index + (25.0 if is_event else 0.0),
                open_interest_available_at=funding_time,
                premium=0.002 if is_event else -0.001,
                premium_available_at=funding_time,
                entry_time=funding_time + timedelta(hours=1),
                entry_available_at=funding_time + timedelta(hours=1),
                entry_mark=100.0,
                entry_index=100.0,
                exit_time=funding_time + timedelta(hours=8),
                exit_available_at=funding_time + timedelta(hours=8),
                exit_mark=99.8 if is_event else 100.0,
                exit_index=100.0,
                long_short_ratio=5.0 if is_event and confounded else 1.0,
                recent_trend=0.01,
                recent_volatility=0.02,
                regime="normal",
                diagnostics_available_at=funding_time,
            )
        )
    return tuple(rows)


def execute_crypto_crowding_d0() -> CryptoCrowdingD0AcceptanceV1:
    """Recompute the closed synthetic acceptance suite; never read market evidence."""
    plan = registered_crypto_crowding_plan()
    planted_rows = _d0_observations(event_index=380)
    planted = evaluate_crypto_crowding(planted_rows, evidence_zone="D1")
    null = evaluate_crypto_crowding(_d0_observations(event_index=None), evidence_zone="D1")
    confounded_rows = _d0_observations(event_index=380, confounded=True)
    confounded = evaluate_crypto_crowding(confounded_rows, evidence_zone="D1")

    future_poison_rejected = False
    try:
        replace(
            planted_rows[380],
            premium_available_at=planted_rows[380].funding_time + timedelta(hours=1),
        )
    except DataError:
        future_poison_rejected = True

    missing_rows = tuple(row for index, row in enumerate(planted_rows) if index != 377)
    missing = evaluate_crypto_crowding(missing_rows, evidence_zone="D1")
    corrected_rows = list(planted_rows)
    corrected_rows[380] = replace(
        corrected_rows[380],
        exit_mark=100.2,
        correction_lineage=("fixture-correction-v1",),
    )
    corrected = evaluate_crypto_crowding(tuple(corrected_rows), evidence_zone="D1")
    original_event = planted.primary_events[0] if planted.primary_events else None
    corrected_event = corrected.primary_events[0] if corrected.primary_events else None
    fixture_definition = {
        "schema": "CryptoCrowdingD0FixtureV1",
        "operator_fingerprint": plan.operator_fingerprint,
        "observation_count": 420,
        "event_index": 380,
        "missing_open_interest_index": 377,
        "confounded_long_short_ratio": 5.0,
        "corrected_exit_mark": 100.2,
    }
    return CryptoCrowdingD0AcceptanceV1(
        operator_fingerprint=plan.operator_fingerprint,
        fixture_definition_sha256=hashlib.sha256(_canonical(fixture_definition)).hexdigest(),
        planted_event_count=planted.primary_event_count,
        null_event_count=null.primary_event_count,
        confounded_event_count=confounded.primary_event_count,
        confounder_recorded=confounded_rows[380].long_short_ratio == 5.0,
        future_poison_rejected=future_poison_rejected,
        missing_required_suppressed=missing.primary_event_count == 0,
        correction_lineage_preserved=(
            corrected_rows[380].correction_lineage == ("fixture-correction-v1",)
        ),
        correction_changes_result=(
            original_event is not None
            and corrected_event is not None
            and original_event.mark_minus_index_return != corrected_event.mark_minus_index_return
            and original_event.clears_practical_hurdle
            and not corrected_event.clears_practical_hurdle
        ),
        insufficient_sample_blocker=(planted.blockers == ("minimum_effective_events:1<50",)),
    )


def _percentile(values: tuple[float, ...], probability: float) -> float:
    """R-7/type-7 linear quantile over an already point-in-time history."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper or ordered[lower] == ordered[upper]:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _events_for_percentile(
    observations: tuple[CryptoCrowdingObservationV1, ...],
    *,
    percentile: float,
    plan: CryptoCrowdingResearchPlanV1,
) -> tuple[CryptoCrowdingEventV1, ...]:
    by_time = {item.funding_time: item for item in observations}
    accepted: list[CryptoCrowdingEventV1] = []
    last_exit: datetime | None = None
    for index in range(plan.history_observations, len(observations) - 1):
        current = observations[index]
        history = observations[index - plan.history_observations : index]
        threshold = _percentile(tuple(item.funding_rate for item in history), percentile)
        prior_oi = by_time.get(
            current.funding_time - timedelta(hours=plan.open_interest_lookback_hours)
        )
        if prior_oi is None:
            continue
        oi_change = current.open_interest - prior_oi.open_interest
        if current.funding_rate < threshold or oi_change <= 0 or current.premium <= 0:
            continue
        if last_exit is not None and current.funding_time <= last_exit:
            continue
        next_funding = observations[index + 1].funding_time
        if current.exit_time != next_funding:
            raise DataError("crypto crowding exit is not the next declared funding timestamp")
        mark_return = current.exit_mark / current.entry_mark - 1
        index_return = current.exit_index / current.entry_index - 1
        relative_return = mark_return - index_return
        accepted.append(
            CryptoCrowdingEventV1(
                observation_index=index,
                funding_time=current.funding_time,
                entry_time=current.entry_time,
                exit_time=current.exit_time,
                funding_rate=current.funding_rate,
                funding_threshold=threshold,
                percentile=percentile,
                open_interest_change_24h=oi_change,
                premium=current.premium,
                mark_minus_index_return=relative_return,
                clears_practical_hurdle=relative_return <= plan.practical_hurdle_return,
            )
        )
        last_exit = current.exit_time
    return tuple(accepted)


def _causal_tercile(
    values: tuple[float, ...],
    *,
    index: int,
    history_observations: int,
) -> str:
    history = values[index - history_observations : index]
    lower = _percentile(history, 1 / 3)
    upper = _percentile(history, 2 / 3)
    current = values[index]
    if current <= lower:
        return "low"
    if current >= upper:
        return "high"
    return "middle"


def _study_observation(
    observations: tuple[CryptoCrowdingObservationV1, ...],
    *,
    index: int,
    is_event: bool,
    plan: CryptoCrowdingResearchPlanV1,
) -> EventStudyObservation:
    row = observations[index]
    iso_year, iso_week, _ = row.funding_time.isocalendar()
    return EventStudyObservation(
        observation_id=f"{'event' if is_event else 'control'}-{index}",
        is_event=is_event,
        event_at=row.funding_time,
        event_available_at=max(
            row.funding_available_at,
            row.open_interest_available_at,
            row.premium_available_at,
            row.diagnostics_available_at,
        ),
        outcome_start_at=row.entry_time,
        outcome_end_at=row.exit_time,
        outcome_available_at=row.exit_available_at,
        outcome=(row.exit_mark / row.entry_mark - 1) - (row.exit_index / row.entry_index - 1),
        cluster_id=f"{iso_year}-W{iso_week:02d}",
        covariates=(
            PreEventCovariate(
                "utc_funding_slot",
                row.funding_time.hour,
                row.funding_time,
                row.funding_available_at,
            ),
            PreEventCovariate(
                "recent_trend_tercile",
                _causal_tercile(
                    tuple(item.recent_trend for item in observations),
                    index=index,
                    history_observations=plan.history_observations,
                ),
                row.funding_time,
                row.diagnostics_available_at,
            ),
            PreEventCovariate(
                "recent_volatility_tercile",
                _causal_tercile(
                    tuple(item.recent_volatility for item in observations),
                    index=index,
                    history_observations=plan.history_observations,
                ),
                row.funding_time,
                row.diagnostics_available_at,
            ),
        ),
    )


def _matched_estimate(
    observations: tuple[CryptoCrowdingObservationV1, ...],
    events: tuple[CryptoCrowdingEventV1, ...],
    *,
    plan: CryptoCrowdingResearchPlanV1,
) -> CryptoCrowdingEstimateV1 | None:
    event_indices = {item.observation_index for item in events}
    eligible = range(plan.history_observations, len(observations) - 1)
    event_rows = tuple(
        _study_observation(observations, index=index, is_event=True, plan=plan)
        for index in sorted(event_indices)
    )
    control_rows = tuple(
        _study_observation(observations, index=index, is_event=False, plan=plan)
        for index in eligible
        if index not in event_indices
    )
    if len(event_rows) < 2 or not control_rows:
        return None
    matched = match_event_controls(
        (*event_rows, *control_rows),
        covariate_names=plan.matching_covariates,
        as_of=observations[-1].exit_available_at,
    )
    if len(matched.pairs) < 2 or matched.effective_event_count < 2:
        return None
    estimate = evaluate_matched_association(
        matched,
        n_resamples=plan.bootstrap_resamples,
        seed=plan.bootstrap_seed,
    )
    return CryptoCrowdingEstimateV1(
        estimate=estimate.estimate,
        ci_lower=estimate.ci_lower,
        ci_upper=estimate.ci_upper,
        p_value=estimate.p_value,
        matched_pairs=len(matched.pairs),
        unmatched_events=len(matched.unmatched_event_ids),
        effective_week_clusters=estimate.effective_event_count,
        low_cluster_count=estimate.low_cluster_count,
    )


def _sensitivity_results(
    observations: tuple[CryptoCrowdingObservationV1, ...],
    *,
    plan: CryptoCrowdingResearchPlanV1,
) -> tuple[CryptoCrowdingSensitivityV1, ...]:
    rows: list[
        tuple[float, tuple[CryptoCrowdingEventV1, ...], CryptoCrowdingEstimateV1 | None]
    ] = []
    for percentile in plan.sensitivity_percentiles:
        events = _events_for_percentile(observations, percentile=percentile, plan=plan)
        rows.append((percentile, events, _matched_estimate(observations, events, plan=plan)))
    estimates = [estimate for _, _, estimate in rows]
    if any(estimate is None for estimate in estimates):
        return tuple(
            CryptoCrowdingSensitivityV1(percentile, len(events), None, None, None)
            for percentile, events, _ in rows
        )
    adjusted = holm_adjust_secondary_family(
        FrozenSecondaryFamily(
            family_id="bybit_btcusdt_funding_percentile_sensitivities_v1",
            hypotheses=tuple(
                SecondaryHypothesis(f"funding_percentile_{percentile:g}", estimate.p_value)
                for percentile, _, estimate in rows
                if estimate is not None
            ),
        )
    )
    by_id = {item.hypothesis_id: item for item in adjusted}
    return tuple(
        CryptoCrowdingSensitivityV1(
            percentile=percentile,
            event_count=len(events),
            p_value=estimate.p_value if estimate is not None else None,
            adjusted_p_value=by_id[f"funding_percentile_{percentile:g}"].adjusted_p_value,
            rejected=by_id[f"funding_percentile_{percentile:g}"].rejected,
        )
        for percentile, events, estimate in rows
    )


def _shifted_date_placebo(
    observations: tuple[CryptoCrowdingObservationV1, ...],
    events: tuple[CryptoCrowdingEventV1, ...],
    *,
    plan: CryptoCrowdingResearchPlanV1,
) -> CryptoCrowdingShiftedPlaceboV1 | None:
    if not events:
        return None
    outcomes = tuple(
        (item.exit_mark / item.entry_mark - 1) - (item.exit_index / item.entry_index - 1)
        for item in observations
    )
    observed = sum(item.mark_minus_index_return for item in events) / len(events)
    means: list[float] = []
    for days in plan.shifted_placebo_days:
        for direction in (-1, 1):
            shift = direction * days * 3
            shifted = [
                item.observation_index + shift
                for item in events
                if plan.history_observations
                <= item.observation_index + shift
                < len(observations) - 1
            ]
            if shifted:
                means.append(sum(outcomes[index] for index in shifted) / len(shifted))
    if not means:
        return None
    p_value = (sum(abs(value) >= abs(observed) for value in means) + 1) / (len(means) + 1)
    return CryptoCrowdingShiftedPlaceboV1(
        shift_count=len(means),
        observed_mean=observed,
        placebo_mean=sum(means) / len(means),
        two_sided_p_value=p_value,
    )


def _diagnostics(
    observations: tuple[CryptoCrowdingObservationV1, ...],
    events: tuple[CryptoCrowdingEventV1, ...],
    *,
    plan: CryptoCrowdingResearchPlanV1,
) -> tuple[
    CryptoCrowdingLongShortDiagnosticV1 | None,
    tuple[CryptoCrowdingRegimeDiagnosticV1, ...],
]:
    event_indices = {item.observation_index for item in events}
    eligible = range(plan.history_observations, len(observations) - 1)
    event_ratios = [
        ratio
        for index in event_indices
        if (ratio := observations[index].long_short_ratio) is not None
    ]
    control_ratios = [
        ratio
        for index in eligible
        if index not in event_indices
        and (ratio := observations[index].long_short_ratio) is not None
    ]
    missing = sum(observations[index].long_short_ratio is None for index in eligible)
    ratio_diagnostic = None
    if event_ratios and control_ratios:
        ratio_diagnostic = CryptoCrowdingLongShortDiagnosticV1(
            event_mean=sum(event_ratios) / len(event_ratios),
            non_event_mean=sum(control_ratios) / len(control_ratios),
            event_count=len(event_ratios),
            non_event_count=len(control_ratios),
            missing_count=missing,
        )
    by_regime: dict[str, list[float]] = {}
    for event in events:
        regime = observations[event.observation_index].regime
        by_regime.setdefault(regime, []).append(event.mark_minus_index_return)
    regimes = tuple(
        CryptoCrowdingRegimeDiagnosticV1(
            regime=regime,
            event_count=len(values),
            mean_outcome=sum(values) / len(values),
        )
        for regime, values in sorted(by_regime.items())
    )
    return ratio_diagnostic, regimes


def evaluate_crypto_crowding(
    observations: tuple[CryptoCrowdingObservationV1, ...],
    *,
    evidence_zone: CryptoEvidenceZone,
) -> CryptoCrowdingEvaluationV1:
    """Evaluate only the registered causal event family; never read D3 observations."""
    if evidence_zone not in {"D1", "D2"}:
        raise DataError("crypto crowding evidence zone must be D1 or D2")
    if not isinstance(observations, tuple) or any(
        not isinstance(item, CryptoCrowdingObservationV1) for item in observations
    ):
        raise DataError("crypto crowding observations must be an ordered typed tuple")
    times = [item.funding_time for item in observations]
    if any(right <= left for left, right in zip(times, times[1:], strict=False)):
        raise DataError("crypto crowding funding observations must be strictly increasing")

    plan = registered_crypto_crowding_plan()
    primary = _events_for_percentile(observations, percentile=plan.primary_percentile, plan=plan)
    primary_estimate = _matched_estimate(observations, primary, plan=plan)
    sensitivity_results = _sensitivity_results(observations, plan=plan)
    sensitivities = tuple((item.percentile, item.event_count) for item in sensitivity_results)
    blockers = {f"minimum_effective_events:{len(primary)}<{plan.minimum_effective_events}"}
    if len(primary) >= plan.minimum_effective_events:
        blockers.clear()
        if primary_estimate is None:
            blockers.add("matched_controls_unavailable")
        elif primary_estimate.low_cluster_count:
            blockers.add(f"minimum_week_clusters:{primary_estimate.effective_week_clusters}<10")
    if evidence_zone == "D2" and len(primary) < plan.minimum_confirmation_events:
        blockers.add(
            f"minimum_confirmation_events:{len(primary)}<{plan.minimum_confirmation_events}"
        )
    long_short, regimes = _diagnostics(observations, primary, plan=plan)
    ordered_blockers = tuple(sorted(blockers))
    return CryptoCrowdingEvaluationV1(
        evidence_zone=evidence_zone,
        plan_fingerprint=plan.operator_fingerprint,
        status="INCONCLUSIVE" if ordered_blockers else "EVALUATED",
        primary_events=primary,
        sensitivity_event_counts=sensitivities,
        blockers=ordered_blockers,
        primary_estimate=primary_estimate,
        sensitivity_results=sensitivity_results,
        shifted_date_placebo=_shifted_date_placebo(observations, primary, plan=plan),
        long_short_diagnostic=long_short,
        regime_diagnostics=regimes,
    )


__all__ = [
    "CryptoCrowdingD0AcceptanceV1",
    "CryptoCrowdingEvaluationV1",
    "CryptoCrowdingEstimateV1",
    "CryptoCrowdingEventV1",
    "CryptoCrowdingLongShortDiagnosticV1",
    "CryptoCrowdingObservationV1",
    "CryptoCrowdingRegimeDiagnosticV1",
    "CryptoCrowdingResearchPlanV1",
    "CryptoCrowdingSensitivityV1",
    "CryptoCrowdingShiftedPlaceboV1",
    "execute_crypto_crowding_d0",
    "evaluate_crypto_crowding",
    "registered_crypto_crowding_plan",
]

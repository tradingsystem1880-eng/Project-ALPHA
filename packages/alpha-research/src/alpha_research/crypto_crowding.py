"""Point-in-time contracts and evaluation for the registered BTCUSDT crowding question."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

from alpha_core import DataError

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
    percentile_method: str = "linear_type7_v1"
    open_interest_lookback_hours: int = 24
    entry_delay_hours: int = 1
    practical_hurdle_return: float = -0.0005
    minimum_effective_events: int = 50
    minimum_confirmation_events: int = 10
    uncertainty_cluster: str = "UTC_week"
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
            or self.percentile_method != "linear_type7_v1"
            or self.open_interest_lookback_hours != 24
            or self.entry_delay_hours != 1
            or self.practical_hurdle_return != -0.0005
            or self.minimum_effective_events != 50
            or self.minimum_confirmation_events != 10
            or self.uncertainty_cluster != "UTC_week"
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
            "percentile_method": self.percentile_method,
            "open_interest_lookback_hours": self.open_interest_lookback_hours,
            "entry_delay_hours": self.entry_delay_hours,
            "practical_hurdle_return": self.practical_hurdle_return,
            "minimum_effective_events": self.minimum_effective_events,
            "minimum_confirmation_events": self.minimum_confirmation_events,
            "uncertainty_cluster": self.uncertainty_cluster,
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
class CryptoCrowdingEvaluationV1:
    evidence_zone: CryptoEvidenceZone
    plan_fingerprint: str
    status: CryptoCrowdingStatus
    primary_events: tuple[CryptoCrowdingEventV1, ...]
    sensitivity_event_counts: tuple[tuple[float, int], ...]
    blockers: tuple[str, ...]
    schema: str = _RESULT_SCHEMA
    schema_version: Literal[1] = 1

    @property
    def primary_event_count(self) -> int:
        return len(self.primary_events)


def registered_crypto_crowding_plan() -> CryptoCrowdingResearchPlanV1:
    """Return the one immutable operator generation admitted by ADR-0033."""
    return CryptoCrowdingResearchPlanV1()


def _percentile(values: tuple[float, ...], probability: float) -> float:
    """R-7/type-7 linear quantile over an already point-in-time history."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
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
    sensitivities = tuple(
        (
            percentile,
            len(_events_for_percentile(observations, percentile=percentile, plan=plan)),
        )
        for percentile in plan.sensitivity_percentiles
    )
    blockers = {f"minimum_effective_events:{len(primary)}<{plan.minimum_effective_events}"}
    if len(primary) >= plan.minimum_effective_events:
        blockers.clear()
    if evidence_zone == "D2" and len(primary) < plan.minimum_confirmation_events:
        blockers.add(
            f"minimum_confirmation_events:{len(primary)}<{plan.minimum_confirmation_events}"
        )
    ordered_blockers = tuple(sorted(blockers))
    return CryptoCrowdingEvaluationV1(
        evidence_zone=evidence_zone,
        plan_fingerprint=plan.operator_fingerprint,
        status="INCONCLUSIVE" if ordered_blockers else "EVALUATED",
        primary_events=primary,
        sensitivity_event_counts=sensitivities,
        blockers=ordered_blockers,
    )


__all__ = [
    "CryptoCrowdingEvaluationV1",
    "CryptoCrowdingEventV1",
    "CryptoCrowdingObservationV1",
    "CryptoCrowdingResearchPlanV1",
    "evaluate_crypto_crowding",
    "registered_crypto_crowding_plan",
]

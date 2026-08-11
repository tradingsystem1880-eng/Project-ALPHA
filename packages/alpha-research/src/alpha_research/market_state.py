"""Causal, calendar-specific daily market-state derivation.

The contract freezes every window and threshold.  A point at session ``t`` reads only closes whose
``available_at`` is no later than that session's close record.  Warm-up and undefined correlation
states remain explicit abstentions rather than being imputed into an apparently usable regime.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, cast

import numpy as np

from alpha_core import DataError
from alpha_research._canonical import canonical_sha256

MarketCalendar = Literal["equity", "crypto_24_7"]

_CONTRACT_SCHEMA = "MarketStateContractV1"
_ARTIFACT_SCHEMA = "MarketStateV1"
_CALENDARS = {"equity", "crypto_24_7"}
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _exact_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise DataError(f"{label} has unexpected or missing fields")


def _integer(value: object, label: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise DataError(f"{label} must be an integer >= {minimum}")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise DataError(f"{label} must be a finite number")
    return float(value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DataError(f"{label} must be a non-empty canonical string")
    return value


def _sha256(value: object, label: str) -> str:
    digest = _text(value, label)
    if _SHA256.fullmatch(digest) is None:
        raise DataError(f"{label} must be a lowercase 64-character SHA-256 digest")
    return digest


def _pair(value: object, label: str) -> tuple[float, float]:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise DataError(f"{label} must contain exactly two thresholds")
    low, high = (_number(item, label) for item in value)
    if low >= high:
        raise DataError(f"{label} thresholds must be strictly increasing")
    return low, high


@dataclass(frozen=True, slots=True)
class MarketStateContractV1:
    """Frozen daily-universe and state semantics for one immutable experiment."""

    universe: tuple[str, ...]
    benchmark: str
    calendar: MarketCalendar
    volatility_window: int
    trend_window: int
    correlation_window: int
    annualization_sessions: int
    volatility_thresholds: tuple[float, float]
    trend_threshold: float
    breadth_thresholds: tuple[float, float]
    correlation_thresholds: tuple[float, float]
    minimum_state_samples: int

    def __post_init__(self) -> None:
        if len(self.universe) < 2:
            raise DataError("MarketStateContractV1 universe requires at least two instruments")
        canonical = tuple(
            _text(symbol, "MarketStateContractV1.universe") for symbol in self.universe
        )
        if canonical != self.universe or len(set(canonical)) != len(canonical):
            raise DataError("MarketStateContractV1 universe must contain unique canonical symbols")
        if self.benchmark not in self.universe:
            raise DataError("MarketStateContractV1 benchmark must belong to the frozen universe")
        if self.calendar not in _CALENDARS:
            raise DataError("MarketStateContractV1 calendar must be equity or crypto_24_7")
        for name in ("volatility_window", "trend_window", "correlation_window"):
            _integer(getattr(self, name), f"MarketStateContractV1.{name}", minimum=2)
        _integer(
            self.annualization_sessions,
            "MarketStateContractV1.annualization_sessions",
            minimum=1,
        )
        if self.calendar == "equity" and self.annualization_sessions != 252:
            raise DataError("equity MarketStateContractV1 annualization_sessions must be 252")
        if self.calendar == "crypto_24_7" and self.annualization_sessions != 365:
            raise DataError("crypto_24_7 MarketStateContractV1 annualization_sessions must be 365")
        volatility = _pair(self.volatility_thresholds, "volatility_thresholds")
        if volatility[0] < 0:
            raise DataError("volatility_thresholds cannot be negative")
        trend = _number(self.trend_threshold, "trend_threshold")
        if trend < 0:
            raise DataError("trend_threshold cannot be negative")
        breadth = _pair(self.breadth_thresholds, "breadth_thresholds")
        if not 0 <= breadth[0] < breadth[1] <= 1:
            raise DataError("breadth_thresholds must lie in [0, 1]")
        correlation = _pair(self.correlation_thresholds, "correlation_thresholds")
        if not -1 <= correlation[0] < correlation[1] <= 1:
            raise DataError("correlation_thresholds must lie in [-1, 1]")
        _integer(
            self.minimum_state_samples,
            "MarketStateContractV1.minimum_state_samples",
            minimum=1,
        )

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "schema": _CONTRACT_SCHEMA,
            "schema_version": 1,
            "universe": list(self.universe),
            "benchmark": self.benchmark,
            "calendar": self.calendar,
            "volatility_window": self.volatility_window,
            "trend_window": self.trend_window,
            "correlation_window": self.correlation_window,
            "annualization_sessions": self.annualization_sessions,
            "volatility_thresholds": list(self.volatility_thresholds),
            "trend_threshold": self.trend_threshold,
            "breadth_thresholds": list(self.breadth_thresholds),
            "correlation_thresholds": list(self.correlation_thresholds),
            "minimum_state_samples": self.minimum_state_samples,
        }

    @property
    def contract_sha256(self) -> str:
        return canonical_sha256(self._semantic_dict())

    def to_dict(self) -> dict[str, object]:
        payload = self._semantic_dict()
        payload["contract_sha256"] = self.contract_sha256
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> MarketStateContractV1:
        _exact_keys(
            value,
            {
                "schema",
                "schema_version",
                "universe",
                "benchmark",
                "calendar",
                "volatility_window",
                "trend_window",
                "correlation_window",
                "annualization_sessions",
                "volatility_thresholds",
                "trend_threshold",
                "breadth_thresholds",
                "correlation_thresholds",
                "minimum_state_samples",
                "contract_sha256",
            },
            _CONTRACT_SCHEMA,
        )
        if value["schema"] != _CONTRACT_SCHEMA or value["schema_version"] != 1:
            raise DataError("unsupported MarketStateContractV1 schema")
        universe = value["universe"]
        if not isinstance(universe, list) or any(not isinstance(item, str) for item in universe):
            raise DataError("MarketStateContractV1 universe must be a string array")
        calendar = _text(value["calendar"], "calendar")
        result = cls(
            universe=tuple(universe),
            benchmark=_text(value["benchmark"], "benchmark"),
            calendar=cast(MarketCalendar, calendar),
            volatility_window=_integer(value["volatility_window"], "volatility_window", minimum=2),
            trend_window=_integer(value["trend_window"], "trend_window", minimum=2),
            correlation_window=_integer(
                value["correlation_window"], "correlation_window", minimum=2
            ),
            annualization_sessions=_integer(
                value["annualization_sessions"], "annualization_sessions", minimum=1
            ),
            volatility_thresholds=_pair(value["volatility_thresholds"], "volatility_thresholds"),
            trend_threshold=_number(value["trend_threshold"], "trend_threshold"),
            breadth_thresholds=_pair(value["breadth_thresholds"], "breadth_thresholds"),
            correlation_thresholds=_pair(value["correlation_thresholds"], "correlation_thresholds"),
            minimum_state_samples=_integer(
                value["minimum_state_samples"], "minimum_state_samples", minimum=1
            ),
        )
        supplied = _sha256(value["contract_sha256"], "contract_sha256")
        if supplied != result.contract_sha256:
            raise DataError("MarketStateContractV1 contract_sha256 does not match its semantics")
        return result


@dataclass(frozen=True, slots=True)
class MarketSessionCloseV1:
    """One aligned universe close vector and its causal availability timestamp."""

    session: date
    available_at: datetime
    closes: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.session, date) or isinstance(self.session, datetime):
            raise DataError("MarketSessionCloseV1.session must be a date")
        if self.available_at.tzinfo is None or self.available_at.utcoffset() is None:
            raise DataError("MarketSessionCloseV1.available_at must be timezone-aware")
        if not self.closes:
            raise DataError("MarketSessionCloseV1.closes cannot be empty")
        if any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or value <= 0
            for value in self.closes
        ):
            raise DataError("MarketSessionCloseV1.closes must be finite positive prices")

    def to_dict(self) -> dict[str, object]:
        return {
            "session": self.session.isoformat(),
            "available_at": self.available_at.isoformat(),
            "closes": list(self.closes),
        }


@dataclass(frozen=True, slots=True)
class MarketStatePointV1:
    """One close-stamped state.  Ineligible points require candidate abstention."""

    session: date
    available_at: datetime
    annualized_volatility: float | None
    benchmark_trend: float | None
    breadth: float | None
    average_correlation: float | None
    volatility_label: str
    trend_label: str
    breadth_label: str
    correlation_label: str
    state_key: str
    eligible: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "session": self.session.isoformat(),
            "available_at": self.available_at.isoformat(),
            "annualized_volatility": self.annualized_volatility,
            "benchmark_trend": self.benchmark_trend,
            "breadth": self.breadth,
            "average_correlation": self.average_correlation,
            "volatility_label": self.volatility_label,
            "trend_label": self.trend_label,
            "breadth_label": self.breadth_label,
            "correlation_label": self.correlation_label,
            "state_key": self.state_key,
            "eligible": self.eligible,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> MarketStatePointV1:
        expected = {
            "session",
            "available_at",
            "annualized_volatility",
            "benchmark_trend",
            "breadth",
            "average_correlation",
            "volatility_label",
            "trend_label",
            "breadth_label",
            "correlation_label",
            "state_key",
            "eligible",
        }
        _exact_keys(value, expected, "MarketStatePointV1")

        def optional_number(name: str) -> float | None:
            item = value[name]
            return None if item is None else _number(item, f"MarketStatePointV1.{name}")

        try:
            session = date.fromisoformat(_text(value["session"], "MarketStatePointV1.session"))
            available_at = datetime.fromisoformat(
                _text(value["available_at"], "MarketStatePointV1.available_at")
            )
        except ValueError as exc:
            raise DataError("MarketStatePointV1 has an invalid date or timestamp") from exc
        eligible = value["eligible"]
        if not isinstance(eligible, bool):
            raise DataError("MarketStatePointV1.eligible must be boolean")
        result = cls(
            session=session,
            available_at=available_at,
            annualized_volatility=optional_number("annualized_volatility"),
            benchmark_trend=optional_number("benchmark_trend"),
            breadth=optional_number("breadth"),
            average_correlation=optional_number("average_correlation"),
            volatility_label=_text(value["volatility_label"], "volatility_label"),
            trend_label=_text(value["trend_label"], "trend_label"),
            breadth_label=_text(value["breadth_label"], "breadth_label"),
            correlation_label=_text(value["correlation_label"], "correlation_label"),
            state_key=_text(value["state_key"], "state_key"),
            eligible=eligible,
        )
        if result.available_at.tzinfo is None or result.available_at.utcoffset() is None:
            raise DataError("MarketStatePointV1.available_at must be timezone-aware")
        if not eligible and result.state_key != "unavailable":
            raise DataError("ineligible MarketStatePointV1 must use the unavailable state_key")
        return result


@dataclass(frozen=True, slots=True)
class MarketStateArtifactV1:
    """Versioned, content-addressed market-state artifact."""

    contract: MarketStateContractV1
    source_sha256: str
    points: tuple[MarketStatePointV1, ...]

    def __post_init__(self) -> None:
        _sha256(self.source_sha256, "MarketStateV1.source_sha256")
        if not self.points:
            raise DataError("MarketStateV1.points cannot be empty")
        previous: MarketStatePointV1 | None = None
        for point in self.points:
            if previous is not None and (
                point.session <= previous.session or point.available_at <= previous.available_at
            ):
                raise DataError(
                    "MarketStateV1 points must have increasing sessions and availability"
                )
            metrics = (
                point.annualized_volatility,
                point.benchmark_trend,
                point.breadth,
                point.average_correlation,
            )
            labels = (
                point.volatility_label,
                point.trend_label,
                point.breadth_label,
                point.correlation_label,
            )
            if point.eligible and (
                any(metric is None for metric in metrics) or "unavailable" in labels
            ):
                raise DataError("eligible MarketStateV1 points require all metrics and labels")
            if not point.eligible and point.state_key != "unavailable":
                raise DataError("ineligible MarketStateV1 points must use unavailable state_key")
            previous = point

    @property
    def contract_sha256(self) -> str:
        return self.contract.contract_sha256

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "schema": _ARTIFACT_SCHEMA,
            "schema_version": 1,
            "contract": self.contract.to_dict(),
            "contract_sha256": self.contract_sha256,
            "source_sha256": self.source_sha256,
            "points": [point.to_dict() for point in self.points],
        }

    @property
    def artifact_sha256(self) -> str:
        return canonical_sha256(self._semantic_dict())

    def to_dict(self) -> dict[str, object]:
        payload = self._semantic_dict()
        payload["artifact_sha256"] = self.artifact_sha256
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> MarketStateArtifactV1:
        _exact_keys(
            value,
            {
                "schema",
                "schema_version",
                "contract",
                "contract_sha256",
                "source_sha256",
                "points",
                "artifact_sha256",
            },
            _ARTIFACT_SCHEMA,
        )
        if value["schema"] != _ARTIFACT_SCHEMA or value["schema_version"] != 1:
            raise DataError("unsupported MarketStateV1 schema")
        contract_value = value["contract"]
        if not isinstance(contract_value, Mapping):
            raise DataError("MarketStateV1.contract must be an object")
        contract = MarketStateContractV1.from_dict(cast(Mapping[str, object], contract_value))
        if value["contract_sha256"] != contract.contract_sha256:
            raise DataError("MarketStateV1 contract_sha256 does not match its contract")
        points_value = value["points"]
        if not isinstance(points_value, list) or any(
            not isinstance(item, Mapping) for item in points_value
        ):
            raise DataError("MarketStateV1.points must be an object array")
        result = cls(
            contract=contract,
            source_sha256=_sha256(value["source_sha256"], "MarketStateV1.source_sha256"),
            points=tuple(
                MarketStatePointV1.from_dict(cast(Mapping[str, object], item))
                for item in points_value
            ),
        )
        if value["artifact_sha256"] != result.artifact_sha256:
            raise DataError("MarketStateV1 artifact_sha256 does not match its content")
        return result


def _label_three(
    value: float, thresholds: tuple[float, float], labels: tuple[str, str, str]
) -> str:
    if value <= thresholds[0]:
        return labels[0]
    if value >= thresholds[1]:
        return labels[2]
    return labels[1]


def _validate_observations(
    contract: MarketStateContractV1, observations: Sequence[MarketSessionCloseV1]
) -> None:
    if not observations:
        raise DataError("MarketStateV1 requires at least one aligned session close")
    previous: MarketSessionCloseV1 | None = None
    for observation in observations:
        if len(observation.closes) != len(contract.universe):
            raise DataError("MarketStateV1 close vector must match the frozen universe")
        if contract.calendar == "equity" and observation.session.weekday() >= 5:
            raise DataError("equity MarketStateV1 cannot contain weekend sessions")
        if previous is not None:
            if observation.session <= previous.session:
                raise DataError("MarketStateV1 sessions must be strictly increasing")
            if observation.available_at <= previous.available_at:
                raise DataError("MarketStateV1 available_at timestamps must be strictly increasing")
            if (
                contract.calendar == "crypto_24_7"
                and observation.session != previous.session + timedelta(days=1)
            ):
                raise DataError("crypto_24_7 MarketStateV1 sessions must be consecutive")
        previous = observation


def derive_market_state(
    contract: MarketStateContractV1,
    observations: Sequence[MarketSessionCloseV1],
) -> MarketStateArtifactV1:
    """Derive close-stamped states without consulting any future observation."""
    _validate_observations(contract, observations)
    closes = np.asarray([observation.closes for observation in observations], dtype=float)
    returns = np.diff(np.log(closes), axis=0)
    benchmark_index = contract.universe.index(contract.benchmark)
    warmup = max(
        contract.volatility_window,
        contract.trend_window,
        contract.correlation_window,
    )
    points: list[MarketStatePointV1] = []
    for index, observation in enumerate(observations):
        if index < warmup:
            points.append(
                MarketStatePointV1(
                    session=observation.session,
                    available_at=observation.available_at,
                    annualized_volatility=None,
                    benchmark_trend=None,
                    breadth=None,
                    average_correlation=None,
                    volatility_label="unavailable",
                    trend_label="unavailable",
                    breadth_label="unavailable",
                    correlation_label="unavailable",
                    state_key="unavailable",
                    eligible=False,
                )
            )
            continue
        volatility_slice = returns[index - contract.volatility_window : index, benchmark_index]
        annualized_volatility = float(
            np.std(volatility_slice, ddof=1) * math.sqrt(contract.annualization_sessions)
        )
        benchmark_trend = float(
            math.log(
                closes[index, benchmark_index]
                / closes[index - contract.trend_window, benchmark_index]
            )
        )
        instrument_trends = np.log(closes[index, :] / closes[index - contract.trend_window, :])
        breadth = float(np.mean(instrument_trends > 0.0))
        correlation_slice = returns[index - contract.correlation_window : index, :]
        correlations: list[float] = []
        for left in range(correlation_slice.shape[1]):
            for right in range(left + 1, correlation_slice.shape[1]):
                left_values = correlation_slice[:, left]
                right_values = correlation_slice[:, right]
                if (
                    float(np.std(left_values)) <= np.finfo(float).eps
                    or float(np.std(right_values)) <= np.finfo(float).eps
                ):
                    continue
                correlations.append(float(np.corrcoef(left_values, right_values)[0, 1]))
        if not correlations:
            points.append(
                MarketStatePointV1(
                    session=observation.session,
                    available_at=observation.available_at,
                    annualized_volatility=annualized_volatility,
                    benchmark_trend=benchmark_trend,
                    breadth=breadth,
                    average_correlation=None,
                    volatility_label=_label_three(
                        annualized_volatility,
                        contract.volatility_thresholds,
                        ("low", "mid", "high"),
                    ),
                    trend_label=_label_three(
                        benchmark_trend,
                        (-contract.trend_threshold, contract.trend_threshold),
                        ("down", "flat", "up"),
                    ),
                    breadth_label=_label_three(
                        breadth, contract.breadth_thresholds, ("weak", "mixed", "strong")
                    ),
                    correlation_label="unavailable",
                    state_key="unavailable",
                    eligible=False,
                )
            )
            continue
        average_correlation = float(np.mean(correlations))
        volatility_label = _label_three(
            annualized_volatility, contract.volatility_thresholds, ("low", "mid", "high")
        )
        trend_label = _label_three(
            benchmark_trend,
            (-contract.trend_threshold, contract.trend_threshold),
            ("down", "flat", "up"),
        )
        breadth_label = _label_three(
            breadth, contract.breadth_thresholds, ("weak", "mixed", "strong")
        )
        correlation_label = _label_three(
            average_correlation, contract.correlation_thresholds, ("low", "mid", "high")
        )
        state_key = (
            f"volatility={volatility_label}|trend={trend_label}|breadth={breadth_label}|"
            f"correlation={correlation_label}"
        )
        points.append(
            MarketStatePointV1(
                session=observation.session,
                available_at=observation.available_at,
                annualized_volatility=annualized_volatility,
                benchmark_trend=benchmark_trend,
                breadth=breadth,
                average_correlation=average_correlation,
                volatility_label=volatility_label,
                trend_label=trend_label,
                breadth_label=breadth_label,
                correlation_label=correlation_label,
                state_key=state_key,
                eligible=True,
            )
        )
    source_sha256 = canonical_sha256([observation.to_dict() for observation in observations])
    return MarketStateArtifactV1(
        contract=contract,
        source_sha256=source_sha256,
        points=tuple(points),
    )


@dataclass(frozen=True, slots=True)
class MarketStateConditionalValueV1:
    """One state diagnostic with an explicit pooled fallback for sparse states."""

    state_key: str
    sample_count: int
    minimum_samples: int
    used_pooled_fallback: bool
    value_count: int
    mean: float
    pooled_count: int


def condition_values_by_market_state(
    artifact: MarketStateArtifactV1, values: Sequence[float]
) -> tuple[MarketStateConditionalValueV1, ...]:
    """Summarize aligned values by eligible state, falling back exactly when preregistered."""
    if len(values) != len(artifact.points):
        raise DataError("market-state conditioned values must align one-for-one with state points")
    numeric = np.asarray(values, dtype=float)
    if numeric.ndim != 1 or not np.all(np.isfinite(numeric)):
        raise DataError("market-state conditioned values must be finite and one-dimensional")
    grouped: dict[str, list[float]] = {}
    pooled: list[float] = []
    for point, value in zip(artifact.points, numeric, strict=True):
        if not point.eligible:
            continue
        grouped.setdefault(point.state_key, []).append(float(value))
        pooled.append(float(value))
    if not pooled:
        return ()
    rows: list[MarketStateConditionalValueV1] = []
    for state_key in sorted(grouped):
        state_values = grouped[state_key]
        fallback = len(state_values) < artifact.contract.minimum_state_samples
        selected = pooled if fallback else state_values
        rows.append(
            MarketStateConditionalValueV1(
                state_key=state_key,
                sample_count=len(state_values),
                minimum_samples=artifact.contract.minimum_state_samples,
                used_pooled_fallback=fallback,
                value_count=len(selected),
                mean=float(np.mean(selected)),
                pooled_count=len(pooled),
            )
        )
    return tuple(rows)


__all__ = [
    "MarketCalendar",
    "MarketSessionCloseV1",
    "MarketStateArtifactV1",
    "MarketStateConditionalValueV1",
    "MarketStateContractV1",
    "MarketStatePointV1",
    "condition_values_by_market_state",
    "derive_market_state",
]

"""Compose verified provider-native crypto frames into the pure crowding contract."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoQualityReportV1, CryptoSnapshotV1
from alpha_research import CryptoCrowdingObservationV1, registered_crypto_crowding_plan


def _time(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DataError(f"crypto crowding {label} timestamp is invalid")
    return value.astimezone(UTC)


def _number(value: object, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise DataError(f"crypto crowding {label} value is invalid")
    result = float(value)
    if positive and result <= 0:
        raise DataError(f"crypto crowding {label} value must be positive")
    return result


def _values(
    frame: pl.DataFrame,
    *,
    family: str,
    column: str,
    positive: bool = False,
) -> dict[datetime, float]:
    required = {"timestamp", "category", "symbol", column}
    if frame.is_empty() or not required.issubset(frame.columns):
        raise DataError(f"crypto crowding {family} frame is invalid")
    if set(frame["category"].unique().to_list()) != {"linear"} or set(
        frame["symbol"].unique().to_list()
    ) != {"BTCUSDT"}:
        raise DataError(f"crypto crowding {family} identity is invalid")
    values: dict[datetime, float] = {}
    for timestamp, value in frame.select("timestamp", column).iter_rows():
        key = _time(timestamp, family)
        if key in values:
            raise DataError(f"crypto crowding {family} timestamps are duplicated")
        values[key] = _number(value, family, positive=positive)
    return values


def _bar_values(frame: pl.DataFrame, *, family: str) -> dict[datetime, float]:
    provider_family = {
        "premium_bars": "premium",
        "mark_bars": "mark",
        "index_bars": "index",
        "derivative_bars": "trade",
    }[family]
    if "family" not in frame.columns or set(frame["family"].unique().to_list()) != {
        provider_family
    }:
        raise DataError(f"crypto crowding {family} provider family is invalid")
    return _values(frame, family=family, column="close", positive=family != "premium_bars")


def _exact(values: Mapping[datetime, float], timestamp: datetime, family: str) -> float:
    try:
        return values[timestamp]
    except KeyError as exc:
        raise DataError(
            f"crypto crowding missing exact {family} close at {timestamp.isoformat()}"
        ) from exc


def _recent_market_state(
    closes: Mapping[datetime, float], funding_time: datetime
) -> tuple[float, float]:
    timestamps = tuple(funding_time - timedelta(hours=offset) for offset in range(25, 0, -1))
    values = [_exact(closes, timestamp, "derivative_bars") for timestamp in timestamps]
    returns = [right / left - 1 for left, right in zip(values, values[1:], strict=False)]
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return values[-1] / values[0] - 1, math.sqrt(variance)


def _type7(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper or ordered[lower] == ordered[upper]:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _regime(volatilities: list[float], index: int) -> str:
    plan = registered_crypto_crowding_plan()
    if index < plan.history_observations:
        return "warmup"
    history = volatilities[index - plan.history_observations : index]
    lower, upper = _type7(history, 1 / 3), _type7(history, 2 / 3)
    if volatilities[index] <= lower:
        return "low_volatility"
    if volatilities[index] >= upper:
        return "high_volatility"
    return "middle_volatility"


def _funding_times(frame: pl.DataFrame) -> tuple[datetime, ...]:
    values = _values(frame, family="funding", column="funding_rate")
    times = tuple(sorted(values))
    if len(times) < 2:
        raise DataError("crypto crowding funding history requires at least two observations")
    return times


def _funding_interval_minutes(frame: pl.DataFrame) -> int:
    required = {
        "symbol",
        "category",
        "status",
        "base_coin",
        "quote_coin",
        "funding_interval_minutes",
    }
    if frame.is_empty() or not required.issubset(frame.columns):
        raise DataError("crypto crowding instrument catalog is invalid")
    selected = frame.filter(
        (pl.col("symbol") == "BTCUSDT")
        & (pl.col("category") == "linear")
        & (pl.col("status") == "Trading")
        & (pl.col("base_coin") == "BTC")
        & (pl.col("quote_coin") == "USDT")
    )
    if selected.height != 1:
        raise DataError("crypto crowding instrument catalog lacks exact trading BTCUSDT")
    value = selected["funding_interval_minutes"][0]
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DataError("crypto crowding funding interval is invalid")
    return value


def compose_crypto_crowding_observations(
    frames: Mapping[str, pl.DataFrame],
    *,
    correction_lineage: tuple[str, ...],
) -> tuple[CryptoCrowdingObservationV1, ...]:
    """Create causal observations from one already reverified exact snapshot."""
    plan = registered_crypto_crowding_plan()
    required = {*plan.required_families, plan.confounder_family}
    if set(frames) != required or any(
        not isinstance(frame, pl.DataFrame) for frame in frames.values()
    ):
        raise DataError("crypto crowding frames do not match the registered family bundle")
    if not isinstance(correction_lineage, tuple) or any(
        not isinstance(item, str) or not item.strip() for item in correction_lineage
    ):
        raise DataError("crypto crowding correction lineage is invalid")

    funding = _values(frames["funding"], family="funding", column="funding_rate")
    funding_times = _funding_times(frames["funding"])
    interval = timedelta(minutes=_funding_interval_minutes(frames["instrument_catalog"]))
    open_interest = _values(
        frames["open_interest"], family="open_interest", column="open_interest", positive=True
    )
    ratios = _values(
        frames[plan.confounder_family],
        family=plan.confounder_family,
        column="long_short_ratio",
        positive=True,
    )
    premium = _bar_values(frames["premium_bars"], family="premium_bars")
    mark = _bar_values(frames["mark_bars"], family="mark_bars")
    index = _bar_values(frames["index_bars"], family="index_bars")
    trade = _bar_values(frames["derivative_bars"], family="derivative_bars")

    rows: list[CryptoCrowdingObservationV1] = []
    volatilities: list[float] = []
    for funding_time, next_funding in zip(funding_times, funding_times[1:], strict=False):
        if next_funding - funding_time != interval:
            raise DataError("crypto crowding funding history has a missing or changed interval")
        entry_time = funding_time + timedelta(hours=plan.entry_delay_hours)
        trend, volatility = _recent_market_state(trade, funding_time)
        prior_oi_time = funding_time - timedelta(hours=plan.open_interest_lookback_hours)
        if funding_time not in open_interest or prior_oi_time not in open_interest:
            raise DataError("crypto crowding open interest lacks the exact 24-hour window")
        if funding_time not in ratios:
            raise DataError("crypto crowding long/short ratio is missing at a funding event")
        volatilities.append(volatility)
        rows.append(
            CryptoCrowdingObservationV1(
                funding_time=funding_time,
                funding_available_at=funding_time,
                funding_rate=funding[funding_time],
                open_interest=open_interest[funding_time],
                open_interest_available_at=funding_time,
                premium=_exact(premium, funding_time - timedelta(hours=1), "premium_bars"),
                premium_available_at=funding_time,
                entry_time=entry_time,
                entry_available_at=entry_time,
                entry_mark=_exact(mark, funding_time, "mark_bars"),
                entry_index=_exact(index, funding_time, "index_bars"),
                exit_time=next_funding,
                exit_available_at=next_funding,
                exit_mark=_exact(mark, next_funding - timedelta(hours=1), "mark_bars"),
                exit_index=_exact(index, next_funding - timedelta(hours=1), "index_bars"),
                long_short_ratio=ratios[funding_time],
                recent_trend=trend,
                recent_volatility=volatility,
                regime=_regime(volatilities, len(rows)),
                diagnostics_available_at=funding_time,
                correction_lineage=correction_lineage,
            )
        )
    return tuple(rows)


def load_crypto_crowding_observations(
    snapshot: CryptoSnapshotV1,
    quality_reports: Mapping[str, CryptoQualityReportV1],
    *,
    bulk_root: Path,
) -> tuple[CryptoCrowdingObservationV1, ...]:
    """Read only the exact already-reverified snapshot members and compose the pure contract."""
    plan = registered_crypto_crowding_plan()
    required = {*plan.required_families, plan.confounder_family}
    members = {member.dataset.family: member for member in snapshot.members}
    if set(members) != required or len(members) != len(snapshot.members):
        raise DataError("crypto crowding snapshot membership is not the exact registered bundle")
    frames: dict[str, pl.DataFrame] = {}
    lineage: set[str] = set()
    for family, member in members.items():
        report = quality_reports.get(member.artifact_sha256)
        if report is None or report.state != "qualified":
            raise DataError("crypto crowding snapshot quality binding is missing")
        if report.correction_lineage:
            raise DataError(
                "crypto crowding snapshot corrections lack row-level availability timestamps"
            )
        lineage.update(report.correction_lineage)
        try:
            frames[family] = pl.read_parquet(bulk_root / member.artifact_key)
        except (OSError, pl.exceptions.PolarsError) as exc:
            raise DataError("crypto crowding snapshot member is unreadable") from exc
    return compose_crypto_crowding_observations(
        frames,
        correction_lineage=tuple(sorted(lineage)),
    )


__all__ = ["compose_crypto_crowding_observations", "load_crypto_crowding_observations"]

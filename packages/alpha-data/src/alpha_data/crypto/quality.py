"""Mechanical qualification for provider-native crypto observations."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import polars as pl

from alpha_core import DataError

from .contracts import (
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    QualificationState,
    content_digest,
    require_utc,
)

QUALITY_METHOD_VERSION: Final = "crypto-quality-v1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class MarketComparisonSummaryV1:
    comparison_id: str
    primary_sha256: str
    comparison_sha256: tuple[tuple[str, str], ...]
    state: QualificationState
    max_abs_divergence_bps: float
    matched_observations: int
    missing_observations: int
    warning_bps: float
    quarantine_bps: float
    schema_version: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "comparison_id": self.comparison_id,
            "primary_sha256": self.primary_sha256,
            "comparison_sha256": [list(item) for item in self.comparison_sha256],
            "state": self.state,
            "max_abs_divergence_bps": self.max_abs_divergence_bps,
            "matched_observations": self.matched_observations,
            "missing_observations": self.missing_observations,
            "warning_bps": self.warning_bps,
            "quarantine_bps": self.quarantine_bps,
        }


def _source_column(provider: str, value_column: str) -> str:
    provider_key = re.sub(r"[^a-z0-9]+", "_", provider.lower()).strip("_")
    if not provider_key:
        raise DataError("crypto comparison provider is invalid")
    return f"{provider_key}_{value_column}"


def compare_market_observations(
    *,
    primary: pl.DataFrame,
    primary_provider: str,
    primary_sha256: str,
    comparisons: tuple[tuple[str, str, pl.DataFrame], ...],
    timestamp_column: str,
    value_column: str,
    warning_bps: float,
    quarantine_bps: float,
) -> tuple[pl.DataFrame, MarketComparisonSummaryV1]:
    """Compare exact observations while preserving the primary as primary."""
    if _SHA256.fullmatch(primary_sha256) is None or any(
        _SHA256.fullmatch(digest) is None for _, digest, _ in comparisons
    ):
        raise DataError("crypto comparison source hash is invalid")
    if not 0 < warning_bps < quarantine_bps:
        raise DataError("crypto comparison thresholds are invalid")
    if not comparisons:
        raise DataError("crypto comparison requires at least one independent source")
    required = {timestamp_column, value_column}
    if not required.issubset(primary.columns):
        raise DataError("crypto comparison primary columns are missing")
    primary_name = _source_column(primary_provider, value_column)
    if primary.select(pl.struct((timestamp_column,)).is_duplicated().any()).item():
        raise DataError("crypto comparison primary timestamps are duplicated")
    diagnostics = primary.select(
        timestamp_column, pl.col(value_column).cast(pl.Float64).alias(primary_name)
    )
    if diagnostics[primary_name].null_count() or any(
        value <= 0 or not math.isfinite(value) for value in diagnostics[primary_name].to_list()
    ):
        raise DataError("crypto comparison primary values are invalid")
    source_hashes: list[tuple[str, str]] = []
    aliases = {primary_name}
    missing = 0
    matched = 0
    max_abs = 0.0
    for provider, digest, frame in comparisons:
        if not required.issubset(frame.columns):
            raise DataError("crypto comparison source columns are missing")
        alias = _source_column(provider, value_column)
        if alias in aliases:
            raise DataError("crypto comparison provider aliases collide")
        aliases.add(alias)
        if frame.select(pl.struct((timestamp_column,)).is_duplicated().any()).item():
            raise DataError("crypto comparison timestamps are duplicated")
        source = frame.select(timestamp_column, pl.col(value_column).cast(pl.Float64).alias(alias))
        diagnostics = diagnostics.join(source, on=timestamp_column, how="left", validate="1:1")
        divergence = f"{alias}_divergence_bps"
        diagnostics = diagnostics.with_columns(
            pl.when(pl.col(alias).is_not_null())
            .then(((pl.col(alias) / pl.col(primary_name) - 1) * 10_000).round(10))
            .otherwise(None)
            .alias(divergence)
        )
        missing += diagnostics[alias].null_count()
        values = [value for value in diagnostics[divergence].to_list() if value is not None]
        matched += len(values)
        if values:
            max_abs = max(max_abs, max(abs(value) for value in values))
        source_hashes.append((provider, digest))
    state: QualificationState
    if max_abs > quarantine_bps:
        state = "quarantined"
    elif max_abs > warning_bps or missing:
        state = "warning"
    else:
        state = "qualified"
    identity_body = {
        "schema_version": 1,
        "primary_provider": primary_provider,
        "primary_sha256": primary_sha256,
        "comparison_sha256": source_hashes,
        "timestamp_column": timestamp_column,
        "value_column": value_column,
        "warning_bps": warning_bps,
        "quarantine_bps": quarantine_bps,
    }
    return diagnostics, MarketComparisonSummaryV1(
        comparison_id=content_digest(identity_body),
        primary_sha256=primary_sha256,
        comparison_sha256=tuple(source_hashes),
        state=state,
        max_abs_divergence_bps=max_abs,
        matched_observations=matched,
        missing_observations=missing,
        warning_bps=float(warning_bps),
        quarantine_bps=float(quarantine_bps),
    )


def _times(frame: pl.DataFrame, column: str) -> list[datetime]:
    if column not in frame.columns:
        return []
    values = frame[column].to_list()
    if any(
        not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None
        for value in values
    ):
        raise DataError(f"crypto quality column {column} must contain aware datetimes")
    return [value.astimezone(UTC) for value in values]


def _numeric_failures(frame: pl.DataFrame) -> set[str]:
    for column in frame.columns:
        for value in frame[column].to_list():
            if isinstance(value, float) and not math.isfinite(value):
                return {"nonfinite_value"}
    return set()


_VOLUME_COLUMNS: Final = ("volume", "base_volume", "quote_volume", "volume_usd")


def _family_checks(
    dataset: CryptoDatasetIdentityV1, frame: pl.DataFrame
) -> tuple[set[str], set[str]]:
    failures: set[str] = set()
    warnings: set[str] = set()

    def values(column: str) -> list[object]:
        if column not in frame.columns:
            failures.add(f"missing_required_column:{column}")
            return []
        return frame[column].to_list()

    def numbers(column: str) -> list[float]:
        result: list[float] = []
        for value in values(column):
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int | float):
                failures.add(f"invalid_numeric_column:{column}")
            else:
                result.append(float(value))
        return result

    if dataset.family in {
        "market_bars",
        "comparison_bars",
        "derivative_bars",
        "mark_bars",
        "index_bars",
        "dex_ohlcv",
    }:
        opens, highs, lows, closes = (values(name) for name in ("open", "high", "low", "close"))
        for open_, high, low, close in zip(opens, highs, lows, closes, strict=False):
            raw = (open_, high, low, close)
            if any(isinstance(item, bool) or not isinstance(item, int | float) for item in raw):
                failures.add("invalid_ohlc")
                continue
            open_value, high_value, low_value, close_value = (
                float(cast(int | float, item)) for item in raw
            )
            if (
                high_value < max(open_value, close_value)
                or low_value > min(open_value, close_value)
                or high_value < low_value
            ):
                failures.add("invalid_ohlc")
        if dataset.family != "index_bars":
            present = [name for name in _VOLUME_COLUMNS if name in frame.columns]
            if not present:
                failures.add("missing_required_column:volume")
            elif any(
                isinstance(value, int | float) and not isinstance(value, bool) and value < 0
                for name in present
                for value in frame[name].to_list()
            ):
                failures.add("negative_volume")
    elif dataset.family == "premium_bars":
        values("close")
    elif dataset.family == "instrument_catalog":
        values("symbol")
        values("status")
        values("base_coin")
        values("quote_coin")
    elif dataset.family == "market_membership":
        values("symbol")
        values("status")
        values("base_asset")
        values("quote_asset")
        values("contract_type")
        values("contract_size")
    elif dataset.family == "derivative_trades":
        values("trade_id")
        if any(value <= 0 for value in numbers("price")):
            failures.add("invalid_trade_price")
        if any(value <= 0 for value in numbers("size")):
            failures.add("invalid_trade_size")
    elif dataset.family == "derivative_book_snapshots":
        values("side")
        values("level")
        if any(value <= 0 for value in numbers("price")):
            failures.add("invalid_book_price")
        if any(value <= 0 for value in numbers("size")):
            failures.add("invalid_book_size")
    elif dataset.family == "funding":
        if any(abs(value) > 1 for value in numbers("funding_rate")):
            failures.add("funding_rate_out_of_bounds")
    elif dataset.family == "open_interest":
        if any(value < 0 for value in numbers("open_interest")):
            failures.add("negative_open_interest")
    elif dataset.family == "long_short_ratio":
        if any(value <= 0 for value in numbers("long_short_ratio")):
            failures.add("invalid_long_short_ratio")
    elif dataset.family in {"option_quotes", "option_instruments"}:
        if dataset.family == "option_quotes":
            if any(value < 0 for value in numbers("mark_iv")):
                failures.add("negative_implied_volatility")
            if any(value < 0 for value in numbers("open_interest")):
                failures.add("negative_open_interest")
            if "crossed_market" in frame.columns and frame["crossed_market"].any():
                warnings.add("crossed_option_market")
            if "stale_snapshot" in frame.columns and frame["stale_snapshot"].any():
                warnings.add("stale_option_snapshot")
        elif any(value <= 0 for value in numbers("strike_price")):
            failures.add("invalid_option_strike")
    elif dataset.family == "historical_volatility":
        if any(value < 0 for value in numbers("volatility")):
            failures.add("negative_volatility")
    elif dataset.family == "dex_pools":
        reserves = values("reserve_usd")
        volumes = values("h24_volume_usd")
        if any(value is None for value in reserves) or any(
            value <= 0 for value in numbers("reserve_usd")
        ):
            failures.add("invalid_dex_liquidity")
        if any(value < 0 for value in numbers("h24_volume_usd")):
            failures.add("negative_dex_volume")
        if any(isinstance(value, int | float) and 0 < value < 10_000 for value in reserves):
            warnings.add("thin_dex_liquidity")
        for reserve, volume in zip(reserves, volumes, strict=True):
            if (
                isinstance(reserve, int | float)
                and isinstance(volume, int | float)
                and reserve > 0
                and volume / reserve > 100
            ):
                warnings.add("dex_volume_reserve_extreme")
    elif dataset.family == "onchain_catalog":
        values("asset")
        values("metric")
        values("family")
        values("frequency")
    elif dataset.family == "onchain_metrics":
        metric_values = values("value")
        if any(value is None for value in metric_values):
            warnings.add("missing_onchain_value")
        if any(value < 0 for value in numbers("value")):
            failures.add("negative_onchain_value")
    elif dataset.family == "market_reference":
        if "current_price" in frame.columns and frame["current_price"].null_count() > 0:
            warnings.add("missing_reference_price")
    elif dataset.family == "protocol_tvl":
        if any(value < 0 for value in numbers("tvl_usd")):
            failures.add("negative_protocol_tvl")
    elif dataset.family == "stablecoin_supply":
        if any(value < 0 for value in numbers("circulating_supply")):
            failures.add("negative_stablecoin_supply")
    elif dataset.family == "yield_pools":
        values("pool_id")
        values("chain")
        values("project")
        values("symbol")
        if any(value < 0 for value in numbers("tvl_usd")):
            failures.add("negative_yield_tvl")
        numbers("apy")
    elif dataset.family == "yield_history":
        if any(value < 0 for value in numbers("tvl_usd")):
            failures.add("negative_yield_tvl")
        numbers("apy")
    return failures, warnings


def qualify_crypto_frame(
    dataset: CryptoDatasetIdentityV1,
    frame: pl.DataFrame,
    *,
    artifact_sha256: str,
    observed_column: str,
    key_columns: tuple[str, ...],
    knowledge_time: datetime,
    as_of: datetime,
    expected_cadence: timedelta | None = None,
    period_start_timestamps: bool = False,
    availability_column: str | None = None,
    correction_lineage: tuple[str, ...] = (),
    unexplained_revision: bool = False,
) -> CryptoQualityReportV1:
    """Classify exact bytes without repairing, replacing, or dropping observations."""
    knowledge = require_utc(knowledge_time, "knowledge time", prefix="crypto quality")
    cutoff = require_utc(as_of, "as_of", prefix="crypto quality")
    failures: set[str] = set()
    warnings: set[str] = set()
    if frame.is_empty():
        return CryptoQualityReportV1(
            dataset_sha256=artifact_sha256,
            method_version=QUALITY_METHOD_VERSION,
            state="unavailable",
            failures=("empty_dataset",),
            warnings=(),
            observed_start=None,
            observed_end=None,
            row_count=0,
            correction_lineage=correction_lineage,
        )
    missing_keys = [name for name in (observed_column, *key_columns) if name not in frame.columns]
    if missing_keys:
        failures.update(f"missing_required_column:{name}" for name in missing_keys)
        observations: list[datetime] = []
    else:
        observations = _times(frame, observed_column)
        if frame.select(pl.struct(key_columns).is_duplicated().any()).item():
            failures.add("duplicate_observation")
        if any(right < left for left, right in zip(observations, observations[1:], strict=False)):
            failures.add("non_monotonic_time")
        if any(value > min(knowledge, cutoff) for value in observations):
            failures.add("future_observation")
    if knowledge > cutoff:
        failures.add("future_knowledge_time")
    if availability_column is not None:
        availability = _times(frame, availability_column)
        if not availability:
            failures.add(f"missing_required_column:{availability_column}")
        elif any(value > cutoff for value in availability):
            failures.add("future_availability")
    failures.update(_numeric_failures(frame))
    if unexplained_revision:
        if not correction_lineage:
            raise DataError("unexplained crypto revision requires correction lineage")
        failures.add("unexplained_provider_revision")
    if expected_cadence is not None and observations:
        if expected_cadence <= timedelta(0):
            raise DataError("crypto quality cadence must be positive")
        gaps = [right - left for left, right in zip(observations, observations[1:], strict=False)]
        if any(gap != expected_cadence for gap in gaps):
            warnings.add("cadence_gap")
        if period_start_timestamps and observations[-1] + expected_cadence > knowledge:
            failures.add("partial_period")
    family_failures, family_warnings = _family_checks(dataset, frame)
    failures.update(family_failures)
    warnings.update(family_warnings)
    state: QualificationState = (
        "quarantined" if failures else ("warning" if warnings else "qualified")
    )
    return CryptoQualityReportV1(
        dataset_sha256=artifact_sha256,
        method_version=QUALITY_METHOD_VERSION,
        state=state,
        failures=tuple(sorted(failures)),
        warnings=tuple(sorted(warnings)),
        observed_start=min(observations) if observations else None,
        observed_end=max(observations) if observations else None,
        row_count=frame.height,
        correction_lineage=correction_lineage,
    )


__all__ = [
    "QUALITY_METHOD_VERSION",
    "MarketComparisonSummaryV1",
    "compare_market_observations",
    "qualify_crypto_frame",
]


DAILY_BAR_AUDIT_COLUMNS: Final = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "base_volume",
    "close_time",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
)
DAILY_BAR_AUDIT_NUMERIC_COLUMNS: Final = tuple(
    name for name in DAILY_BAR_AUDIT_COLUMNS if name not in {"open_time", "close_time"}
)


def audit_daily_bar_grid(
    dataset: CryptoDatasetIdentityV1,
    frame: pl.DataFrame,
    *,
    artifact_sha256: str,
    start: datetime,
    end: datetime,
    as_of: datetime,
    cadence_seconds: int,
    max_rows: int,
    max_missing_ranges: int,
) -> dict[str, object]:
    """Inspect one explicit daily UTC grid; never repair or requalify retained bars.

    Grid anchor is caller start, not inferred exchange/calendar/source availability.
    Missing slots mean absent observations on that grid, not a provider-history claim.
    Only in-window valid timestamps enter OHLCV/order checks; unplaceable timestamps
    remain a blocking finding. Original order/duplicates are preserved for qualification.
    """
    if not (
        dataset.provider == dataset.venue == "binance"
        and dataset.market_type == "spot"
        and dataset.family == "market_bars"
        and dataset.frequency == "1d"
        and dataset.timestamp_convention == "interval_start_utc"
        and dataset.units == "provider_native_ohlcv"
    ):
        raise DataError("retained bar audit supports only Binance spot daily native OHLCV")
    if type(cadence_seconds) is not int or cadence_seconds != 86400:
        raise DataError("retained daily bar audit cadence must match native 1d identity")
    if any(type(value) is not int or value < 1 for value in (max_rows, max_missing_ranges)):
        raise DataError("retained bar audit limits must be positive")
    if frame.height > max_rows:
        raise DataError("retained bar audit row limit exceeded; no prefix audit")
    if not set(DAILY_BAR_AUDIT_COLUMNS) <= set(frame.columns):
        raise DataError("retained daily bar audit columns are missing")
    for name in ("open_time", "close_time"):
        dtype = frame.schema[name]
        if isinstance(dtype, pl.Datetime) and dtype.time_unit == "ns":
            raise DataError("retained daily bar audit timestamp precision unsupported")
    first = require_utc(start, "audit start")
    final = require_utc(end, "audit end")
    cutoff = require_utc(as_of, "audit as_of")
    step = cadence_seconds * 1_000_000

    def micros(delta: timedelta) -> int:
        return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds

    duration = micros(final - first)
    if duration <= 0 or duration % step or final > cutoff:
        raise DataError("retained daily grid must have whole closed periods before as_of")
    expected = duration // step
    mask: list[bool] = []
    invalid_time = invalid_close_time = outside = off_grid = invalid_numeric = 0
    invalid_count = 0
    slots: set[int] = set()
    groups: dict[datetime, list[tuple[object, ...]]] = {}

    def value_key(value: object) -> object:
        if (
            isinstance(value, datetime)
            and value.tzinfo is not None
            and value.utcoffset() is not None
        ):
            return value.astimezone(UTC)
        if isinstance(value, bool) or not isinstance(value, int | float):
            return (type(value).__name__, repr(value))
        if isinstance(value, float) and not math.isfinite(value):
            return ("nonfinite", repr(value))
        return value

    for row in frame.select(DAILY_BAR_AUDIT_COLUMNS).iter_rows(named=True):
        timestamp = row["open_time"]
        if (
            not isinstance(timestamp, datetime)
            or timestamp.tzinfo is None
            or timestamp.utcoffset() is None
        ):
            invalid_time += 1
            mask.append(False)
            continue
        timestamp = timestamp.astimezone(UTC)
        inside = first <= timestamp < final
        mask.append(inside)
        if not inside:
            outside += 1
            continue
        close_time = row["close_time"]
        if (
            not isinstance(close_time, datetime)
            or close_time.tzinfo is None
            or close_time.utcoffset() is None
            or not timestamp
            <= close_time.astimezone(UTC)
            < timestamp + timedelta(seconds=cadence_seconds)
        ):
            invalid_close_time += 1
        values = tuple(row[name] for name in DAILY_BAR_AUDIT_COLUMNS[1:])
        if any(
            isinstance(row[name], bool)
            or not isinstance(row[name], int | float)
            or not math.isfinite(row[name])
            for name in DAILY_BAR_AUDIT_NUMERIC_COLUMNS
        ):
            invalid_numeric += 1
        count = row["trade_count"]
        if (
            isinstance(count, bool)
            or not isinstance(count, int | float)
            or not math.isfinite(count)
            or count < 0
            or (isinstance(count, float) and not count.is_integer())
        ):
            invalid_count += 1
        groups.setdefault(timestamp, []).append(tuple(value_key(value) for value in values))
        offset = micros(timestamp - first)
        if offset % step:
            off_grid += 1
        else:
            slots.add(offset // step)
    checked = frame.select(DAILY_BAR_AUDIT_COLUMNS).filter(pl.Series(mask, dtype=pl.Boolean))
    mechanical = qualify_crypto_frame(
        dataset,
        checked,
        artifact_sha256=artifact_sha256,
        observed_column="open_time",
        key_columns=("open_time",),
        knowledge_time=cutoff,
        as_of=cutoff,
        expected_cadence=timedelta(seconds=cadence_seconds),
        period_start_timestamps=True,
    )
    failures = set(mechanical.failures)
    if invalid_time:
        failures.add("invalid_or_unplaceable_timestamp")
    if invalid_close_time:
        failures.add("invalid_native_bar_close_time")
    if invalid_numeric:
        failures.add("invalid_required_ohlcv_numeric")
    if invalid_count:
        failures.add("invalid_native_trade_count")
    if off_grid:
        failures.add("off_declared_grid")
    duplicates = [values for values in groups.values() if len(values) > 1]
    conflicts = sum(len(set(values)) > 1 for values in duplicates)
    ranges: list[dict[str, object]] = []
    missing_ranges = 0
    cursor = 0
    # Work scales with observed rows, never the number of missing expected slots.
    for position in [*sorted(slots), expected]:
        if position > cursor:
            missing_ranges += 1
            if len(ranges) < max_missing_ranges:
                ranges.append(
                    {
                        "start": (first + timedelta(microseconds=cursor * step)).isoformat(),
                        "end": (first + timedelta(microseconds=position * step)).isoformat(),
                        "slots": position - cursor,
                    }
                )
        cursor = position + 1
    missing = expected - len(slots)
    return {
        "grid_basis": "caller_declared_start_and_native_daily_cadence",
        "start": first.isoformat(),
        "end_exclusive": final.isoformat(),
        "as_of": cutoff.isoformat(),
        "cadence_seconds": cadence_seconds,
        "expected_slots": expected,
        "covered_slots": len(slots),
        "missing_slots": missing,
        "missing_ranges": ranges,
        "missing_range_count": missing_ranges,
        "missing_ranges_truncated": missing_ranges > len(ranges),
        "row_count": frame.height,
        "in_window_rows": checked.height,
        "outside_window_rows": outside,
        "invalid_timestamp_rows": invalid_time,
        "invalid_close_timestamp_rows": invalid_close_time,
        "off_grid_rows": off_grid,
        "invalid_numeric_rows": invalid_numeric,
        "duplicate_timestamp_groups": len(duplicates),
        "duplicate_extra_rows": sum(len(values) - 1 for values in duplicates),
        "conflicting_duplicate_groups": conflicts,
        "identical_duplicate_groups": len(duplicates) - conflicts,
        "failures": sorted(failures),
        "warnings": list(mechanical.warnings),
        "audited_columns": list(DAILY_BAR_AUDIT_COLUMNS),
        "declared_grid_satisfied": not failures and missing == 0,
        "provider_history_complete": False,
        "point_in_time_eligibility": False,
        "execution_authority": False,
    }

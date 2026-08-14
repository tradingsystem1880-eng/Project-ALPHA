"""Mechanical qualification for provider-native crypto observations."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import polars as pl

from alpha_core import DataError

from .contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1, QualificationState

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


def _comparison_id(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


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
        comparison_id=_comparison_id(identity_body),
        primary_sha256=primary_sha256,
        comparison_sha256=tuple(source_hashes),
        state=state,
        max_abs_divergence_bps=max_abs,
        matched_observations=matched,
        missing_observations=missing,
        warning_bps=float(warning_bps),
        quarantine_bps=float(quarantine_bps),
    )


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DataError(f"crypto quality {label} must be timezone-aware")
    return value.astimezone(UTC)


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
        if (
            dataset.family != "index_bars"
            and "volume" in frame.columns
            and any(value is not None and value < 0 for value in frame["volume"].to_list())
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
    elif dataset.family == "onchain_metrics":
        metric_values = values("value")
        if any(value is None for value in metric_values):
            warnings.add("missing_onchain_value")
        if any(value < 0 for value in numbers("value")):
            failures.add("negative_onchain_value")
    elif dataset.family == "market_reference":
        if "current_price" in frame.columns and frame["current_price"].null_count() > 0:
            warnings.add("missing_reference_price")
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
    knowledge = _utc(knowledge_time, "knowledge time")
    cutoff = _utc(as_of, "as_of")
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

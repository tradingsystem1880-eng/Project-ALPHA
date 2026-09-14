"""Provenance-bound research features derived from qualified crypto inputs."""

from __future__ import annotations

import hashlib
import io
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast

import numpy as np
import polars as pl

from alpha_core import DataError

from .contracts import (
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    content_digest,
    require_utc,
)

type CryptoFeatureName = Literal[
    "funding",
    "basis",
    "open_interest_change",
    "volatility_surface",
    "liquidity",
    "onchain_change",
    "defi_tvl_residual",
]

FEATURE_METHOD_VERSION: Final = "crypto-features-v1"
_FEATURE_NAMES: Final = frozenset(
    {
        "funding",
        "basis",
        "open_interest_change",
        "volatility_surface",
        "liquidity",
        "onchain_change",
        "defi_tvl_residual",
    }
)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


def _utc(value: datetime, label: str) -> datetime:
    return require_utc(value, label, prefix="crypto feature")


@dataclass(frozen=True)
class QualifiedCryptoFrame:
    """One exact frame paired with its identity and mechanical qualification."""

    name: str
    dataset: CryptoDatasetIdentityV1
    artifact_sha256: str
    quality: CryptoQualityReportV1
    frame: pl.DataFrame

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Reverify the mutable frame boundary before every derivation."""
        if not self.name.strip():
            raise DataError("crypto feature input name is invalid")
        if _SHA256.fullmatch(self.artifact_sha256) is None:
            raise DataError("crypto feature input hash is invalid")
        if self.quality.dataset_sha256 != self.artifact_sha256:
            raise DataError("crypto feature input hash does not match its quality report")
        if self.quality.state != "qualified" or self.quality.failures or self.quality.warnings:
            raise DataError("crypto feature requires an exact qualified input")
        if self.frame.is_empty() or self.quality.row_count != self.frame.height:
            raise DataError("crypto feature input row count does not match qualification")


@dataclass(frozen=True)
class CryptoFeatureArtifactV1:
    feature_id: str
    feature_name: CryptoFeatureName
    method_version: str
    input_sha256: tuple[tuple[str, str], ...]
    available_at: datetime
    row_count: int
    artifact_sha256: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if (
            _SHA256.fullmatch(self.feature_id) is None
            or _SHA256.fullmatch(self.artifact_sha256) is None
        ):
            raise DataError("crypto feature artifact hash is invalid")
        if self.feature_name not in _FEATURE_NAMES:
            raise DataError("crypto feature artifact name is invalid")
        if self.method_version != FEATURE_METHOD_VERSION or not self.input_sha256:
            raise DataError("crypto feature artifact provenance is invalid")
        if len({name for name, _ in self.input_sha256}) != len(self.input_sha256) or any(
            not name.strip() or _SHA256.fullmatch(digest) is None
            for name, digest in self.input_sha256
        ):
            raise DataError("crypto feature artifact inputs are invalid")
        object.__setattr__(self, "available_at", _utc(self.available_at, "availability"))
        if self.row_count <= 0:
            raise DataError("crypto feature artifact row count must be positive")
        if self.feature_id != content_digest(self._body()):
            raise DataError("crypto feature artifact identity is invalid")

    def _body(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "feature_name": self.feature_name,
            "method_version": self.method_version,
            "input_sha256": [list(item) for item in self.input_sha256],
            "available_at": self.available_at.isoformat().replace("+00:00", "Z"),
            "row_count": self.row_count,
            "artifact_sha256": self.artifact_sha256,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._body(), "feature_id": self.feature_id}

    @classmethod
    def create(
        cls,
        *,
        feature_name: CryptoFeatureName,
        input_sha256: tuple[tuple[str, str], ...],
        available_at: datetime,
        row_count: int,
        artifact_sha256: str,
    ) -> CryptoFeatureArtifactV1:
        body = {
            "schema_version": 1,
            "feature_name": feature_name,
            "method_version": FEATURE_METHOD_VERSION,
            "input_sha256": [list(item) for item in input_sha256],
            "available_at": _utc(available_at, "availability").isoformat().replace("+00:00", "Z"),
            "row_count": row_count,
            "artifact_sha256": artifact_sha256,
        }
        return cls(
            feature_id=content_digest(body),
            feature_name=feature_name,
            method_version=FEATURE_METHOD_VERSION,
            input_sha256=input_sha256,
            available_at=available_at,
            row_count=row_count,
            artifact_sha256=artifact_sha256,
        )

    @classmethod
    def from_dict(cls, value: object) -> CryptoFeatureArtifactV1:
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "feature_id",
            "feature_name",
            "method_version",
            "input_sha256",
            "available_at",
            "row_count",
            "artifact_sha256",
        }:
            raise DataError("crypto feature artifact is malformed")
        inputs = value.get("input_sha256")
        if (
            value.get("schema_version") != 1
            or not isinstance(inputs, list)
            or any(
                not isinstance(item, list)
                or len(item) != 2
                or any(not isinstance(part, str) for part in item)
                for item in inputs
            )
            or not isinstance(value.get("available_at"), str)
        ):
            raise DataError("crypto feature artifact is malformed")
        try:
            return cls(
                feature_id=cast(str, value["feature_id"]),
                feature_name=cast(CryptoFeatureName, value["feature_name"]),
                method_version=cast(str, value["method_version"]),
                input_sha256=tuple((str(item[0]), str(item[1])) for item in inputs),
                available_at=datetime.fromisoformat(
                    cast(str, value["available_at"]).replace("Z", "+00:00")
                ),
                row_count=cast(int, value["row_count"]),
                artifact_sha256=cast(str, value["artifact_sha256"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataError("crypto feature artifact is malformed") from exc


def feature_frame_bytes(frame: pl.DataFrame) -> bytes:
    """Serialize the exact immutable feature payload used by its artifact hash."""
    if not isinstance(frame, pl.DataFrame) or frame.is_empty():
        raise DataError("crypto feature payload is empty")
    output = io.BytesIO()
    frame.write_parquet(output, compression="zstd", statistics=True)
    return output.getvalue()


def _require_columns(source: QualifiedCryptoFrame, columns: tuple[str, ...]) -> None:
    missing = [column for column in columns if column not in source.frame.columns]
    if missing:
        raise DataError(f"crypto feature input is missing columns: {', '.join(missing)}")


def derive_available_at(sources: tuple[QualifiedCryptoFrame, ...]) -> datetime:
    """Derive availability from the ordered inputs so a feature id is a content address."""
    bounds: list[datetime] = []
    for source in sources:
        observed_end = source.quality.observed_end
        if observed_end is not None:
            bounds.append(_utc(observed_end, "observed end"))
        if "available_at" in source.frame.columns:
            values = source.frame["available_at"].to_list()
            if any(not isinstance(value, datetime) for value in values):
                raise DataError("crypto feature input availability is invalid")
            bounds.extend(_utc(value, "input availability") for value in values)
    if not bounds:
        raise DataError("crypto feature inputs carry no availability evidence")
    return max(bounds)


def _validate_sources(
    sources: tuple[QualifiedCryptoFrame, ...],
    expected_families: tuple[str, ...],
    available_at: datetime,
) -> datetime:
    availability = _utc(available_at, "availability")
    if len(sources) != len(expected_families) or len({source.name for source in sources}) != len(
        sources
    ):
        raise DataError("crypto feature input set is invalid")
    for source, family in zip(sources, expected_families, strict=True):
        source.validate()
        if source.dataset.family != family:
            raise DataError(f"crypto feature requires {family} input")
        observed_end = source.quality.observed_end
        if observed_end is not None and availability < _utc(observed_end, "observed end"):
            raise DataError("crypto feature availability precedes an input observation")
        if "available_at" in source.frame.columns:
            values = source.frame["available_at"].to_list()
            if any(not isinstance(value, datetime) for value in values):
                raise DataError("crypto feature input availability is invalid")
            if values and availability < max(_utc(value, "input availability") for value in values):
                raise DataError("crypto feature availability precedes source availability")
    return availability


def _artifact(
    feature_name: CryptoFeatureName,
    sources: tuple[QualifiedCryptoFrame, ...],
    frame: pl.DataFrame,
    available_at: datetime,
) -> CryptoFeatureArtifactV1:
    input_sha256 = tuple((source.name, source.artifact_sha256) for source in sources)
    artifact_sha256 = hashlib.sha256(feature_frame_bytes(frame)).hexdigest()
    return CryptoFeatureArtifactV1.create(
        feature_name=feature_name,
        input_sha256=input_sha256,
        available_at=available_at,
        row_count=frame.height,
        artifact_sha256=artifact_sha256,
    )


def _require_single_instrument(source: QualifiedCryptoFrame, label: str) -> None:
    """These series accumulate ungrouped, so a multi-instrument frame must never be mixed."""
    if "symbol" in source.frame.columns and source.frame["symbol"].n_unique() > 1:
        raise DataError(f"crypto {label} features require a single instrument")


def funding_features(
    source: QualifiedCryptoFrame, *, available_at: datetime
) -> tuple[pl.DataFrame, CryptoFeatureArtifactV1]:
    availability = _validate_sources((source,), ("funding",), available_at)
    _require_columns(source, ("timestamp", "funding_rate"))
    _require_single_instrument(source, "funding")
    frame = (
        source.frame.select("timestamp", "funding_rate")
        .sort("timestamp")
        .with_columns(
            pl.col("funding_rate").cum_sum().alias("cumulative_funding"),
            pl.col("funding_rate").diff().alias("funding_rate_change"),
            pl.lit(availability).alias("available_at"),
        )
    )
    return frame, _artifact("funding", (source,), frame, availability)


def open_interest_features(
    source: QualifiedCryptoFrame, *, available_at: datetime
) -> tuple[pl.DataFrame, CryptoFeatureArtifactV1]:
    availability = _validate_sources((source,), ("open_interest",), available_at)
    _require_columns(source, ("timestamp", "open_interest"))
    _require_single_instrument(source, "open interest")
    frame = (
        source.frame.select("timestamp", "open_interest")
        .sort("timestamp")
        .with_columns(
            pl.col("open_interest").diff().alias("open_interest_change"),
            # nosemgrep: alpha-negative-shift  (positive lag = prior row; no future row is read)
            pl.when(pl.col("open_interest").shift(1) > 0)
            # nosemgrep: alpha-negative-shift  (positive lag = prior row; no future row is read)
            .then(pl.col("open_interest").diff() / pl.col("open_interest").shift(1))
            .otherwise(None)
            .alias("open_interest_pct_change"),
            pl.lit(availability).alias("available_at"),
        )
    )
    return frame, _artifact("open_interest_change", (source,), frame, availability)


def basis_features(
    mark: QualifiedCryptoFrame,
    index: QualifiedCryptoFrame,
    premium: QualifiedCryptoFrame,
    *,
    available_at: datetime,
) -> tuple[pl.DataFrame, CryptoFeatureArtifactV1]:
    sources = (mark, index, premium)
    availability = _validate_sources(
        sources, ("mark_bars", "index_bars", "premium_bars"), available_at
    )
    keys = ("timestamp", "category", "symbol")
    for source in sources:
        _require_columns(source, (*keys, "close"))
        if source.frame.select(pl.struct(keys).is_duplicated().any()).item():
            raise DataError("crypto basis feature input keys are duplicated")
    frame = mark.frame.select(*keys, pl.col("close").alias("mark_close")).join(
        index.frame.select(*keys, pl.col("close").alias("index_close")),
        on=list(keys),
        how="inner",
        validate="1:1",
    )
    frame = frame.join(
        premium.frame.select(*keys, pl.col("close").alias("reported_premium")),
        on=list(keys),
        how="inner",
        validate="1:1",
    )
    if any(frame.height != source.frame.height for source in sources):
        raise DataError("crypto basis feature inputs are not exactly aligned")
    if any(value <= 0 or not math.isfinite(value) for value in frame["index_close"].to_list()):
        raise DataError("crypto basis feature index values are invalid")
    frame = frame.with_columns(
        (pl.col("mark_close") / pl.col("index_close") - 1).alias("observed_basis")
    ).with_columns(
        (pl.col("observed_basis") - pl.col("reported_premium")).alias("basis_premium_difference"),
        pl.lit(availability).alias("available_at"),
    )
    return frame, _artifact("basis", sources, frame, availability)


def volatility_surface_features(
    quotes: QualifiedCryptoFrame,
    instruments: QualifiedCryptoFrame,
    *,
    available_at: datetime,
) -> tuple[pl.DataFrame, CryptoFeatureArtifactV1]:
    sources = (quotes, instruments)
    availability = _validate_sources(sources, ("option_quotes", "option_instruments"), available_at)
    _require_columns(
        quotes,
        (
            "available_at",
            "symbol",
            "underlying_price",
            "mark_iv",
            "delta",
            "gamma",
            "vega",
            "theta",
            "open_interest",
        ),
    )
    _require_columns(instruments, ("symbol", "delivery_time", "strike_price", "option_kind"))
    if (
        quotes.frame["symbol"].n_unique() != quotes.frame.height
        or instruments.frame["symbol"].n_unique() != instruments.frame.height
    ):
        raise DataError("crypto volatility surface option identities are duplicated")
    frame = quotes.frame.select(
        "available_at",
        "symbol",
        "underlying_price",
        "mark_iv",
        "delta",
        "gamma",
        "vega",
        "theta",
        "open_interest",
    ).join(
        instruments.frame.select("symbol", "delivery_time", "strike_price", "option_kind"),
        on="symbol",
        how="inner",
        validate="1:1",
    )
    if frame.height != quotes.frame.height:
        raise DataError("crypto volatility surface has unmatched option identities")
    if any(
        value is None or value <= 0 or not math.isfinite(value)
        for value in frame["underlying_price"].to_list()
    ):
        raise DataError("crypto volatility surface underlying prices are invalid")
    frame = frame.with_columns(
        (pl.col("strike_price") / pl.col("underlying_price")).alias("moneyness"),
        (
            (pl.col("delivery_time") - pl.col("available_at")).dt.total_seconds()
            / (365.25 * 24 * 60 * 60)
        ).alias("time_to_expiry_years"),
    )
    if any(value <= 0 for value in frame["time_to_expiry_years"].to_list()):
        raise DataError("crypto volatility surface contains an expired option")
    return frame, _artifact("volatility_surface", sources, frame, availability)


def liquidity_features(
    source: QualifiedCryptoFrame, *, available_at: datetime
) -> tuple[pl.DataFrame, CryptoFeatureArtifactV1]:
    availability = _validate_sources((source,), ("dex_pools",), available_at)
    columns = (
        "network",
        "pool_address",
        "reserve_usd",
        "h24_volume_usd",
        "h24_buys",
        "h24_sells",
    )
    _require_columns(source, columns)
    if any(reserve is None or reserve <= 0 for reserve in source.frame["reserve_usd"].to_list()):
        raise DataError("crypto liquidity feature reserve is invalid")
    frame = source.frame.select(*columns).with_columns(
        (pl.col("h24_volume_usd") / pl.col("reserve_usd")).alias("turnover_to_reserve"),
        pl.when((pl.col("h24_buys") + pl.col("h24_sells")) > 0)
        .then(
            (pl.col("h24_buys") - pl.col("h24_sells")) / (pl.col("h24_buys") + pl.col("h24_sells"))
        )
        .otherwise(None)
        .alias("buy_sell_imbalance"),
        pl.lit(availability).alias("available_at"),
    )
    return frame, _artifact("liquidity", (source,), frame, availability)


def onchain_features(
    source: QualifiedCryptoFrame, *, available_at: datetime
) -> tuple[pl.DataFrame, CryptoFeatureArtifactV1]:
    availability = _validate_sources((source,), ("onchain_metrics",), available_at)
    columns = ("asset", "timestamp", "metric", "family", "value")
    _require_columns(source, columns)
    frame = (
        source.frame.select(*columns)
        .sort("asset", "metric", "timestamp")
        .with_columns(
            pl.col("value").diff().over("asset", "metric").alias("value_change"),
            # nosemgrep: alpha-negative-shift  (positive lag = prior row; no future row is read)
            pl.when(pl.col("value").shift(1).over("asset", "metric") > 0)
            .then(
                pl.col("value").diff().over("asset", "metric")
                # nosemgrep: alpha-negative-shift  (positive lag = prior row; no future row is read)
                / pl.col("value").shift(1).over("asset", "metric")
            )
            .otherwise(None)
            .alias("value_pct_change"),
            pl.lit(availability).alias("available_at"),
        )
    )
    return frame, _artifact("onchain_change", (source,), frame, availability)


def _trailing_log_ols_prediction(x: np.ndarray, y: np.ndarray, window: int) -> np.ndarray:
    """Prediction of ``y[i]`` from the OLS line fitted on ``[i-window+1, i]``; NaN before that.

    A trailing-window ordinary least squares in numpy: ``alpha_data`` may not import
    ``alpha_patterns.vsa.rolling_ols_residual`` (import-linter: data depends on core only), so the
    same closed form lives here and is pinned equal to it by a unit test. Any NaN in the window
    yields NaN.
    """
    n = x.size
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        xs = x[i - window + 1 : i + 1]
        ys = y[i - window + 1 : i + 1]
        if not (np.all(np.isfinite(xs)) and np.all(np.isfinite(ys))):
            continue
        x_mean = xs.mean()
        var = float(np.sum((xs - x_mean) ** 2))
        if var <= 0.0:
            continue
        slope = float(np.sum((xs - x_mean) * (ys - ys.mean()))) / var
        out[i] = ys.mean() + slope * (x[i] - x_mean)
    return out


def defi_tvl_residual_features(
    tvl: QualifiedCryptoFrame,
    market: QualifiedCryptoFrame,
    *,
    available_at: datetime,
    window: int = 60,
    atr_window: int = 14,
) -> tuple[pl.DataFrame, CryptoFeatureArtifactV1]:
    """TVL residual (ADR-0036; ported from neurotrader888/TVLIndicator, provenance doc).

    Daily market bars are joined to the chain's TVL by UTC day; the TVL used on day ``t`` is the
    day ``t - 1`` value because a day's TVL is only available after that day closes (upstream uses
    the same-day value — a recorded deviation). A trailing ``window``-day OLS of log close on log
    lagged TVL predicts the close; ``tvl_residual`` is ``(close - predicted) / ATR`` with a
    ``atr_window`` simple-mean true range. NaN until both windows are full.
    """
    if window < 3 or atr_window < 1:
        raise DataError("defi_tvl_residual windows must be >= 3 (ols) and >= 1 (atr)")
    sources = (tvl, market)
    availability = _validate_sources(sources, ("defi_tvl", "market_bars"), available_at)
    _require_columns(tvl, ("chain", "observed_at", "tvl_usd"))
    _require_columns(market, ("timestamp", "open", "high", "low", "close"))
    if tvl.frame["chain"].n_unique() != 1:
        raise DataError("defi_tvl_residual requires exactly one chain")
    days = (
        tvl.frame.select("chain", "observed_at", "tvl_usd")
        .sort("observed_at")
        .with_columns(pl.col("observed_at").dt.truncate("1d").alias("day"))
    )
    bars = (
        market.frame.select("timestamp", "open", "high", "low", "close")
        .sort("timestamp")
        .with_columns(pl.col("timestamp").dt.truncate("1d").alias("day"))
    )
    for frame, label in ((days, "tvl"), (bars, "market")):
        if frame["day"].is_duplicated().any():
            raise DataError(f"defi_tvl_residual {label} input has more than one row per day")
    joined = bars.join(days.drop("observed_at"), on="day", how="inner", validate="1:1").sort("day")
    if joined.height < window + 1:
        raise DataError("defi_tvl_residual needs more aligned days than the OLS window")
    close = joined["close"].to_numpy().astype(np.float64)
    high = joined["high"].to_numpy().astype(np.float64)
    low = joined["low"].to_numpy().astype(np.float64)
    tvl_lag = np.concatenate(([np.nan], joined["tvl_usd"].to_numpy().astype(np.float64)[:-1]))
    if np.any(close <= 0.0) or np.any(tvl_lag[1:] <= 0.0):
        raise DataError("defi_tvl_residual requires positive close and TVL values")
    predicted_log = _trailing_log_ols_prediction(np.log(tvl_lag), np.log(close), window)
    prev_close = np.concatenate(([np.nan], close[:-1]))
    true_range = np.maximum.reduce(
        [high - low, np.abs(high - prev_close), np.abs(low - prev_close)]
    )
    atr = np.full(close.size, np.nan)
    for i in range(atr_window, close.size):  # true range needs a previous close: start at 1
        atr[i] = float(np.mean(true_range[i - atr_window + 1 : i + 1]))
    residual = (close - np.exp(predicted_log)) / atr
    frame = joined.select("chain", "timestamp", "close").with_columns(
        pl.Series("tvl_usd_lag1", tvl_lag, dtype=pl.Float64),
        pl.Series("predicted_close", np.exp(predicted_log), dtype=pl.Float64),
        pl.Series("atr", atr, dtype=pl.Float64),
        pl.Series("tvl_residual", residual, dtype=pl.Float64),
        pl.lit(availability).alias("available_at"),
    )
    return frame, _artifact("defi_tvl_residual", sources, frame, availability)


__all__ = [
    "FEATURE_METHOD_VERSION",
    "CryptoFeatureArtifactV1",
    "QualifiedCryptoFrame",
    "basis_features",
    "feature_frame_bytes",
    "funding_features",
    "liquidity_features",
    "defi_tvl_residual_features",
    "onchain_features",
    "open_interest_features",
    "volatility_surface_features",
]

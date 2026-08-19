"""Provenance-bound research features derived from qualified crypto inputs."""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal, cast

import polars as pl

from alpha_core import DataError

from .contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1

type CryptoFeatureName = Literal[
    "funding",
    "basis",
    "open_interest_change",
    "volatility_surface",
    "liquidity",
    "onchain_change",
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
    }
)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DataError(f"crypto feature {label} must be timezone-aware")
    return value.astimezone(UTC)


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


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
        if self.feature_id != _digest(self._body()):
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
            feature_id=_digest(body),
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


__all__ = [
    "FEATURE_METHOD_VERSION",
    "CryptoFeatureArtifactV1",
    "QualifiedCryptoFrame",
    "basis_features",
    "feature_frame_bytes",
    "funding_features",
    "liquidity_features",
    "onchain_features",
    "open_interest_features",
    "volatility_surface_features",
]

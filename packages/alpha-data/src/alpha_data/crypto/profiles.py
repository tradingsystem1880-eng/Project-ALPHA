"""Deterministic provider-native acquisition profiles from frozen catalogs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import polars as pl

from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoFamily
from alpha_data.crypto.providers.geckoterminal import NETWORKS

type CoverageCadence = Literal["daily", "hourly", "five_minute", "funding_interval"]


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


@dataclass(frozen=True)
class CryptoCoverageTaskV1:
    provider: str
    family: CryptoFamily
    instrument: str
    base_asset: str | None
    quote_asset: str | None
    category: str | None
    frequency: str
    cadence: CoverageCadence
    network: str | None = None
    metrics: tuple[str, ...] = ()
    lookback_days: int | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.provider, "provider"),
            (self.family, "family"),
            (self.instrument, "instrument"),
            (self.frequency, "frequency"),
            (self.cadence, "cadence"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise DataError(f"crypto coverage task {label} is invalid")
        if self.lookback_days is not None and not 1 <= self.lookback_days <= 3_650:
            raise DataError("crypto coverage task lookback is invalid")
        if any(not metric.strip() for metric in self.metrics):
            raise DataError("crypto coverage task metric is invalid")

    @property
    def task_id(self) -> str:
        return hashlib.sha256(_canonical(self._identity())).hexdigest()

    @property
    def execution_authority(self) -> bool:
        return False

    def _identity(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "provider": self.provider,
            "family": self.family,
            "instrument": self.instrument,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "category": self.category,
            "frequency": self.frequency,
            "cadence": self.cadence,
            "network": self.network,
            "metrics": list(self.metrics),
            "lookback_days": self.lookback_days,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._identity(),
            "task_id": self.task_id,
            "execution_authority": False,
        }


_PERPETUAL_COLUMNS = frozenset(
    {
        "status",
        "contract_type",
        "symbol",
        "base_coin",
        "quote_coin",
        "launch_time",
        "delivery_time",
    }
)
_OPTION_COLUMNS = frozenset(
    {"status", "symbol", "base_coin", "quote_coin", "launch_time", "delivery_time"}
)


def _active_perpetuals(
    frame: pl.DataFrame, *, category: Literal["linear", "inverse"], as_of: datetime
) -> tuple[tuple[str, str, str, str], ...]:
    if not _PERPETUAL_COLUMNS.issubset(frame.columns):
        raise DataError("Bybit perpetual catalog schema is incomplete")
    expected_type = "LinearPerpetual" if category == "linear" else "InversePerpetual"
    selected = frame.filter(
        (pl.col("status") == "Trading")
        & (pl.col("contract_type") == expected_type)
        & (pl.col("launch_time") <= as_of)
        & (pl.col("delivery_time").is_null() | (pl.col("delivery_time") > as_of))
    ).select("symbol", "base_coin", "quote_coin")
    rows: list[tuple[str, str, str, str]] = []
    for row in selected.sort("symbol").iter_rows(named=True):
        symbol, base, quote = row["symbol"], row["base_coin"], row["quote_coin"]
        if not all(isinstance(value, str) and value for value in (symbol, base, quote)):
            raise DataError("Bybit perpetual catalog identity is invalid")
        rows.append((str(symbol), str(base), str(quote), category))
    return tuple(rows)


def _active_option_markets(frame: pl.DataFrame, *, as_of: datetime) -> tuple[tuple[str, str], ...]:
    if not _OPTION_COLUMNS.issubset(frame.columns):
        raise DataError("Bybit option catalog schema is incomplete")
    selected = frame.filter(
        (pl.col("status") == "Trading")
        & (pl.col("launch_time") <= as_of)
        & (pl.col("delivery_time").is_null() | (pl.col("delivery_time") > as_of))
    ).select("base_coin", "quote_coin")
    markets: set[tuple[str, str]] = set()
    for base, quote in selected.iter_rows():
        if not isinstance(base, str) or not base or not isinstance(quote, str) or not quote:
            raise DataError("Bybit option catalog identity is invalid")
        markets.add((base, quote))
    return tuple(sorted(markets))


def _task(
    provider: str,
    family: CryptoFamily,
    instrument: str,
    *,
    base: str | None,
    quote: str | None,
    category: str | None,
    frequency: str,
    cadence: CoverageCadence,
    network: str | None = None,
    metrics: tuple[str, ...] = (),
    lookback_days: int | None = None,
) -> CryptoCoverageTaskV1:
    return CryptoCoverageTaskV1(
        provider=provider,
        family=family,
        instrument=instrument,
        base_asset=base,
        quote_asset=quote,
        category=category,
        frequency=frequency,
        cadence=cadence,
        network=network,
        metrics=metrics,
        lookback_days=lookback_days,
    )


def build_default_coverage_tasks(
    *,
    linear_catalog: pl.DataFrame,
    inverse_catalog: pl.DataFrame,
    option_catalog: pl.DataFrame,
    option_open_interest: dict[tuple[str, str], float],
    as_of: datetime,
) -> tuple[CryptoCoverageTaskV1, ...]:
    """Build the fixed public-data profile without fetching or granting authority."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise DataError("crypto coverage profile as_of must be timezone-aware")
    as_of = as_of.astimezone(UTC)
    tasks: list[CryptoCoverageTaskV1] = [
        _task(
            "coingecko",
            "asset_metadata",
            "all",
            base=None,
            quote=None,
            category=None,
            frequency="catalog_snapshot",
            cadence="daily",
        ),
        _task(
            "coingecko",
            "market_reference",
            "all",
            base=None,
            quote="USD",
            category=None,
            frequency="point_in_time_reference",
            cadence="daily",
        ),
    ]
    tasks.extend(
        _task(
            "geckoterminal",
            "dex_pools",
            network,
            base=None,
            quote="USD",
            category=None,
            frequency="daily_catalog",
            cadence="daily",
            network=network,
        )
        for network in sorted(NETWORKS)
    )
    reviewed_metrics = ("AdrActCnt", "FeeTotNtv", "HashRate", "PriceUSD", "SplyCur", "TxCnt")
    tasks.extend(
        _task(
            "coinmetrics",
            "onchain_metrics",
            asset.lower(),
            base=asset,
            quote=None,
            category=None,
            frequency="1d",
            cadence="daily",
            metrics=reviewed_metrics,
            lookback_days=30,
        )
        for asset in ("BTC", "ETH")
    )
    tasks.extend(
        _task(
            "bybit",
            "instrument_catalog",
            category,
            base=None,
            quote=None,
            category=category,
            frequency="catalog_snapshot",
            cadence="daily",
        )
        for category in ("spot", "linear", "inverse", "option")
    )

    perpetuals = (
        *_active_perpetuals(linear_catalog, category="linear", as_of=as_of),
        *_active_perpetuals(inverse_catalog, category="inverse", as_of=as_of),
    )
    families: tuple[tuple[CryptoFamily, str, CoverageCadence], ...] = (
        ("funding", "1h", "funding_interval"),
        ("open_interest", "1h", "hourly"),
        ("long_short_ratio", "1h", "hourly"),
        ("derivative_bars", "1h", "hourly"),
        ("mark_bars", "1h", "hourly"),
        ("index_bars", "1h", "hourly"),
        ("premium_bars", "1h", "hourly"),
    )
    for symbol, base, quote, category in perpetuals:
        tasks.extend(
            _task(
                "bybit",
                family,
                symbol,
                base=base,
                quote=quote,
                category=category,
                frequency=frequency,
                cadence=cadence,
            )
            for family, frequency, cadence in families
        )

    option_markets = _active_option_markets(option_catalog, as_of=as_of)
    for base, quote in option_markets:
        instrument = f"{base}-OPTIONS"
        tasks.extend(
            (
                _task(
                    "bybit",
                    "option_instruments",
                    instrument,
                    base=base,
                    quote=quote,
                    category="option",
                    frequency="catalog_snapshot",
                    cadence="daily",
                ),
                _task(
                    "bybit",
                    "option_quotes",
                    instrument,
                    base=base,
                    quote=quote,
                    category="option",
                    frequency="point_in_time_chain",
                    cadence="hourly",
                ),
                _task(
                    "bybit",
                    "historical_volatility",
                    instrument,
                    base=base,
                    quote=quote,
                    category="option",
                    frequency="1h",
                    cadence="hourly",
                ),
            )
        )
    ranked = sorted(
        (
            (float(option_open_interest.get(market, 0.0)), market)
            for market in option_markets
            if float(option_open_interest.get(market, 0.0)) > 0
        ),
        key=lambda item: (-item[0], item[1]),
    )[:3]
    tasks.extend(
        _task(
            "bybit",
            "option_quotes",
            f"{base}-OPTIONS",
            base=base,
            quote=quote,
            category="option",
            frequency="point_in_time_chain",
            cadence="five_minute",
        )
        for _, (base, quote) in ranked
    )
    if len({task.task_id for task in tasks}) != len(tasks):
        raise DataError("crypto coverage profile contains duplicate tasks")
    return tuple(tasks)


__all__ = ["CryptoCoverageTaskV1", "CoverageCadence", "build_default_coverage_tasks"]

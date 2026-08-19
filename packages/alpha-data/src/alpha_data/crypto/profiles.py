"""Deterministic provider-native acquisition profiles from frozen catalogs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

import polars as pl

from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoFamily
from alpha_data.crypto.providers.geckoterminal import NETWORKS

type CoverageCadence = Literal["daily", "hourly", "five_minute", "funding_interval"]

_PROVIDERS = frozenset({"binance", "bybit", "coingecko", "geckoterminal", "coinmetrics"})
_CADENCES = frozenset({"daily", "hourly", "five_minute", "funding_interval"})
_FAMILIES = frozenset(
    {
        "instrument_catalog",
        "market_membership",
        "market_bars",
        "derivative_bars",
        "funding",
        "open_interest",
        "long_short_ratio",
        "mark_bars",
        "index_bars",
        "premium_bars",
        "option_instruments",
        "option_quotes",
        "historical_volatility",
        "asset_metadata",
        "market_reference",
        "onchain_catalog",
        "onchain_metrics",
        "dex_pools",
    }
)


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
        if self.provider not in _PROVIDERS or self.family not in _FAMILIES:
            raise DataError("crypto coverage task provider or family is unsupported")
        if self.cadence not in _CADENCES:
            raise DataError("crypto coverage task cadence is unsupported")
        for optional_value, label in (
            (self.base_asset, "base asset"),
            (self.quote_asset, "quote asset"),
            (self.category, "category"),
            (self.network, "network"),
        ):
            if optional_value is not None and (
                not isinstance(optional_value, str) or not optional_value.strip()
            ):
                raise DataError(f"crypto coverage task {label} is invalid")
        if self.lookback_days is not None and (
            not isinstance(self.lookback_days, int)
            or isinstance(self.lookback_days, bool)
            or not 1 <= self.lookback_days <= 3_650
        ):
            raise DataError("crypto coverage task lookback is invalid")
        if not isinstance(self.metrics, tuple) or any(
            not isinstance(metric, str) or not metric.strip() for metric in self.metrics
        ):
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

    @classmethod
    def from_dict(cls, value: object) -> CryptoCoverageTaskV1:
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise DataError("crypto coverage task has an unsupported schema")
        expected = {
            "schema_version",
            "provider",
            "family",
            "instrument",
            "base_asset",
            "quote_asset",
            "category",
            "frequency",
            "cadence",
            "network",
            "metrics",
            "lookback_days",
            "task_id",
            "execution_authority",
        }
        if set(value) != expected or not isinstance(value.get("metrics"), list):
            raise DataError("crypto coverage task is malformed")
        try:
            task = cls(
                provider=cast(str, value["provider"]),
                family=cast(CryptoFamily, value["family"]),
                instrument=cast(str, value["instrument"]),
                base_asset=cast(str | None, value["base_asset"]),
                quote_asset=cast(str | None, value["quote_asset"]),
                category=cast(str | None, value["category"]),
                frequency=cast(str, value["frequency"]),
                cadence=cast(CoverageCadence, value["cadence"]),
                network=cast(str | None, value["network"]),
                metrics=tuple(cast(list[str], value["metrics"])),
                lookback_days=cast(int | None, value["lookback_days"]),
            )
        except (KeyError, TypeError) as exc:
            raise DataError("crypto coverage task is malformed") from exc
        if value.get("task_id") != task.task_id or value.get("execution_authority") is not False:
            raise DataError("crypto coverage task identity is invalid")
        return task


@dataclass(frozen=True)
class CryptoCoverageProfileV1:
    profile_id: str
    as_of: datetime
    source_manifest_ids: tuple[str, ...]
    tasks: tuple[CryptoCoverageTaskV1, ...]

    @classmethod
    def create(
        cls,
        *,
        as_of: datetime,
        source_manifest_ids: tuple[str, ...],
        tasks: tuple[CryptoCoverageTaskV1, ...],
    ) -> CryptoCoverageProfileV1:
        if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
            raise DataError("crypto coverage profile as_of must be timezone-aware")
        normalized_at = as_of.astimezone(UTC)
        if (
            not isinstance(source_manifest_ids, tuple)
            or not source_manifest_ids
            or len(set(source_manifest_ids)) != len(source_manifest_ids)
            or any(
                not isinstance(manifest_id, str)
                or len(manifest_id) != 64
                or any(character not in "0123456789abcdef" for character in manifest_id)
                for manifest_id in source_manifest_ids
            )
        ):
            raise DataError("crypto coverage profile source membership is invalid")
        if (
            not isinstance(tasks, tuple)
            or not tasks
            or len(tasks) > 10_000
            or any(not isinstance(task, CryptoCoverageTaskV1) for task in tasks)
            or len({task.task_id for task in tasks}) != len(tasks)
        ):
            raise DataError("crypto coverage profile task membership is invalid")
        body = cls._body(normalized_at, source_manifest_ids, tasks)
        return cls(
            profile_id=hashlib.sha256(_canonical(body)).hexdigest(),
            as_of=normalized_at,
            source_manifest_ids=source_manifest_ids,
            tasks=tasks,
        )

    @staticmethod
    def _body(
        as_of: datetime,
        source_manifest_ids: tuple[str, ...],
        tasks: tuple[CryptoCoverageTaskV1, ...],
    ) -> dict[str, object]:
        return {
            "schema_version": 1,
            "as_of": as_of.isoformat().replace("+00:00", "Z"),
            "source_manifest_ids": list(source_manifest_ids),
            "tasks": [task.to_dict() for task in tasks],
            "execution_authority": False,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._body(self.as_of, self.source_manifest_ids, self.tasks),
            "profile_id": self.profile_id,
        }

    @classmethod
    def from_dict(cls, value: object) -> CryptoCoverageProfileV1:
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise DataError("crypto coverage profile has an unsupported schema")
        expected = {
            "schema_version",
            "as_of",
            "source_manifest_ids",
            "tasks",
            "execution_authority",
            "profile_id",
        }
        if (
            set(value) != expected
            or not isinstance(value.get("as_of"), str)
            or not isinstance(value.get("source_manifest_ids"), list)
            or not isinstance(value.get("tasks"), list)
        ):
            raise DataError("crypto coverage profile is malformed")
        try:
            as_of = datetime.fromisoformat(cast(str, value["as_of"]).replace("Z", "+00:00"))
            sources = tuple(cast(list[str], value["source_manifest_ids"]))
            tasks = tuple(
                CryptoCoverageTaskV1.from_dict(item) for item in cast(list[object], value["tasks"])
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataError("crypto coverage profile is malformed") from exc
        profile = cls.create(as_of=as_of, source_manifest_ids=sources, tasks=tasks)
        if (
            value.get("profile_id") != profile.profile_id
            or value.get("execution_authority") is not False
        ):
            raise DataError("crypto coverage profile identity is invalid")
        return profile


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


def active_option_markets(frame: pl.DataFrame, *, as_of: datetime) -> tuple[tuple[str, str], ...]:
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


def active_binance_markets(
    frames: tuple[pl.DataFrame, ...], *, as_of: datetime
) -> tuple[tuple[str, str, str, str], ...]:
    """Return exact active spot/perpetual identities from all three venue catalogs."""
    required = frozenset(
        {
            "fetched_at",
            "category",
            "symbol",
            "status",
            "contract_type",
            "base_asset",
            "quote_asset",
            "onboard_time",
            "delivery_time",
            "contract_size",
        }
    )
    if len(frames) != 3 or any(not required.issubset(frame.columns) for frame in frames):
        raise DataError("Binance market-membership source coverage is incomplete")
    as_of = as_of.astimezone(UTC)
    rows: list[tuple[str, str, str, str]] = []
    seen_categories: set[str] = set()
    for frame in frames:
        categories = set(frame["category"].to_list())
        if len(categories) != 1 or not categories <= {"spot", "linear", "inverse"}:
            raise DataError("Binance market-membership category is invalid")
        category = str(next(iter(categories)))
        if category in seen_categories:
            raise DataError("Binance market-membership category is duplicated")
        seen_categories.add(category)
        selected = frame.filter(
            (pl.col("fetched_at") <= as_of)
            & (pl.col("status") == "TRADING")
            & (
                (pl.col("contract_type") == "SPOT")
                if category == "spot"
                else (pl.col("contract_type") == "PERPETUAL")
            )
            & (pl.col("onboard_time").is_null() | (pl.col("onboard_time") <= as_of))
            & (pl.col("delivery_time").is_null() | (pl.col("delivery_time") > as_of))
        )
        for symbol, base, quote in selected.select(
            "symbol", "base_asset", "quote_asset"
        ).iter_rows():
            if not all(isinstance(value, str) and value for value in (symbol, base, quote)):
                raise DataError("Binance market-membership identity is invalid")
            rows.append((str(symbol), str(base), str(quote), category))
    if seen_categories != {"spot", "linear", "inverse"} or not rows:
        raise DataError("Binance market-membership source coverage is incomplete")
    ordered = tuple(sorted(rows, key=lambda item: (item[3], item[0])))
    if len({(category, symbol) for symbol, _base, _quote, category in ordered}) != len(ordered):
        raise DataError("Binance market-membership identity is duplicated")
    return ordered


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


def _reference_tasks(
    coinmetrics_catalog: pl.DataFrame, *, as_of: datetime
) -> list[CryptoCoverageTaskV1]:
    tasks = [
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
    required_columns = {"asset", "metric", "family", "frequency", "fetched_at"}
    if not required_columns.issubset(coinmetrics_catalog.columns):
        raise DataError("Coin Metrics Community catalog schema is incomplete")
    tasks.append(
        _task(
            "coinmetrics",
            "onchain_catalog",
            "community",
            base=None,
            quote=None,
            category=None,
            frequency="catalog_snapshot",
            cadence="daily",
        )
    )
    for asset in ("BTC", "ETH"):
        available = coinmetrics_catalog.filter(
            (pl.col("asset") == asset.lower())
            & (pl.col("frequency") == "1d")
            & (pl.col("fetched_at") <= as_of)
        )
        metrics = tuple(sorted(set(str(value) for value in available["metric"].to_list())))
        if not metrics:
            raise DataError(f"Coin Metrics Community catalog has no daily {asset} metrics")
        tasks.append(
            _task(
                "coinmetrics",
                "onchain_metrics",
                asset.lower(),
                base=asset,
                quote=None,
                category=None,
                frequency="1d",
                cadence="daily",
                metrics=metrics,
                lookback_days=30,
            )
        )
    return tasks


def _binance_tasks(
    memberships: tuple[pl.DataFrame, ...],
    hourly_memberships: tuple[pl.DataFrame, ...],
    *,
    as_of: datetime,
) -> list[CryptoCoverageTaskV1]:
    if not memberships:
        return []
    active = active_binance_markets(memberships, as_of=as_of)
    tasks = [
        _task(
            "binance",
            "market_membership",
            category,
            base=None,
            quote=None,
            category=category,
            frequency="catalog_snapshot",
            cadence="daily",
        )
        for category in ("spot", "linear", "inverse")
    ]
    tasks.extend(
        _task(
            "binance",
            "market_bars",
            symbol,
            base=base,
            quote=quote,
            category=category,
            frequency="1d",
            cadence="daily",
        )
        for symbol, base, quote, category in active
    )
    active_ids = set(active)
    seen_scopes: set[tuple[str, str]] = set()
    required_columns = {
        "session",
        "rank",
        "category",
        "symbol",
        "base_asset",
        "quote_asset",
        "liquidity_score",
        "liquidity_units",
    }
    for membership in hourly_memberships:
        if not required_columns.issubset(membership.columns) or not 1 <= membership.height <= 250:
            raise DataError("Binance hourly membership schema is invalid")
        categories = set(membership["category"].to_list())
        quotes = set(membership["quote_asset"].to_list())
        if len(categories) != 1 or len(quotes) != 1:
            raise DataError("Binance hourly membership mixes unit scopes")
        scope = (str(next(iter(categories))), str(next(iter(quotes))))
        if scope in seen_scopes:
            raise DataError("Binance hourly membership scope is duplicated")
        seen_scopes.add(scope)
        if membership["rank"].to_list() != list(range(1, membership.height + 1)):
            raise DataError("Binance hourly membership ranks are invalid")
        sessions = membership["session"].to_list()
        if len(set(sessions)) != 1 or any(
            not isinstance(session, datetime) or session >= as_of for session in sessions
        ):
            raise DataError("Binance hourly membership session is not point-in-time")
        for row in membership.iter_rows(named=True):
            identity = (
                str(row["symbol"]),
                str(row["base_asset"]),
                str(row["quote_asset"]),
                str(row["category"]),
            )
            if identity not in active_ids:
                raise DataError("Binance hourly membership is outside active venue membership")
            tasks.append(
                _task(
                    "binance",
                    "market_bars",
                    identity[0],
                    base=identity[1],
                    quote=identity[2],
                    category=identity[3],
                    frequency="1h",
                    cadence="hourly",
                )
            )
    return tasks


def _bybit_perpetual_tasks(
    linear_catalog: pl.DataFrame, inverse_catalog: pl.DataFrame, *, as_of: datetime
) -> list[CryptoCoverageTaskV1]:
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
    return [
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
        for symbol, base, quote, category in perpetuals
        for family, frequency, cadence in families
    ]


def _bybit_option_tasks(
    option_catalog: pl.DataFrame,
    option_open_interest: dict[tuple[str, str], float],
    *,
    as_of: datetime,
) -> list[CryptoCoverageTaskV1]:
    markets = active_option_markets(option_catalog, as_of=as_of)
    if set(option_open_interest) != set(markets) or any(
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not 0 <= float(value) < float("inf")
        for value in option_open_interest.values()
    ):
        raise DataError("Bybit option open-interest coverage is incomplete")
    tasks: list[CryptoCoverageTaskV1] = []
    for base, quote in markets:
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
            for market in markets
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
    return tasks


def build_default_coverage_tasks(
    *,
    linear_catalog: pl.DataFrame,
    inverse_catalog: pl.DataFrame,
    option_catalog: pl.DataFrame,
    option_open_interest: dict[tuple[str, str], float],
    coinmetrics_catalog: pl.DataFrame,
    as_of: datetime,
    binance_memberships: tuple[pl.DataFrame, ...] = (),
    binance_hourly_memberships: tuple[pl.DataFrame, ...] = (),
) -> tuple[CryptoCoverageTaskV1, ...]:
    """Build the fixed public-data profile without fetching or granting authority."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise DataError("crypto coverage profile as_of must be timezone-aware")
    as_of = as_of.astimezone(UTC)
    tasks = _reference_tasks(coinmetrics_catalog, as_of=as_of)
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
    tasks.extend(
        _binance_tasks(
            binance_memberships,
            binance_hourly_memberships,
            as_of=as_of,
        )
    )
    tasks.extend(
        _bybit_perpetual_tasks(
            linear_catalog,
            inverse_catalog,
            as_of=as_of,
        )
    )
    tasks.extend(
        _bybit_option_tasks(
            option_catalog,
            option_open_interest,
            as_of=as_of,
        )
    )
    if len({task.task_id for task in tasks}) != len(tasks):
        raise DataError("crypto coverage profile contains duplicate tasks")
    return tuple(tasks)


__all__ = [
    "CryptoCoverageProfileV1",
    "CryptoCoverageTaskV1",
    "CoverageCadence",
    "active_binance_markets",
    "active_option_markets",
    "build_default_coverage_tasks",
]

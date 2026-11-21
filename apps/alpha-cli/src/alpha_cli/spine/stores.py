"""Frequency inference and single-source asset resolution for the command spine."""

from __future__ import annotations

import json
import tomllib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median

from alpha_core import DataError
from alpha_data.store import ParquetStore
from alpha_data.timeframe import DAILY, BarTimeframe, parse_timeframe, store_dir


def annualisation(
    timestamps: Sequence[datetime], bar_size: BarTimeframe | None = None
) -> tuple[int, str]:
    """Periods per year and a short note on how it was derived.

    Intraday: median bars per trading date times 252, or 365 when at least a fifth of the
    distinct bar dates (UTC) fall on a weekend; weekend dates are then left out of the median
    only for non-weekend instruments. Daily: elapsed calendar years, snapped to 252 or 365.
    """
    if len(timestamps) < 30:
        raise ValueError("periods_per_year requires at least 30 bars")
    if any(right <= left for left, right in zip(timestamps, timestamps[1:], strict=False)):
        raise ValueError("periods_per_year requires strictly increasing timestamps")
    intraday = (
        not bar_size.is_daily
        if bar_size is not None
        else median(
            (right - left).total_seconds()
            for left, right in zip(timestamps, timestamps[1:], strict=False)
        )
        < 86400
    )
    counts = Counter(stamp.date() for stamp in timestamps)
    weekend = sum(day.weekday() >= 5 for day in counts) / len(counts)
    if intraday:
        trades_weekends = weekend >= 0.2
        days = 365 if trades_weekends else 252
        per_day = median(n for day, n in counts.items() if trades_weekends or day.weekday() < 5)
        basis = (
            f"median {per_day:g} bars per {'date' if trades_weekends else 'weekday'} times "
            f"{days} days; {weekend:.0%} of bar dates fall on weekends"
        )
        return round(per_day * days), basis
    years = (timestamps[-1] - timestamps[0]).total_seconds() / (365.25 * 86400)
    frequency = len(timestamps) / years
    note = f"elapsed calendar years; {weekend:.0%} of bar dates fall on weekends"
    from alpha_cli.spine.cost_classes import CRYPTO_DAYS, STOCK_SESSIONS

    for daily in (STOCK_SESSIONS, CRYPTO_DAYS):
        if abs(frequency - daily) <= daily * 0.03:
            return daily, f"{note}; daily snap to {daily}"
    return round(frequency), note


def periods_per_year(timestamps: Sequence[datetime], bar_size: BarTimeframe | None = None) -> int:
    return annualisation(timestamps, bar_size)[0]


@dataclass(frozen=True)
class ResolvedAsset:
    """One symbol bound to exactly one data directory and its declared provider."""

    symbol: str
    store_name: str
    data_dir: Path
    source: str
    defaulted: bool

    def daily_store(self) -> ParquetStore:
        return ParquetStore(store_dir(self.data_dir, DAILY))


def _stores(data_dir: Path) -> dict[str, Path]:
    stores = {"home": data_dir}
    path = data_dir / "stores.toml"
    if not path.exists():
        return stores
    with path.open("rb") as stream:
        registry = tomllib.load(stream)
    for name, directory in registry.items():
        if not name or "@" in name or name == "home":
            raise DataError(f"invalid or reserved store name {name!r}")
        if not isinstance(directory, str) or not directory.strip():
            raise DataError(f"store {name!r} must name a data directory")
        stores[name] = (data_dir / directory).resolve()
    return stores


def _source(path: Path) -> str:
    try:
        provenance = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DataError(f"cannot read provenance at {path}") from exc
    if not isinstance(provenance, dict):
        raise DataError(f"invalid provenance at {path}")
    dataset = provenance.get("dataset")
    source = dataset.get("provider") if isinstance(dataset, dict) else None
    if source is None:
        source = provenance.get("source")
    if not isinstance(source, str) or not source.strip():
        raise DataError(f"provenance at {path} has no source or dataset.provider")
    return source


def resolve_asset(asset: str, *, data_dir: Path, timeframe: str = "1D") -> ResolvedAsset:
    """Resolve an explicit store or the first provenance match, without reading any bars.

    ``timeframe`` picks the stored bar size whose store root is searched (daily: ``store/``).
    """
    stored = parse_timeframe(timeframe)
    stores = _stores(data_dir)
    symbol, separator, requested = asset.partition("@")
    if separator and requested not in stores:
        raise DataError(f"unknown store {requested!r}; known stores: {', '.join(stores)}")
    searched = {requested: stores[requested]} if separator else stores
    matches: list[tuple[str, Path, Path]] = []
    for name, directory in searched.items():
        path = ParquetStore(store_dir(directory, stored))._provenance_path(symbol)
        if path.exists():
            matches.append((name, directory, path))
    if not matches:
        raise DataError(f"asset {symbol!r} not found; stores searched: {', '.join(searched)}")
    name, directory, path = matches[0]
    return ResolvedAsset(symbol, name, directory, _source(path), len(matches) > 1)

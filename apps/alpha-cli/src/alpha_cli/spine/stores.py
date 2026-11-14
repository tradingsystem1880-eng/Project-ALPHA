"""Frequency inference and single-source asset resolution for the command spine."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from alpha_core import DataError
from alpha_data.store import ParquetStore


def periods_per_year(timestamps: Sequence[datetime]) -> int:
    """Infer bar frequency from elapsed years, snapping daily exchange/crypto calendars."""
    if len(timestamps) < 30:
        raise ValueError("periods_per_year requires at least 30 bars")
    if any(right <= left for left, right in zip(timestamps, timestamps[1:], strict=False)):
        raise ValueError("periods_per_year requires strictly increasing timestamps")
    years = (timestamps[-1] - timestamps[0]).total_seconds() / (365.25 * 86400)
    frequency = len(timestamps) / years
    for daily in (252, 365):
        if abs(frequency - daily) <= daily * 0.03:
            return daily
    return round(frequency)


@dataclass(frozen=True)
class ResolvedAsset:
    """One symbol bound to exactly one data directory and its declared provider."""

    symbol: str
    store_name: str
    data_dir: Path
    source: str
    defaulted: bool


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


def resolve_asset(asset: str, *, data_dir: Path) -> ResolvedAsset:
    """Resolve an explicit store or the first provenance match, without reading any bars."""
    stores = _stores(data_dir)
    symbol, separator, requested = asset.partition("@")
    if separator and requested not in stores:
        raise DataError(f"unknown store {requested!r}; known stores: {', '.join(stores)}")
    searched = {requested: stores[requested]} if separator else stores
    matches: list[tuple[str, Path, Path]] = []
    for name, directory in searched.items():
        path = ParquetStore(directory / "store")._provenance_path(symbol)
        if path.exists():
            matches.append((name, directory, path))
    if not matches:
        raise DataError(f"asset {symbol!r} not found; stores searched: {', '.join(searched)}")
    name, directory, path = matches[0]
    return ResolvedAsset(symbol, name, directory, _source(path), len(matches) > 1)

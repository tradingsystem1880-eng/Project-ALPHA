"""PIT-adjusted candles via the CLI (``alpha data candles --json``), cached on the store mtime.

Reading candles through the CLI keeps the point-in-time / split-adjustment firewall in its one
audited seam (the web layer never imports ``alpha_data``). Results are cached until the symbol's
stored parquet changes, so repeat chart loads don't re-spawn the CLI. The cache keeps at most
``_CACHE_LIMIT`` results and drops the oldest first, so a long session cannot grow it without limit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alpha_web._catalog import _run_json

_CACHE_LIMIT = 32
_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}


def _remember(key: tuple[Any, ...], result: dict[str, Any]) -> None:
    """Store ``result`` under ``key``; drop the oldest entries past ``_CACHE_LIMIT``."""
    _CACHE.pop(key, None)
    _CACHE[key] = result
    while len(_CACHE) > _CACHE_LIMIT:
        del _CACHE[next(iter(_CACHE))]


def candles(
    symbol: str,
    *,
    data_dir: Path,
    start: str | None = None,
    end: str | None = None,
    snapshot: str | None = None,
    manifest_id: str | None = None,
) -> dict[str, Any]:
    """``{symbol, snapshot_id, bars:[{t,o,h,l,c,v}]}`` for ``symbol`` over the window."""
    # Guard the cache-key mtime probe against traversal (a crafted ``../`` symbol must not stat
    # files outside the store). The real read is ParquetStore-guarded and fails loud regardless.
    safe = ".." not in symbol and "\\" not in symbol and not symbol.startswith("/")
    parquet = data_dir / "store" / "bars" / f"{symbol}.parquet"
    mtime = parquet.stat().st_mtime if (safe and parquet.exists()) else None
    key = (str(data_dir), symbol, start, end, snapshot, mtime)
    if manifest_id is None and key in _CACHE:
        return _CACHE[key]
    args = ["data", "candles", symbol, "--json"]
    for flag, value in (
        ("--start", start),
        ("--end", end),
        ("--snapshot", snapshot),
        ("--manifest-id", manifest_id),
    ):
        if value:
            args += [flag, value]
    result: dict[str, Any] = _run_json(args, data_dir=data_dir)
    if manifest_id is None:
        _remember(key, result)
    return result


def overlays(
    symbol: str,
    *,
    data_dir: Path,
    indicators: tuple[str, ...] = (),
    patterns: tuple[str, ...] = (),
    end: str | None = None,
    snapshot: str | None = None,
    manifest_id: str | None = None,
) -> dict[str, Any]:
    """``alpha chart overlays --json`` over the same PIT window, cached like :func:`candles`."""
    safe = ".." not in symbol and "\\" not in symbol and not symbol.startswith("/")
    parquet = data_dir / "store" / "bars" / f"{symbol}.parquet"
    mtime = parquet.stat().st_mtime if (safe and parquet.exists()) else None
    key = ("overlays", str(data_dir), symbol, indicators, patterns, end, snapshot, mtime)
    if manifest_id is None and key in _CACHE:
        return _CACHE[key]
    args = ["chart", "overlays", symbol, "--json"]
    for spec in indicators:
        args += ["--indicator", spec]
    for spec in patterns:
        args += ["--pattern", spec]
    for flag, value in (("--end", end), ("--snapshot", snapshot), ("--manifest-id", manifest_id)):
        if value:
            args += [flag, value]
    result: dict[str, Any] = _run_json(args, data_dir=data_dir)
    if manifest_id is None:
        _remember(key, result)
    return result

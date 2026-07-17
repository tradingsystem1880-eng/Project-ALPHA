"""PIT-adjusted candles via the CLI (``alpha data candles --json``), cached on the store mtime.

Reading candles through the CLI keeps the point-in-time / split-adjustment firewall in its one
audited seam (the web layer never imports ``alpha_data``). Results are cached until the symbol's
stored parquet changes, so repeat chart loads don't re-spawn the CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alpha_web._catalog import _run_json

_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}


def candles(
    symbol: str,
    *,
    data_dir: Path,
    start: str | None = None,
    end: str | None = None,
    snapshot: str | None = None,
) -> dict[str, Any]:
    """``{symbol, snapshot_id, bars:[{t,o,h,l,c,v}]}`` for ``symbol`` over the window."""
    parquet = data_dir / "store" / "bars" / f"{symbol}.parquet"
    mtime = parquet.stat().st_mtime if parquet.exists() else None
    key = (str(data_dir), symbol, start, end, snapshot, mtime)
    if key in _CACHE:
        return _CACHE[key]
    args = ["data", "candles", symbol, "--json"]
    for flag, value in (("--start", start), ("--end", end), ("--snapshot", snapshot)):
        if value:
            args += [flag, value]
    result: dict[str, Any] = _run_json(args, data_dir=data_dir)
    _CACHE[key] = result
    return result

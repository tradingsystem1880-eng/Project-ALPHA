"""Filesystem reads over the run store for the workstation (same store the CLI + MCP server use).

``alpha`` writes a byte-stable ``manifest.json`` per run under one of a few run-type directories
(plus an ``equity_curve.parquet`` and ``tearsheet.html`` for engine runs). These helpers read them
back for the run browser and run detail — no engine, no subprocess.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from alpha_cli import RUN_DIRS
from alpha_cli._artifacts import find_run_dir
from alpha_core import DataError


def _run_dir(run_id: str, *, data_dir: Path) -> Path | None:
    return find_run_dir(data_dir, run_id)


def forecast_series(run_id: str, *, data_dir: Path) -> dict[str, Any] | None:
    """History + forecast-cone closes (median + quantile bands) for a forecast run's chart.

    Reads the CLI's ``quantiles.parquet`` (per-step close quantiles) and ``history.parquet``. The
    median line is ``q50``; the outer band is q05–q95 (served as the SPA's pre-existing
    ``p10``/``p90`` keys — kept verbatim, the fan chart depends on them) and the inner band plus
    the sample mean ride along as ``q25``/``q75``/``mean``. Returns None for runs that wrote no
    cone artifacts (a ``forecast eval`` run, or any non-forecast run type).
    """
    rdir = _run_dir(run_id, data_dir=data_dir)
    if rdir is None:
        return None
    qpath, hpath = rdir / "quantiles.parquet", rdir / "history.parquet"
    if not (qpath.exists() and hpath.exists()):
        return None
    quant = pl.read_parquet(qpath)
    history = pl.read_parquet(hpath)
    return {
        "history": [float(v) for v in history["close"].to_list()],
        "forecast": [float(v) for v in quant["q50"].to_list()],
        "p10": [float(v) for v in quant["q05"].to_list()],
        "p90": [float(v) for v in quant["q95"].to_list()],
        "q25": [float(v) for v in quant["q25"].to_list()],
        "q75": [float(v) for v in quant["q75"].to_list()],
        "mean": [float(v) for v in quant["mean"].to_list()],
        # timestamps (epoch seconds) for the client-side chart's x-axis.
        "history_ts": [t.timestamp() for t in history["ts"].to_list()],
        "forecast_ts": [t.timestamp() for t in quant["ts"].to_list()],
    }


MAX_FORECAST_PATHS = 40  # spaghetti-line cap: more is unreadable and bloats the payload


def forecast_paths(run_id: str, *, data_dir: Path, n: int = 20) -> dict[str, Any] | None:
    """The first ``n`` sampled close paths of a forecast run (deterministic — no RNG).

    Reads the CLI's ``paths.parquet`` (per-sample OHLCV, long) and returns
    ``{samples: [{sample, closes}], ts}`` with ``ts`` in epoch seconds. ``n`` is clamped to
    [1, MAX_FORECAST_PATHS]. Returns None when the run is absent, is not a forecast run (a
    propfirm run also writes a — differently shaped — ``paths.parquet``), or wrote no paths.
    """
    rdir = _run_dir(run_id, data_dir=data_dir)
    if rdir is None or rdir.parent.name != "forecast":
        return None
    path = rdir / "paths.parquet"
    if not path.exists():
        return None
    n = max(1, min(n, MAX_FORECAST_PATHS))
    frame = pl.read_parquet(path).sort("sample", "step")
    wanted = frame["sample"].unique(maintain_order=True).to_list()[:n]
    if not wanted:
        raise DataError(f"forecast run {run_id!r} wrote an empty paths.parquet")
    samples = [
        {
            "sample": int(s),
            "closes": [float(v) for v in frame.filter(pl.col("sample") == s)["close"].to_list()],
        }
        for s in wanted
    ]
    return {
        "samples": samples,
        "ts": [t.timestamp() for t in frame.filter(pl.col("sample") == wanted[0])["ts"].to_list()],
    }


def tearsheet_file(run_id: str, *, data_dir: Path) -> Path | None:
    """Path to the run's ``tearsheet.html`` if written (gauntlet/portfolio runs), else None."""
    rdir = _run_dir(run_id, data_dir=data_dir)
    if rdir is None:
        return None
    path = rdir / "tearsheet.html"
    return path if path.exists() else None


# --- workstation JSON API helpers (richer indexing/series for the SPA panels) ------------------


def _index_runs(*, data_dir: Path) -> list[dict[str, Any]]:
    """Every stored run as a rich record (run_id, kind, command, label, verdict, mtime), unsorted.

    ``mtime`` is the ``manifest.json`` filesystem timestamp — deliberately NOT a manifest field, so
    time-ordering the browser never touches the byte-stable, wall-clock-free manifests.
    """
    records: list[dict[str, Any]] = []
    for sub in RUN_DIRS:
        base = data_dir / sub
        if not base.is_dir():
            continue
        for rdir in base.iterdir():
            mpath = rdir / "manifest.json"
            if not mpath.exists():
                continue
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
            symbols = manifest.get("symbols")
            verdict = manifest.get("verdict")
            records.append(
                {
                    "run_id": rdir.name,
                    "kind": sub,
                    "command": manifest.get("command"),
                    "label": manifest.get("symbol")
                    or (", ".join(symbols) if symbols else None)
                    or manifest.get("source"),
                    "symbol": manifest.get("symbol"),
                    "symbols": symbols,
                    "passed": manifest.get("passed"),
                    "verdict": verdict.get("overall") if isinstance(verdict, dict) else None,
                    "mtime": mpath.stat().st_mtime,
                }
            )
    return records


def query_runs(
    *,
    data_dir: Path,
    kind: str | None = None,
    symbol: str | None = None,
    verdict: str | None = None,
    passed: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Filtered, newest-first (mtime-desc), paginated run index for the run browser."""
    records = _index_runs(data_dir=data_dir)
    if kind is not None:
        records = [r for r in records if r["kind"] == kind]
    if symbol is not None:
        records = [
            r for r in records if r["symbol"] == symbol or (r["symbols"] and symbol in r["symbols"])
        ]
    if verdict is not None:
        records = [r for r in records if r["verdict"] == verdict]
    if passed is not None:
        records = [r for r in records if r["passed"] is passed]
    records.sort(key=lambda r: r["mtime"], reverse=True)
    total = len(records)
    return {"total": total, "items": records[offset : offset + limit]}


def run_detail(run_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Full manifest + kind/mtime + artifact-presence flags. Fail loud if the run is absent."""
    rdir = _run_dir(run_id, data_dir=data_dir)
    if rdir is None:
        raise FileNotFoundError(f"no run {run_id!r} under {data_dir}")
    mpath = rdir / "manifest.json"
    return {
        "run_id": run_id,
        "kind": rdir.parent.name,
        "mtime": mpath.stat().st_mtime,
        "manifest": json.loads(mpath.read_text(encoding="utf-8")),
        "has_equity": (rdir / "equity_curve.parquet").exists(),
        "has_trades": (rdir / "trades.parquet").exists(),
        "has_tearsheet": (rdir / "tearsheet.html").exists(),
        "has_forecast": (rdir / "quantiles.parquet").exists(),
    }


def equity_series(run_id: str, *, data_dir: Path) -> dict[str, list[float]]:
    """Equity curve as ``{ts (epoch seconds), equity, drawdown}``; empty lists when no curve."""
    empty: dict[str, list[float]] = {"ts": [], "equity": [], "drawdown": []}
    rdir = _run_dir(run_id, data_dir=data_dir)
    if rdir is None:
        return empty
    path = rdir / "equity_curve.parquet"
    if not path.exists():
        return empty
    frame = pl.read_parquet(path)
    equity = [float(v) for v in frame["equity"].to_list()]
    ts = [t.timestamp() for t in frame["ts"].to_list()]
    peak = float("-inf")
    drawdown: list[float] = []
    for v in equity:
        peak = max(peak, v)
        drawdown.append(v / peak - 1.0 if peak > 0 else 0.0)
    return {"ts": ts, "equity": equity, "drawdown": drawdown}


def trades(run_id: str, *, data_dir: Path) -> list[dict[str, Any]]:
    """The run's trade log rows (datetimes serialized to ISO strings); ``[]`` when none written."""
    rdir = _run_dir(run_id, data_dir=data_dir)
    if rdir is None:
        return []
    path = rdir / "trades.parquet"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = pl.read_parquet(path).to_dicts()
    for row in rows:
        for key in ("entry_ts", "exit_ts"):
            value = row.get(key)
            if value is not None and hasattr(value, "isoformat"):
                row[key] = value.isoformat()
    return rows

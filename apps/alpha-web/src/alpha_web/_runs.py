"""Filesystem reads over the run store for the workstation (same store the CLI + MCP server use).

``alpha`` writes a byte-stable ``manifest.json`` per run under one of a few run-type directories
(plus an ``equity_curve.parquet`` and ``tearsheet.html`` for engine runs). These helpers read them
back for the run browser and run detail — no engine, no subprocess.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import polars as pl

from alpha_cli import RUN_DIRS
from alpha_cli._artifacts import find_run_dir
from alpha_core import DataError


def _run_dir(run_id: str, *, data_dir: Path) -> Path | None:
    return find_run_dir(data_dir, run_id)


def _artifact_frame(
    run_id: str,
    filename: str,
    *,
    data_dir: Path,
    sort: tuple[str, ...] = (),
) -> pl.DataFrame | None:
    """A run's parquet artifact, sorted; None when the run is absent or the file unwritten."""
    rdir = _run_dir(run_id, data_dir=data_dir)
    if rdir is None:
        return None
    path = rdir / filename
    if not path.exists():
        return None
    frame = pl.read_parquet(path)
    return frame.sort(*sort) if sort else frame


def forecast_series(run_id: str, *, data_dir: Path) -> dict[str, Any] | None:
    """History + forecast-cone closes (median + quantile bands) for a forecast run's chart.

    Reads the CLI's ``quantiles.parquet`` (per-step close quantiles) and ``history.parquet``.
    The median line is ``q50``; the bands are served under their honest quantile names
    (``q05/q25/q75/q95``) plus the sample ``mean``. Returns None for runs that wrote no cone
    artifacts (a ``forecast eval`` run, or any non-forecast run type).
    """
    quant = _artifact_frame(run_id, "quantiles.parquet", data_dir=data_dir)
    history = _artifact_frame(run_id, "history.parquet", data_dir=data_dir)
    if quant is None or history is None:
        return None
    return {
        "history": [float(v) for v in history["close"].to_list()],
        "forecast": [float(v) for v in quant["q50"].to_list()],
        "q05": [float(v) for v in quant["q05"].to_list()],
        "q95": [float(v) for v in quant["q95"].to_list()],
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

    Reads the forecast run's ``paths.parquet`` (per-sample OHLCV, long) and returns
    ``{samples: [{sample, closes}], ts}`` with ``ts`` in epoch seconds. ``n`` is clamped to
    [1, MAX_FORECAST_PATHS]. Returns None when the run is absent or wrote no paths.
    """
    frame = _artifact_frame(run_id, "paths.parquet", data_dir=data_dir, sort=("sample", "step"))
    if frame is None:
        return None
    n = max(1, min(n, MAX_FORECAST_PATHS))
    parts = frame.partition_by("sample", maintain_order=True)[:n]
    if not parts:
        raise DataError(f"forecast run {run_id!r} wrote an empty paths.parquet")
    return {
        "samples": [
            {
                "sample": int(part["sample"][0]),
                "closes": [float(v) for v in part["close"].to_list()],
            }
            for part in parts
        ],
        "ts": [t.timestamp() for t in parts[0]["ts"].to_list()],
    }


def null_distributions(run_id: str, *, data_dir: Path) -> dict[str, Any] | None:
    """A gauntlet run's raw per-tier null distributions, ``{tiers: [{tier, statistics}]}``.

    Reads ``nulls.parquet`` (one row per (tier, path), written sorted). Statistics are served in
    (tier, path_index) order. Returns None when the run is absent or wrote no null artifact.
    """
    frame = _artifact_frame(run_id, "nulls.parquet", data_dir=data_dir, sort=("tier", "path_index"))
    if frame is None:
        return None
    return {
        "tiers": [
            {
                "tier": str(part["tier"][0]),
                "statistics": [float(v) for v in part["statistic"].to_list()],
            }
            for part in frame.partition_by("tier", maintain_order=True)
        ]
    }


def optim_trials(run_id: str, *, data_dir: Path) -> dict[str, Any] | None:
    """A sweep's per-config OOS return streams, ``{trials: [{trial, returns}]}``.

    Reads ``trials.parquet`` (one row per (trial, step), written sorted); ``trial`` aligns with
    the manifest's ``configs``/``sharpes`` order. No server-side math beyond grouping. Returns
    None when the run is absent or wrote no trials artifact.
    """
    frame = _artifact_frame(run_id, "trials.parquet", data_dir=data_dir, sort=("trial", "step"))
    if frame is None:
        return None
    return {
        "trials": [
            {
                "trial": int(part["trial"][0]),
                "returns": [float(v) for v in part["oos_return"].to_list()],
            }
            for part in frame.partition_by("trial", maintain_order=True)
        ]
    }


def propfirm_paths(run_id: str, *, data_dir: Path) -> dict[str, Any] | None:
    """A prop-firm run's per-path Monte-Carlo outcomes, columnar.

    Reads ``propfirm_paths.parquet`` (one row per path, sorted by path_index). ``days_to_pass``
    is NaN on disk for never-passed paths — converted to None here (JSON has no NaN). Returns
    None when the run is absent or wrote no paths artifact.
    """
    frame = _artifact_frame(
        run_id, "propfirm_paths.parquet", data_dir=data_dir, sort=("path_index",)
    )
    if frame is None:
        return None
    return {
        "paths": {
            "passed": [bool(v) for v in frame["passed"].to_list()],
            "busted": [bool(v) for v in frame["busted"].to_list()],
            "days_to_pass": [
                None if math.isnan(v) else float(v) for v in frame["days_to_pass"].to_list()
            ],
            "payout": [float(v) for v in frame["payout"].to_list()],
        }
    }


def forecast_origins(run_id: str, *, data_dir: Path) -> dict[str, Any] | None:
    """A forecast-eval run's per-origin skill scores, columnar (``origin_ts`` in epoch seconds).

    Reads ``origins.parquet`` (one row per rolling origin) and serves the chart/table columns:
    timestamps, cutoff split, CRPS vs both baselines, end returns, and the hit/coverage booleans.
    Returns None when the run is absent or wrote no origins artifact.
    """
    frame = _artifact_frame(run_id, "origins.parquet", data_dir=data_dir, sort=("origin_index",))
    if frame is None:
        return None
    return {
        "origin_ts": [t.timestamp() for t in frame["origin_ts"].to_list()],
        "pre_cutoff": [bool(v) for v in frame["pre_cutoff"].to_list()],
        "crps": [float(v) for v in frame["crps"].to_list()],
        "crps_rw": [float(v) for v in frame["crps_rw"].to_list()],
        "crps_bootstrap": [float(v) for v in frame["crps_bootstrap"].to_list()],
        "realized_end_return": [float(v) for v in frame["realized_end_return"].to_list()],
        "median_end_return": [float(v) for v in frame["median_end_return"].to_list()],
        "hit": [bool(v) for v in frame["hit"].to_list()],
        "cover50": [bool(v) for v in frame["cover50"].to_list()],
        "cover80": [bool(v) for v in frame["cover80"].to_list()],
        "cover90": [bool(v) for v in frame["cover90"].to_list()],
    }


def tearsheet_file(run_id: str, *, data_dir: Path) -> Path | None:
    """Path to the run's ``tearsheet.html`` if written (gauntlet/portfolio runs), else None."""
    rdir = _run_dir(run_id, data_dir=data_dir)
    if rdir is None:
        return None
    path = rdir / "tearsheet.html"
    return path if path.exists() else None


# --- workstation JSON API helpers (richer indexing/series for the SPA panels) ------------------

# run_record cache keyed on manifest path — invalidated by mtime, so the index endpoint re-reads
# only changed manifests (the activity stream turns /api/runs into a per-event hot path).
_RECORD_CACHE: dict[Path, tuple[float, dict[str, Any]]] = {}


def run_record(kind: str, run_id: str, *, data_dir: Path) -> dict[str, Any]:
    """One run's browser record — THE shared shape of ``/api/runs`` index items and the activity
    stream's ``run_added``/``run_updated`` payloads (the SPA consumes both as ``RunListItem``).

    ``mtime`` is the ``manifest.json`` filesystem timestamp — deliberately NOT a manifest field,
    so time-ordering the browser never touches the byte-stable, wall-clock-free manifests.
    Raises ``OSError``/``json.JSONDecodeError`` on a vanished or mid-write manifest.
    """
    mpath = data_dir / kind / run_id / "manifest.json"
    mtime = mpath.stat().st_mtime
    cached = _RECORD_CACHE.get(mpath)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    symbols = manifest.get("symbols")
    verdict = manifest.get("verdict")
    record = {
        "run_id": run_id,
        "kind": kind,
        "command": manifest.get("command"),
        "label": manifest.get("symbol")
        or (", ".join(symbols) if symbols else None)
        or manifest.get("source"),
        "symbol": manifest.get("symbol"),
        "symbols": symbols,
        "passed": manifest.get("passed"),
        "verdict": verdict.get("overall") if isinstance(verdict, dict) else None,
        "mtime": mtime,
    }
    _RECORD_CACHE[mpath] = (mtime, record)
    return record


def _index_runs(*, data_dir: Path) -> list[dict[str, Any]]:
    """Every stored run as a rich record (see ``run_record``), unsorted."""
    records: list[dict[str, Any]] = []
    for sub in RUN_DIRS:
        base = data_dir / sub
        if not base.is_dir():
            continue
        for rdir in base.iterdir():
            try:
                records.append(run_record(sub, rdir.name, data_dir=data_dir))
            except (OSError, json.JSONDecodeError):
                continue  # no/partial manifest yet — invisible until fully written
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
        "has_nulls": (rdir / "nulls.parquet").exists(),
        "has_trials": (rdir / "trials.parquet").exists(),
        "has_forecast_paths": (rdir / "paths.parquet").exists(),
        "has_propfirm_paths": (rdir / "propfirm_paths.parquet").exists(),
        "has_origins": (rdir / "origins.parquet").exists(),
    }


def equity_series(run_id: str, *, data_dir: Path) -> dict[str, list[float]]:
    """Equity curve as ``{ts (epoch seconds), equity, drawdown}``; empty lists when no curve."""
    frame = _artifact_frame(run_id, "equity_curve.parquet", data_dir=data_dir)
    if frame is None:
        return {"ts": [], "equity": [], "drawdown": []}
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
    frame = _artifact_frame(run_id, "trades.parquet", data_dir=data_dir)
    if frame is None:
        return []
    rows: list[dict[str, Any]] = frame.to_dicts()
    for row in rows:
        for key in ("entry_ts", "exit_ts"):
            value = row.get(key)
            if value is not None and hasattr(value, "isoformat"):
                row[key] = value.isoformat()
    return rows

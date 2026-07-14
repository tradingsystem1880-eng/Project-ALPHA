"""Filesystem reads over the run store for the web IDE (same store the CLI + MCP server use).

``alpha`` writes a byte-stable ``manifest.json`` per run under one of a few run-type directories
(plus an ``equity_curve.parquet`` and ``tearsheet.html`` for engine runs). These helpers read them
back for the run browser and run-detail pages — no engine, no subprocess.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from alpha_cli._artifacts import RUN_DIRS


def _run_dir(run_id: str, *, data_dir: Path) -> Path | None:
    for sub in RUN_DIRS:
        rdir = data_dir / sub / run_id
        if (rdir / "manifest.json").exists():
            return rdir
    return None


def list_runs(*, data_dir: Path) -> list[dict[str, Any]]:
    """Index every stored run for the browser: run_id, command, label, pass/Verdict badges."""
    runs: list[dict[str, Any]] = []
    for sub in RUN_DIRS:
        base = data_dir / sub
        if not base.is_dir():
            continue
        for rdir in sorted(p for p in base.iterdir() if (p / "manifest.json").exists()):
            manifest = json.loads((rdir / "manifest.json").read_text(encoding="utf-8"))
            symbols = manifest.get("symbols")
            verdict = manifest.get("verdict")
            runs.append(
                {
                    "run_id": rdir.name,
                    "command": manifest.get("command"),
                    "label": manifest.get("symbol")
                    or (", ".join(symbols) if symbols else None)
                    or manifest.get("source"),
                    "passed": manifest.get("passed"),
                    "verdict": verdict.get("overall") if isinstance(verdict, dict) else None,
                }
            )
    return runs


def get_run(run_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Return a stored run's full manifest by id. Fail loud (``FileNotFoundError``) if absent."""
    rdir = _run_dir(run_id, data_dir=data_dir)
    if rdir is None:
        raise FileNotFoundError(f"no run {run_id!r} under {data_dir}")
    result: dict[str, Any] = json.loads((rdir / "manifest.json").read_text(encoding="utf-8"))
    return result


def equity_values(run_id: str, *, data_dir: Path) -> list[float]:
    """The run's equity values in order, or ``[]`` when it wrote no curve (optim/portfolio)."""
    rdir = _run_dir(run_id, data_dir=data_dir)
    if rdir is None:
        return []
    path = rdir / "equity_curve.parquet"
    if not path.exists():
        return []
    return [float(v) for v in pl.read_parquet(path)["equity"].to_list()]


def forecast_series(run_id: str, *, data_dir: Path) -> dict[str, Any] | None:
    """History + forecast closes (and the optional p10/p90 band) for a forecast run's chart.

    Returns None for runs that wrote no forecast artifacts (every non-forecast run type).
    """
    rdir = _run_dir(run_id, data_dir=data_dir)
    if rdir is None:
        return None
    fpath, hpath = rdir / "forecast.parquet", rdir / "history.parquet"
    if not (fpath.exists() and hpath.exists()):
        return None
    forecast = pl.read_parquet(fpath)
    history = pl.read_parquet(hpath)
    has_band = "close_p10" in forecast.columns and "close_p90" in forecast.columns
    return {
        "history": [float(v) for v in history["close"].to_list()],
        "forecast": [float(v) for v in forecast["close"].to_list()],
        "p10": [float(v) for v in forecast["close_p10"].to_list()] if has_band else None,
        "p90": [float(v) for v in forecast["close_p90"].to_list()] if has_band else None,
    }


def tearsheet_file(run_id: str, *, data_dir: Path) -> Path | None:
    """Path to the run's ``tearsheet.html`` if written (gauntlet/portfolio runs), else None."""
    rdir = _run_dir(run_id, data_dir=data_dir)
    if rdir is None:
        return None
    path = rdir / "tearsheet.html"
    return path if path.exists() else None

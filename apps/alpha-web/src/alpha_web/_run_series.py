"""One run's stored series for the interactive tear sheet: read, sample, relay. No statistic."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from alpha_cli import run_projection
from alpha_web import _runs

MAX_SERIES_POINTS = _runs.MAX_NATIVE_TEARSHEET_POINTS
TRADE_CAP = 2_000
_ARTIFACTS = ("equity_curve.parquet", "trades.parquet", "benchmark_comparison.parquet")


def _by_ts(frame: pl.DataFrame | None, column: str, *, flag: str) -> dict[float, float]:
    """A stored column keyed by epoch seconds; empty unless the artifact says it is available."""
    if frame is None or frame.is_empty() or column not in frame.columns:
        return {}
    if flag in frame.columns and frame[flag][0] is not True:
        return {}
    stamp = "ts" if "ts" in frame.columns else "start_ts"
    return {
        t.timestamp(): float(v)
        for t, v in zip(frame[stamp].to_list(), frame[column].to_list(), strict=True)
        if v is not None
    }


def _period(value: Any) -> dict[str, str] | None:
    if (
        isinstance(value, dict)
        and isinstance(value.get("first_ts"), str)
        and isinstance(value.get("last_ts"), str)
    ):
        return {"first_ts": value["first_ts"], "last_ts": value["last_ts"]}
    return None


def _bands(manifest: dict[str, Any]) -> dict[str, Any]:
    spine = manifest.get("spine")
    periods = spine.get("periods") if isinstance(spine, dict) else None
    periods = periods if isinstance(periods, dict) else {}
    folds: list[dict[str, Any]] = []
    raw = manifest.get("folds")
    for position, fold in enumerate(raw if isinstance(raw, list) else []):
        if (
            isinstance(fold, dict)
            and isinstance(fold.get("test_start_ts"), str)
            and isinstance(fold.get("test_end_ts"), str)
        ):
            index = fold.get("index", position)
            folds.append(
                {
                    "index": index if isinstance(index, int) else position,
                    "start_ts": fold["test_start_ts"],
                    "end_ts": fold["test_end_ts"],
                }
            )
    return {
        "tradable": _period(periods.get("tradable")),
        "scored": _period(periods.get("scored")),
        "folds": folds,
    }


def _trades(run_id: str, data_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    frame = _runs._artifact_frame(run_id, "trades.parquet", data_dir=data_dir, sort=("entry_ts",))
    total = 0 if frame is None else frame.height
    rows: list[dict[str, Any]] = []
    if frame is not None:
        for row in frame.head(TRADE_CAP).iter_rows(named=True):
            entry, exit_ = row["entry_ts"], row["exit_ts"]
            if not isinstance(entry, datetime) or not isinstance(exit_, datetime):
                continue
            rows.append(
                {
                    "entry_ts": entry.timestamp(),
                    "exit_ts": exit_.timestamp(),
                    "side": str(row["side"]),
                    "entry_price": float(row["entry_price"]),
                    "exit_price": float(row["exit_price"]),
                    "realized_return": float(row["realized_return"]),
                }
            )
    bounds = {
        "original": total,
        "returned": len(rows),
        "truncated": total > len(rows),
        "cap": TRADE_CAP,
    }
    return rows, bounds


def _price(run_id: str, data_dir: Path, limit: int) -> dict[str, Any]:
    status, bars, _ = run_projection.price_series(run_id, data_dir=data_dir, limit=limit)
    return {"status": status, "ts": [b["t"] for b in bars], "close": [b["c"] for b in bars]}


def run_series(run_id: str, *, data_dir: Path, limit: int) -> dict[str, Any]:
    """Bounded stored series of one run; raises ``FileNotFoundError`` for an unknown run."""
    rdir = _runs._run_dir(run_id, data_dir=data_dir)
    if rdir is None:
        raise FileNotFoundError(f"no run {run_id!r} under {data_dir}")
    manifest = _runs._verified_manifest(rdir)
    curve = _runs.equity_series(run_id, data_dir=data_dir)
    benchmark = _by_ts(
        _runs._artifact_frame(
            run_id, "benchmark_comparison.parquet", data_dir=data_dir, sort=("ts",)
        ),
        "benchmark_equity",
        flag="available",
    )
    exposure = _by_ts(
        _runs._artifact_frame(
            run_id, "exposure_turnover.parquet", data_dir=data_dir, sort=("start_ts",)
        ),
        "gross_exposure",
        flag="exposure_available",
    )
    rows = [
        {
            "ts": t,
            "equity": e,
            "drawdown": d,
            "benchmark": benchmark.get(t),
            "exposure": exposure.get(t),
        }
        for t, e, d in zip(curve["ts"], curve["equity"], curve["drawdown"], strict=True)
    ]
    sampled, points = (
        _runs._bounded_rows(rows, limit)
        if len(rows) >= 2
        else (
            rows,
            {"original": len(rows), "returned": len(rows), "truncated": False, "sampling": "all"},
        )
    )
    trades, trade_bounds = _trades(run_id, data_dir)
    declared = manifest.get("artifacts")
    shas = {
        name: declared[name]["sha256"]
        for name in _ARTIFACTS
        if isinstance(declared, dict)
        and isinstance(declared.get(name), dict)
        and isinstance(declared[name].get("sha256"), str)
    }
    return {
        "run_id": run_id,
        "ts": [r["ts"] for r in sampled],
        "equity": [r["equity"] for r in sampled],
        "drawdown": [r["drawdown"] for r in sampled],
        "benchmark": [r["benchmark"] for r in sampled] if benchmark else None,
        "exposure": [r["exposure"] for r in sampled] if exposure else None,
        "trades": trades,
        "bands": _bands(manifest),
        "price": _price(run_id, data_dir, limit),
        "bounds": {"points": points, "trades": trade_bounds},
        "provenance": {"artifact_sha256": shas},
    }

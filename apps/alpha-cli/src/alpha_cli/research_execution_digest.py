"""Read-only execution accounting; counts are evidence, never research admission."""

from __future__ import annotations

import math
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from alpha_cli import _artifacts
from alpha_cli.artifact_contract import sha256_file
from alpha_core import DataError


def execution_digest(
    directory: Path,
    *,
    cutoff: str,
    expected_sessions: int | None = None,
    expected_timestamps: list[datetime] | None = None,
) -> dict[str, Any]:
    """Verify immutable bytes and cross-check execution quantities and measurement scope.

    Does not certify the information previously visible to a caller. Legacy/unbound runs fail.
    Session counts include the initial equity observation, not just return intervals.
    """
    manifest = _artifacts.read_manifest(directory)
    if manifest.get("schema_version") != 3:
        raise DataError("execution digest requires a verified v3 run")
    command = manifest.get("command")
    if command not in {"backtest_run", "validate"}:
        raise DataError("execution digest supports baseline backtest and validation only")
    if manifest.get("research_cutoff") != cutoff:
        raise DataError("execution cutoff mismatch")
    end = date.fromisoformat(cutoff)
    names = ("orders", "fills", "trades", "equity_curve")
    for name in names:
        if f"{name}.parquet" not in manifest["artifacts"]:
            raise DataError(f"execution evidence unavailable: {name}")
    frames = {name: pl.read_parquet(directory / f"{name}.parquet") for name in names}
    for frame in frames.values():
        for column in ("ts", "entry_ts", "exit_ts"):
            if column in frame.columns and any(
                value is None or value.date() > end for value in frame[column].to_list()
            ):
                raise DataError("execution timestamp exceeds cutoff or is missing")
    equity = frames["equity_curve"]
    timestamps = equity["ts"].to_list()
    if not timestamps or timestamps != sorted(set(timestamps)):
        raise DataError("equity sessions must be nonempty, unique and ordered")
    if expected_timestamps is not None and timestamps != expected_timestamps:
        raise DataError("execution sessions disagree with frozen snapshot schedule")
    if any(not math.isfinite(v) for v in equity["equity"].to_list()):
        raise DataError("non-finite equity")
    if command == "validate":
        folds = manifest.get("folds", [])
        if not folds or any(type(f.get("n_test")) is not int or f["n_test"] <= 0 for f in folds):
            raise DataError("validation expected sessions unavailable")
        declared_sessions = 1 + sum(f["n_test"] for f in folds)
        if expected_sessions is not None and expected_sessions != declared_sessions:
            raise DataError("validation session expectation mismatch")
        expected_sessions = declared_sessions
    if expected_sessions is not None and expected_sessions != equity.height:
        raise DataError("execution session count mismatch")
    orders, fills, trades = (frames[n] for n in ("orders", "fills", "trades"))
    order_rows = orders.to_dicts()
    by_id = {row["sequence_id"]: row for row in order_rows}
    if len(by_id) != orders.height or fills["sequence_id"].n_unique() != fills.height:
        raise DataError("duplicate execution identifiers")
    filled: Counter[int] = Counter()
    for fill in fills.to_dicts():
        order = by_id.get(fill["order_sequence_id"])
        if (
            order is None
            or any(fill[k] != order[k] for k in ("instrument_id", "side"))
            or fill["ts"] < order["ts"]
            or not math.isfinite(fill["quantity"])
            or fill["quantity"] <= 0
            or not math.isfinite(fill["price"])
            or fill["price"] <= 0
        ):
            raise DataError("invalid fill linkage or quantity")
        filled[fill["order_sequence_id"]] += fill["quantity"]
    counts = Counter(row["status"] for row in order_rows)
    for row in order_rows:
        quantity, actual = row["quantity"], row["filled_quantity"]
        if (
            not math.isfinite(quantity)
            or not math.isfinite(actual)
            or quantity <= 0
            or actual < 0
            or actual > quantity
            or not math.isclose(actual, filled[row["sequence_id"]], abs_tol=1e-8)
            or (row["status"] in {"DENIED", "REJECTED"} and actual != 0)
            or (row["status"] == "FILLED" and not math.isclose(actual, quantity))
        ):
            raise DataError("order/fill accounting mismatch")
    rejected = counts["DENIED"] + counts["REJECTED"]
    for key, value in {
        "orders": orders.height,
        "fills": fills.height,
        "rejected": rejected,
        "n_trades": trades.height,
    }.items():
        if key in manifest and manifest[key] != value:
            raise DataError(f"manifest {key} disagrees with execution sidecars")
    config = manifest.get("params", manifest.get("metadata", {}))
    return {
        "schema_version": 1,
        "admitted": False,
        "run_id": directory.name,
        "command": command,
        "research_cutoff": cutoff,
        "manifest_sha256": sha256_file(directory / "manifest.json"),
        "snapshot_id": manifest.get("snapshot_id", config.get("snapshot_id")),
        "snapshot_hash": manifest.get("snapshot_hash"),
        "source_fingerprint": manifest["source_fingerprint"],
        "configuration": config,
        "sessions": {
            "observed": equity.height,
            "expected": expected_sessions,
            "coverage": "reconciled" if expected_sessions is not None else "unverified",
            "expectation_source": "snapshot_schedule"
            if expected_timestamps is not None
            else "supplied_count"
            if command == "backtest_run" and expected_sessions is not None
            else "manifest_fold_counts"
            if command == "validate"
            else "unavailable",
            "first": timestamps[0].isoformat(),
            "last": timestamps[-1].isoformat(),
            "definition": "equity observations including initial observation",
        },
        "orders_by_status": dict(sorted(counts.items())),
        "denied_or_rejected_orders": rejected,
        "fill_events": fills.height,
        "closed_trades": trades.height,
        "closed_trades_by_instrument": dict(
            sorted(Counter(trades["instrument_id"].to_list()).items())
        ),
        "validation_passed": manifest.get("passed"),
        "oos_metrics": manifest.get("oos_metrics"),
        "unavailable": [
            "rejection_reasons",
            "terminal_open_positions",
            "agent_information_history",
        ],
        "evidence": {
            name: {
                "file": f"{name}.parquet",
                "sha256": manifest["artifacts"][f"{name}.parquet"]["sha256"],
            }
            for name in names
        },
    }

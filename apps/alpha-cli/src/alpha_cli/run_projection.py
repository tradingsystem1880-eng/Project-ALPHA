"""Bounded, typed run projections shared by the workstation and MCP surfaces.

This module performs no analytics: it verifies immutable artifacts, windows/downsamples their
stored rows, and loads candles through ALPHA's point-in-time data seam.  Python artifacts remain
authoritative and clients never reconstruct decisions, fills, indicators, or metrics.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from alpha_cli.artifact_contract import verify_manifest_artifacts
from alpha_cli.run_store import find_run_dir, read_manifest, valid_run_id
from alpha_core import DataError

MAX_CHART_POINTS = 5_000
MAX_CHART_BARS = 25_000
MAX_COMPARE_RUNS = 8
MAX_PORTFOLIO_ANALYTICS_TIMESTAMPS = 5_000
MAX_PORTFOLIO_ANALYTICS_SYMBOLS = 100
_ALPHA_BIN = "alpha"
_PROJECTION_TIMEOUT_S = 30.0
_PROCESS_ENV_NAMES = frozenset(
    {"LANG", "LC_ALL", "LC_CTYPE", "PATH", "PYTHONPATH", "TMPDIR", "TZ", "VIRTUAL_ENV"}
)
_DATA_ENV_NAMES = frozenset({"ALPHA_BULK_DATA_DIR", "ALPHA_BULK_VOLUME_UUID"})
_TRACE_ARTIFACTS = (
    "decision_trace.parquet",
    "orders.parquet",
    "fills.parquet",
    "execution_trace.parquet",
    "indicator_series.parquet",
    "chart_annotations.parquet",
)


def _bound(name: str, value: int, maximum: int) -> int:
    if isinstance(value, bool) or not 1 <= value <= maximum:
        raise DataError(f"{name} must be in 1..{maximum}")
    return value


def _run_dir(run_id: str, data_dir: Path) -> Path:
    if not valid_run_id(run_id):
        raise DataError(f"invalid run id {run_id!r}; expected 16 lowercase hex characters")
    result = find_run_dir(data_dir, run_id)
    if result is None:
        raise DataError(f"unknown completed run {run_id!r}")
    return result


def _frame(rdir: Path, name: str, *sort: str) -> pl.DataFrame | None:
    path = rdir / name
    if not path.is_file() or path.is_symlink():
        return None
    result = pl.read_parquet(path)
    return result.sort(*sort) if sort else result


def _indices(size: int, limit: int) -> list[int]:
    if size <= limit:
        return list(range(size))
    if limit == 1:
        return [0]
    return [round(index * (size - 1) / (limit - 1)) for index in range(limit)]


def _epoch(value: object) -> float | int:
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, int | float) and not isinstance(value, bool):
        return value
    raise DataError(f"fold boundary must be a timestamp or index, got {value!r}")


def _window_dates(start: str | None, end: str | None) -> tuple[date | None, date | None]:
    try:
        lower = date.fromisoformat(start) if start is not None else None
        cutoff = date.fromisoformat(end) if end is not None else None
    except ValueError as exc:
        raise DataError("chart start/end must be canonical YYYY-MM-DD") from exc
    if lower is not None and cutoff is not None and lower > cutoff:
        raise DataError("chart start must not follow end")
    return lower, cutoff


def _in_window(value: datetime, lower: date | None, cutoff: date | None) -> bool:
    day = value.astimezone(UTC).date()
    return (lower is None or day >= lower) and (cutoff is None or day <= cutoff)


def _window_frame(
    frame: pl.DataFrame,
    field: str,
    lower: date | None,
    cutoff: date | None,
) -> pl.DataFrame:
    if lower is not None:
        frame = frame.filter(pl.col(field).dt.date() >= lower)
    if cutoff is not None:
        frame = frame.filter(pl.col(field).dt.date() <= cutoff)
    return frame


def _candle_rows(
    symbol: str,
    snapshot: str,
    *,
    data_dir: Path,
    start: str | None,
    end: str | None,
) -> list[dict[str, float]]:
    """Load PIT candles through the canonical CLI without importing the data/engine stack."""
    args = ["data", "candles", symbol, "--snapshot", snapshot, "--json"]
    if start is not None:
        args.extend(["--start", start])
    if end is not None:
        args.extend(["--end", end])
    allowed = _PROCESS_ENV_NAMES | _DATA_ENV_NAMES
    env = {name: value for name, value in os.environ.items() if name in allowed}
    env["ALPHA_DATA_DIR"] = str(data_dir)
    try:
        proc = subprocess.run(
            [_ALPHA_BIN, *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=_PROJECTION_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DataError(f"could not load snapshot candles for {symbol!r}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "no CLI output"
        raise DataError(f"could not load snapshot candles for {symbol!r}: {detail}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise DataError(f"invalid candle projection for {symbol!r}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("bars"), list):
        raise DataError(f"invalid candle projection for {symbol!r}")
    rows: list[dict[str, float]] = []
    for raw in payload["bars"]:
        if not isinstance(raw, dict):
            raise DataError(f"invalid candle row for {symbol!r}")
        row: dict[str, float] = {}
        for field in ("t", "o", "h", "l", "c", "v"):
            value = raw.get(field)
            if not isinstance(value, int | float) or isinstance(value, bool):
                raise DataError(f"invalid candle field {field!r} for {symbol!r}")
            number = float(value)
            if not math.isfinite(number):
                raise DataError(f"non-finite candle field {field!r} for {symbol!r}")
            row[field] = number
        rows.append(row)
    return rows


def _bars(
    manifest: dict[str, Any],
    *,
    data_dir: Path,
    limit: int,
    start: str | None,
    end: str | None,
    lower: date | None,
    cutoff: date | None,
) -> tuple[str, list[dict[str, float]], bool]:
    symbol = manifest.get("symbol")
    snapshot = manifest.get("snapshot_id")
    if not isinstance(symbol, str):
        return "not_applicable", [], False
    if not isinstance(snapshot, str):
        return "snapshot_unavailable", [], False
    try:
        rows = _candle_rows(
            symbol,
            snapshot,
            data_dir=data_dir,
            start=start,
            end=end,
        )
    except DataError:
        return "snapshot_unavailable", [], False
    windowed = [
        row for row in rows if _in_window(datetime.fromtimestamp(row["t"], tz=UTC), lower, cutoff)
    ]
    selected = _indices(len(windowed), limit)
    return "available", [windowed[index] for index in selected], len(windowed) > limit


def _equity(
    rdir: Path,
    limit: int,
    lower: date | None,
    cutoff: date | None,
) -> tuple[dict[str, list[float]], bool]:
    frame = _frame(rdir, "equity_curve.parquet", "ts")
    if frame is None:
        return {"ts": [], "equity": [], "drawdown": []}, False
    values = [float(value) for value in frame["equity"].to_list()]
    raw_timestamps = frame["ts"].to_list()
    timestamps = [value.timestamp() for value in raw_timestamps]
    peak = float("-inf")
    drawdown: list[float] = []
    for value in values:
        peak = max(peak, value)
        drawdown.append(value / peak - 1.0 if peak > 0.0 else 0.0)
    windowed = [
        index
        for index, timestamp in enumerate(raw_timestamps)
        if _in_window(timestamp, lower, cutoff)
    ]
    selected = [windowed[index] for index in _indices(len(windowed), limit)]
    return (
        {
            "ts": [timestamps[index] for index in selected],
            "equity": [values[index] for index in selected],
            "drawdown": [drawdown[index] for index in selected],
        },
        len(windowed) > limit,
    )


def _forecast(rdir: Path) -> dict[str, Any] | None:
    quantiles = _frame(rdir, "quantiles.parquet", "step")
    history = _frame(rdir, "history.parquet", "ts")
    if quantiles is None or history is None:
        return None
    ohlcv_columns = {"open", "high", "low", "close", "volume"}
    history_ohlcv_available = ohlcv_columns.issubset(history.columns)
    return {
        "history": [float(value) for value in history["close"].to_list()],
        "history_bars": (
            [
                {
                    "t": row["ts"].timestamp(),
                    "o": float(row["open"]),
                    "h": float(row["high"]),
                    "l": float(row["low"]),
                    "c": float(row["close"]),
                    "v": float(row["volume"]),
                }
                for row in history.iter_rows(named=True)
            ]
            if history_ohlcv_available
            else []
        ),
        "history_ohlcv_available": history_ohlcv_available,
        "forecast": [float(value) for value in quantiles["q50"].to_list()],
        "p10": [float(value) for value in quantiles["q05"].to_list()],
        "q25": [float(value) for value in quantiles["q25"].to_list()],
        "q75": [float(value) for value in quantiles["q75"].to_list()],
        "p90": [float(value) for value in quantiles["q95"].to_list()],
        "mean": [float(value) for value in quantiles["mean"].to_list()],
        "history_ts": [value.timestamp() for value in history["ts"].to_list()],
        "forecast_ts": [value.timestamp() for value in quantiles["ts"].to_list()],
    }


def _folds(rdir: Path, manifest: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    frame = _frame(rdir, "folds.parquet", "fold")
    if frame is not None:
        return [
            {
                "fold": int(row["fold"]),
                "semantics": "fold_by_fold_refit",
                "train_start": _epoch(row["train_start"]),
                "train_end": _epoch(row["train_end"]),
                "validation_start": _epoch(row["validation_start"]),
                "validation_end": _epoch(row["validation_end"]),
                "test_start": _epoch(row["test_start"]),
                "test_end": _epoch(row["test_end"]),
            }
            for row in frame.head(limit).iter_rows(named=True)
        ]
    raw = manifest.get("folds")
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    for index, item in enumerate(raw[:limit]):
        if not isinstance(item, dict):
            continue
        try:
            result.append(
                {
                    "fold": int(item.get("index", index)),
                    "semantics": "fixed_rule_evaluation_no_refit",
                    "train_start": _epoch(item["train_start"]),
                    "train_end": _epoch(item["train_end"]),
                    "validation_start": None,
                    "validation_end": None,
                    "test_start": _epoch(item["test_start"]),
                    "test_end": _epoch(item["test_end"]),
                }
            )
        except (KeyError, TypeError, ValueError, DataError):
            continue
    return result


def chart_bundle(
    run_id: str,
    *,
    data_dir: Path,
    limit: int = 2_000,
    bar_limit: int = MAX_CHART_BARS,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """Return one bounded, snapshot-locked chart/evidence bundle without inferred events."""
    limit = _bound("limit", limit, MAX_CHART_POINTS)
    bar_limit = _bound("bar_limit", bar_limit, MAX_CHART_BARS)
    lower, cutoff = _window_dates(start, end)
    rdir = _run_dir(run_id, data_dir)
    manifest = read_manifest(rdir)
    if manifest.get("schema_version") == 3:
        verify_manifest_artifacts(rdir, manifest)

    bars_status, bars, bars_truncated = _bars(
        manifest,
        data_dir=data_dir,
        limit=bar_limit,
        start=start,
        end=end,
        lower=lower,
        cutoff=cutoff,
    )
    equity, equity_truncated = _equity(rdir, limit, lower, cutoff)
    trades_frame = _frame(rdir, "trades.parquet", "entry_ts")
    if trades_frame is not None:
        trades_frame = _window_frame(trades_frame, "exit_ts", lower, cutoff)
    trade_count = 0 if trades_frame is None else trades_frame.height
    trades = []
    if trades_frame is not None:
        for row in trades_frame.head(limit).iter_rows(named=True):
            trades.append(
                {
                    **row,
                    "entry_ts": row["entry_ts"].timestamp(),
                    "exit_ts": row["exit_ts"].timestamp(),
                }
            )

    declared = manifest.get("artifacts")
    trace_available = (
        manifest.get("schema_version") == 3
        and isinstance(declared, dict)
        and all(name in declared and (rdir / name).is_file() for name in _TRACE_ARTIFACTS)
    )
    all_trace: list[dict[str, Any]] = []
    indicators: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    trace_count = indicator_count = annotation_count = 0
    if trace_available:
        trace_frame = pl.read_parquet(rdir / "execution_trace.parquet").sort("sequence_id")
        trace_frame = _window_frame(trace_frame, "ts", lower, cutoff)
        trace_count = trace_frame.height
        for row in trace_frame.iter_rows(named=True):
            for field in ("ts", "entry_ts", "exit_ts"):
                value = row.get(field)
                row[field] = value.timestamp() if isinstance(value, datetime) else None
            all_trace.append(row)
        indicator_frame = pl.read_parquet(rdir / "indicator_series.parquet").sort("sequence_id")
        indicator_frame = _window_frame(indicator_frame, "ts", lower, cutoff)
        indicator_count = indicator_frame.height
        for row in indicator_frame.head(limit).iter_rows(named=True):
            row["ts"] = row["ts"].timestamp()
            indicators.append(row)
        annotation_frame = pl.read_parquet(rdir / "chart_annotations.parquet").sort(
            "annotation_id", "anchor_index"
        )
        annotation_parts = [
            windowed
            for part in annotation_frame.partition_by("annotation_id", maintain_order=True)
            if (windowed := _window_frame(part, "ts", lower, cutoff)).height >= 2
        ]
        annotation_count = len(annotation_parts)
        for part in annotation_parts[:limit]:
            first = part.row(0, named=True)
            annotations.append(
                {
                    "annotation_id": int(first["annotation_id"]),
                    "decision_sequence_id": first["decision_sequence_id"],
                    "kind": first["kind"],
                    "label": first["label"],
                    "unit": first["unit"],
                    "reason": first["reason"],
                    "anchors": [
                        {
                            "anchor_index": int(row["anchor_index"]),
                            "ts": row["ts"].timestamp(),
                            "value": float(row["value"]),
                        }
                        for row in part.iter_rows(named=True)
                    ],
                }
            )

    artifact_hashes = {
        name: item["sha256"]
        for name, item in (declared.items() if isinstance(declared, dict) else ())
        if isinstance(name, str) and isinstance(item, dict) and isinstance(item.get("sha256"), str)
    }
    return _finish_chart_bundle(
        run_id=run_id,
        manifest=manifest,
        rdir=rdir,
        limit=limit,
        bars_status=bars_status,
        bars=bars,
        equity=equity,
        trades=trades,
        all_trace=all_trace,
        indicators=indicators,
        annotations=annotations,
        bars_truncated=bars_truncated,
        equity_truncated=equity_truncated,
        trade_count=trade_count,
        trace_count=trace_count,
        indicator_count=indicator_count,
        annotation_count=annotation_count,
        trace_available=trace_available,
        artifact_hashes=artifact_hashes,
    )


def portfolio_analytics(
    run_id: str,
    *,
    data_dir: Path,
    timestamp_limit: int = 2_000,
    symbol_limit: int = 50,
) -> dict[str, Any] | None:
    """Project immutable causal allocations and exact aligned-OOS correlations, bounded."""
    if (
        isinstance(timestamp_limit, bool)
        or not 2 <= timestamp_limit <= MAX_PORTFOLIO_ANALYTICS_TIMESTAMPS
    ):
        raise DataError(f"timestamp_limit must be in 2..{MAX_PORTFOLIO_ANALYTICS_TIMESTAMPS}")
    symbol_limit = _bound("symbol_limit", symbol_limit, MAX_PORTFOLIO_ANALYTICS_SYMBOLS)
    rdir = _run_dir(run_id, data_dir)
    manifest = read_manifest(rdir)
    if manifest.get("command") != "backtest_portfolio":
        return None
    allocations = _frame(rdir, "portfolio_allocations.parquet")
    correlations = _frame(rdir, "correlations.parquet")
    exposure = _frame(rdir, "exposure_turnover.parquet")
    if allocations is None or correlations is None:
        return None
    if exposure is None:
        raise DataError(f"portfolio run {run_id!r} has no exposure artifact")

    symbols_value = manifest.get("symbols")
    if not isinstance(symbols_value, list) or not all(
        isinstance(symbol, str) for symbol in symbols_value
    ):
        raise DataError(f"portfolio run {run_id!r} has invalid symbols")
    all_symbols = list(symbols_value)
    symbols = all_symbols[:symbol_limit]
    required_allocations = {
        "source_run_id",
        "snapshot_id",
        "snapshot_hash",
        "research_cutoff",
        "frequency",
        "start_ts",
        "ts",
        "symbol",
        "weight",
        "leg_return",
        "contribution",
        "leg_gross_exposure",
        "leg_net_exposure",
        "weighted_gross_exposure",
        "weighted_net_exposure",
    }
    required_correlations = {
        "source_run_id",
        "snapshot_id",
        "snapshot_hash",
        "research_cutoff",
        "asset_a",
        "asset_b",
        "metric_name",
        "metric_unit",
        "correlation",
        "sample_count",
        "aligned_oos",
        "frequency",
        "oos_start",
        "oos_end",
        "association_not_causation",
    }
    if missing := required_allocations.difference(allocations.columns):
        raise DataError(f"portfolio allocation artifact is missing columns {sorted(missing)}")
    if missing := required_correlations.difference(correlations.columns):
        raise DataError(f"portfolio correlation artifact is missing columns {sorted(missing)}")
    for frame, label in ((allocations, "allocation"), (correlations, "correlation")):
        for field, expected in (
            ("source_run_id", run_id),
            ("snapshot_id", manifest.get("snapshot_id")),
            ("snapshot_hash", manifest.get("snapshot_hash")),
            ("research_cutoff", manifest.get("research_cutoff")),
            ("frequency", "1d"),
        ):
            if frame.get_column(field).unique().to_list() != [expected]:
                raise DataError(f"portfolio {label} artifact has inconsistent {field}")

    timestamps = allocations.get_column("ts").unique().sort().to_list()
    timestamp_indices = _indices(len(timestamps), timestamp_limit)
    selected_timestamps = [timestamps[index] for index in timestamp_indices]
    allocation_rows = (
        allocations.filter(
            pl.col("symbol").is_in(symbols) & pl.col("ts").is_in(selected_timestamps)
        )
        .sort("ts", "symbol")
        .to_dicts()
    )
    correlation_rows = (
        correlations.filter(pl.col("asset_a").is_in(symbols) & pl.col("asset_b").is_in(symbols))
        .sort("asset_a", "asset_b")
        .to_dicts()
    )
    expected_pairs = {(left, right) for left in symbols for right in symbols}
    actual_pairs = {(row["asset_a"], row["asset_b"]) for row in correlation_rows}
    if actual_pairs != expected_pairs or len(correlation_rows) != len(expected_pairs):
        raise DataError(f"portfolio run {run_id!r} has an incomplete correlation matrix")
    if any(
        row["metric_name"] != "pearson_correlation"
        or row["metric_unit"] != "coefficient"
        or row["aligned_oos"] is not True
        or row["association_not_causation"] is not True
        for row in correlation_rows
    ):
        raise DataError(f"portfolio run {run_id!r} has invalid correlation semantics")
    exposure_rows = (
        exposure.filter(pl.col("end_ts").is_in(selected_timestamps)).sort("start_ts").to_dicts()
    )
    declared = manifest.get("artifacts")
    artifact_hashes = {
        name: declared[name]["sha256"]
        for name in (
            "portfolio_allocations.parquet",
            "correlations.parquet",
            "exposure_turnover.parquet",
        )
        if isinstance(declared, dict)
        and isinstance(declared.get(name), dict)
        and isinstance(declared[name].get("sha256"), str)
    }
    return {
        "symbols": symbols,
        "allocations": [
            {
                "start_ts": row["start_ts"].timestamp(),
                "ts": row["ts"].timestamp(),
                "symbol": str(row["symbol"]),
                "weight": float(row["weight"]),
                "leg_return": float(row["leg_return"]),
                "contribution": float(row["contribution"]),
                "leg_gross_exposure": float(row["leg_gross_exposure"]),
                "leg_net_exposure": float(row["leg_net_exposure"]),
                "weighted_gross_exposure": float(row["weighted_gross_exposure"]),
                "weighted_net_exposure": float(row["weighted_net_exposure"]),
            }
            for row in allocation_rows
        ],
        "correlations": [
            {
                "asset_a": str(row["asset_a"]),
                "asset_b": str(row["asset_b"]),
                "metric_name": "pearson_correlation",
                "metric_unit": "coefficient",
                "correlation": float(row["correlation"])
                if row["correlation"] is not None
                else None,
                "sample_count": int(row["sample_count"]),
                "aligned_oos": True,
                "frequency": "1d",
                "oos_start": row["oos_start"],
                "oos_end": row["oos_end"],
                "association_not_causation": True,
            }
            for row in correlation_rows
        ],
        "exposure": [
            {
                "start_ts": row["start_ts"].timestamp(),
                "end_ts": row["end_ts"].timestamp(),
                "gross_exposure": float(row["gross_exposure"])
                if row.get("gross_exposure") is not None
                else None,
                "net_exposure": float(row["net_exposure"])
                if row.get("net_exposure") is not None
                else None,
                "turnover": float(row["turnover"]) if row.get("turnover") is not None else None,
                "exposure_available": row.get("exposure_available") is True,
                "turnover_available": row.get("turnover_available") is True,
                "exposure_unavailable_reason": row.get("exposure_unavailable_reason"),
                "turnover_unavailable_reason": row.get("turnover_unavailable_reason"),
            }
            for row in exposure_rows
        ],
        "provenance": {
            "source_run_id": run_id,
            "source_command": "backtest_portfolio",
            "snapshot_id": manifest.get("snapshot_id"),
            "snapshot_hash": manifest.get("snapshot_hash"),
            "research_cutoff": manifest.get("research_cutoff"),
            "as_of": timestamps[-1].timestamp() if timestamps else None,
            "timezone": "UTC",
            "frequency": "1d",
            "metric_namespace": "alpha_validation.portfolio",
            "correlation_alignment": "exact_pairwise_oos_timestamp_intersection",
            "allocation_semantics": "causal_sleeve_weight_at_interval_start",
            "association_label": "association, not causation",
            "artifact_contract_version": manifest.get("artifact_contract_version"),
            "artifact_sha256": artifact_hashes,
        },
        "bounds": {
            "timestamp_limit": timestamp_limit,
            "symbol_limit": symbol_limit,
            "allocation_timestamps": {
                "original": len(timestamps),
                "returned": len(selected_timestamps),
                "truncated": len(selected_timestamps) < len(timestamps),
                "sampling": "endpoint_uniform"
                if len(selected_timestamps) < len(timestamps)
                else "all",
            },
            "symbols": {
                "original": len(all_symbols),
                "returned": len(symbols),
                "truncated": len(symbols) < len(all_symbols),
                "sampling": "canonical_prefix" if len(symbols) < len(all_symbols) else "all",
            },
        },
    }


def _finish_chart_bundle(
    *,
    run_id: str,
    manifest: dict[str, Any],
    rdir: Path,
    limit: int,
    bars_status: str,
    bars: list[dict[str, float]],
    equity: dict[str, list[float]],
    trades: list[dict[str, Any]],
    all_trace: list[dict[str, Any]],
    indicators: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
    bars_truncated: bool,
    equity_truncated: bool,
    trade_count: int,
    trace_count: int,
    indicator_count: int,
    annotation_count: int,
    trace_available: bool,
    artifact_hashes: dict[str, str],
) -> dict[str, Any]:
    provenance = {
        "command": manifest.get("command") if isinstance(manifest.get("command"), str) else None,
        "symbol": manifest.get("symbol") if isinstance(manifest.get("symbol"), str) else None,
        "symbols": manifest.get("symbols") if isinstance(manifest.get("symbols"), list) else None,
        "snapshot_id": (
            manifest.get("snapshot_id") if isinstance(manifest.get("snapshot_id"), str) else None
        ),
        "snapshot_hash": (
            manifest.get("snapshot_hash")
            if isinstance(manifest.get("snapshot_hash"), str)
            else None
        ),
        "timezone": "UTC",
        "price_unit": "native_quote",
        "artifact_contract_version": (
            manifest.get("artifact_contract_version")
            if isinstance(manifest.get("artifact_contract_version"), int)
            else None
        ),
        "as_of": equity["ts"][-1] if equity["ts"] else None,
        "artifact_sha256": artifact_hashes,
    }
    return {
        "run_id": run_id,
        "trace_status": "available" if trace_available else "trace_unavailable",
        "bars_status": bars_status,
        "provenance": provenance,
        "bars": bars,
        "equity": equity,
        "trades": trades,
        "trace": all_trace[:limit],
        "decisions": [row for row in all_trace if row["event_type"] == "decision"][:limit],
        "orders": [row for row in all_trace if row["event_type"] == "order"][:limit],
        "fills": [row for row in all_trace if row["event_type"] == "fill"][:limit],
        "indicators": indicators,
        "annotations": annotations,
        "folds": _folds(rdir, manifest, limit),
        "forecast": _forecast(rdir),
        "truncated": {
            "bars": bars_truncated,
            "equity": equity_truncated,
            "trades": trade_count > limit,
            "trace": trace_count > limit,
            "indicators": indicator_count > limit,
            "annotations": annotation_count > limit,
        },
    }


def _metric_rows(manifest: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for container_name in ("metrics", "oos_metrics"):
        container = manifest.get(container_name)
        if not isinstance(container, dict):
            continue
        for name, value in sorted(container.items()):
            if isinstance(value, int | float) and not isinstance(value, bool):
                rows.append(
                    {
                        "name": str(name),
                        "value": float(value),
                        "unit": "ratio",
                        "source_artifact": "manifest.json",
                        "source_field": f"{container_name}.{name}",
                    }
                )
    for name in ("final_equity", "n_trades", "n_periods"):
        value = manifest.get(name)
        if isinstance(value, int | float) and not isinstance(value, bool):
            rows.append(
                {
                    "name": name,
                    "value": float(value),
                    "unit": "currency" if name == "final_equity" else "count",
                    "source_artifact": "manifest.json",
                    "source_field": name,
                }
            )
    return rows[:64]


def compare_runs(run_ids: list[str], *, data_dir: Path) -> dict[str, object]:
    """Compare up to eight immutable manifests using exact, bounded metric citations."""
    if not 2 <= len(run_ids) <= MAX_COMPARE_RUNS:
        raise DataError(f"run comparison requires 2..{MAX_COMPARE_RUNS} run ids")
    if len(set(run_ids)) != len(run_ids):
        raise DataError("run comparison does not accept duplicate run ids")
    rows: list[dict[str, object]] = []
    snapshot_hashes: set[str] = set()
    for run_id in run_ids:
        rdir = _run_dir(run_id, data_dir)
        manifest = read_manifest(rdir)
        snapshot_hash = manifest.get("snapshot_hash")
        if isinstance(snapshot_hash, str):
            snapshot_hashes.add(snapshot_hash)
        rows.append(
            {
                "run_id": run_id,
                "command": manifest.get("command"),
                "symbol": manifest.get("symbol"),
                "symbols": manifest.get("symbols"),
                "snapshot_id": manifest.get("snapshot_id"),
                "snapshot_hash": snapshot_hash,
                "passed": manifest.get("passed")
                if isinstance(manifest.get("passed"), bool)
                else None,
                "metrics": _metric_rows(manifest),
            }
        )
    return {
        "run_ids": run_ids,
        "same_snapshot_hash": len(snapshot_hashes) == 1
        and len(snapshot_hashes) == len({row["snapshot_hash"] for row in rows}),
        "rows": rows,
    }


__all__ = [
    "MAX_CHART_BARS",
    "MAX_CHART_POINTS",
    "MAX_COMPARE_RUNS",
    "MAX_PORTFOLIO_ANALYTICS_SYMBOLS",
    "MAX_PORTFOLIO_ANALYTICS_TIMESTAMPS",
    "chart_bundle",
    "compare_runs",
    "portfolio_analytics",
]

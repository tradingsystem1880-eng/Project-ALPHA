"""Run-artifact layout: ``data_dir/runs/<run_id>/`` with a JSON manifest + Parquet series.

The ``manifest.json`` is the byte-stable reproducibility artifact (sorted keys, ``allow_nan=False``
so non-finite values must already be ``null``); the equity curve and trade log ride alongside as
Parquet. The HTML tear sheet is written separately by the renderer and is not byte-pinned.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl

from alpha_cli._native_tearsheet import native_tearsheet_frames
from alpha_cli.run_store import find_run_dir as find_run_dir
from alpha_core import DataError
from alpha_validation import FloatArray


def sanitize(value: Any) -> Any:
    """Non-finite floats → None so manifests stay valid under ``allow_nan=False``.

    The one shared manifest sanitizer (propfirm/optim/forecast all write manifests).
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [sanitize(v) for v in value]
    return value


if TYPE_CHECKING:
    from alpha_backtest.results import BacktestResult, Trade

MANIFEST_SCHEMA_VERSION = 3
ARTIFACT_CONTRACT_VERSION = 3
_NATIVE_TEARSHEET_PARQUET = (
    "calendar_returns.parquet",
    "return_distribution.parquet",
    "rolling_metrics.parquet",
)
_REQUIRED_PARQUET: dict[str, tuple[str, ...]] = {
    "backtest_run": (
        "equity_curve.parquet",
        "trades.parquet",
        "decision_trace.parquet",
        "orders.parquet",
        "fills.parquet",
        "execution_trace.parquet",
        "indicator_series.parquet",
        "chart_annotations.parquet",
        *_NATIVE_TEARSHEET_PARQUET,
    ),
    "validate": (
        "equity_curve.parquet",
        "trades.parquet",
        "decision_trace.parquet",
        "orders.parquet",
        "fills.parquet",
        "execution_trace.parquet",
        "indicator_series.parquet",
        "chart_annotations.parquet",
        "nulls.parquet",
        *_NATIVE_TEARSHEET_PARQUET,
    ),
    "backtest_portfolio": ("equity_curve.parquet", *_NATIVE_TEARSHEET_PARQUET),
    "cross_sectional": ("equity_curve.parquet", *_NATIVE_TEARSHEET_PARQUET),
    "backtest_cross_sectional": ("equity_curve.parquet", *_NATIVE_TEARSHEET_PARQUET),
    "optim_grid": ("trials.parquet",),
    "propfirm": ("propfirm_paths.parquet",),
    "propfirm_run": ("propfirm_paths.parquet",),
    "forecast_run": ("paths.parquet", "quantiles.parquet", "history.parquet"),
    "forecast_eval": ("origins.parquet",),
}

# schema for an EMPTY trade log (no rows to infer dtypes from); non-empty infers from the rows
_TRADES_SCHEMA: dict[str, pl.DataType] = {
    "instrument_id": pl.String(),
    "side": pl.String(),
    "quantity": pl.Float64(),
    "entry_price": pl.Float64(),
    "exit_price": pl.Float64(),
    "entry_ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "exit_ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "realized_pnl": pl.Float64(),
    "realized_return": pl.Float64(),
}

_TRACE_SCHEMA: dict[str, pl.DataType] = {
    "sequence_id": pl.Int64(),
    "event_type": pl.String(),
    "ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "parent_sequence_id": pl.Int64(),
    "instrument_id": pl.String(),
    "side": pl.String(),
    "quantity": pl.Float64(),
    "filled_quantity": pl.Float64(),
    "price": pl.Float64(),
    "status": pl.String(),
    "signal": pl.Int64(),
    "decision_reason": pl.String(),
    "entry_ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "exit_ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "entry_price": pl.Float64(),
    "exit_price": pl.Float64(),
    "realized_pnl": pl.Float64(),
    "realized_return": pl.Float64(),
}

_DECISION_TRACE_SCHEMA: dict[str, pl.DataType] = {
    "sequence_id": pl.Int64(),
    "ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "instrument_id": pl.String(),
    "signal": pl.Int64(),
    "target_quantity": pl.Float64(),
    "reason": pl.String(),
}

_ORDER_TRACE_SCHEMA: dict[str, pl.DataType] = {
    "sequence_id": pl.Int64(),
    "decision_sequence_id": pl.Int64(),
    "ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "instrument_id": pl.String(),
    "side": pl.String(),
    "quantity": pl.Float64(),
    "filled_quantity": pl.Float64(),
    "status": pl.String(),
}

_FILL_TRACE_SCHEMA: dict[str, pl.DataType] = {
    "sequence_id": pl.Int64(),
    "order_sequence_id": pl.Int64(),
    "ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "instrument_id": pl.String(),
    "side": pl.String(),
    "quantity": pl.Float64(),
    "price": pl.Float64(),
}

_INDICATOR_TRACE_SCHEMA: dict[str, pl.DataType] = {
    "sequence_id": pl.Int64(),
    "decision_sequence_id": pl.Int64(),
    "ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "instrument_id": pl.String(),
    "name": pl.String(),
    "value": pl.Float64(),
    "unit": pl.String(),
}

_ANNOTATION_TRACE_SCHEMA: dict[str, pl.DataType] = {
    "annotation_id": pl.Int64(),
    "decision_sequence_id": pl.Int64(),
    "kind": pl.String(),
    "label": pl.String(),
    "unit": pl.String(),
    "reason": pl.String(),
    "anchor_index": pl.Int64(),
    "ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64(),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _same_bytes(left: Path, right: Path) -> bool:
    return left.stat().st_size == right.stat().st_size and _sha256(left) == _sha256(right)


def publish_artifact(path: Path, writer: Callable[[Path], object]) -> None:
    """Create one immutable artifact atomically; identical concurrent/repeated writes are no-ops."""
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = path.parent / "manifest.json"
    if manifest_path.exists() and not path.exists():
        raise DataError(f"cannot add artifact {path.name!r} after immutable manifest publication")
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp = Path(raw_tmp)
    try:
        writer(tmp)
        if path.exists():
            if _same_bytes(path, tmp):
                return
            raise DataError(f"immutable artifact {path} already exists with different bytes")
        if manifest_path.exists():
            raise DataError(
                f"cannot add artifact {path.name!r} after immutable manifest publication"
            )
        try:
            os.link(tmp, path)
        except FileExistsError:
            if not _same_bytes(path, tmp):
                raise DataError(
                    f"immutable artifact {path} was concurrently published with different bytes"
                ) from None
    finally:
        tmp.unlink(missing_ok=True)


def _artifact_metadata(path: Path) -> dict[str, Any]:
    try:
        schema = pl.read_parquet_schema(path)
        rows = int(pl.scan_parquet(path).select(pl.len()).collect().item())
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise DataError(f"unreadable parquet artifact {path}") from exc
    return {
        "schema": [{"name": name, "dtype": str(dtype)} for name, dtype in schema.items()],
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
        "rows": rows,
    }


def _artifact_contract(rdir: Path) -> dict[str, dict[str, Any]]:
    return {
        path.name: _artifact_metadata(path)
        for path in sorted(rdir.glob("*.parquet"), key=lambda item: item.name)
    }


def _validate_identity_fields(manifest: Mapping[str, Any]) -> None:
    if manifest.get("run_identity_version") != 3:
        raise DataError("new manifests require run_identity_version=3")
    for field in ("execution_fingerprint", "strategy_fingerprint", "source_fingerprint"):
        value = manifest.get(field)
        if field == "strategy_fingerprint" and value is None:
            continue
        if not isinstance(value, str) or len(value) != 64:
            raise DataError(f"new manifests require a 64-hex {field}")
        try:
            int(value, 16)
        except ValueError:
            raise DataError(f"new manifests require a 64-hex {field}") from None


def verify_manifest_artifacts(rdir: Path, manifest: Mapping[str, Any]) -> None:
    """Verify a v3 manifest's identity and complete machine-readable artifact contract."""
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        return
    _validate_identity_fields(manifest)
    if manifest.get("artifact_contract_version") != ARTIFACT_CONTRACT_VERSION:
        raise DataError(f"unsupported artifact contract at {rdir}")
    if manifest.get("run_id") != rdir.name:
        raise DataError(f"run manifest identity does not match directory {rdir}")
    declared = manifest.get("artifacts")
    if not isinstance(declared, dict):
        raise DataError(f"invalid artifact contract at {rdir}: expected an object")
    actual_names = {path.name for path in rdir.glob("*.parquet")}
    if set(declared) != actual_names:
        raise DataError(
            f"artifact set mismatch at {rdir}: declared {sorted(declared)}, "
            f"actual {sorted(actual_names)}"
        )
    for filename in sorted(actual_names):
        expected = declared.get(filename)
        if not isinstance(expected, dict):
            raise DataError(f"artifact {filename} metadata mismatch at {rdir}")
        path = rdir / filename
        if expected.get("size_bytes") != path.stat().st_size:
            raise DataError(f"artifact {filename} size mismatch at {rdir}")
        if expected.get("sha256") != _sha256(path):
            raise DataError(f"artifact {filename} hash mismatch at {rdir}")
        metadata = _artifact_metadata(path)
        if expected != metadata:
            for field in ("rows", "schema"):
                if expected.get(field) != metadata[field]:
                    raise DataError(f"artifact {filename} {field} mismatch at {rdir}")
            raise DataError(f"artifact {filename} metadata mismatch at {rdir}")


def run_dir(data_dir: Path, run_id: str) -> Path:
    """The artifact directory for a run: ``data_dir/runs/<run_id>``."""
    return data_dir / "runs" / run_id


def write_equity_curve(
    rdir: Path,
    *,
    baseline_ts: datetime,
    timestamps: Sequence[datetime],
    returns: Sequence[float],
    periods_per_year: int = 252,
) -> None:
    """Write a returns-level ``equity_curve.parquet`` (validate-run schema, base 1.0).

    Convention (see ``_portfolio``): ``returns[i]`` realizes at ``timestamps[i]``, so the stored
    curve is a leading ``(baseline_ts, 1.0)`` point followed by ``equity[i] = prod(1 + r[0..i])``
    at ``timestamps[i]`` — the same length-N+1, leading-1.0 shape as a gauntlet run's OOS curve.
    ``read_equity`` + ``to_returns`` therefore recovers the FULL return stream (``alpha propfirm
    --from-run`` / ``alpha risk scenario``). Deterministic: fixed column order, pinned dtypes,
    strictly-increasing rows by construction. Callers must write this BEFORE the manifest (the
    run-exists marker).
    """
    if len(timestamps) != len(returns):
        raise DataError(
            f"equity curve misaligned: {len(timestamps)} timestamps vs {len(returns)} returns"
        )
    if timestamps and baseline_ts >= timestamps[0]:
        raise DataError(
            f"baseline_ts {baseline_ts} must precede the first realization ts {timestamps[0]}"
        )
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1.0 + float(r)))
    frame = pl.DataFrame(
        {"ts": [baseline_ts, *timestamps], "equity": equity},
        schema={"ts": pl.Datetime(time_unit="us", time_zone="UTC"), "equity": pl.Float64()},
    )
    rdir.mkdir(parents=True, exist_ok=True)
    publish_artifact(rdir / "equity_curve.parquet", frame.write_parquet)
    write_native_tearsheet(
        rdir,
        equity=list(zip([baseline_ts, *timestamps], equity, strict=True)),
        periods_per_year=periods_per_year,
    )


def write_native_tearsheet(
    rdir: Path,
    *,
    equity: Sequence[tuple[datetime, float]],
    periods_per_year: int,
) -> None:
    """Publish Python-authoritative analytics consumed by the native workstation report."""
    for filename, frame in native_tearsheet_frames(
        equity, periods_per_year=periods_per_year
    ).items():
        publish_artifact(rdir / filename, frame.write_parquet)


def write_nulls(rdir: Path, *, tiers: Sequence[tuple[str, Sequence[float]]]) -> None:
    """Write ``nulls.parquet`` — the raw per-tier null distributions behind a gauntlet run.

    One row per (tier, path): ``tier`` String, ``path_index`` Int64, ``statistic`` Float64,
    sorted by (tier, path_index) regardless of caller order. Statistics are finite by construction
    (the null generators fail loud on non-finite paths). Deterministic: fixed column order, pinned
    dtypes, no wall-clock. Callers must write this BEFORE the manifest (the run-exists marker).
    """
    names = [name for name, _ in tiers]
    if len(set(names)) != len(names):
        raise DataError(f"duplicate null tiers: {names}")
    tier_col: list[str] = []
    idx_col: list[int] = []
    stat_col: list[float] = []
    for name, stats in sorted(tiers, key=lambda pair: pair[0]):
        tier_col.extend([name] * len(stats))
        idx_col.extend(range(len(stats)))
        stat_col.extend(float(v) for v in stats)
    frame = pl.DataFrame(
        {"tier": tier_col, "path_index": idx_col, "statistic": stat_col},
        schema={"tier": pl.String(), "path_index": pl.Int64(), "statistic": pl.Float64()},
    )
    rdir.mkdir(parents=True, exist_ok=True)
    publish_artifact(rdir / "nulls.parquet", frame.write_parquet)


def write_trials(rdir: Path, *, matrix: FloatArray) -> None:
    """Write ``trials.parquet`` — the ``(n_oos × n_configs)`` OOS return matrix behind a sweep.

    One row per (trial, step): ``trial`` Int64 (config index, aligned with the manifest's
    ``configs``/``sharpes``), ``step`` Int64 (position in the concatenated walk-forward OOS
    stream), ``oos_return`` Float64, sorted by (trial, step). Deterministic: fixed column order,
    pinned dtypes, no wall-clock. Callers must write this BEFORE the manifest (the run-exists
    marker).
    """
    if matrix.ndim != 2:
        raise DataError(f"trials matrix must be 2-D (n_oos × n_configs), got shape {matrix.shape}")
    n_oos, n_configs = matrix.shape
    frame = pl.DataFrame(
        {
            "trial": np.repeat(np.arange(n_configs, dtype=np.int64), n_oos),
            "step": np.tile(np.arange(n_oos, dtype=np.int64), n_configs),
            "oos_return": np.ascontiguousarray(matrix.T).reshape(-1),
        },
        schema={"trial": pl.Int64(), "step": pl.Int64(), "oos_return": pl.Float64()},
    )
    rdir.mkdir(parents=True, exist_ok=True)
    publish_artifact(rdir / "trials.parquet", frame.write_parquet)


def write_propfirm_paths(
    rdir: Path,
    *,
    passed: Sequence[bool],
    busted: Sequence[bool],
    days_to_pass: Sequence[float],
    payout: Sequence[float],
) -> None:
    """Write ``propfirm_paths.parquet`` — a prop-firm run's per-path Monte-Carlo outcomes.

    One row per path, sorted by ``path_index`` Int64 (0..n-1): ``passed``/``busted`` Boolean,
    ``days_to_pass`` Float64 (NaN when the path never passed — this is Parquet, not the manifest,
    so NaN is representable) and ``payout`` Float64. Deterministic: fixed column order, pinned
    dtypes, no wall-clock. Callers must write this BEFORE the manifest (the run-exists marker).
    """
    n = len(passed)
    if not len(busted) == len(days_to_pass) == len(payout) == n:
        raise DataError(
            f"propfirm path arrays misaligned: {n}/{len(busted)}/{len(days_to_pass)}/{len(payout)}"
        )
    frame = pl.DataFrame(
        {
            "path_index": list(range(n)),
            "passed": list(passed),
            "busted": list(busted),
            "days_to_pass": [float(v) for v in days_to_pass],
            "payout": [float(v) for v in payout],
        },
        schema={
            "path_index": pl.Int64(),
            "passed": pl.Boolean(),
            "busted": pl.Boolean(),
            "days_to_pass": pl.Float64(),
            "payout": pl.Float64(),
        },
    )
    rdir.mkdir(parents=True, exist_ok=True)
    publish_artifact(rdir / "propfirm_paths.parquet", frame.write_parquet)


def write_run(
    rdir: Path,
    *,
    manifest: dict[str, Any],
    equity: Sequence[tuple[datetime, float]],
    trades: Sequence[Trade],
    trace_result: BacktestResult | None = None,
    periods_per_year: int = 252,
) -> None:
    """Write ``equity_curve.parquet`` + ``trades.parquet`` + ``manifest.json`` into ``rdir``.

    The manifest is written LAST (atomically): every reader treats ``manifest.json`` as the
    marker that a run exists, so a crash mid-write leaves an invisible partial directory, never a
    listed run with missing series.
    """
    write_run_sidecars(
        rdir,
        equity=equity,
        trades=trades,
        trace_result=trace_result,
        periods_per_year=periods_per_year,
    )
    write_manifest(rdir, manifest)


def write_run_sidecars(
    rdir: Path,
    *,
    equity: Sequence[tuple[datetime, float]],
    trades: Sequence[Trade],
    trace_result: BacktestResult | None = None,
    periods_per_year: int = 252,
) -> None:
    """Atomically publish the standard Parquet sidecars without a completion marker."""
    rdir.mkdir(parents=True, exist_ok=True)
    equity_frame = pl.DataFrame(
        {"ts": [ts for ts, _ in equity], "equity": [v for _, v in equity]},
        schema={"ts": pl.Datetime(time_unit="us", time_zone="UTC"), "equity": pl.Float64()},
    )
    publish_artifact(rdir / "equity_curve.parquet", equity_frame.write_parquet)
    rows = [dataclasses.asdict(t) for t in trades]
    frame = (
        pl.DataFrame(rows, schema=_TRADES_SCHEMA) if rows else pl.DataFrame(schema=_TRADES_SCHEMA)
    )
    publish_artifact(rdir / "trades.parquet", frame.write_parquet)
    if len(equity) >= 2:
        write_native_tearsheet(rdir, equity=equity, periods_per_year=periods_per_year)
    if trace_result is not None:
        write_execution_trace(rdir, trace_result)


def write_execution_trace(rdir: Path, result: BacktestResult) -> None:
    """Persist truthful typed sidecars plus one consolidated canonical causal sequence."""
    events: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    order_rows: list[dict[str, Any]] = []
    fill_rows: list[dict[str, Any]] = []
    decisions = sorted(
        result.decision_trace,
        key=lambda item: (item.ts, item.instrument_id, item.reason, item.target_quantity),
    )
    for index, decision in enumerate(decisions, start=1):
        decision_rows.append(
            {
                "sequence_id": index,
                "ts": decision.ts,
                "instrument_id": decision.instrument_id,
                "signal": decision.signal,
                "target_quantity": decision.target_quantity,
                "reason": decision.reason,
            }
        )
        events.append(
            {
                "_key": f"decision:{index}",
                "_parent": None,
                "event_type": "decision",
                "ts": decision.ts,
                "instrument_id": decision.instrument_id,
                "side": None,
                "quantity": decision.target_quantity,
                "filled_quantity": None,
                "price": None,
                "status": None,
                "signal": decision.signal,
                "decision_reason": decision.reason,
                "entry_ts": None,
                "exit_ts": None,
                "entry_price": None,
                "exit_price": None,
                "realized_pnl": None,
                "realized_return": None,
            }
        )
    decision_events = [event for event in events if event["event_type"] == "decision"]
    for order in result.order_trace:
        candidates = [
            event
            for event in decision_events
            if event["instrument_id"] == order.instrument_id and event["ts"] < order.ts
        ]
        parent = max(candidates, key=lambda event: event["ts"])["_key"] if candidates else None
        decision_sequence_id = int(parent.split(":", maxsplit=1)[1]) if parent else None
        order_rows.append(
            {
                "sequence_id": order.sequence_id,
                "decision_sequence_id": decision_sequence_id,
                "ts": order.ts,
                "instrument_id": order.instrument_id,
                "side": order.side,
                "quantity": order.quantity,
                "filled_quantity": order.filled_quantity,
                "status": order.status,
            }
        )
        events.append(
            {
                "_key": f"order:{order.sequence_id}",
                "_parent": parent,
                "event_type": "order",
                "ts": order.ts,
                "instrument_id": order.instrument_id,
                "side": order.side,
                "quantity": order.quantity,
                "filled_quantity": order.filled_quantity,
                "price": None,
                "status": order.status,
                "signal": None,
                "decision_reason": None,
                "entry_ts": None,
                "exit_ts": None,
                "entry_price": None,
                "exit_price": None,
                "realized_pnl": None,
                "realized_return": None,
            }
        )
    for fill in result.fill_trace:
        fill_rows.append(
            {
                "sequence_id": fill.sequence_id,
                "order_sequence_id": fill.order_sequence_id,
                "ts": fill.ts,
                "instrument_id": fill.instrument_id,
                "side": fill.side,
                "quantity": fill.quantity,
                "price": fill.price,
            }
        )
        events.append(
            {
                "_key": f"fill:{fill.sequence_id}",
                "_parent": f"order:{fill.order_sequence_id}",
                "event_type": "fill",
                "ts": fill.ts,
                "instrument_id": fill.instrument_id,
                "side": fill.side,
                "quantity": fill.quantity,
                "filled_quantity": fill.quantity,
                "price": fill.price,
                "status": None,
                "signal": None,
                "decision_reason": None,
                "entry_ts": None,
                "exit_ts": None,
                "entry_price": None,
                "exit_price": None,
                "realized_pnl": None,
                "realized_return": None,
            }
        )
    fill_events = [event for event in events if event["event_type"] == "fill"]
    for index, trade in enumerate(
        sorted(result.trades, key=lambda item: (item.exit_ts, item.entry_ts, item.instrument_id)),
        start=1,
    ):
        exit_side = "SELL" if trade.side == "BUY" else "BUY"
        candidates = [
            event
            for event in fill_events
            if event["instrument_id"] == trade.instrument_id
            and event["ts"] == trade.exit_ts
            and event["side"] == exit_side
        ]
        parent = candidates[0]["_key"] if candidates else None
        events.append(
            {
                "_key": f"trade:{index}",
                "_parent": parent,
                "event_type": "trade",
                "ts": trade.exit_ts,
                "instrument_id": trade.instrument_id,
                "side": trade.side,
                "quantity": trade.quantity,
                "filled_quantity": None,
                "price": trade.exit_price,
                "status": "CLOSED",
                "signal": None,
                "decision_reason": None,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "realized_pnl": trade.realized_pnl,
                "realized_return": trade.realized_return,
            }
        )
    rank = {"decision": 0, "order": 1, "fill": 2, "trade": 3}
    events.sort(key=lambda event: (event["ts"], rank[event["event_type"]], event["_key"]))
    sequence_by_key = {event["_key"]: index for index, event in enumerate(events, start=1)}
    rows = [
        {
            "sequence_id": sequence_by_key[event["_key"]],
            "event_type": event["event_type"],
            "ts": event["ts"],
            "parent_sequence_id": sequence_by_key.get(event["_parent"]),
            **{
                key: value
                for key, value in event.items()
                if not key.startswith("_") and key not in {"event_type", "ts"}
            },
        }
        for event in events
    ]
    decision_frame = (
        pl.DataFrame(decision_rows, schema=_DECISION_TRACE_SCHEMA)
        if decision_rows
        else pl.DataFrame(schema=_DECISION_TRACE_SCHEMA)
    )
    order_frame = (
        pl.DataFrame(order_rows, schema=_ORDER_TRACE_SCHEMA)
        if order_rows
        else pl.DataFrame(schema=_ORDER_TRACE_SCHEMA)
    )
    fill_frame = (
        pl.DataFrame(fill_rows, schema=_FILL_TRACE_SCHEMA)
        if fill_rows
        else pl.DataFrame(schema=_FILL_TRACE_SCHEMA)
    )
    decision_ids = {(row["ts"], row["instrument_id"]): row["sequence_id"] for row in decision_rows}
    indicator_rows = [
        {
            "sequence_id": index,
            "decision_sequence_id": decision_ids.get((indicator.ts, indicator.instrument_id)),
            "ts": indicator.ts,
            "instrument_id": indicator.instrument_id,
            "name": indicator.name,
            "value": indicator.value,
            "unit": indicator.unit,
        }
        for index, indicator in enumerate(
            sorted(
                result.indicator_trace,
                key=lambda item: (item.ts, item.instrument_id, item.name),
            ),
            start=1,
        )
    ]
    annotation_rows: list[dict[str, Any]] = []
    annotations = sorted(
        result.chart_annotations,
        key=lambda item: (item.decision_ts, item.instrument_id, item.kind, item.label),
    )
    for annotation_id, annotation in enumerate(annotations, start=1):
        for anchor_index, anchor in enumerate(annotation.anchors):
            annotation_rows.append(
                {
                    "annotation_id": annotation_id,
                    "decision_sequence_id": decision_ids.get(
                        (annotation.decision_ts, annotation.instrument_id)
                    ),
                    "kind": annotation.kind,
                    "label": annotation.label,
                    "unit": annotation.unit,
                    "reason": annotation.reason,
                    "anchor_index": anchor_index,
                    "ts": anchor.ts,
                    "value": anchor.value,
                }
            )
    indicator_frame = (
        pl.DataFrame(indicator_rows, schema=_INDICATOR_TRACE_SCHEMA)
        if indicator_rows
        else pl.DataFrame(schema=_INDICATOR_TRACE_SCHEMA)
    )
    annotation_frame = (
        pl.DataFrame(annotation_rows, schema=_ANNOTATION_TRACE_SCHEMA)
        if annotation_rows
        else pl.DataFrame(schema=_ANNOTATION_TRACE_SCHEMA)
    )
    frame = pl.DataFrame(rows, schema=_TRACE_SCHEMA) if rows else pl.DataFrame(schema=_TRACE_SCHEMA)
    publish_artifact(rdir / "decision_trace.parquet", decision_frame.write_parquet)
    publish_artifact(rdir / "orders.parquet", order_frame.write_parquet)
    publish_artifact(rdir / "fills.parquet", fill_frame.write_parquet)
    publish_artifact(rdir / "execution_trace.parquet", frame.write_parquet)
    publish_artifact(rdir / "indicator_series.parquet", indicator_frame.write_parquet)
    publish_artifact(rdir / "chart_annotations.parquet", annotation_frame.write_parquet)


def write_manifest(rdir: Path, manifest: dict[str, Any]) -> None:
    """Publish an immutable v3 completion marker after hashing every deterministic sidecar."""
    _validate_identity_fields(manifest)
    complete = dict(manifest)
    complete["schema_version"] = MANIFEST_SCHEMA_VERSION
    complete["artifact_contract_version"] = ARTIFACT_CONTRACT_VERSION
    complete["artifacts"] = _artifact_contract(rdir)
    required = _REQUIRED_PARQUET.get(str(complete.get("command")), ())
    missing = sorted(set(required) - set(complete["artifacts"]))
    if missing:
        raise DataError(f"cannot publish incomplete run {rdir}: missing artifacts {missing}")
    verify_manifest_artifacts(rdir, complete)
    text = json.dumps(complete, indent=2, sort_keys=True, allow_nan=False)
    path = rdir / "manifest.json"
    if path.exists():
        existing = read_manifest(rdir)
        if existing == complete:
            return
        raise DataError(f"immutable manifest {path} already exists with different content")
    fd, raw_tmp = tempfile.mkstemp(prefix=".manifest.json.", suffix=".tmp", dir=rdir)
    os.close(fd)
    tmp = Path(raw_tmp)
    try:
        tmp.write_text(text, encoding="utf-8")
        try:
            os.link(tmp, path)
        except FileExistsError:
            existing = read_manifest(rdir)
            if existing != complete:
                raise DataError(
                    f"immutable manifest {path} was concurrently published with different content"
                ) from None
    finally:
        tmp.unlink(missing_ok=True)


def read_manifest(rdir: Path) -> dict[str, Any]:
    """Load a run's ``manifest.json`` back into a dict."""
    path = rdir / "manifest.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise DataError(f"corrupt run manifest at {path}") from exc
    if not isinstance(raw, dict):
        raise DataError(f"invalid run manifest at {path}: expected a JSON object")
    result: dict[str, Any] = raw
    verify_manifest_artifacts(rdir, result)
    return result


def read_equity(rdir: Path) -> list[tuple[datetime, float]]:
    """Load a run's ``equity_curve.parquet`` back into ``(timestamp, equity)`` pairs (ts order).

    The symmetric reader for :func:`write_run`'s equity column — used by ``alpha propfirm
    --from-run`` to recover a prior run's return stream without re-running the engine. Fails loud
    (``DataError``) if the run has no equity curve (e.g. an optim/portfolio run).
    """
    path = rdir / "equity_curve.parquet"
    if not path.exists():
        raise DataError(f"run at {rdir} has no equity_curve.parquet")
    frame = pl.read_parquet(path)
    return list(zip(frame["ts"].to_list(), frame["equity"].to_list(), strict=True))

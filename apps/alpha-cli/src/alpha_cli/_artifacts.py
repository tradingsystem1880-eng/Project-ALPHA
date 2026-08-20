"""Run-artifact layout: ``data_dir/runs/<run_id>/`` with a JSON manifest + Parquet series.

The ``manifest.json`` is the byte-stable reproducibility artifact (sorted keys, ``allow_nan=False``
so non-finite values must already be ``null``); the equity curve and trade log ride alongside as
Parquet. Export views such as HTML are also published immutably and pinned in the artifact contract.
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import tempfile
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl

from alpha_cli._native_tearsheet import native_tearsheet_frames
from alpha_cli.artifact_contract import (
    ARTIFACT_CONTRACT_VERSION,
    MANIFEST_SCHEMA_VERSION,
    RESEARCH_PILOT_REQUIRED_ARTIFACTS,
    verify_manifest_artifacts,
)
from alpha_cli.artifact_contract import (
    artifact_contract as _artifact_contract,
)
from alpha_cli.artifact_contract import (
    sha256_file as _sha256,
)
from alpha_cli.artifact_contract import (
    validate_identity_fields as _validate_identity_fields,
)
from alpha_cli.run_store import (
    RESEARCH_GATE_OVERRIDE_WATERMARK,
)
from alpha_cli.run_store import (
    find_run_dir as find_run_dir,
)
from alpha_core import DataError
from alpha_validation import FloatArray
from alpha_validation.native_tearsheet import TradeObservation


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


def research_gate_override_identity(overridden: bool) -> dict[str, bool]:
    """Identity-payload fields for a run launched under an owner research-gate override.

    Conditional so unmarked runs keep their historical run ids, and a watermarked run is a
    DIFFERENT immutable run — the marker can never byte-conflict with, or be silently dropped
    from, an unmarked identity-matched run (spec §15, ADR-0026).
    """
    return {"research_gate_override": True} if overridden else {}


def research_gate_override_fields(overridden: bool) -> dict[str, dict[str, str]]:
    """Manifest fields recording the EXPLORATORY watermark under an overridden research gate."""
    if not overridden:
        return {}
    return {
        "research_gate": {
            "state": "overridden",
            "watermark": RESEARCH_GATE_OVERRIDE_WATERMARK,
        }
    }


if TYPE_CHECKING:
    from alpha_backtest.results import BacktestResult, Trade
    from alpha_cli._portfolio import PortfolioAllocation, PortfolioCorrelation

_NATIVE_TEARSHEET_PARQUET = (
    "calendar_returns.parquet",
    "benchmark_comparison.parquet",
    "exposure_turnover.parquet",
    "return_distribution.parquet",
    "rolling_metrics.parquet",
    "trade_statistics.parquet",
)
_REQUIRED_ARTIFACTS: dict[str, tuple[str, ...]] = {
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
    "backtest_oos": (
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
    "backtest_holdout": (
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
        "tearsheet.html",
        *_NATIVE_TEARSHEET_PARQUET,
    ),
    "backtest_portfolio": (
        "equity_curve.parquet",
        "tearsheet.html",
        "portfolio_allocations.parquet",
        "correlations.parquet",
        *_NATIVE_TEARSHEET_PARQUET,
    ),
    "cross_sectional": (
        "equity_curve.parquet",
        "tearsheet.html",
        *_NATIVE_TEARSHEET_PARQUET,
    ),
    "backtest_cross_sectional": (
        "equity_curve.parquet",
        "tearsheet.html",
        *_NATIVE_TEARSHEET_PARQUET,
    ),
    "optim_grid": ("trials.parquet", "trial_ledger.parquet"),
    "propfirm": ("propfirm_paths.parquet",),
    "propfirm_run": ("propfirm_paths.parquet",),
    "forecast_run": ("paths.parquet", "quantiles.parquet", "history.parquet"),
    "forecast_eval": ("origins.parquet",),
    "monte_carlo_classical": (
        "observed_oos.parquet",
        "paths.parquet",
        "path_metrics.parquet",
        "regime_diagnostics.parquet",
        "regime_emissions.parquet",
        "report.md",
    ),
    "monte_carlo_kronos": (
        "observed_oos.parquet",
        "synthetic_bars.parquet",
        "paths.parquet",
        "path_metrics.parquet",
        "model_diagnostics.json",
        "calibration_origins.parquet",
        "report.md",
    ),
    "ml_replay": (
        "equity_curve.parquet",
        "trades.parquet",
        "decision_trace.parquet",
        "orders.parquet",
        "fills.parquet",
        "execution_trace.parquet",
        "indicator_series.parquet",
        "chart_annotations.parquet",
        "ml_predictions.parquet",
        "ml_signals.parquet",
        "ml_periods.parquet",
        "folds.parquet",
        *_NATIVE_TEARSHEET_PARQUET,
    ),
    "research_pilot": RESEARCH_PILOT_REQUIRED_ARTIFACTS,
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
    gross_exposure: Sequence[float] | None = None,
    net_exposure: Sequence[float] | None = None,
    turnover: Sequence[float] | None = None,
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
        gross_exposure=gross_exposure,
        net_exposure=net_exposure,
        turnover=turnover,
    )


def write_native_tearsheet(
    rdir: Path,
    *,
    equity: Sequence[tuple[datetime, float]],
    periods_per_year: int,
    trace_result: BacktestResult | None = None,
    trades: Sequence[Trade] | None = None,
    gross_exposure: Sequence[float] | None = None,
    net_exposure: Sequence[float] | None = None,
    turnover: Sequence[float] | None = None,
) -> None:
    """Publish Python-authoritative analytics consumed by the native workstation report."""
    if trace_result is not None and any(
        value is not None for value in (gross_exposure, net_exposure, turnover)
    ):
        raise DataError("direct portfolio analytics cannot be combined with trace_result")
    benchmark_equity: list[float] | None = None
    benchmark_kind: str | None = None
    if trace_result is not None and trace_result.portfolio_state_trace:
        by_ts = {row.ts: row for row in trace_result.portfolio_state_trace}
        if len(by_ts) != len(trace_result.portfolio_state_trace):
            raise DataError("portfolio state trace has duplicate timestamps")
        starts = [ts for ts, _ in equity[:-1]]
        missing = [ts for ts in starts if ts not in by_ts]
        if missing:
            raise DataError(
                "portfolio state trace does not cover native tear-sheet interval starts: "
                + ", ".join(ts.isoformat() for ts in missing[:3])
            )
        gross_exposure = [by_ts[ts].gross_exposure for ts in starts]
        net_exposure = [by_ts[ts].net_exposure for ts in starts]
        turnover = [by_ts[ts].turnover for ts in starts]
    if trace_result is not None and trace_result.benchmark_curve:
        benchmark_by_ts = dict(trace_result.benchmark_curve)
        if len(benchmark_by_ts) != len(trace_result.benchmark_curve):
            raise DataError("benchmark curve has duplicate timestamps")
        timestamps = [ts for ts, _ in equity]
        missing = [ts for ts in timestamps if ts not in benchmark_by_ts]
        if missing:
            raise DataError(
                "benchmark curve does not cover native tear-sheet equity points: "
                + ", ".join(ts.isoformat() for ts in missing[:3])
            )
        benchmark_equity = [benchmark_by_ts[ts] for ts in timestamps]
        benchmark_kind = trace_result.benchmark_kind
        if benchmark_kind is None:
            raise DataError("benchmark curve requires a benchmark_kind")
    trade_observations = (
        [
            TradeObservation(
                side=trade.side,
                realized_pnl=trade.realized_pnl,
                realized_return=trade.realized_return,
                entry_ts=trade.entry_ts,
                exit_ts=trade.exit_ts,
            )
            for trade in trades
        ]
        if trades is not None
        else None
    )
    for filename, frame in native_tearsheet_frames(
        equity,
        periods_per_year=periods_per_year,
        gross_exposure=gross_exposure,
        net_exposure=net_exposure,
        turnover=turnover,
        benchmark_equity=benchmark_equity,
        benchmark_kind=benchmark_kind,
        trades=trade_observations,
    ).items():
        publish_artifact(rdir / filename, frame.write_parquet)


def write_portfolio_analytics(
    rdir: Path,
    *,
    source_run_id: str,
    snapshot_id: str | None,
    snapshot_hash: str | None,
    research_cutoff: str | None,
    allocations: Sequence[PortfolioAllocation],
    correlations: Sequence[PortfolioCorrelation],
) -> None:
    """Publish exact causal sleeve allocations and aligned-OOS correlation evidence."""
    allocation_frame = pl.DataFrame(
        [
            {
                "source_run_id": source_run_id,
                "snapshot_id": snapshot_id,
                "snapshot_hash": snapshot_hash,
                "research_cutoff": research_cutoff,
                "frequency": "1d",
                "start_ts": row.start_ts,
                "ts": row.ts,
                "symbol": row.symbol,
                "weight": row.weight,
                "leg_return": row.leg_return,
                "contribution": row.contribution,
                "leg_gross_exposure": row.leg_gross_exposure,
                "leg_net_exposure": row.leg_net_exposure,
                "weighted_gross_exposure": row.weighted_gross_exposure,
                "weighted_net_exposure": row.weighted_net_exposure,
            }
            for row in allocations
        ],
        schema={
            "source_run_id": pl.String(),
            "snapshot_id": pl.String(),
            "snapshot_hash": pl.String(),
            "research_cutoff": pl.String(),
            "frequency": pl.String(),
            "start_ts": pl.Datetime(time_unit="us", time_zone="UTC"),
            "ts": pl.Datetime(time_unit="us", time_zone="UTC"),
            "symbol": pl.String(),
            "weight": pl.Float64(),
            "leg_return": pl.Float64(),
            "contribution": pl.Float64(),
            "leg_gross_exposure": pl.Float64(),
            "leg_net_exposure": pl.Float64(),
            "weighted_gross_exposure": pl.Float64(),
            "weighted_net_exposure": pl.Float64(),
        },
    ).sort("ts", "symbol")
    correlation_frame = pl.DataFrame(
        [
            {
                "source_run_id": source_run_id,
                "snapshot_id": snapshot_id,
                "snapshot_hash": snapshot_hash,
                "research_cutoff": research_cutoff,
                "asset_a": row.asset_a,
                "asset_b": row.asset_b,
                "metric_name": row.metric_name,
                "metric_unit": row.metric_unit,
                "correlation": row.correlation,
                "sample_count": row.sample_count,
                "aligned_oos": row.aligned_oos,
                "frequency": row.frequency,
                "oos_start": row.oos_start,
                "oos_end": row.oos_end,
                "association_not_causation": row.association_not_causation,
            }
            for row in correlations
        ],
        schema={
            "source_run_id": pl.String(),
            "snapshot_id": pl.String(),
            "snapshot_hash": pl.String(),
            "research_cutoff": pl.String(),
            "asset_a": pl.String(),
            "asset_b": pl.String(),
            "metric_name": pl.String(),
            "metric_unit": pl.String(),
            "correlation": pl.Float64(),
            "sample_count": pl.Int64(),
            "aligned_oos": pl.Boolean(),
            "frequency": pl.String(),
            "oos_start": pl.String(),
            "oos_end": pl.String(),
            "association_not_causation": pl.Boolean(),
        },
    ).sort("asset_a", "asset_b")
    rdir.mkdir(parents=True, exist_ok=True)
    publish_artifact(rdir / "portfolio_allocations.parquet", allocation_frame.write_parquet)
    publish_artifact(rdir / "correlations.parquet", correlation_frame.write_parquet)


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


def write_trials(
    rdir: Path,
    *,
    matrix: FloatArray,
    trial_indices: Sequence[int] | None = None,
) -> None:
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
    indices = list(range(n_configs)) if trial_indices is None else list(trial_indices)
    if len(indices) != n_configs:
        raise DataError(
            f"trial index count {len(indices)} does not match matrix columns {n_configs}"
        )
    if len(set(indices)) != len(indices) or any(index < 0 for index in indices):
        raise DataError("trial indices must be unique non-negative integers")
    frame = pl.DataFrame(
        {
            "trial": np.repeat(np.asarray(indices, dtype=np.int64), n_oos),
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
        write_native_tearsheet(
            rdir,
            equity=equity,
            periods_per_year=periods_per_year,
            trace_result=trace_result,
            trades=trades,
        )
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
    # A decision's artifact identifier is its position in the one canonical causal sequence, not
    # its earlier position in the decision-only list.  The two positions diverge as soon as an
    # order/fill is interleaved before a later decision.  Remap every decision reference only after
    # the consolidated sequence is final so all sidecars and projections share one immutable id.
    decision_global_ids = {
        local_id: sequence_by_key[f"decision:{local_id}"]
        for local_id in range(1, len(decision_rows) + 1)
    }
    for row in decision_rows:
        row["sequence_id"] = decision_global_ids[int(row["sequence_id"])]
    for row in order_rows:
        local_id = row["decision_sequence_id"]
        if local_id is not None:
            row["decision_sequence_id"] = decision_global_ids[int(local_id)]
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
    if len(decision_ids) != len(decision_rows):
        raise DataError(
            "causal decision evidence is ambiguous: duplicate decision timestamp/instrument"
        )
    evidence_keys = {
        (indicator.ts, indicator.instrument_id) for indicator in result.indicator_trace
    } | {
        (annotation.decision_ts, annotation.instrument_id)
        for annotation in result.chart_annotations
    }
    if missing := evidence_keys.difference(decision_ids):
        raise DataError(f"causal evidence has no matching decision: {sorted(missing)!r}")
    indicator_rows = [
        {
            "sequence_id": index,
            "decision_sequence_id": decision_ids[(indicator.ts, indicator.instrument_id)],
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
                    "decision_sequence_id": decision_ids[
                        (annotation.decision_ts, annotation.instrument_id)
                    ],
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
    from alpha_cli.run_context import run_context_from_environment

    run_context = run_context_from_environment()
    if run_context is not None:
        supplied_context = manifest.get("run_context")
        if supplied_context is not None and supplied_context != run_context:
            raise DataError("manifest run context differs from the authenticated child context")
        manifest = {**manifest, "run_context": run_context}
    _validate_identity_fields(manifest)
    # Compare the same JSON-domain value that is persisted.  In-memory specs legitimately carry
    # tuples (for example normalized strategy parameters); after the first read those values are
    # JSON lists, so comparing the raw Python containers would reject an otherwise byte-identical
    # rerun under the same identity.
    normalized = sanitize(manifest)
    if not isinstance(normalized, dict):  # defensive: the public input is typed as a mapping
        raise DataError("run manifest must normalize to an object")
    complete = normalized
    complete["schema_version"] = MANIFEST_SCHEMA_VERSION
    complete["artifact_contract_version"] = ARTIFACT_CONTRACT_VERSION
    complete["artifacts"] = _artifact_contract(rdir)
    required = _REQUIRED_ARTIFACTS.get(str(complete.get("command")), ())
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

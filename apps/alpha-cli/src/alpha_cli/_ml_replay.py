"""Compose validated worker predictions with ALPHA's synchronized portfolio execution seam."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from alpha_backtest.portfolio_replay import PortfolioReplayResult, WeightTarget, run_weight_replay
from alpha_cli import _artifacts, _runner
from alpha_cli.ml_contract import (
    ValidatedResult,
    replay_signal_frame,
    sha256_file,
    validate_result_bundle,
)
from alpha_core import Bar, DataError
from alpha_validation import (
    annualized_volatility,
    cagr,
    deflated_sharpe,
    max_drawdown,
    sharpe_ratio,
)

REPLAY_LABEL = "OOS replay validated — model not recomputed under counterfactual"


@dataclass(frozen=True, slots=True)
class MlReplayRun:
    """One immutable canonical ML replay and its authoritative manifest."""

    run_id: str
    run_dir: Path
    manifest: dict[str, Any]


def _bars(validated: ValidatedResult) -> dict[str, list[Bar]]:
    result: dict[str, list[Bar]] = {symbol: [] for symbol in validated.request.universe}
    for row in validated.request.panel.iter_rows(named=True):
        result[row["symbol"]].append(
            Bar(
                symbol=row["symbol"],
                ts=row["session_ts"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
        )
    return result


def _targets(signals: pl.DataFrame) -> list[WeightTarget]:
    return [
        WeightTarget(
            symbol=row["symbol"],
            origin_ts=row["origin_ts"],
            available_at=row["available_at"],
            target_ts=row["entry_ts"],
            target_weight=row["target_weight"],
            score=row["score"],
            fold=row["fold"],
        )
        for row in signals.iter_rows(named=True)
    ]


def _metrics(result: PortfolioReplayResult, *, periods_per_year: int) -> dict[str, float | None]:
    returns = np.array([period.net_return for period in result.periods], dtype=np.float64)
    equity = np.array([value for _, value in result.backtest.equity_curve], dtype=np.float64)
    gross_equity = float(np.prod([1.0 + period.gross_return for period in result.periods]))
    benchmark_equity = float(np.prod([1.0 + period.benchmark_return for period in result.periods]))
    metrics: dict[str, float | None] = {
        "total_return": float(equity[-1] / equity[0] - 1.0),
        "gross_total_return": gross_equity - 1.0,
        "benchmark_total_return": benchmark_equity - 1.0,
        "costed_excess_total_return": float(equity[-1] / equity[0] - benchmark_equity),
        "max_drawdown": max_drawdown(equity),
        "mean_turnover": float(np.mean([period.turnover for period in result.periods])),
        "total_fees": float(sum(period.fees for period in result.periods)),
        "total_slippage_cost": float(sum(period.slippage_cost for period in result.periods)),
        "sharpe": None,
        "annualized_volatility": None,
        "cagr": cagr(equity, periods_per_year=periods_per_year),
        "psr": None,
        "dsr": None,
    }
    if returns.size >= 2 and float(np.std(returns, ddof=1)) > 0.0:
        metrics["sharpe"] = sharpe_ratio(returns, periods_per_year=periods_per_year)
        metrics["annualized_volatility"] = annualized_volatility(
            returns, periods_per_year=periods_per_year
        )
        dsr = deflated_sharpe(returns)
        metrics["psr"] = dsr.psr
        metrics["dsr"] = dsr.dsr
    return metrics


def _period_frame(result: PortfolioReplayResult) -> pl.DataFrame:
    return pl.DataFrame(
        [dataclasses.asdict(period) for period in result.periods],
        schema={
            "fold": pl.Int64,
            "target_ts": pl.Datetime("us", "UTC"),
            "exit_ts": pl.Datetime("us", "UTC"),
            "gross_return": pl.Float64,
            "net_return": pl.Float64,
            "benchmark_return": pl.Float64,
            "excess_return": pl.Float64,
            "turnover": pl.Float64,
            "fees": pl.Float64,
            "slippage_cost": pl.Float64,
        },
    )


def _fold_frame(validated: ValidatedResult) -> pl.DataFrame:
    rows = [
        {
            "fold": fold["fold"],
            "train_start": datetime.fromisoformat(fold["train_start"]),
            "train_end": datetime.fromisoformat(fold["train_end"]),
            "validation_start": datetime.fromisoformat(fold["validation_start"]),
            "validation_end": datetime.fromisoformat(fold["validation_end"]),
            "test_start": datetime.fromisoformat(fold["test_start"]),
            "test_end": datetime.fromisoformat(fold["test_end"]),
        }
        for fold in validated.request.request["folds"]
    ]
    utc = pl.Datetime("us", "UTC")
    return pl.DataFrame(
        rows,
        schema={
            "fold": pl.Int64,
            "train_start": utc,
            "train_end": utc,
            "validation_start": utc,
            "validation_end": utc,
            "test_start": utc,
            "test_end": utc,
        },
    )


def _source_fingerprint(validated: ValidatedResult, exchange_dir: Path) -> str:
    payload = {
        "snapshot_hash": validated.request.request["snapshot_hash"],
        "panel_sha256": validated.request.request["panel"]["sha256"],
        "predictions_sha256": sha256_file(exchange_dir / "predictions.parquet"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(
        b"project-alpha-ml-replay-source-v1\0" + canonical.encode("utf-8")
    ).hexdigest()


def run_ml_replay(
    exchange_dir: Path,
    *,
    data_dir: Path,
    starting_cash: float = 1_000_000.0,
    periods_per_year: int = 252,
    research_cutoff: datetime | None = None,
) -> MlReplayRun:
    """Validate, execute, score, and immutably publish one OOS ML replay."""
    if periods_per_year < 1:
        raise DataError(f"periods_per_year must be >= 1, got {periods_per_year}")
    exchange_dir = Path(exchange_dir)
    validated = validate_result_bundle(exchange_dir)
    cutoff_text: str | None = None
    if research_cutoff is not None:
        offset = research_cutoff.utcoffset()
        if research_cutoff.tzinfo is None or offset is None or offset.total_seconds() != 0:
            raise DataError("ML research cutoff must be timezone-aware UTC")
        cutoff_text = research_cutoff.date().isoformat()
        if validated.request.sessions[-1] > research_cutoff:
            raise DataError("ML input panel contains sessions after the research cutoff")
    signals = replay_signal_frame(exchange_dir)
    if signals.is_empty():
        raise DataError("validated worker result contains no test predictions to replay")
    costs = validated.request.request["costs"]
    replay = run_weight_replay(
        _bars(validated),
        _targets(signals),
        starting_cash=starting_cash,
        fee_bps=float(costs["fee_bps"]),
        slippage_bps=float(costs["slippage_bps"]),
    )
    metrics = _metrics(replay, periods_per_year=periods_per_year)
    predictions_sha = sha256_file(exchange_dir / "predictions.parquet")
    result_sha = sha256_file(exchange_dir / "result.json")
    request = validated.request.request
    identity = _runner.run_identity_for(
        {
            "command": "ml_replay",
            "snapshot_hash": request["snapshot_hash"],
            "config_hash": request["config_hash"],
            "worker_lock_hash": request["worker_lock_hash"],
            "predictions_sha256": predictions_sha,
            "worker_result_sha256": result_sha,
            "starting_cash": starting_cash,
            "periods_per_year": periods_per_year,
            "seed": request["seed"],
            "costs": costs,
            "research_cutoff": cutoff_text,
        },
        source_fingerprint=_source_fingerprint(validated, exchange_dir),
    )
    run_id = identity.run_id
    rdir = _artifacts.run_dir(data_dir, run_id)
    _artifacts.write_run_sidecars(
        rdir,
        equity=replay.backtest.equity_curve,
        trades=replay.backtest.trades,
        trace_result=replay.backtest,
        periods_per_year=periods_per_year,
    )
    _artifacts.publish_artifact(
        rdir / "ml_predictions.parquet", validated.predictions.write_parquet
    )
    _artifacts.publish_artifact(rdir / "ml_signals.parquet", signals.write_parquet)
    _artifacts.publish_artifact(rdir / "ml_periods.parquet", _period_frame(replay).write_parquet)
    _artifacts.publish_artifact(rdir / "folds.parquet", _fold_frame(validated).write_parquet)

    reconciliation = replay.reconciled_order_fills()
    manifest: dict[str, Any] = {
        "schema_version": 3,
        "run_id": run_id,
        "command": "ml_replay",
        "authority": "alpha_canonical_execution_and_validation",
        "label": REPLAY_LABEL,
        "snapshot_hash": request["snapshot_hash"],
        "config_hash": request["config_hash"],
        "worker_lock_hash": request["worker_lock_hash"],
        "seed": request["seed"],
        "universe": list(validated.request.universe),
        "universe_membership": request["universe_membership"],
        "survivorship_warning": request["survivorship_warning"],
        "portfolio": request["portfolio"],
        "costs": costs,
        "research_cutoff": cutoff_text,
        "starting_cash": starting_cash,
        "periods_per_year": periods_per_year,
        "n_oos_periods": len(replay.periods),
        "orders": replay.backtest.orders,
        "fills": replay.backtest.fills,
        "rejected": replay.backtest.rejected,
        "n_trades": len(replay.backtest.trades),
        "starting_equity": replay.backtest.starting_equity,
        "final_equity": replay.backtest.final_equity,
        "metrics": metrics,
        "worker": validated.result["worker"],
        "model_hashes": sorted(validated.predictions.get_column("model_hash").unique().to_list()),
        "source_artifacts": {
            "request_sha256": sha256_file(exchange_dir / "request.json"),
            "worker_result_sha256": result_sha,
            "predictions_sha256": predictions_sha,
            "panel_sha256": request["panel"]["sha256"],
        },
        "validation": {
            "status": "warning",
            "execution_reconciled": len(reconciliation) == replay.backtest.fills,
            "close_t_open_t_plus_1": all(order.ts < fill.ts for order, fill in reconciliation),
            "finite_oos_returns": all(
                math.isfinite(period.net_return) for period in replay.periods
            ),
            "counterfactual_refit": False,
            "null_validation": "not_run_model_not_recomputed_under_counterfactual",
            "promotion_eligible": False,
        },
        **identity.manifest_fields(),
    }
    _artifacts.write_manifest(rdir, _artifacts.sanitize(manifest))
    return MlReplayRun(run_id=run_id, run_dir=rdir, manifest=_artifacts.read_manifest(rdir))

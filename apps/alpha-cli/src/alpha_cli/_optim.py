"""Parameter optimization wired to the overfitting-aware gates (spec §8 note on PBO/DSR).

A sweep that just reports the best Sharpe is the textbook way to overfit. This module runs a grid of
configurations through the *same* engine + walk-forward OOS the gauntlet uses, assembles their OOS
return streams into a ``(T × S)`` performance matrix, and judges the selection with the gates that
only become meaningful once you have many trials:

- **Deflated Sharpe** of the selected config, deflated against the variance of *all* trial Sharpes;
- **PBO** (CSCV) — the probability the in-sample winner is below the OOS median;
- **White's Reality Check / Hansen's SPA** — does the best config beat the data-snooping null?

Because every valid config shares the same ``train_size``/``test_size``/``embargo`` and bar series,
its walk-forward test windows tile identically. Invalid, failed, and rejected configurations remain
in an ordered trial ledger; aggregate statistics use only successful, aligned OOS streams. Engine
work uses a spawn pool (nautilus is fork-unsafe) while preserving declared order and determinism.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from itertools import product
from pathlib import Path
from typing import Any, Literal

import numpy as np
import polars as pl

from alpha_cli._runner import RunSpec, fresh_oos_execution
from alpha_core import Bar, CorporateAction, DataError
from alpha_validation import (
    DataSnoopingResult,
    DeflatedSharpeResult,
    FloatArray,
    PBOResult,
    deflated_sharpe,
    probability_of_backtest_overfitting,
    reality_check,
    sharpe_ratio,
    spa_test,
)

_SERIAL_THRESHOLD = 8  # below this many configs the pool's spin-up costs more than it saves
_INT_FIELDS = frozenset({"lookback", "skip", "vol_window", "rebalance_every"})
_FLOAT_FIELDS = frozenset({"target_vol", "max_leverage"})

Config = tuple[tuple[str, float], ...]  # sorted (name, value) pairs — one swept configuration
TrialStatus = Literal["passed", "failed", "pruned", "rejected"]

_TRIAL_LEDGER_SCHEMA: dict[str, pl.DataType] = {
    "trial": pl.Int64(),
    "status": pl.String(),
    "config_json": pl.String(),
    "config_fingerprint": pl.String(),
    "error": pl.String(),
    "annualized_sharpe": pl.Float64(),
    "n_oos": pl.Int64(),
    "oos_returns": pl.List(pl.Float64()),
}


@dataclass(frozen=True)
class TrialOutcome:
    """One declared optimization trial, including negative and rejected results."""

    trial_index: int
    config: Config
    config_fingerprint: str
    status: TrialStatus
    error: str | None
    oos_returns: tuple[float, ...]
    annualized_sharpe: float | None


@dataclass(frozen=True)
class OptimResult:
    """The overfitting-aware verdict for a parameter sweep."""

    best_config: Config | None
    best_sharpe: float | None  # annualized OOS Sharpe of the selected config
    n_configs: int
    n_successful_configs: int
    n_oos: int
    dsr: DeflatedSharpeResult | None  # deflated Sharpe of the best config vs successful trials
    pbo: PBOResult | None
    reality_check: DataSnoopingResult | None
    spa: DataSnoopingResult | None
    configs: tuple[Config, ...]
    # annualized OOS Sharpe per declared config; negative outcomes carry NaN and sanitize to null
    sharpes: FloatArray
    passed: bool  # DSR, PBO and SPA all pass — the selection is not just snooping
    # the aligned OOS matrix for successful trials only; column order is identified explicitly by
    # successful_trial_indices and persisted by the CLI with the original declared trial indices
    oos_matrix: FloatArray
    successful_trial_indices: tuple[int, ...]
    outcomes: tuple[TrialOutcome, ...]
    analysis_error: str | None


def expand_grid(grid: Mapping[str, Sequence[float]]) -> list[Config]:
    """Cartesian product of a parameter grid into sorted ``(name, value)`` configurations."""
    if not grid:
        raise DataError("optimization grid is empty")
    names = sorted(grid)
    for name in names:
        if len(grid[name]) == 0:
            raise DataError(f"grid axis {name!r} has no values")
        normalized = [float(value) for value in grid[name]]
        if any(not np.isfinite(value) for value in normalized):
            raise DataError(f"grid axis {name!r} values must be finite")
        if len(set(normalized)) != len(normalized):
            raise DataError(f"grid axis {name!r} contains duplicate values")
    configs = [
        tuple(zip(names, (float(v) for v in combo), strict=True))
        for combo in product(*(grid[name] for name in names))
    ]
    if len(set(configs)) != len(configs):
        raise DataError("optimization grid contains duplicate normalized trials")
    return configs


def _spec_for(base: RunSpec, config: Config) -> RunSpec:
    """Apply one configuration to the base ``RunSpec`` (first-class fields or strategy_params)."""
    overrides: dict[str, Any] = {}
    extra = dict(base.strategy_params)
    for name, value in config:
        if name in _INT_FIELDS:
            if not float(value).is_integer():
                raise DataError(
                    f"grid axis {name!r} is integer-valued; {value!r} would be silently "
                    f"truncated to {int(value)} (a duplicate trial skews PBO/DSR/SPA)"
                )
            overrides[name] = int(value)
        elif name in _FLOAT_FIELDS:
            overrides[name] = float(value)
        else:
            extra[name] = float(value)
    from alpha_cli._schemas import normalize_params

    normalized = normalize_params(base.strategy_name, tuple(sorted(extra.items())))
    return replace(base, strategy_params=normalized, **overrides)


@dataclass(frozen=True)
class _ConfigTask:
    """One picklable unit of sweep work: a bar series + a fully-resolved spec."""

    bars: list[Bar]
    spec: RunSpec
    dividends: tuple[CorporateAction, ...] = ()


def _oos_returns_for(task: _ConfigTask) -> FloatArray:
    """Run one config through the engine + walk-forward and return its OOS return stream."""
    oos, _ = fresh_oos_execution(task.bars, task.spec, dividends=task.dividends)
    return oos.oos_returns


@dataclass(frozen=True)
class _TaskEvaluation:
    """Picklable worker result that preserves an execution failure as data."""

    oos_returns: tuple[float, ...]
    error: str | None


def _error_message(exc: Exception) -> str:
    """Stable one-line exception evidence suitable for manifests and Parquet."""
    detail = " ".join(str(exc).split())
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


def _evaluate_task(task: _ConfigTask) -> _TaskEvaluation:
    """Evaluate one config without letting its expected failure erase sibling results."""
    try:
        returns = np.asarray(_oos_returns_for(task), dtype=np.float64)
        if returns.ndim != 1:
            raise DataError(f"OOS returns must be one-dimensional, got shape {returns.shape}")
        if returns.size < 2:
            raise DataError(f"OOS stream too short ({returns.size}) to evaluate the trial")
        if not np.all(np.isfinite(returns)):
            raise DataError("OOS returns contain non-finite values")
    except Exception as exc:
        return _TaskEvaluation(oos_returns=(), error=_error_message(exc))
    return _TaskEvaluation(
        oos_returns=tuple(float(value) for value in returns.tolist()),
        error=None,
    )


def _safe_period_sharpe(returns: FloatArray) -> float:
    sd = float(np.std(returns, ddof=1)) if returns.size >= 2 else 0.0
    return float(np.mean(returns)) / sd if sd > 0.0 else 0.0


def _annualized_sharpe(returns: FloatArray, periods_per_year: int) -> float:
    if returns.size >= 2 and float(np.std(returns, ddof=1)) > 0.0:
        return sharpe_ratio(returns, periods_per_year=periods_per_year)
    return 0.0


def run_optimization(
    bars: Sequence[Bar],
    base_spec: RunSpec,
    grid: Mapping[str, Sequence[float]],
    *,
    pbo_blocks: int = 10,
    n_resamples: int = 2000,
    mean_block: float = 5.0,
    dsr_threshold: float = 0.95,
    alpha: float = 0.05,
    seed: int | None = 7,
    max_workers: int | None = None,
    dividends: Sequence[CorporateAction] = (),
    data_dir: Path | None = None,
) -> OptimResult:
    """Run every declared trial and return its complete ledger plus aggregate verdict."""
    if base_spec.size_on_equity or base_spec.halt_drawdown is not None:
        raise DataError(
            "size_on_equity / halt_drawdown are not supported by the optimizer (see the "
            "gauntlet's Tier-1 fidelity constraint)"
        )
    configs = expand_grid(grid)
    outcomes_by_index: dict[int, TrialOutcome] = {}
    runnable: list[tuple[int, Config, _ConfigTask]] = []
    for trial_index, config in enumerate(configs):
        try:
            spec = _spec_for(base_spec, config)
        except DataError as exc:
            outcomes_by_index[trial_index] = _negative_outcome(
                trial_index, config, "rejected", _error_message(exc)
            )
            continue
        if base_spec.train_size < spec.min_train:
            error = (
                f"DataError: train_size {base_spec.train_size} < warmup floor {spec.min_train} "
                "for this config"
            )
            outcomes_by_index[trial_index] = _negative_outcome(
                trial_index, config, "rejected", error
            )
            continue
        if base_spec.strategy_name == "kronos":
            # Cache preparation stays in the parent; a preparation failure belongs to this trial.
            try:
                if data_dir is None:
                    raise DataError(
                        "kronos optimization needs data_dir for signal-cache precompute"
                    )
                from alpha_cli._forecast_cache import prepare_spec_for_engine

                cache_seed = seed if seed is not None else 7
                spec = prepare_spec_for_engine(bars, spec, data_dir=data_dir, seed=cache_seed)[0]
            except Exception as exc:
                outcomes_by_index[trial_index] = _negative_outcome(
                    trial_index, config, "failed", _error_message(exc)
                )
                continue
        runnable.append(
            (
                trial_index,
                config,
                _ConfigTask(bars=list(bars), spec=spec, dividends=tuple(dividends)),
            )
        )

    evaluations = _run_configs([task for _, _, task in runnable], max_workers)
    for (trial_index, config, _), evaluation in zip(runnable, evaluations, strict=True):
        if evaluation.error is not None:
            outcomes_by_index[trial_index] = _negative_outcome(
                trial_index, config, "failed", evaluation.error
            )
            continue
        returns = np.asarray(evaluation.oos_returns, dtype=np.float64)
        outcomes_by_index[trial_index] = TrialOutcome(
            trial_index=trial_index,
            config=config,
            config_fingerprint=_config_fingerprint(config),
            status="passed",
            error=None,
            oos_returns=evaluation.oos_returns,
            annualized_sharpe=_annualized_sharpe(returns, base_spec.periods_per_year),
        )

    outcomes = tuple(outcomes_by_index[index] for index in range(len(configs)))
    return _analyze_outcomes(
        configs=tuple(configs),
        outcomes=outcomes,
        pbo_blocks=pbo_blocks,
        n_resamples=n_resamples,
        mean_block=mean_block,
        dsr_threshold=dsr_threshold,
        alpha=alpha,
        seed=seed,
    )


def _run_configs(tasks: list[_ConfigTask], max_workers: int | None) -> list[_TaskEvaluation]:
    """Evaluate configs in declared order while converting per-trial exceptions to data."""
    if max_workers is not None and max_workers > 1 and len(tasks) > _SERIAL_THRESHOLD:
        ctx = multiprocessing.get_context("spawn")  # nautilus/Cython is fork-unsafe
        try:
            with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as pool:
                return list(pool.map(_evaluate_task, tasks))
        except Exception as exc:
            error = f"WorkerPoolError: {_error_message(exc)}"
            return [_TaskEvaluation(oos_returns=(), error=error) for _ in tasks]
    return [_evaluate_task(task) for task in tasks]


def _config_json(config: Config) -> str:
    return json.dumps(
        [[name, float(value)] for name, value in config],
        separators=(",", ":"),
        allow_nan=False,
    )


def _config_fingerprint(config: Config) -> str:
    return hashlib.sha256(_config_json(config).encode("utf-8")).hexdigest()


def _negative_outcome(
    trial_index: int,
    config: Config,
    status: Literal["failed", "pruned", "rejected"],
    error: str,
) -> TrialOutcome:
    return TrialOutcome(
        trial_index=trial_index,
        config=config,
        config_fingerprint=_config_fingerprint(config),
        status=status,
        error=error,
        oos_returns=(),
        annualized_sharpe=None,
    )


def _analysis_failure(
    *,
    configs: tuple[Config, ...],
    outcomes: tuple[TrialOutcome, ...],
    sharpes: FloatArray,
    matrix: FloatArray,
    n_oos: int,
    successful_indices: tuple[int, ...],
    error: str,
) -> OptimResult:
    return OptimResult(
        best_config=None,
        best_sharpe=None,
        n_configs=len(configs),
        n_successful_configs=len(successful_indices),
        n_oos=n_oos,
        dsr=None,
        pbo=None,
        reality_check=None,
        spa=None,
        configs=configs,
        sharpes=sharpes,
        passed=False,
        oos_matrix=matrix,
        successful_trial_indices=successful_indices,
        outcomes=outcomes,
        analysis_error=error,
    )


def _analyze_outcomes(
    *,
    configs: tuple[Config, ...],
    outcomes: tuple[TrialOutcome, ...],
    pbo_blocks: int,
    n_resamples: int,
    mean_block: float,
    dsr_threshold: float,
    alpha: float,
    seed: int | None,
) -> OptimResult:
    """Compute selection statistics only over successful, aligned trial streams."""
    successful = tuple(outcome for outcome in outcomes if outcome.status == "passed")
    successful_indices = tuple(outcome.trial_index for outcome in successful)
    sharpes = np.full(len(configs), np.nan, dtype=np.float64)
    for outcome in successful:
        if outcome.annualized_sharpe is None:  # protected by construction and ledger validation
            raise DataError(f"successful trial {outcome.trial_index} has no Sharpe")
        sharpes[outcome.trial_index] = outcome.annualized_sharpe

    if not successful:
        return _analysis_failure(
            configs=configs,
            outcomes=outcomes,
            sharpes=sharpes,
            matrix=np.empty((0, 0), dtype=np.float64),
            n_oos=0,
            successful_indices=successful_indices,
            error=(
                "optimization analysis requires >= 2 successful aligned configs, "
                f"got 0 of {len(configs)}"
            ),
        )

    lengths = {len(outcome.oos_returns) for outcome in successful}
    if len(lengths) != 1:
        return _analysis_failure(
            configs=configs,
            outcomes=outcomes,
            sharpes=sharpes,
            matrix=np.empty((0, 0), dtype=np.float64),
            n_oos=0,
            successful_indices=successful_indices,
            error=(
                "optimization analysis requires aligned successful OOS streams, got lengths "
                f"{sorted(lengths)}"
            ),
        )

    n_oos = lengths.pop()
    matrix = np.column_stack(
        [np.asarray(outcome.oos_returns, dtype=np.float64) for outcome in successful]
    )
    if len(successful) < 2:
        return _analysis_failure(
            configs=configs,
            outcomes=outcomes,
            sharpes=sharpes,
            matrix=matrix,
            n_oos=n_oos,
            successful_indices=successful_indices,
            error=(
                "optimization analysis requires >= 2 successful aligned configs, "
                f"got {len(successful)} of {len(configs)}"
            ),
        )

    successful_sharpes = np.asarray(
        [outcome.annualized_sharpe for outcome in successful], dtype=np.float64
    )
    best_position = int(np.argmax(successful_sharpes))
    best_outcome = successful[best_position]
    best_returns = np.asarray(best_outcome.oos_returns, dtype=np.float64)
    per_period = np.asarray(
        [
            _safe_period_sharpe(np.asarray(outcome.oos_returns, dtype=np.float64))
            for outcome in successful
        ],
        dtype=np.float64,
    )
    try:
        if float(np.std(best_returns, ddof=1)) <= 0.0:
            raise DataError("the best config produced a flat OOS — no edge to optimize")
        dsr = deflated_sharpe(
            best_returns,
            trial_sharpes=per_period,
            threshold=dsr_threshold,
        )
        pbo = probability_of_backtest_overfitting(
            matrix,
            n_blocks=_even_blocks(pbo_blocks, n_oos),
        )
        rc = reality_check(
            matrix,
            n_resamples=n_resamples,
            mean_block=mean_block,
            alpha=alpha,
            seed=seed,
        )
        spa = spa_test(
            matrix,
            n_resamples=n_resamples,
            mean_block=mean_block,
            alpha=alpha,
            seed=seed,
        )
    except (DataError, ValueError) as exc:
        return _analysis_failure(
            configs=configs,
            outcomes=outcomes,
            sharpes=sharpes,
            matrix=matrix,
            n_oos=n_oos,
            successful_indices=successful_indices,
            error=" ".join(str(exc).split()),
        )

    return OptimResult(
        best_config=best_outcome.config,
        best_sharpe=best_outcome.annualized_sharpe,
        n_configs=len(configs),
        n_successful_configs=len(successful),
        n_oos=n_oos,
        dsr=dsr,
        pbo=pbo,
        reality_check=rc,
        spa=spa,
        configs=configs,
        sharpes=sharpes,
        passed=dsr.passed and pbo.passed and spa.passed,
        oos_matrix=matrix,
        successful_trial_indices=successful_indices,
        outcomes=outcomes,
        analysis_error=None,
    )


def _validate_outcome(outcome: TrialOutcome, *, expected_index: int) -> None:
    if outcome.trial_index != expected_index:
        raise DataError(
            "trial ledger must be contiguous and ordered: "
            f"expected {expected_index}, got {outcome.trial_index}"
        )
    if tuple(sorted(outcome.config)) != outcome.config:
        raise DataError(f"trial {expected_index} config keys must be sorted")
    if len({name for name, _ in outcome.config}) != len(outcome.config):
        raise DataError(f"trial {expected_index} config contains duplicate keys")
    if any(not name or not np.isfinite(value) for name, value in outcome.config):
        raise DataError(f"trial {expected_index} config must contain named finite values")
    if outcome.config_fingerprint != _config_fingerprint(outcome.config):
        raise DataError(f"trial {expected_index} config fingerprint mismatch")
    if outcome.status not in {"passed", "failed", "pruned", "rejected"}:
        raise DataError(f"trial {expected_index} has invalid status {outcome.status!r}")
    returns = np.asarray(outcome.oos_returns, dtype=np.float64)
    if returns.ndim != 1 or not np.all(np.isfinite(returns)):
        raise DataError(f"trial {expected_index} OOS returns must be a finite vector")
    if outcome.status == "passed":
        if outcome.error is not None:
            raise DataError(f"successful trial {expected_index} cannot contain an error")
        if returns.size < 2:
            raise DataError(f"successful trial {expected_index} needs at least two OOS returns")
        if outcome.annualized_sharpe is None or not np.isfinite(outcome.annualized_sharpe):
            raise DataError(f"successful trial {expected_index} needs a finite Sharpe")
    elif (
        not isinstance(outcome.error, str)
        or not outcome.error
        or returns.size
        or outcome.annualized_sharpe is not None
    ):
        raise DataError(f"negative trial {expected_index} needs an error and no returns or Sharpe")


def write_trial_ledger(rdir: Path, outcomes: Sequence[TrialOutcome]) -> None:
    """Publish one immutable, deterministic row for every declared grid configuration."""
    for expected_index, outcome in enumerate(outcomes):
        _validate_outcome(outcome, expected_index=expected_index)
    frame = pl.DataFrame(
        {
            "trial": [outcome.trial_index for outcome in outcomes],
            "status": [outcome.status for outcome in outcomes],
            "config_json": [_config_json(outcome.config) for outcome in outcomes],
            "config_fingerprint": [outcome.config_fingerprint for outcome in outcomes],
            "error": [outcome.error for outcome in outcomes],
            "annualized_sharpe": [outcome.annualized_sharpe for outcome in outcomes],
            "n_oos": [len(outcome.oos_returns) for outcome in outcomes],
            "oos_returns": [list(outcome.oos_returns) for outcome in outcomes],
        },
        schema=_TRIAL_LEDGER_SCHEMA,
    )
    from alpha_cli._artifacts import publish_artifact

    publish_artifact(rdir / "trial_ledger.parquet", frame.write_parquet)


def _config_from_json(raw: object, *, trial_index: int) -> Config:
    if not isinstance(raw, str):
        raise DataError(f"trial {trial_index} config_json must be a string")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DataError(f"trial {trial_index} config_json is invalid JSON") from exc
    if not isinstance(decoded, list):
        raise DataError(f"trial {trial_index} config_json must contain a list")
    pairs: list[tuple[str, float]] = []
    for pair in decoded:
        if not isinstance(pair, list) or len(pair) != 2:
            raise DataError(f"trial {trial_index} config_json contains an invalid pair")
        name, value = pair
        if (
            not isinstance(name, str)
            or not name
            or isinstance(value, bool)
            or not isinstance(value, int | float)
            or not np.isfinite(value)
        ):
            raise DataError(f"trial {trial_index} config_json contains an invalid value")
        pairs.append((name, float(value)))
    config = tuple(pairs)
    if _config_json(config) != raw:
        raise DataError(f"trial {trial_index} config_json is not canonical")
    return config


def read_trial_ledger(rdir: Path) -> tuple[TrialOutcome, ...]:
    """Read and strictly validate the immutable optimization attempt ledger."""
    path = rdir / "trial_ledger.parquet"
    try:
        frame = pl.read_parquet(path)
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise DataError(f"unreadable optimization trial ledger {path}") from exc
    if dict(frame.schema) != _TRIAL_LEDGER_SCHEMA:
        raise DataError(f"invalid optimization trial ledger schema at {path}: {dict(frame.schema)}")
    outcomes: list[TrialOutcome] = []
    for expected_index, row in enumerate(frame.iter_rows(named=True)):
        trial_index = row["trial"]
        if trial_index != expected_index:
            raise DataError(
                "trial ledger must be contiguous and ordered: "
                f"expected {expected_index}, got {trial_index}"
            )
        config = _config_from_json(row["config_json"], trial_index=expected_index)
        raw_returns = row["oos_returns"]
        if not isinstance(raw_returns, list):
            raise DataError(f"trial {expected_index} oos_returns must be a list")
        outcome = TrialOutcome(
            trial_index=expected_index,
            config=config,
            config_fingerprint=row["config_fingerprint"],
            status=row["status"],
            error=row["error"],
            oos_returns=tuple(float(value) for value in raw_returns),
            annualized_sharpe=row["annualized_sharpe"],
        )
        if row["n_oos"] != len(outcome.oos_returns):
            raise DataError(f"trial {expected_index} n_oos does not match its return vector")
        _validate_outcome(outcome, expected_index=expected_index)
        outcomes.append(outcome)
    if not outcomes:
        raise DataError(f"optimization trial ledger is empty at {path}")
    return tuple(outcomes)


def _even_blocks(requested: int, n_oos: int) -> int:
    """Largest even block count <= ``requested`` that fits ``n_oos`` (CSCV needs even >= 2)."""
    blocks = min(requested, n_oos)
    if blocks % 2 != 0:
        blocks -= 1
    if blocks < 2:
        raise DataError(f"too few OOS points ({n_oos}) for PBO blocks")
    return blocks

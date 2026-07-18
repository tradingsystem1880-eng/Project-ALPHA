"""Prop-firm Monte Carlo orchestration: resolve a return stream + rules, then simulate.

The CLI is the only layer the import DAG lets compose the backtest engine with the validation
primitives, so the glue lives here (mirrors ``_optim`` / ``_portfolio``). A strategy's daily return
stream comes from either a fresh inline backtest or a prior run's stored equity curve; the firm
rules come from a preset (optionally overridden flag-by-flag) or a fully custom set.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from alpha_cli import _artifacts, _runner
from alpha_core import DataError
from alpha_validation import (
    FIRM_PRESETS,
    FloatArray,
    PropFirmResult,
    PropFirmRules,
    simulate_propfirm,
    to_returns,
)

# Default custom rules (a generic 50k combine) when no --firm preset is selected; every field is
# overridable by an explicit CLI flag.
_DEFAULT_RULES = PropFirmRules(
    account_size=50_000.0,
    profit_target=3_000.0,
    max_drawdown=2_000.0,
    trailing=True,
    lock_at_profit=None,
    daily_loss_limit=None,
    min_trading_days=5,
    profit_split=0.90,
    min_payout=1_000.0,
    min_funded_days=5,
    eval_fee=0.0,
)

# CLI override flag -> PropFirmRules field; ``min_trading_days`` is the lone int field (cast below).
_OVERRIDE_FIELDS: dict[str, str] = {
    "account_size": "account_size",
    "profit_target": "profit_target",
    "max_drawdown": "max_drawdown",
    "daily_loss": "daily_loss_limit",
    "profit_split": "profit_split",
    "min_trading_days": "min_trading_days",
}


@dataclass(frozen=True)
class PropFirmRunResult:
    """A completed prop-firm run: the resolved firm/source/rules plus the simulation outcome."""

    firm: str
    source: str
    rules: PropFirmRules
    result: PropFirmResult


def resolve_rules(firm: str | None, overrides: Mapping[str, float]) -> PropFirmRules:
    """Pick the preset (or the default custom rules) and apply explicit flag overrides.

    Fails loud (``DataError``) on an unknown ``firm``. Overridden values are re-validated by
    ``PropFirmRules.__post_init__`` (e.g. a negative target or out-of-range split is rejected).
    """
    if firm is not None and firm not in FIRM_PRESETS:
        known = ", ".join(sorted(FIRM_PRESETS))
        raise DataError(f"unknown firm {firm!r}; known presets: {known}")
    base = FIRM_PRESETS[firm] if firm is not None else _DEFAULT_RULES
    if not overrides:
        return base
    changes: dict[str, Any] = {}
    for flag, value in overrides.items():
        field = _OVERRIDE_FIELDS[flag]
        changes[field] = int(value) if field == "min_trading_days" else float(value)
    return replace(base, **changes)


def trim_warmup(returns: FloatArray) -> FloatArray:
    """Drop the leading flat (all-zero) warmup span of a strategy's return stream.

    A fresh backtest's equity curve is flat until the strategy warms up and first trades;
    resampling those structural zeros into the Monte Carlo dilutes the return distribution and
    biases pass/bust/payout probabilities toward "nothing happens". Interior flat days (real
    no-position days) are kept — only the leading span goes.
    """
    nonzero = np.flatnonzero(returns != 0.0)
    return returns if nonzero.size == 0 else returns[int(nonzero[0]) :]


def _returns_from_run(data_dir: Path, run_id: str) -> FloatArray:
    """Daily returns from a prior run's stored equity curve (any ``RUN_DIRS`` run type).

    Resolves the run across every run-type subdir (backtest/validate runs, portfolio,
    cross-sectional, …) via ``find_run_dir``; ``read_equity`` still fails loud on a run type
    without a stored equity curve (e.g. optim).
    """
    rdir = _artifacts.find_run_dir(data_dir, run_id)
    if rdir is None:
        raise DataError(f"no run {run_id!r} found under {data_dir}")
    equity = _artifacts.read_equity(rdir)
    return to_returns([value for _, value in equity])


def _returns_from_backtest(
    symbol: str, spec: _runner.RunSpec, data_dir: Path, snapshot: str | None
) -> FloatArray:
    """Daily returns from a fresh full backtest of ``symbol`` (the equity curve, net of costs)."""
    bars, _ = _runner.load_bars(symbol, data_dir=data_dir, snapshot_id=snapshot)
    dividends = _runner.load_dividends(symbol, data_dir=data_dir, snapshot_id=snapshot)
    result = _runner.run_full_backtest(bars, spec, dividends=dividends)
    return to_returns([value for _, value in result.equity_curve])


def run_propfirm(
    *,
    data_dir: Path,
    symbol: str | None,
    from_run: str | None,
    spec: _runner.RunSpec,
    snapshot: str | None,
    firm: str | None,
    overrides: Mapping[str, float],
    n_paths: int,
    mean_block: float,
    seed: int | None,
    horizon_days: int | None,
) -> PropFirmRunResult:
    """Resolve the return stream + rules and run the prop-firm Monte Carlo.

    Exactly one of ``symbol`` / ``from_run`` must be set (enforced by the caller). Fails loud
    (``DataError``) on a missing run, an unknown firm, or a degenerate return stream.
    """
    if from_run is not None:
        returns: Sequence[float] | FloatArray = trim_warmup(_returns_from_run(data_dir, from_run))
        source = f"run:{from_run}"
    elif symbol is not None:
        returns = trim_warmup(_returns_from_backtest(symbol, spec, data_dir, snapshot))
        source = f"symbol:{symbol}"
    else:  # pragma: no cover - the CLI guarantees one input is set
        raise DataError("provide a SYMBOL or --from-run RUN_ID")

    rules = resolve_rules(firm, overrides)
    result = simulate_propfirm(
        returns, rules, n_paths=n_paths, mean_block=mean_block, seed=seed, horizon_days=horizon_days
    )
    return PropFirmRunResult(firm=firm or "custom", source=source, rules=rules, result=result)

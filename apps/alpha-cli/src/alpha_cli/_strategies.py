"""Strategy registry — the one place that maps a ``RunSpec.strategy_name`` to its wiring.

The engine harness (``_runner.run_full_backtest``), the Tier-2 full-engine null, and the Tier-1
surrogate all dispatch through here, so adding a strategy means registering one ``StrategyDef`` —
not editing the orchestration. Each entry supplies three pure-of-orchestration callables:

- ``warmup(spec)`` — the warmup floor (closes needed before the first scored OOS bar); pure, no
  nautilus, so ``RunSpec.min_train`` and the walk-forward splitter can use it in plain tests.
- ``build(spec, instrument_id, bar_type)`` — construct the nautilus ``Strategy`` (engine imports are
  lazy, inside the body, so importing this module never drags in nautilus).
- ``surrogate(spec)`` — the cheap engine-free analogue for the Tier-1 randomized-price null.

Per-strategy parameters that are not first-class ``RunSpec`` fields are read from
``spec.strategy_params`` via ``spec.param(name, default)`` so the spec stays a fixed, picklable
shape across every strategy.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from alpha_core import DataError
from alpha_validation import StrategyFn

if TYPE_CHECKING:
    from nautilus_trader.model.data import BarType
    from nautilus_trader.model.identifiers import InstrumentId
    from nautilus_trader.trading.strategy import Strategy

    from alpha_cli._runner import RunSpec


@dataclass(frozen=True)
class StrategyDef:
    """The three seams a strategy must provide to plug into the engine + gauntlet."""

    warmup: Callable[[RunSpec], int]
    build: Callable[[RunSpec, InstrumentId, BarType], Strategy]
    surrogate: Callable[[RunSpec], StrategyFn]


# --- ts_momentum (the v1 strategy) -------------------------------------------------------------


def _ts_momentum_warmup(spec: RunSpec) -> int:
    return max(spec.lookback + spec.skip + 1, spec.vol_window + 1)


def _ts_momentum_build(spec: RunSpec, instrument_id: InstrumentId, bar_type: BarType) -> Strategy:
    from alpha_strategies.ts_momentum import TimeSeriesMomentum

    return TimeSeriesMomentum(
        instrument_id=instrument_id,
        bar_type=bar_type,
        lookback=spec.lookback,
        skip=spec.skip,
        vol_window=spec.vol_window,
        target_vol=spec.target_vol,
        capital=spec.starting_cash,
        max_leverage=spec.max_leverage,
        rebalance_every=spec.rebalance_every,
        periods_per_year=spec.periods_per_year,
        allow_short=spec.allow_short,
    )


def _ts_momentum_surrogate(spec: RunSpec) -> StrategyFn:
    from alpha_cli._surrogate import make_ts_momentum_surrogate

    return make_ts_momentum_surrogate(
        lookback=spec.lookback,
        skip=spec.skip,
        vol_window=spec.vol_window,
        target_vol=spec.target_vol,
        rebalance_every=spec.rebalance_every,
        periods_per_year=spec.periods_per_year,
        max_leverage=spec.max_leverage,
        allow_short=spec.allow_short,
        cost_bps=spec.fee_bps + spec.slippage_bps,
    )


STRATEGIES: dict[str, StrategyDef] = {
    "ts_momentum": StrategyDef(
        warmup=_ts_momentum_warmup,
        build=_ts_momentum_build,
        surrogate=_ts_momentum_surrogate,
    ),
}


def _resolve(name: str) -> StrategyDef:
    try:
        return STRATEGIES[name]
    except KeyError:
        raise DataError(f"unknown strategy {name!r}; known: {known_strategies()}") from None


def known_strategies() -> list[str]:
    """The registered strategy names, sorted (for stable CLI help + error messages)."""
    return sorted(STRATEGIES)


def warmup_for(spec: RunSpec) -> int:
    """Warmup floor for ``spec``'s strategy (pure; safe to call without nautilus installed)."""
    return _resolve(spec.strategy_name).warmup(spec)


def build_strategy(spec: RunSpec, instrument_id: InstrumentId, bar_type: BarType) -> Strategy:
    """Construct the nautilus ``Strategy`` for ``spec`` (engine imports happen lazily inside)."""
    return _resolve(spec.strategy_name).build(spec, instrument_id, bar_type)


def surrogate_for(spec: RunSpec) -> StrategyFn:
    """Build the Tier-1 engine-free surrogate for ``spec``'s strategy."""
    return _resolve(spec.strategy_name).surrogate(spec)

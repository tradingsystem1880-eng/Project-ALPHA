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
from alpha_validation import FloatArray

if TYPE_CHECKING:
    from nautilus_trader.model.data import BarType
    from nautilus_trader.model.identifiers import InstrumentId
    from nautilus_trader.trading.strategy import Strategy

    from alpha_cli._runner import RunSpec
    from alpha_cli._surrogate import Surrogate


@dataclass(frozen=True)
class StrategyDef:
    """The seams a strategy must provide to plug into the engine + gauntlet.

    ``params`` declares the strategy-specific ``--param`` names it reads; anything else in
    ``RunSpec.strategy_params`` is a typo that would otherwise be silently ignored (results
    attributed to parameters that were never applied), so it fails loud instead.
    """

    warmup: Callable[[RunSpec], int]
    build: Callable[[RunSpec, InstrumentId, BarType], Strategy]
    surrogate: Callable[[RunSpec], Surrogate]
    params: frozenset[str] = frozenset()


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
        capital=_sizing_capital(spec),
        max_leverage=spec.max_leverage,
        rebalance_every=spec.rebalance_every,
        periods_per_year=spec.periods_per_year,
        allow_short=spec.allow_short,
        size_on_equity=spec.size_on_equity,
        halt_drawdown=spec.halt_drawdown,
    )


def _ts_momentum_surrogate(spec: RunSpec) -> Surrogate:
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


# --- ma_crossover -------------------------------------------------------------------------------


def _ma_crossover_params(spec: RunSpec) -> tuple[int, int]:
    return int(spec.param("fast", 21.0)), int(spec.param("slow", 100.0))


def _ma_crossover_warmup(spec: RunSpec) -> int:
    _, slow = _ma_crossover_params(spec)
    return max(slow, spec.vol_window + 1)


def _ma_crossover_build(spec: RunSpec, instrument_id: InstrumentId, bar_type: BarType) -> Strategy:
    from alpha_strategies.ma_crossover import MovingAverageCrossover

    fast, slow = _ma_crossover_params(spec)
    return MovingAverageCrossover(
        instrument_id=instrument_id,
        bar_type=bar_type,
        fast=fast,
        slow=slow,
        vol_window=spec.vol_window,
        target_vol=spec.target_vol,
        capital=_sizing_capital(spec),
        max_leverage=spec.max_leverage,
        rebalance_every=spec.rebalance_every,
        periods_per_year=spec.periods_per_year,
        allow_short=spec.allow_short,
        size_on_equity=spec.size_on_equity,
        halt_drawdown=spec.halt_drawdown,
    )


def _ma_crossover_surrogate(spec: RunSpec) -> Surrogate:
    from alpha_cli._surrogate import make_surrogate
    from alpha_strategies.signals import ma_crossover_signal

    fast, slow = _ma_crossover_params(spec)

    def signal_fn(closes_prefix: FloatArray) -> int:
        return ma_crossover_signal(closes_prefix[-slow:].tolist(), fast, slow)

    return make_surrogate(
        signal_fn=signal_fn,
        warmup=_ma_crossover_warmup(spec) - 1,
        vol_window=spec.vol_window,
        target_vol=spec.target_vol,
        rebalance_every=spec.rebalance_every,
        periods_per_year=spec.periods_per_year,
        max_leverage=spec.max_leverage,
        allow_short=spec.allow_short,
        cost_bps=spec.fee_bps + spec.slippage_bps,
    )


# --- mean_reversion -----------------------------------------------------------------------------


def _mean_reversion_params(spec: RunSpec) -> tuple[int, float]:
    return int(spec.param("window", 20.0)), spec.param("entry_z", 1.5)


def _mean_reversion_warmup(spec: RunSpec) -> int:
    window, _ = _mean_reversion_params(spec)
    return max(window, spec.vol_window + 1)


def _mean_reversion_build(
    spec: RunSpec, instrument_id: InstrumentId, bar_type: BarType
) -> Strategy:
    from alpha_strategies.mean_reversion import MeanReversion

    window, entry_z = _mean_reversion_params(spec)
    return MeanReversion(
        instrument_id=instrument_id,
        bar_type=bar_type,
        window=window,
        entry_z=entry_z,
        vol_window=spec.vol_window,
        target_vol=spec.target_vol,
        capital=_sizing_capital(spec),
        max_leverage=spec.max_leverage,
        rebalance_every=spec.rebalance_every,
        periods_per_year=spec.periods_per_year,
        allow_short=spec.allow_short,
        size_on_equity=spec.size_on_equity,
        halt_drawdown=spec.halt_drawdown,
    )


def _mean_reversion_surrogate(spec: RunSpec) -> Surrogate:
    from alpha_cli._surrogate import make_surrogate
    from alpha_strategies.signals import zscore_reversion_signal

    window, entry_z = _mean_reversion_params(spec)

    def signal_fn(closes_prefix: FloatArray) -> int:
        return zscore_reversion_signal(closes_prefix[-window:].tolist(), window, entry_z)

    return make_surrogate(
        signal_fn=signal_fn,
        warmup=_mean_reversion_warmup(spec) - 1,
        vol_window=spec.vol_window,
        target_vol=spec.target_vol,
        rebalance_every=spec.rebalance_every,
        periods_per_year=spec.periods_per_year,
        max_leverage=spec.max_leverage,
        allow_short=spec.allow_short,
        cost_bps=spec.fee_bps + spec.slippage_bps,
    )


# --- breakout (Donchian) ------------------------------------------------------------------------


def _breakout_window(spec: RunSpec) -> int:
    return int(spec.param("window", 55.0))


def _breakout_warmup(spec: RunSpec) -> int:
    return max(_breakout_window(spec) + 1, spec.vol_window + 1)


def _breakout_build(spec: RunSpec, instrument_id: InstrumentId, bar_type: BarType) -> Strategy:
    from alpha_strategies.breakout import DonchianBreakout

    return DonchianBreakout(
        instrument_id=instrument_id,
        bar_type=bar_type,
        window=_breakout_window(spec),
        vol_window=spec.vol_window,
        target_vol=spec.target_vol,
        capital=_sizing_capital(spec),
        max_leverage=spec.max_leverage,
        rebalance_every=spec.rebalance_every,
        periods_per_year=spec.periods_per_year,
        allow_short=spec.allow_short,
        size_on_equity=spec.size_on_equity,
        halt_drawdown=spec.halt_drawdown,
    )


def _breakout_surrogate(spec: RunSpec) -> Surrogate:
    from alpha_cli._surrogate import make_surrogate
    from alpha_strategies.signals import breakout_signal

    window = _breakout_window(spec)

    def signal_fn(closes_prefix: FloatArray) -> int:
        # Tier-1 has no synthetic intrabar range, so the channel is built from closes (Donchian on
        # closes); the Tier-2 full-engine null uses the real OHLC highs/lows for the faithful check.
        prices = closes_prefix[-window - 1 :].tolist()
        return breakout_signal(prices, prices, prices, window)

    return make_surrogate(
        signal_fn=signal_fn,
        warmup=_breakout_warmup(spec) - 1,
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
        params=frozenset(),  # its knobs (lookback/skip/...) are first-class RunSpec fields
    ),
    "ma_crossover": StrategyDef(
        warmup=_ma_crossover_warmup,
        build=_ma_crossover_build,
        surrogate=_ma_crossover_surrogate,
        params=frozenset({"fast", "slow"}),
    ),
    "mean_reversion": StrategyDef(
        warmup=_mean_reversion_warmup,
        build=_mean_reversion_build,
        surrogate=_mean_reversion_surrogate,
        params=frozenset({"window", "entry_z"}),
    ),
    "breakout": StrategyDef(
        warmup=_breakout_warmup,
        build=_breakout_build,
        surrogate=_breakout_surrogate,
        params=frozenset({"window"}),
    ),
}


def _sizing_capital(spec: RunSpec) -> float:
    """The capital handed to vol-target sizing: friction-derated on CASH accounts.

    A CASH fill consumes ``notional*(1+slippage)*(1+fee)``; when realized vol sits below
    ``target_vol`` the leverage cap sizes the FULL balance, and the frictions then tip the
    account negative - nautilus stops the backtest at that point. Reserving the friction
    headroom up front keeps the worst-case boundary fill solvent (a ~3bp sizing haircut at the
    default frictions). MARGIN accounts have buying-power headroom and are left untouched.
    """
    if spec.account_type.upper() == "MARGIN":
        return spec.starting_cash
    slip = spec.slippage_bps / 10_000.0
    fee = spec.fee_bps / 10_000.0
    return spec.starting_cash / ((1.0 + slip) * (1.0 + fee))


def _resolve(name: str) -> StrategyDef:
    try:
        return STRATEGIES[name]
    except KeyError:
        raise DataError(f"unknown strategy {name!r}; known: {known_strategies()}") from None


def _check_params(spec: RunSpec, sdef: StrategyDef) -> None:
    """Fail loud on ``--param`` names the strategy never reads (silently-ignored typos)."""
    unknown = {name for name, _ in spec.strategy_params} - sdef.params
    if unknown:
        known = sorted(sdef.params) if sdef.params else "none (all knobs are first-class flags)"
        raise DataError(
            f"unknown --param name(s) {sorted(unknown)} for strategy "
            f"{spec.strategy_name!r}; known strategy params: {known}"
        )


def known_strategies() -> list[str]:
    """The registered strategy names, sorted (for stable CLI help + error messages)."""
    return sorted(STRATEGIES)


def warmup_for(spec: RunSpec) -> int:
    """Warmup floor for ``spec``'s strategy (pure; safe to call without nautilus installed)."""
    sdef = _resolve(spec.strategy_name)
    _check_params(spec, sdef)
    return sdef.warmup(spec)


def build_strategy(spec: RunSpec, instrument_id: InstrumentId, bar_type: BarType) -> Strategy:
    """Construct the nautilus ``Strategy`` for ``spec`` (engine imports happen lazily inside)."""
    sdef = _resolve(spec.strategy_name)
    _check_params(spec, sdef)
    return sdef.build(spec, instrument_id, bar_type)


def surrogate_for(spec: RunSpec) -> Surrogate:
    """Build the Tier-1 engine-free surrogate for ``spec``'s strategy."""
    sdef = _resolve(spec.strategy_name)
    _check_params(spec, sdef)
    return sdef.surrogate(spec)

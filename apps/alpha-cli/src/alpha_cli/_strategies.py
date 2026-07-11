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
from alpha_validation import FloatArray, StrategyFn

if TYPE_CHECKING:
    from collections.abc import Sequence

    from nautilus_trader.model.data import BarType
    from nautilus_trader.model.identifiers import InstrumentId
    from nautilus_trader.trading.strategy import Strategy

    from alpha_cli._runner import RunSpec
    from alpha_core import Bar


@dataclass(frozen=True)
class StrategyDef:
    """The three seams a strategy must provide to plug into the engine + gauntlet.

    ``surrogate`` may be ``None`` for strategies with no honest engine-free analogue (e.g. a
    foundation-model forecaster: replaying it inside a 1000-path null is computationally
    impossible, and a cheap proxy would Tier-1-test a *different* strategy). The gauntlet then
    records Tier-1 as skipped-with-reason and gates the null on Tier-2 alone.
    """

    warmup: Callable[[RunSpec], int]
    build: Callable[[RunSpec, InstrumentId, BarType], Strategy]
    surrogate: Callable[[RunSpec], StrategyFn] | None


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
        capital=spec.starting_cash,
        max_leverage=spec.max_leverage,
        rebalance_every=spec.rebalance_every,
        periods_per_year=spec.periods_per_year,
        allow_short=spec.allow_short,
    )


def _ma_crossover_surrogate(spec: RunSpec) -> StrategyFn:
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
        capital=spec.starting_cash,
        max_leverage=spec.max_leverage,
        rebalance_every=spec.rebalance_every,
        periods_per_year=spec.periods_per_year,
        allow_short=spec.allow_short,
    )


def _mean_reversion_surrogate(spec: RunSpec) -> StrategyFn:
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
        capital=spec.starting_cash,
        max_leverage=spec.max_leverage,
        rebalance_every=spec.rebalance_every,
        periods_per_year=spec.periods_per_year,
        allow_short=spec.allow_short,
    )


def _breakout_surrogate(spec: RunSpec) -> StrategyFn:
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


# --- kronos_forecast (foundation-model forecaster; alpha_forecast is composed in here) ----------


_KRONOS_MODELS = ("mini", "small", "base")  # float param model=0|1|2 indexes this tuple


@dataclass(frozen=True)
class KronosParams:
    """The kronos_forecast per-strategy params decoded from ``spec.strategy_params``."""

    model: str
    context: int
    horizon: int
    deadband_bps: float
    temperature: float
    top_p: float
    sample_count: int


def _kronos_params(spec: RunSpec) -> KronosParams:
    idx = int(spec.param("model", 2.0))  # default 2 -> Kronos-base (user decision)
    if idx not in (0, 1, 2):
        raise DataError(
            f"kronos_forecast param model={idx} is invalid; use 0=mini, 1=small, 2=base"
        )
    model = _KRONOS_MODELS[idx]
    context = int(spec.param("context", 400.0))
    from alpha_forecast import resolve_model  # torch-free module of alpha_forecast

    max_context = resolve_model(model).max_context
    if not 2 <= context <= max_context:
        raise DataError(
            f"kronos_forecast param context={context} out of range [2, {max_context}] "
            f"for Kronos-{model}"
        )
    horizon = int(spec.param("horizon", 30.0))
    if horizon < 1:
        raise DataError(f"kronos_forecast param horizon={horizon} must be >= 1")
    return KronosParams(
        model=model,
        context=context,
        horizon=horizon,
        deadband_bps=spec.param("deadband", 25.0),
        temperature=spec.param("temperature", 1.0),
        top_p=spec.param("top_p", 0.9),
        sample_count=int(spec.param("sample_count", 1.0)),
    )


def _kronos_warmup(spec: RunSpec) -> int:
    return max(_kronos_params(spec).context, spec.vol_window + 1)


def _default_kronos_factory(params: KronosParams) -> object:
    """Build the real torch-backed forecaster from settings (lazy alpha_forecast import)."""
    from alpha_core.config import AlphaSettings
    from alpha_forecast import KronosForecaster

    settings = AlphaSettings()
    return KronosForecaster(
        model_name=params.model,
        weights_dir=settings.resolved_weights_dir,
        cache_dir=settings.data_dir / "forecast_cache",
        seed=settings.random_seed,
        temperature=params.temperature,
        top_p=params.top_p,
        sample_count=params.sample_count,
    )


# Test seam (mirrors data_cmds._ADAPTERS): monkeypatch with a stub factory to run the
# strategy without torch/weights. NOTE: a monkeypatch does not survive spawn workers, so
# stub-forecaster gauntlet runs must stay serial (max_workers=None).
_KRONOS_FACTORY: Callable[[KronosParams], object] = _default_kronos_factory


def _kronos_build(spec: RunSpec, instrument_id: InstrumentId, bar_type: BarType) -> Strategy:
    from alpha_strategies.kronos_forecast import KronosForecast

    params = _kronos_params(spec)
    forecaster = _KRONOS_FACTORY(params)
    return KronosForecast(
        instrument_id=instrument_id,
        bar_type=bar_type,
        forecaster=forecaster,  # type: ignore[arg-type]  # factory seam returns a BarForecaster
        context=params.context,
        horizon=params.horizon,
        deadband_bps=params.deadband_bps,
        vol_window=spec.vol_window,
        target_vol=spec.target_vol,
        capital=spec.starting_cash,
        max_leverage=spec.max_leverage,
        rebalance_every=spec.rebalance_every,
        periods_per_year=spec.periods_per_year,
        allow_short=spec.allow_short,
    )


STRATEGIES: dict[str, StrategyDef] = {
    "ts_momentum": StrategyDef(
        warmup=_ts_momentum_warmup,
        build=_ts_momentum_build,
        surrogate=_ts_momentum_surrogate,
    ),
    "ma_crossover": StrategyDef(
        warmup=_ma_crossover_warmup,
        build=_ma_crossover_build,
        surrogate=_ma_crossover_surrogate,
    ),
    "mean_reversion": StrategyDef(
        warmup=_mean_reversion_warmup,
        build=_mean_reversion_build,
        surrogate=_mean_reversion_surrogate,
    ),
    "breakout": StrategyDef(
        warmup=_breakout_warmup,
        build=_breakout_build,
        surrogate=_breakout_surrogate,
    ),
    "kronos_forecast": StrategyDef(
        warmup=_kronos_warmup,
        build=_kronos_build,
        surrogate=None,  # no honest engine-free analogue; Tier-1 is skipped-with-reason
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


def has_tier1_surrogate(spec: RunSpec) -> bool:
    """Whether ``spec``'s strategy has an engine-free Tier-1 surrogate at all."""
    return _resolve(spec.strategy_name).surrogate is not None


def surrogate_for(spec: RunSpec) -> StrategyFn:
    """Build the Tier-1 engine-free surrogate for ``spec``'s strategy (fail loud when absent)."""
    surrogate = _resolve(spec.strategy_name).surrogate
    if surrogate is None:
        raise DataError(
            f"strategy {spec.strategy_name!r} has no engine-free Tier-1 surrogate; the gauntlet "
            "records Tier-1 as skipped for it (check has_tier1_surrogate before calling)"
        )
    return surrogate(spec)


def pre_run_warnings(spec: RunSpec, bars: Sequence[Bar]) -> list[str]:
    """Strategy-specific loud caveats for a run over ``bars``.

    Currently: kronos_forecast weight-level look-ahead (pretrained weights saw market data
    up to ~2025-08, which accessor-level PIT guards cannot catch).
    """
    if spec.strategy_name != "kronos_forecast" or not bars:
        return []
    from alpha_forecast import training_overlap_warning

    warning = training_overlap_warning(bars[0].ts, bars[-1].ts)
    return [warning] if warning else []

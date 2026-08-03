"""Causal chart evidence must be invariant to mutations strictly after its decision timestamp."""

from __future__ import annotations

from alpha_cli._runner import RunSpec, run_full_backtest
from alpha_core import Bar
from tests.fixtures.forecast_fixtures import daily_bars


def _spec() -> RunSpec:
    return RunSpec(
        lookback=5,
        skip=1,
        vol_window=3,
        target_vol=0.1,
        rebalance_every=1,
        max_leverage=1.0,
        allow_short=True,
        periods_per_year=252,
        fee_bps=0.0,
        slippage_bps=0.0,
        starting_cash=100_000.0,
        account_type="MARGIN",
        train_size=10,
        test_size=5,
        embargo=1,
        anchored=False,
        strategy_name="breakout",
        strategy_params=(("window", 5.0),),
    )


def _spike(bar: Bar) -> Bar:
    return Bar(
        symbol=bar.symbol,
        ts=bar.ts,
        open=bar.open * 3.0,
        high=bar.high * 3.0,
        low=bar.low * 3.0,
        close=bar.close * 3.0,
        volume=bar.volume * 2.0,
    )


def test_future_poison_cannot_change_prior_indicators_or_annotations() -> None:
    clean = daily_bars(40)
    cutoff_index = 24
    poisoned = clean[: cutoff_index + 1] + [_spike(bar) for bar in clean[cutoff_index + 1 :]]

    result_a = run_full_backtest(clean, _spec())
    result_b = run_full_backtest(poisoned, _spec())
    cutoff = clean[cutoff_index].ts

    indicators_a = [row for row in result_a.indicator_trace if row.ts <= cutoff]
    indicators_b = [row for row in result_b.indicator_trace if row.ts <= cutoff]
    annotations_a = [row for row in result_a.chart_annotations if row.decision_ts <= cutoff]
    annotations_b = [row for row in result_b.chart_annotations if row.decision_ts <= cutoff]

    assert indicators_a == indicators_b
    assert annotations_a == annotations_b
    assert result_a.indicator_trace != result_b.indicator_trace

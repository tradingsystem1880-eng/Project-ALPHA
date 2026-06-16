"""TimeSeriesMomentum runs end-to-end through the harness, taking signal-consistent positions."""

from __future__ import annotations

from datetime import UTC, datetime

from nautilus_trader.model.enums import AccountType

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from alpha_core import Bar
from alpha_strategies.ts_momentum import TimeSeriesMomentum


def _trend_bars(symbol: str, step: float, n: int = 14) -> list[Bar]:
    """n daily bars trending by `step`/bar (positive = up, negative = down)."""
    bars = []
    for i in range(n):
        close = 100.0 + step * i
        bars.append(
            Bar(
                symbol=symbol,
                ts=datetime(2024, 1, 2 + i, tzinfo=UTC),
                open=close - 0.5 * (1 if step > 0 else -1),
                high=close + 2.0,
                low=close - 2.0,
                close=close,
                volume=1000.0,
            )
        )
    return bars


def _run(step: float, *, allow_short: bool, account_type: AccountType) -> TimeSeriesMomentum:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    data = to_execution_feed(_trend_bars("AAPL", step), bar_type)
    # small windows so a short fixture is enough to trade
    strat = TimeSeriesMomentum(
        instrument_id=inst.id,
        bar_type=bar_type,
        allow_short=allow_short,
        lookback=3,
        skip=1,
        vol_window=3,
        rebalance_every=1,
        capital=100_000.0,
    )
    run_backtest(inst, data, strat, account_type=account_type)
    return strat


def test_uptrend_goes_long() -> None:
    strat = _run(step=2.0, allow_short=True, account_type=AccountType.CASH)
    assert strat.fills > 0
    assert strat.net_units > 0  # long in an uptrend


def test_downtrend_goes_short_on_margin() -> None:
    strat = _run(step=-2.0, allow_short=True, account_type=AccountType.MARGIN)
    assert strat.fills > 0
    assert strat.net_units < 0  # short in a downtrend (long-short crypto/FX path)


def test_downtrend_long_flat_stays_flat() -> None:
    # equities are long-flat (spec §7): a short signal becomes no position, no order.
    strat = _run(step=-2.0, allow_short=False, account_type=AccountType.CASH)
    assert strat.fills == 0
    assert strat.net_units == 0.0

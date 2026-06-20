"""The added strategies run end-to-end through the harness, taking signal-consistent positions.

Mirrors ``test_ts_momentum_backtest``: a strategy fed a constructed price path should reach the
position its pure signal implies (long on the bullish case, short on margin for the bearish case).
"""

from __future__ import annotations

from nautilus_trader.model.enums import AccountType

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from alpha_core import Bar
from alpha_strategies.base import VolTargetStrategy
from alpha_strategies.breakout import DonchianBreakout
from alpha_strategies.ma_crossover import MovingAverageCrossover
from alpha_strategies.mean_reversion import MeanReversion
from tests.fixtures.nautilus_fixtures import bars_from_closes, trend_bars

_VOL_WINDOW, _CAPITAL = 3, 100_000.0


def _drive(strat: VolTargetStrategy, bars: list[Bar], account_type: AccountType) -> None:
    inst = equity_instrument("AAPL")
    run_backtest(
        inst, to_execution_feed(bars, daily_bar_type("AAPL")), strat, account_type=account_type
    )


def _ma(allow_short: bool) -> MovingAverageCrossover:
    inst = equity_instrument("AAPL")
    return MovingAverageCrossover(
        instrument_id=inst.id,
        bar_type=daily_bar_type("AAPL"),
        fast=2,
        slow=4,
        vol_window=_VOL_WINDOW,
        capital=_CAPITAL,
        rebalance_every=1,
        allow_short=allow_short,
    )


def test_ma_crossover_uptrend_goes_long() -> None:
    strat = _ma(allow_short=True)
    _drive(strat, trend_bars("AAPL", 2.0, n=10), AccountType.CASH)
    assert strat.fills > 0
    assert strat.net_units > 0


def test_ma_crossover_downtrend_goes_short_on_margin() -> None:
    strat = _ma(allow_short=True)
    _drive(strat, trend_bars("AAPL", -2.0, n=10), AccountType.MARGIN)
    assert strat.fills > 0
    assert strat.net_units < 0


def _mr(window: int, entry_z: float, allow_short: bool) -> MeanReversion:
    inst = equity_instrument("AAPL")
    return MeanReversion(
        instrument_id=inst.id,
        bar_type=daily_bar_type("AAPL"),
        window=window,
        entry_z=entry_z,
        vol_window=_VOL_WINDOW,
        capital=_CAPITAL,
        rebalance_every=1,
        allow_short=allow_short,
    )


def test_mean_reversion_oversold_goes_long() -> None:
    # the spike (oversold) is on the 5th bar so its decision fills at the 6th bar's open
    strat = _mr(window=4, entry_z=1.0, allow_short=True)
    bars = bars_from_closes("AAPL", [100.0, 100.0, 100.0, 100.0, 70.0, 70.0])
    _drive(strat, bars, AccountType.CASH)
    assert strat.fills > 0
    assert strat.net_units > 0  # oversold → buy


def test_mean_reversion_overbought_goes_short_on_margin() -> None:
    strat = _mr(window=4, entry_z=1.0, allow_short=True)
    bars = bars_from_closes("AAPL", [100.0, 100.0, 100.0, 100.0, 130.0, 130.0])
    _drive(strat, bars, AccountType.MARGIN)
    assert strat.fills > 0
    assert strat.net_units < 0  # overbought → fade short


def _breakout(allow_short: bool) -> DonchianBreakout:
    inst = equity_instrument("AAPL")
    return DonchianBreakout(
        instrument_id=inst.id,
        bar_type=daily_bar_type("AAPL"),
        window=3,
        vol_window=_VOL_WINDOW,
        capital=_CAPITAL,
        rebalance_every=1,
        allow_short=allow_short,
    )


def test_breakout_new_high_goes_long() -> None:
    strat = _breakout(allow_short=True)
    _drive(
        strat,
        bars_from_closes("AAPL", [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]),
        AccountType.CASH,
    )
    assert strat.fills > 0
    assert strat.net_units > 0  # steadily making new highs → long


def test_breakout_new_low_goes_short_on_margin() -> None:
    strat = _breakout(allow_short=True)
    _drive(
        strat,
        bars_from_closes("AAPL", [105.0, 104.0, 103.0, 102.0, 101.0, 100.0]),
        AccountType.MARGIN,
    )
    assert strat.fills > 0
    assert strat.net_units < 0  # steadily making new lows → short

"""TimeSeriesMomentum runs end-to-end through the harness, taking signal-consistent positions."""

from __future__ import annotations

from nautilus_trader.model.enums import AccountType

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_core import Bar
from alpha_execution.instruments import equity_instrument
from alpha_strategies.signals import ts_momentum_signal
from alpha_strategies.sizing import realized_volatility, vol_target_size
from alpha_strategies.ts_momentum import TimeSeriesMomentum
from tests.fixtures.nautilus_fixtures import bars_from_closes, trend_bars

# small windows (so a short fixture is enough to trade) and a fixed capital for reproducible sizing
_LOOKBACK, _SKIP, _VOL_WINDOW, _CAPITAL = 3, 1, 3, 100_000.0


def _run(
    bars: list[Bar], *, allow_short: bool, account_type: AccountType, rebalance_every: int = 1
) -> TimeSeriesMomentum:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    strat = TimeSeriesMomentum(
        instrument_id=inst.id,
        bar_type=bar_type,
        allow_short=allow_short,
        rebalance_every=rebalance_every,
        lookback=_LOOKBACK,
        skip=_SKIP,
        vol_window=_VOL_WINDOW,
        capital=_CAPITAL,
    )
    run_backtest(inst, to_execution_feed(bars, bar_type), strat, account_type=account_type)
    return strat


def test_uptrend_goes_long() -> None:
    strat = _run(trend_bars("AAPL", 2.0), allow_short=True, account_type=AccountType.CASH)
    assert strat.fills > 0
    assert strat.net_units > 0  # long in an uptrend


def test_downtrend_goes_short_on_margin() -> None:
    strat = _run(trend_bars("AAPL", -2.0), allow_short=True, account_type=AccountType.MARGIN)
    assert strat.fills > 0
    assert strat.net_units < 0  # short in a downtrend (long-short crypto/FX path)


def test_downtrend_long_flat_stays_flat() -> None:
    # equities are long-flat (spec §7): a short signal becomes no position, no order.
    strat = _run(trend_bars("AAPL", -2.0), allow_short=False, account_type=AccountType.CASH)
    assert strat.fills == 0
    assert strat.net_units == 0.0


def test_single_rebalance_position_matches_sizing() -> None:
    # rebalance_every huge -> exactly one rebalance, on the first eligible bar (the 5th close).
    bars = trend_bars("AAPL", 2.0, n=6)
    strat = _run(bars, allow_short=True, account_type=AccountType.CASH, rebalance_every=100)
    closes = [b.close for b in bars][:5]  # the history at that single rebalance
    signal = ts_momentum_signal(closes, lookback=_LOOKBACK, skip=_SKIP)
    vol = realized_volatility(closes[-(_VOL_WINDOW + 1) :])
    expected = round(vol_target_size(signal, closes[-1], vol, target_vol=0.15, capital=_CAPITAL))
    assert strat.fills == 1
    assert strat.net_units == expected  # position equals the model size, executed at the next open


def test_zero_volatility_window_holds_flat() -> None:
    # Long signal (recent 200 > past 100) but a flat vol window -> realized vol 0. Must hold flat,
    # not raise a DataError out of on_bar mid-run (a zero-vol window is a normal market state).
    bars = bars_from_closes("AAPL", [100.0, 200.0, 200.0, 200.0, 200.0, 200.0])
    strat = _run(bars, allow_short=True, account_type=AccountType.CASH)
    assert strat.fills == 0
    assert strat.net_units == 0.0

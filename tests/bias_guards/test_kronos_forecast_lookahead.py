"""Kronos-forecast strategy look-ahead guards (future-poison, through the real engine).

The stub forecaster records every window it is handed; poisoning bars AFTER the decision
windows must change neither the recorded windows nor the resulting position, and no
recorded bar may ever postdate the bar count at its decision point.
"""

from __future__ import annotations

import pytest
from nautilus_trader.model.enums import AccountType

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from alpha_core import Bar
from alpha_strategies.kronos_forecast import KronosForecast
from tests.fixtures.forecast_fixtures import StubForecaster
from tests.fixtures.nautilus_fixtures import bars_from_closes

pytestmark = pytest.mark.bias_guard

_SPIKE = 1.0e9


def _strategy(stub: StubForecaster) -> KronosForecast:
    inst = equity_instrument("AAPL")
    return KronosForecast(
        instrument_id=inst.id,
        bar_type=daily_bar_type("AAPL"),
        forecaster=stub,
        context=4,
        horizon=3,
        deadband_bps=0.0,
        vol_window=3,
        capital=100_000.0,
        rebalance_every=1,
        allow_short=True,
    )


def _drive(stub: StubForecaster, closes: list[float]) -> KronosForecast:
    strat = _strategy(stub)
    bars = bars_from_closes("AAPL", closes)
    inst = equity_instrument("AAPL")
    run_backtest(
        inst,
        to_execution_feed(bars, daily_bar_type("AAPL")),
        strat,
        account_type=AccountType.MARGIN,
    )
    return strat


_CLEAN = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]


def test_forecaster_never_sees_beyond_the_decision_bar() -> None:
    stub = StubForecaster(drift=0.01)
    _drive(stub, _CLEAN)
    assert stub.received_windows, "the strategy never consulted the forecaster"
    for i, window in enumerate(stub.received_windows):
        assert len(window) == 4  # exactly the trailing context
        # windows arrive in decision order; each must end no later than the bars seen so far
        closes = [b.close for b in window]
        assert closes == sorted(closes)  # uptrend fixture: any future bar would break order
        assert max(closes) <= _CLEAN[3 + i] + 1e-9  # decision bar for the i-th rebalance


def test_future_poison_changes_nothing_before_the_cutoff() -> None:
    stub_clean = StubForecaster(drift=0.01)
    _drive(stub_clean, _CLEAN)

    # poison every bar after the 6th: decisions made on bars 4..6 must be unaffected
    poisoned = [*_CLEAN[:6], _SPIKE, _SPIKE]
    stub_poisoned = StubForecaster(drift=0.01)
    _drive(stub_poisoned, poisoned)

    n_unaffected = 3  # windows decided on bars 4, 5, 6 (context=4)
    clean_windows = stub_clean.received_windows[:n_unaffected]
    poisoned_windows = stub_poisoned.received_windows[:n_unaffected]
    assert len(poisoned_windows) == n_unaffected
    for cw, pw in zip(clean_windows, poisoned_windows, strict=True):
        assert [b.close for b in cw] == [b.close for b in pw]
        assert [b.ts for b in cw] == [b.ts for b in pw]

    # the poison MUST reach later windows, else this test has no discriminating power
    # (compare with a threshold: nautilus price quantization perturbs the spike's last digit)
    later = stub_poisoned.received_windows[n_unaffected:]
    assert any(any(b.close > _SPIKE / 10 for b in w) for w in later)


def test_positions_match_the_forecast_direction() -> None:
    bullish = StubForecaster(drift=0.05)
    strat_long = _drive(bullish, _CLEAN)
    assert strat_long.fills > 0
    assert strat_long.net_units > 0

    bearish = StubForecaster(drift=-0.05)
    strat_short = _drive(bearish, _CLEAN)
    assert strat_short.fills > 0
    assert strat_short.net_units < 0


def test_recorded_windows_are_real_bars() -> None:
    stub = StubForecaster()
    _drive(stub, _CLEAN)
    for window in stub.received_windows:
        assert all(isinstance(b, Bar) for b in window)
        ts = [b.ts for b in window]
        assert ts == sorted(ts)

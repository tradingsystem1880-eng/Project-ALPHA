"""``SignalReplay``: index-aligned replay of a precomputed signal sequence (fail-loud)."""

from __future__ import annotations

import pytest

from alpha_backtest.feed import daily_bar_type
from alpha_backtest.instruments import equity_instrument
from alpha_core import DataError
from alpha_strategies.signal_replay import SignalReplay


def _strategy(signals: list[int | None]) -> SignalReplay:
    instrument = equity_instrument("SPY")
    return SignalReplay(
        instrument_id=instrument.id,
        bar_type=daily_bar_type("SPY"),
        signals=signals,
        min_history=4,
        vol_window=3,
    )


def test_replays_signal_at_current_bar_index() -> None:
    strat = _strategy([None, None, None, 1, None, -1])
    strat._closes = [100.0, 101.0, 102.0, 103.0]  # bar index 3
    assert strat._signal() == 1
    strat._closes += [104.0, 105.0]  # bar index 5
    assert strat._signal() == -1


def test_fails_loud_on_uncovered_index() -> None:
    strat = _strategy([None, None, None, 1])
    strat._closes = [100.0, 101.0, 102.0]  # bar index 2: schedule says no signal here
    with pytest.raises(DataError, match="cover"):
        strat._signal()


def test_fails_loud_beyond_cache_end() -> None:
    strat = _strategy([None, None, None, 1])
    strat._closes = [100.0] * 5  # bar index 4: past the cached series
    with pytest.raises(DataError, match="cover"):
        strat._signal()

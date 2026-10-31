"""Artificial chronological and cash references for full UTC-day decision availability."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from nautilus_trader.model.data import Bar as NautilusBar
from nautilus_trader.model.data import QuoteTick

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from alpha_core import Bar, DataError
from alpha_strategies.rule_strategy import RuleStrategy
from alpha_strategies.rules import rule_spec_from_json


def _bars() -> list[Bar]:
    return [
        Bar(
            symbol="CLOCK",
            ts=datetime(2000, 1, 1, tzinfo=UTC) + timedelta(days=i),
            open=float(price),
            high=float(price + 1),
            low=float(price - 1),
            close=float(price),
            volume=10000.0,
        )
        for i, price in enumerate((6, 8, 12, 10, 16, 8, 8))
    ]


def test_utc_day_end_precedes_next_open_quote_without_early_close() -> None:
    feed = to_execution_feed(_bars()[:2], daily_bar_type("CLOCK"), timing="utc_day_end_next_open")
    assert [type(item) for item in feed] == [QuoteTick, NautilusBar, QuoteTick, NautilusBar]
    # Hand-specified epoch times, independent of the production timestamp arithmetic.
    assert [item.ts_event for item in feed] == [
        946684800000001000,
        946771200000000000,
        946771200000001000,
        946857600000000000,
    ]
    assert [item.ts_init for item in feed] == [item.ts_event for item in feed]


def test_default_feed_timestamps_remain_unchanged() -> None:
    feed = to_execution_feed(_bars()[:2], daily_bar_type("CLOCK"))
    assert [item.ts_event for item in feed] == [
        946684800000000000,
        946767600000000000,
        946771200000000000,
        946854000000000000,
    ]


@pytest.mark.parametrize("timing", [None, True, "UTC", "utc_day_end", 1])
def test_unknown_timing_fails_before_building_feed(timing: object) -> None:
    with pytest.raises(DataError, match="timing"):
        to_execution_feed(_bars(), daily_bar_type("CLOCK"), timing=timing)  # type: ignore[arg-type]


def test_utc_daily_mode_rejects_nonmidnight_and_subdaily_rows() -> None:
    bars = _bars()[:2]
    bars[0] = bars[0].model_copy(update={"ts": bars[0].ts + timedelta(hours=1)})
    with pytest.raises(DataError, match="midnight"):
        to_execution_feed(bars, daily_bar_type("CLOCK"), timing="utc_day_end_next_open")
    bars = _bars()[:2]
    bars[1] = bars[1].model_copy(update={"ts": bars[0].ts + timedelta(hours=12)})
    with pytest.raises(DataError, match="24h|midnight"):
        to_execution_feed(bars, daily_bar_type("CLOCK"), timing="utc_day_end_next_open")


@pytest.mark.parametrize("slippage", [float("nan"), float("inf"), -float("inf"), -1.0])
def test_nonfinite_or_negative_slippage_is_rejected(slippage: float) -> None:
    with pytest.raises(DataError, match="slippage"):
        to_execution_feed(_bars(), daily_bar_type("CLOCK"), slippage_bps=slippage)


@pytest.mark.parametrize("control", [False, True])
def test_engine_matches_independent_next_open_cash_reference(control: bool) -> None:
    # Price>10 decisions on Jan3/Jan5 buy Jan4/Jan6. Price<=10 decisions sell on
    # Jan5/Jan7. Cash: 12000-1011.01+1582.416-606.606+593.406 = 12558.206,
    # with cent-rounded commissions ->12558.21. This is an artificial fixture.
    condition = '"op":"<","right":{"value":0}' if control else '"op":">","right":{"value":10}'
    spec = rule_spec_from_json(
        '{"history":2,"long_when":[{"left":{"source":"close"},'
        + condition
        + '}],"name":"clock-fixture","short_when":[],"version":1}'
    )
    instrument = equity_instrument("CLOCK")
    bar_type = daily_bar_type("CLOCK")
    strategy = RuleStrategy(
        instrument_id=instrument.id,
        bar_type=bar_type,
        spec=spec,
        vol_window=2,
        target_vol=1.0,
        capital=12000.0,
        max_leverage=0.1,
        rebalance_every=1,
        allow_short=False,
    )
    result = run_backtest(
        instrument,
        to_execution_feed(_bars(), bar_type, slippage_bps=100.0, timing="utc_day_end_next_open"),
        strategy,
        starting_cash=12000.0,
        fee_bps=10.0,
    )
    if control:
        assert result.fill_trace == ()
        assert result.equity_curve[-1][1] == pytest.approx(12000.0, abs=0.005)
        return
    assert [(decision.ts, decision.signal) for decision in result.decision_trace] == [
        (datetime(2000, 1, 4, tzinfo=UTC), 1),
        (datetime(2000, 1, 5, tzinfo=UTC), 0),
        (datetime(2000, 1, 6, tzinfo=UTC), 1),
        (datetime(2000, 1, 7, tzinfo=UTC), 0),
        (datetime(2000, 1, 8, tzinfo=UTC), 0),
    ]
    assert [(fill.ts, fill.side) for fill in result.fill_trace] == [
        (datetime(2000, 1, 4, microsecond=1, tzinfo=UTC), "BUY"),
        (datetime(2000, 1, 5, microsecond=1, tzinfo=UTC), "SELL"),
        (datetime(2000, 1, 6, microsecond=1, tzinfo=UTC), "BUY"),
        (datetime(2000, 1, 7, microsecond=1, tzinfo=UTC), "SELL"),
    ]
    assert [fill.quantity for fill in result.fill_trace] == pytest.approx([100, 100, 75, 75])
    assert [fill.price for fill in result.fill_trace] == pytest.approx([10.1, 15.84, 8.08, 7.92])
    assert result.equity_curve[-1][1] == pytest.approx(12558.21, abs=0.005)
    assert result.rejected == 0

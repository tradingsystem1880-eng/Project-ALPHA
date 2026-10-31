"""Artificial fixed-unit cash fixtures; no real-market study acceptance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import crypto_instrument
from alpha_backtest.results import AccountingTrace, BacktestResult
from alpha_core import Bar, DataError
from alpha_strategies.rule_strategy import RuleStrategy
from alpha_strategies.rules import rule_spec_from_json


def _run(
    *,
    control: bool = False,
    entry_once: bool = False,
    cash: float = 10000.0,
    quantity: float = 0.05,
    closes: tuple[float, ...] = (8, 12, 15, 5, 11, 5, 5),
) -> tuple[BacktestResult, list[AccountingTrace]]:
    instrument = crypto_instrument(
        "BTC/USDT", price_precision=2, size_precision=6, size_increment=0.000001
    )
    bar_type = daily_bar_type("BTC/USDT")
    spec = rule_spec_from_json(
        '{"history":2,"long_when":[{"left":{"source":"close"},"op":">",'
        '"right":{"value":'
        + ("0" if control else "10")
        + '}}],"name":"fixed-fixture","short_when":[],"version":1}'
    )
    bars = [
        Bar(
            symbol="BTC/USDT",
            ts=datetime(2000, 1, 1, tzinfo=UTC) + timedelta(days=i),
            open=float(p),
            high=float(p + 1),
            low=float(p - 1),
            close=float(p),
            volume=10000.0,
        )
        for i, p in enumerate(closes)
    ]
    strategy = RuleStrategy(
        instrument_id=instrument.id,
        bar_type=bar_type,
        spec=spec,
        fixed_quantity=quantity,
        fixed_entry_once=entry_once,
        allow_short=False,
    )
    accounting: list[AccountingTrace] = []
    result = run_backtest(
        instrument,
        to_execution_feed(
            bars, bar_type, price_precision=2, size_precision=6, timing="utc_day_end_next_open"
        ),
        strategy,
        starting_cash=cash,
        fee_bps=10.0,
        accounting_trace=accounting,
    )
    return result, accounting


def test_fractional_fixed_units_do_not_resize_while_long_and_reenter_same_units() -> None:
    result, accounting = _run()
    assert [(fill.ts, fill.side) for fill in result.fill_trace] == [
        (datetime(2000, 1, 3, microsecond=1, tzinfo=UTC), "BUY"),
        (datetime(2000, 1, 5, microsecond=1, tzinfo=UTC), "SELL"),
        (datetime(2000, 1, 6, microsecond=1, tzinfo=UTC), "BUY"),
        (datetime(2000, 1, 7, microsecond=1, tzinfo=UTC), "SELL"),
    ]
    assert [fill.quantity for fill in result.fill_trace] == pytest.approx([0.05] * 4)
    assert [fill.price for fill in result.fill_trace] == pytest.approx([15, 11, 5, 5])
    rows = [row for row in accounting if row.event == "fill"]
    assert [row.fill_sequence_id for row in rows] == [1, 2, 3, 4]
    assert [row.cash for row in rows] == pytest.approx(
        [9999.24925, 9999.7987, 9999.54845, 9999.7982], abs=1e-8
    )
    assert [row.position_units for row in rows] == pytest.approx([0.05, 0, 0.05, 0])
    assert [row.commission for row in rows] == pytest.approx([0.00075, 0.00055, 0.00025, 0.00025])
    assert rows[-1].fees_total == pytest.approx(0.0018)
    assert all(row.currency == "USDT" for row in rows)
    assert result.final_equity == pytest.approx(9999.7982, abs=1e-8)
    assert all(row.cash_free == pytest.approx(row.cash) for row in rows)


def test_buy_and_hold_control_buys_once_at_same_first_eligible_open() -> None:
    result, accounting = _run(control=True, entry_once=True)
    assert len(result.fill_trace) == 1
    fill = result.fill_trace[0]
    assert fill.ts == datetime(2000, 1, 3, microsecond=1, tzinfo=UTC)
    assert fill.quantity == pytest.approx(0.05)
    assert result.final_equity == pytest.approx(9999.49925, abs=1e-8)
    assert accounting[-1].position_units == pytest.approx(0.05)
    assert accounting[-1].cash == pytest.approx(9999.24925, abs=1e-8)
    assert result.decision_trace[-1].reason == "control_entry_attempt_complete"


def test_single_entry_control_never_retries_after_initial_affordability_rejection() -> None:
    result, accounting = _run(control=True, entry_once=True, cash=0.75)
    assert result.fill_trace == ()
    assert len(result.execution_rejections) == 1
    assert result.decision_trace[-1].reason == "control_entry_attempt_complete"
    assert result.final_equity == pytest.approx(0.75)
    assert all(row.cash == pytest.approx(0.75) for row in accounting)
    assert all(row.position_units == pytest.approx(0) for row in accounting)


def test_fixed_quantity_needs_no_realized_volatility() -> None:
    result, _ = _run(control=True, closes=(10, 10, 10, 10))
    assert len(result.fill_trace) == 1
    assert result.final_equity == pytest.approx(9999.9995, abs=1e-8)


def test_unaffordable_gap_rejects_whole_quantity_without_resizing() -> None:
    result, accounting = _run(control=True, cash=0.75)
    assert result.fill_trace[0].ts == datetime(2000, 1, 4, microsecond=1, tzinfo=UTC)
    assert result.fill_trace[0].quantity == pytest.approx(0.05)
    assert len(result.execution_rejections) == 1
    assert result.execution_rejections[0].reason == "cash_plus_commission_exceeds_free_balance"
    assert accounting[0].cash == pytest.approx(0.75)


@pytest.mark.parametrize("quantity", [True, 0, -1, float("nan"), float("inf")])
def test_invalid_fixed_quantity_rejected(quantity: float) -> None:
    with pytest.raises(DataError, match="fixed quantity"):
        _run(quantity=quantity)


def test_legacy_crypto_integer_lots_and_five_decimal_prices_unchanged() -> None:
    instrument = crypto_instrument("BTC/USDT")
    assert instrument.price_precision == 5
    assert instrument.size_precision == 0
    assert float(instrument.size_increment) == pytest.approx(1)


@pytest.mark.parametrize("increment", [0.0000001, 0, -1, float("nan"), True])
def test_invalid_fractional_increment_rejected(increment: float) -> None:
    with pytest.raises(DataError, match="precision/increment"):
        crypto_instrument("BTC/USDT", size_precision=6, size_increment=increment)

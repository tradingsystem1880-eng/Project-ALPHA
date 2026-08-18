"""Independent P&L re-derivation: rebuild the equity curve from fills, fees and opens.

The engine's equity curve is a Nautilus portfolio projection (realized + unrealized PnL). This
oracle recomputes it from first principles — cash ledger from the canonical ``fill_trace``,
commission = notional × fee_bps / 1e4 per fill, open position marked at each session's open —
and asserts equality. A crediting bug (double-counted fee, wrong mark, lost final-session fill)
that a frozen golden would happily preserve is caught here because the reference is derived,
not recorded.

Sampling convention (engine.py ``_EquityRecorder``): the session-``t`` point is taken after the
portfolio marks to the ``t`` open quote but BEFORE an order submitted on that quote fills, so a
fill at session ``t`` first appears at ``t+1``; the terminal point is re-sampled after the last
fill settles.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from nautilus_trader.model.enums import OrderSide

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from alpha_backtest.results import BacktestResult
from alpha_core import Bar
from tests.fixtures.nautilus_fixtures import BuyAndHold, RoundTrip, ladder_bars

pytestmark = pytest.mark.oracle

_CASH = 1_000_000.0


def _rederive(
    result: BacktestResult, bars: list[Bar], *, fee_bps: float
) -> list[tuple[datetime, float]]:
    """Equity per session from the fill ledger alone (no engine state consulted)."""
    fills = sorted(result.fill_trace, key=lambda f: (f.ts, f.sequence_id))
    curve: list[tuple[datetime, float]] = []
    last = len(bars) - 1
    for i, bar in enumerate(bars):
        cash, pos = _CASH, 0.0
        for f in fills:
            # a fill stamped at session t settles after the t snapshot — except the terminal one
            if f.ts < bar.ts or (i == last and f.ts <= bar.ts):
                sign = 1.0 if f.side == "BUY" else -1.0
                notional = f.quantity * f.price
                cash -= sign * notional
                cash -= notional * fee_bps / 10_000.0
                pos += sign * f.quantity
        curve.append((bar.ts, cash + pos * bar.open))
    return curve


def _assert_curves_equal(
    observed: list[tuple[datetime, float]], expected: list[tuple[datetime, float]]
) -> None:
    assert [ts for ts, _ in observed] == [ts for ts, _ in expected]
    for (ts, o), (_, e) in zip(observed, expected, strict=True):
        assert o == pytest.approx(e, abs=1e-6), f"equity mismatch at {ts}: engine {o} vs {e}"


@pytest.mark.parametrize("fee_bps", [0.0, 25.0])
def test_buy_and_hold_equity_rederives_from_fills(fee_bps: float) -> None:
    inst = equity_instrument("AAPL")
    bars = ladder_bars("AAPL", n=6)
    result = run_backtest(
        inst, to_execution_feed(bars, daily_bar_type("AAPL")), BuyAndHold(inst.id), fee_bps=fee_bps
    )
    assert result.fills == 1
    expected = _rederive(result, bars, fee_bps=fee_bps)
    _assert_curves_equal(list(result.equity_curve), expected)
    assert result.final_equity == pytest.approx(expected[-1][1], abs=1e-6)


@pytest.mark.parametrize("opening_side", [OrderSide.BUY, OrderSide.SELL])
@pytest.mark.parametrize("fee_bps", [0.0, 10.0])
def test_round_trip_equity_rederives_from_fills(opening_side: object, fee_bps: float) -> None:
    from nautilus_trader.model.enums import AccountType

    inst = equity_instrument("AAPL")
    bars = ladder_bars("AAPL", n=6)
    result = run_backtest(
        inst,
        to_execution_feed(bars, daily_bar_type("AAPL")),
        RoundTrip(inst.id, exit_at=3, opening_side=opening_side),
        account_type=AccountType.MARGIN,
        fee_bps=fee_bps,
    )
    assert result.fills == 2 and len(result.trades) == 1
    expected = _rederive(result, bars, fee_bps=fee_bps)
    _assert_curves_equal(list(result.equity_curve), expected)
    # once flat, equity is pure cash: realized P&L must equal the ledger's cash change
    trade = result.trades[0]
    ledger_cash = expected[-1][1] - _CASH
    assert trade.realized_pnl == pytest.approx(ledger_cash, abs=1e-6)


def test_last_session_fill_is_reflected_in_the_terminal_point() -> None:
    """A fill on the final open settles after that session's sample; the terminal re-sample
    must include its notional and fee. Modeled by re-deriving with the terminal rule."""
    inst = equity_instrument("AAPL")
    bars = ladder_bars("AAPL", n=4)
    fee_bps = 100.0
    result = run_backtest(
        inst,
        to_execution_feed(bars, daily_bar_type("AAPL")),
        RoundTrip(inst.id, exit_at=len(bars)),  # closes on the last open
        fee_bps=fee_bps,
    )
    assert result.fills == 2
    expected = _rederive(result, bars, fee_bps=fee_bps)
    _assert_curves_equal(list(result.equity_curve), expected)
    # sanity: the two fills' fees are both in the terminal cash
    total_fees = sum(f.quantity * f.price * fee_bps / 10_000.0 for f in result.fill_trace)
    gross = sum(
        (-1.0 if f.side == "BUY" else 1.0) * f.quantity * f.price for f in result.fill_trace
    )
    assert result.final_equity == pytest.approx(_CASH + gross - total_fees, abs=1e-6)

"""Rejected orders are surfaced, not swallowed (golden rule: fail loud).

A vol-targeted notional far larger than CASH buying power must be denied/rejected by the venue and
counted — never silently dropped to a misleading flat equity. The CLI then fails loud.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from nautilus_trader.model.data import Bar as NautilusBar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.identifiers import InstrumentId
from typer.testing import CliRunner

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from alpha_cli.main import app
from alpha_strategies.base import VolTargetStrategy
from alpha_strategies.ts_momentum import TimeSeriesMomentum
from tests.fixtures.cli_fixtures import seed_store
from tests.fixtures.nautilus_fixtures import ladder_bars, trend_bars

runner = CliRunner()


def test_oversized_order_is_rejected_and_counted() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    strat = TimeSeriesMomentum(
        instrument_id=inst.id,
        bar_type=bar_type,
        lookback=3,
        skip=1,
        vol_window=3,
        target_vol=1.0,  # 100% vol target → notional far exceeds cash
        capital=100_000.0,
        max_leverage=10.0,
        rebalance_every=1,
        allow_short=True,
    )
    result = run_backtest(
        inst,
        to_execution_feed(trend_bars("AAPL", 2.0), bar_type),
        strat,
        starting_cash=100_000.0,
        account_type=AccountType.CASH,  # buying power = cash; 10x notional can't fill
    )
    assert result.rejected > 0
    assert result.fills == 0  # nothing affordable filled


class _FixedNextOpenBuy(VolTargetStrategy):
    """Test strategy that decides at the first close and requests a fixed next-open buy."""

    def __init__(
        self,
        instrument_id: InstrumentId,
        bar_type: BarType,
        quantity: int,
        *,
        exit_on_next_close: bool = False,
    ) -> None:
        super().__init__(
            instrument_id=instrument_id,
            bar_type=bar_type,
            min_history=1,
            vol_window=1,
            capital=11_000,
            allow_short=False,
        )
        self._quantity = quantity
        self._decided = False
        self._exit_on_next_close = exit_on_next_close
        self._exit_queued = False

    def on_bar(self, bar: NautilusBar) -> None:
        if not self._decided:
            self._decided = True
            self._target_units = float(self._quantity)
            self._record_decision(
                bar, signal=1, target_quantity=float(self._quantity), reason="target"
            )
        elif self._exit_on_next_close and not self._exit_queued:
            self._exit_queued = True
            self._target_units = 0.0
            self._record_decision(bar, signal=0, target_quantity=0.0, reason="liquidate")

    def _signal(self) -> int:
        return 1

    def _indicator_snapshot(self) -> Mapping[str, tuple[float, str]]:
        return {}


def test_cash_fee_shortfall_is_rejected_before_it_can_truncate_the_run() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    result = run_backtest(
        inst,
        to_execution_feed(ladder_bars("AAPL"), bar_type),
        _FixedNextOpenBuy(inst.id, bar_type, 100),
        starting_cash=11_000.0,  # precisely the next-open principal: 100 × $110
        fee_bps=100.0,  # the additional $110 commission is unaffordable
    )
    assert len(result.equity_curve) == 5  # no silently truncated run
    assert result.fills == 0
    assert result.rejected == 1
    assert len(result.execution_rejections) == 1
    rejection = result.execution_rejections[0]
    assert rejection.reference_price == pytest.approx(110.0)  # next-open, not close-t $105
    assert rejection.requested_quantity == pytest.approx(100.0)
    assert rejection.available_cash == pytest.approx(11_000.0)
    assert rejection.estimated_fee == pytest.approx(110.0)
    assert rejection.required_cash == pytest.approx(11_110.0)


def test_cash_buy_at_exact_principal_boundary_still_fills_with_zero_fee() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    result = run_backtest(
        inst,
        to_execution_feed(ladder_bars("AAPL"), bar_type),
        _FixedNextOpenBuy(inst.id, bar_type, 100),
        starting_cash=11_000.0,
    )
    assert result.fills == 1
    assert result.rejected == 0


def test_cash_position_can_be_sold_when_free_cash_is_low() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    result = run_backtest(
        inst,
        to_execution_feed(ladder_bars("AAPL"), bar_type),
        _FixedNextOpenBuy(inst.id, bar_type, 100, exit_on_next_close=True),
        starting_cash=12_000.0,
        fee_bps=100.0,
    )
    assert result.fills == 2
    assert result.rejected == 0
    assert [fill.side for fill in result.fill_trace] == ["BUY", "SELL"]
    assert len(result.trades) == 1


def test_margin_buy_is_not_limited_by_cash_account_fee_guard() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    result = run_backtest(
        inst,
        to_execution_feed(ladder_bars("AAPL"), bar_type),
        _FixedNextOpenBuy(inst.id, bar_type, 100),
        starting_cash=6_000.0,
        account_type=AccountType.MARGIN,
        leverage=2.0,
        fee_bps=100.0,
    )
    assert result.fills == 1
    assert result.rejected == 0
    assert not result.execution_rejections


def test_retained_tier2_fee_shortfall_is_detected_at_the_opening_quote() -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    bars = ladder_bars("AAPL")
    bars[1] = bars[1].model_copy(update={"open": 122.57})
    result = run_backtest(
        inst,
        to_execution_feed(bars, bar_type),
        _FixedNextOpenBuy(inst.id, bar_type, 7_513),
        starting_cash=920_929.25,
        fee_bps=1.0,
    )
    assert len(result.equity_curve) == 5
    assert result.fills == 0
    assert result.rejected == 1
    rejection = result.execution_rejections[0]
    assert rejection.reference_price == pytest.approx(122.57)
    assert rejection.requested_quantity == pytest.approx(7_513)
    assert rejection.available_cash == pytest.approx(920_929.25)
    assert rejection.estimated_fee == pytest.approx(92.09)
    assert rejection.required_cash == pytest.approx(920_960.50)


@pytest.mark.parametrize(
    ("starting_cash", "expected_fills", "expected_rejections"),
    [(920_960.50, 1, 0), (920_960.49, 0, 1)],
)
def test_cash_fee_check_uses_currency_rounded_exact_boundary(
    starting_cash: float, expected_fills: int, expected_rejections: int
) -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    bars = ladder_bars("AAPL")
    bars[1] = bars[1].model_copy(update={"open": 122.57})
    result = run_backtest(
        inst,
        to_execution_feed(bars, bar_type),
        _FixedNextOpenBuy(inst.id, bar_type, 7_513),
        starting_cash=starting_cash,
        fee_bps=1.0,
    )
    assert result.fills == expected_fills
    assert result.rejected == expected_rejections


@pytest.mark.parametrize(
    ("opening_price", "fee_bps", "cash", "expected_fills", "expected_fee"),
    [(725.0, 2.0, 725.14, 0, 0.15), (450.0, 3.0, 450.13, 1, 0.13)],
)
def test_fee_reserve_uses_the_identical_rate_operation_and_currency_rounding(
    opening_price: float,
    fee_bps: float,
    cash: float,
    expected_fills: int,
    expected_fee: float,
) -> None:
    inst = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL")
    bars = ladder_bars("AAPL")
    bars[1] = bars[1].model_copy(
        update={
            "open": opening_price,
            "high": opening_price + 40.0,
            "low": opening_price - 10.0,
            "close": opening_price + 5.0,
        }
    )
    result = run_backtest(
        inst,
        to_execution_feed(bars, bar_type),
        _FixedNextOpenBuy(inst.id, bar_type, 1),
        starting_cash=cash,
        fee_bps=fee_bps,
    )
    assert result.fills == expected_fills
    assert result.rejected == 1 - expected_fills
    if result.execution_rejections:
        assert result.execution_rejections[0].estimated_fee == pytest.approx(expected_fee)


def test_cli_fails_loud_when_all_orders_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(
        app,
        [
            "backtest",
            "run",
            "SPY",
            "--lookback",
            "5",
            "--skip",
            "1",
            "--vol-window",
            "3",
            "--target-vol",
            "1.0",
            "--max-leverage",
            "10",
            "--account-type",
            "CASH",
        ],  # fmt: skip
    )
    assert result.exit_code != 0
    assert "rejected" in result.output.lower()

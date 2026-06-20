"""Rejected orders are surfaced, not swallowed (golden rule: fail loud).

A vol-targeted notional far larger than CASH buying power must be denied/rejected by the venue and
counted — never silently dropped to a misleading flat equity. The CLI then fails loud.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from nautilus_trader.model.enums import AccountType
from typer.testing import CliRunner

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from alpha_cli.main import app
from alpha_strategies.ts_momentum import TimeSeriesMomentum
from tests.fixtures.cli_fixtures import seed_store
from tests.fixtures.nautilus_fixtures import trend_bars

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

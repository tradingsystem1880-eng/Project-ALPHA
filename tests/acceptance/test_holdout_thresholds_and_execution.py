"""Hidden holdout: DSR/PBO pass semantics, split causality, and the t+1-open fill convention.

Behavioural contracts (CLAUDE.md): DSR passes iff ``dsr >= threshold`` and a standalone run has
``N=1, DSR=PSR``; PBO passes iff ``pbo <= threshold``; walk-forward tests start strictly after
train + embargo; decide on close of ``t``, fill at the OPEN of ``t+1`` (never the close of ``t``);
fees are notional × bps / 1e4.
"""

from __future__ import annotations

import numpy as np
import pytest
from nautilus_trader.model.enums import OrderSide

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from alpha_validation.dsr import deflated_sharpe, probabilistic_sharpe_ratio
from alpha_validation.overfitting import probability_of_backtest_overfitting
from alpha_validation.walkforward import walk_forward_splits
from tests.fixtures.nautilus_fixtures import DecideCloseExecuteOpen, RoundTrip, ladder_bars

pytestmark = pytest.mark.holdout

_RETURNS = np.random.default_rng(11).normal(0.001, 0.01, size=400)


def test_dsr_pass_is_exactly_at_or_above_threshold_and_standalone_equals_psr() -> None:
    psr = probabilistic_sharpe_ratio(_RETURNS)
    standalone = deflated_sharpe(_RETURNS, threshold=0.5)
    assert standalone.n_trials == 1
    assert standalone.dsr == pytest.approx(psr)
    at = deflated_sharpe(_RETURNS, threshold=standalone.dsr)
    above = deflated_sharpe(_RETURNS, threshold=min(1.0, standalone.dsr + 1e-6))
    assert at.passed is True  # >= is inclusive
    assert above.passed is False


def test_more_trials_can_only_lower_dsr_and_flip_pass_to_fail() -> None:
    lone = deflated_sharpe(_RETURNS, threshold=0.5)
    sharpes = [lone.sharpe] + list(np.linspace(-0.05, 0.05, 40))
    deflated = deflated_sharpe(_RETURNS, trial_sharpes=sharpes, threshold=lone.dsr)
    assert deflated.n_trials == len(sharpes)
    assert deflated.dsr < lone.dsr
    assert deflated.passed is False


def test_pbo_pass_is_at_or_below_threshold() -> None:
    rng = np.random.default_rng(5)
    matrix = rng.normal(size=(160, 12))
    result = probability_of_backtest_overfitting(matrix, n_blocks=8, threshold=0.5)
    assert 0.0 <= result.pbo <= 1.0
    assert result.passed is (result.pbo <= 0.5)
    tight = probability_of_backtest_overfitting(matrix, n_blocks=8, threshold=result.pbo)
    assert tight.passed is True
    if result.pbo > 0.0:
        stricter = probability_of_backtest_overfitting(
            matrix, n_blocks=8, threshold=result.pbo - 1e-9
        )
        assert stricter.passed is False


def test_walk_forward_test_windows_start_after_train_plus_embargo() -> None:
    splits = walk_forward_splits(300, train_size=100, test_size=25, embargo=5)
    assert splits, "geometry must yield folds"
    for split in splits:
        assert split.test.start == split.train.stop + 5
        assert len(split.test) == 25
        assert len(split.train) == 100
    for earlier, later in zip(splits, splits[1:], strict=False):
        assert later.test.start == earlier.test.stop  # contiguous OOS windows


def test_a_decision_on_close_t_fills_at_the_open_of_t_plus_one() -> None:
    inst = equity_instrument("AAPL")
    bars = ladder_bars("AAPL", n=4)  # opens 100,110,120,130 ; closes +5
    strat = DecideCloseExecuteOpen(daily_bar_type("AAPL"), inst.id)
    result = run_backtest(inst, to_execution_feed(bars, daily_bar_type("AAPL")), strat)
    assert result.fills == 1
    fill = result.fill_trace[0]
    assert fill.price == pytest.approx(bars[1].open)  # NOT bars[0].close (105) — t+1 open
    assert fill.ts == bars[1].ts


def test_fees_are_notional_times_bps_over_ten_thousand() -> None:
    inst = equity_instrument("AAPL")
    bars = ladder_bars("AAPL", n=4)
    fee_bps = 20.0
    result = run_backtest(
        inst,
        to_execution_feed(bars, daily_bar_type("AAPL")),
        RoundTrip(inst.id, qty=100, exit_at=3, opening_side=OrderSide.BUY),
        fee_bps=fee_bps,
        starting_cash=1_000_000.0,
    )
    assert result.fills == 2
    buy, sell = sorted(result.fill_trace, key=lambda f: f.ts)
    gross = (sell.price - buy.price) * 100
    fees = (buy.price + sell.price) * 100 * fee_bps / 10_000.0
    assert result.final_equity == pytest.approx(1_000_000.0 + gross - fees, abs=1e-6)

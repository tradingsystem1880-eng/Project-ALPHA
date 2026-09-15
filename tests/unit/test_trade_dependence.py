"""Unit tests for the trade-dependence runs test (alpha_validation.trade_dependence)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.native_tearsheet import (
    TradeObservation,
    TradeStatistic,
    build_native_tearsheet,
)
from alpha_validation.trade_dependence import RunsTestResult, runs_test, trade_runs_test


def test_hand_computed_goldens() -> None:
    # n=5, 3 positive, 2 negative: mean = 2*3*2/5 + 1 = 3.4, var = 2.4*1.4/4 = 0.84, R = 3
    clustered = runs_test([1, 1, -1, -1, 1])
    assert isinstance(clustered, RunsTestResult)
    assert clustered.z == pytest.approx(-0.4364357804719848, rel=1e-12)
    assert clustered.p_value == pytest.approx(0.6625205835400574, rel=1e-9)
    assert clustered.expected_runs == pytest.approx(3.4, rel=1e-12)
    assert (clustered.n_runs, clustered.n_signs) == (3, 5)
    # n=6, alternating: mean = 4, var = 1.2, R = 6
    alternating = runs_test(np.array([1.0, -1.0, 1.0, -1.0, 1.0, -1.0]))
    assert alternating.z == pytest.approx(1.8257418583505538, rel=1e-12)
    assert alternating.p_value == pytest.approx(0.06788915486182899, rel=1e-9)
    assert alternating.n_runs == 6 and alternating.expected_runs == pytest.approx(4.0)


def test_magnitudes_are_reduced_to_signs_before_counting_runs() -> None:
    # [2, 1, -1] has ONE sign change (R = 2), not two value changes: n=3, n_pos=2, n_neg=1,
    # mean = 2*2*1/3 + 1 = 7/3, var = (4/3)(1/3)/2 = 2/9, z = (2 - 7/3) / sqrt(2/9)
    raw = runs_test([2.0, 1.0, -1.0])
    assert raw.n_runs == 2
    assert raw.z == pytest.approx(-(1.0 / 3.0) / np.sqrt(2.0 / 9.0), rel=1e-12)
    assert raw.z == pytest.approx(-0.7071067811865475, rel=1e-12)
    unit = runs_test([1.0, 1.0, -1.0])
    assert raw.z == pytest.approx(unit.z, rel=1e-12)
    assert raw.p_value == pytest.approx(unit.p_value, rel=1e-12)
    assert (raw.n_runs, raw.expected_runs, raw.n_signs) == (unit.n_runs, unit.expected_runs, 3)
    pnl = [12.5, 3.0, -1.0, -8.0, 2.0]
    from_trades = trade_runs_test(pnl)
    assert from_trades is not None
    assert runs_test(pnl).z == pytest.approx(from_trades.z, rel=1e-12)
    assert runs_test(pnl).n_runs == from_trades.n_runs == 3


def test_zeros_count_in_n_and_break_runs_without_a_sign() -> None:
    # [1, 0, 1, -1]: n=4, n_pos=2, n_neg=1, mean = 2*2*1/4 + 1 = 2, var = 1*0/3 = 0 -> undefined
    with pytest.raises(
        DataError, match=r"^runs test variance is zero for 2 positive and 1 negative signs$"
    ):
        runs_test([1.0, 0.0, 1.0, -1.0])
    # [1, 0, 1, -1, -1]: n=5, n_pos=2, n_neg=2, mean = 2.6, var = 1.6*0.6/4 = 0.24, R = 4
    result = runs_test([1.0, 0.0, 1.0, -1.0, -1.0])
    assert result.n_runs == 4 and result.n_signs == 5
    assert result.z == pytest.approx((4.0 - 2.6) / np.sqrt(0.24), rel=1e-12)


def test_fails_loud_on_malformed_or_degenerate_signs() -> None:
    with pytest.raises(DataError, match=r"^runs test signs must be a 1-D array$"):
        runs_test(np.array([[1.0, -1.0]]))
    with pytest.raises(DataError, match=r"^runs test signs contain non-finite values$"):
        runs_test([1.0, float("nan"), -1.0])
    with pytest.raises(DataError, match=r"^runs test needs at least two signs, got 1$"):
        runs_test([1.0])
    with pytest.raises(DataError, match=r"^runs test needs at least two signs, got 0$"):
        runs_test([])
    with pytest.raises(
        DataError, match=r"^runs test variance is zero for 3 positive and 0 negative signs$"
    ):
        runs_test([1.0, 1.0, 1.0])
    with pytest.raises(
        DataError, match=r"^runs test variance is zero for 1 positive and 1 negative signs$"
    ):
        runs_test([1.0, -1.0])


def test_trade_runs_test_returns_none_only_for_the_undefined_cases() -> None:
    assert trade_runs_test([]) is None
    assert trade_runs_test([5.0]) is None
    assert trade_runs_test([5.0, 5.0, 5.0]) is None  # one sign only
    assert trade_runs_test([5.0, -5.0]) is None  # one win, one loss: zero variance
    assert trade_runs_test([1.0, 0.0, 1.0, -1.0]) is None  # zero-variance with a breakeven
    defined = trade_runs_test([12.5, 3.0, -1.0, -8.0, 2.0])
    assert defined is not None
    assert defined.z == pytest.approx(-0.4364357804719848, rel=1e-12)
    assert defined.n_runs == 3 and defined.n_signs == 5
    # magnitudes are irrelevant, only signs (and zeros) matter
    scaled = trade_runs_test([1e6, 1e-6, -1e3, -0.5, 7.0])
    assert scaled is not None and scaled.z == pytest.approx(defined.z, rel=1e-12)
    with pytest.raises(DataError, match=r"^trade PnLs must be a 1-D array$"):
        trade_runs_test(np.array([[1.0, -1.0, 1.0]]))
    with pytest.raises(DataError, match=r"^trade PnLs contain non-finite values$"):
        trade_runs_test([1.0, float("inf"), -1.0])


def _trade(pnl: float, entry_day: int, hold_days: int = 1) -> TradeObservation:
    entry = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=entry_day)
    return TradeObservation(
        side="BUY",
        realized_pnl=pnl,
        realized_return=pnl / 1000.0,
        entry_ts=entry,
        exit_ts=entry + timedelta(days=hold_days),
    )


def _rows(trades: list[TradeObservation] | None) -> dict[str, TradeStatistic]:
    ts = [datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(8)]
    equity = [100.0 + i for i in range(8)]
    report = build_native_tearsheet(ts, equity, rolling_window=2, trades=trades)
    return {row.metric: row for row in report.trade_statistics}


def test_tearsheet_reports_the_runs_z_over_entry_ordered_trades() -> None:
    # supplied out of entry order; entry order is +, +, -, -, + (z = -0.4364...)
    trades = [_trade(2.0, 4), _trade(12.5, 0), _trade(-8.0, 3), _trade(3.0, 1), _trade(-1.0, 2)]
    row = _rows(trades)["trade_runs_z"]
    assert row.available is True and row.unit == "z_score" and row.unavailable_reason is None
    assert row.value == pytest.approx(-0.4364357804719848, rel=1e-12)
    # in the supplied (non-entry) order the signs are +, +, -, +, - (R = 4): a different z
    assert row.value != pytest.approx(runs_test([2.0, 12.5, -8.0, 3.0, -1.0]).z, rel=1e-12)


def test_tearsheet_runs_z_is_unavailable_with_a_reason_never_nan() -> None:
    single_sign = _rows([_trade(1.0, 0), _trade(2.0, 1)])
    row = single_sign["trade_runs_z"]
    assert row.available is False and row.value is None
    assert row.unavailable_reason == "runs_test_undefined"
    one_trade = _rows([_trade(1.0, 0)])
    assert one_trade["trade_runs_z"].unavailable_reason == "runs_test_undefined"
    empty = _rows([])
    assert empty["trade_runs_z"].value is None
    assert empty["trade_runs_z"].unavailable_reason == "no_closed_trades"
    absent = _rows(None)
    assert absent["trade_runs_z"].unavailable_reason == "trade_input_unavailable"
    # the profit-factor None path keeps its own reason
    assert single_sign["profit_factor"].unavailable_reason == "no_losing_trades"

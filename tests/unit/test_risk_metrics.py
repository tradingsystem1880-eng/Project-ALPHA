"""Tail-risk metrics for the Verdict (spec §8): historical VaR, expected shortfall, risk-of-ruin.

VaR/ES are pure quantile statistics; risk-of-ruin is a stationary-bootstrap estimate of the
probability an equity path breaches a ruin drawdown, so it is seeded and deterministic.
"""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_validation import expected_shortfall, risk_of_ruin, value_at_risk


def test_value_at_risk_is_the_loss_at_the_tail_quantile() -> None:
    # 5 evenly-spaced returns; numpy 'linear' 0.10-quantile sits at position 0.10*4 = 0.4 between
    # -0.02 and -0.01 -> -0.016. VaR reports it as a positive loss fraction.
    rets = [-0.02, -0.01, 0.0, 0.01, 0.02]
    assert value_at_risk(rets, confidence=0.90) == pytest.approx(0.016)


def test_value_at_risk_fails_loud_on_degenerate_input() -> None:
    with pytest.raises(DataError):
        value_at_risk([0.01])  # < 2 returns
    with pytest.raises(DataError):
        value_at_risk([0.01, float("nan")])  # non-finite
    with pytest.raises(DataError):
        value_at_risk([0.01, 0.02], confidence=1.0)  # confidence must be in (0, 1)


def test_expected_shortfall_averages_the_tail_beyond_var() -> None:
    # Same series: the only return at/below the -0.016 quantile is -0.02, so ES = 0.02.
    rets = [-0.02, -0.01, 0.0, 0.01, 0.02]
    assert expected_shortfall(rets, confidence=0.90) == pytest.approx(0.02)
    # ES is never lighter than VaR (it averages the worst tail, which includes the VaR point).
    assert expected_shortfall(rets, confidence=0.90) >= value_at_risk(rets, confidence=0.90)


def test_expected_shortfall_fails_loud_on_degenerate_input() -> None:
    with pytest.raises(DataError):
        expected_shortfall([0.01])
    with pytest.raises(DataError):
        expected_shortfall([0.01, 0.02], confidence=0.0)


def test_risk_of_ruin_is_zero_for_a_monotone_up_path() -> None:
    # All-positive identical returns -> every resample is monotonically rising -> no drawdown ever.
    assert risk_of_ruin([0.01] * 20, ruin_drawdown=0.1, n_paths=200, seed=7) == 0.0


def test_risk_of_ruin_is_a_probability_for_a_volatile_path() -> None:
    rets = [(-0.3 if i % 2 else 0.3) for i in range(24)]  # whipsaw: clustered draws cut deep
    ror = risk_of_ruin(rets, ruin_drawdown=0.5, n_paths=500, seed=7)
    assert 0.0 < ror <= 1.0


def test_risk_of_ruin_is_deterministic_under_a_seed() -> None:
    rets = [(-0.3 if i % 2 else 0.3) for i in range(24)]
    assert risk_of_ruin(rets, n_paths=300, seed=7) == risk_of_ruin(rets, n_paths=300, seed=7)


def test_risk_of_ruin_fails_loud_on_bad_parameters() -> None:
    with pytest.raises(DataError):
        risk_of_ruin([0.01, -0.01], ruin_drawdown=0.0)  # must be in (0, 1]
    with pytest.raises(DataError):
        risk_of_ruin([0.01, -0.01], ruin_drawdown=1.5)
    with pytest.raises(DataError):
        risk_of_ruin([0.01, -0.01], n_paths=0)  # need >= 1 path
    with pytest.raises(DataError):
        risk_of_ruin([0.01])  # < 2 returns

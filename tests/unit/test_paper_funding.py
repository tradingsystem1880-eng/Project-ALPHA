"""Unit tests for the short-funding cost estimator (Phase 4g)."""

from __future__ import annotations

import pytest

from alpha_paper.errors import PaperError
from alpha_paper.funding import estimate_short_funding_cost


def test_funding_cost_scales_with_notional_rate_and_time() -> None:
    # $100k short at 7.3%/yr (730 bps) for 5 days = 100000 * 0.073 * 5/365 = 100.0
    assert estimate_short_funding_cost(100_000.0, 730.0, 5.0) == pytest.approx(100.0)


def test_zero_notional_or_zero_days_is_free() -> None:
    assert estimate_short_funding_cost(0.0, 1000.0, 30.0) == 0.0
    assert estimate_short_funding_cost(50_000.0, 1000.0, 0.0) == 0.0


@pytest.mark.parametrize(
    ("notional", "rate", "days"),
    [(-1.0, 100.0, 1.0), (1.0, -100.0, 1.0), (1.0, 100.0, -1.0)],
)
def test_negative_inputs_fail_loud(notional: float, rate: float, days: float) -> None:
    with pytest.raises(PaperError):
        estimate_short_funding_cost(notional, rate, days)

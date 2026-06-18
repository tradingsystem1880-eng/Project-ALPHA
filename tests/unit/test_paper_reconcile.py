"""Unit tests for the pure slippage-reconciliation helpers (Phase 4e)."""

from __future__ import annotations

import pytest

from alpha_paper.errors import PaperError
from alpha_paper.reconcile import realized_slippage_bps, reconcile


def test_buy_above_reference_is_a_positive_cost() -> None:
    assert realized_slippage_bps("BUY", 100.02, 100.0) == pytest.approx(2.0)


def test_sell_below_reference_is_a_positive_cost() -> None:
    assert realized_slippage_bps("SELL", 99.98, 100.0) == pytest.approx(2.0)


def test_sell_above_reference_is_favorable_negative() -> None:
    assert realized_slippage_bps("SELL", 100.02, 100.0) == pytest.approx(-2.0)


def test_non_positive_reference_fails_loud() -> None:
    with pytest.raises(PaperError, match="reference price must be positive"):
        realized_slippage_bps("BUY", 100.0, 0.0)


def test_reconcile_reports_realized_modeled_and_delta() -> None:
    rows = reconcile([("BUY", 100.02, 100.0), ("SELL", 99.99, 100.0)], modeled_bps=2.0)
    assert [r.side for r in rows] == ["BUY", "SELL"]
    assert rows[0].realized_bps == pytest.approx(2.0)
    assert rows[0].delta_bps == pytest.approx(0.0)  # realized matches modeled
    assert rows[1].realized_bps == pytest.approx(1.0)
    assert rows[1].delta_bps == pytest.approx(-1.0)  # realized 1bp < modeled 2bp

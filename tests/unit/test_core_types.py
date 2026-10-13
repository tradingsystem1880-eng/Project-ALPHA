from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from alpha_core import AlphaError, Bar, ExecutionRejectionTrace, LookAheadError


def test_bar_is_frozen() -> None:
    bar = Bar(
        symbol="BTCUSD",
        ts=datetime(2024, 1, 1, tzinfo=UTC),
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.5,
        volume=10.0,
    )
    with pytest.raises(ValidationError):
        # __setattr__ avoids the pydantic-plugin mypy error a direct frozen write would raise
        bar.__setattr__("close", 999.0)


def test_lookahead_error_is_alpha_error() -> None:
    assert issubclass(LookAheadError, AlphaError)


def test_execution_rejection_trace_requires_a_real_cash_shortfall() -> None:
    values = {
        "ts": datetime(2024, 1, 1, tzinfo=UTC),
        "instrument_id": "AAPL.SIM",
        "side": "BUY",
        "requested_quantity": 1.0,
        "reference_price": 100.0,
        "available_cash": 100.0,
        "estimated_fee": 0.01,
        "required_cash": 100.01,
        "reason": "cash_plus_commission_exceeds_free_balance",
    }
    assert ExecutionRejectionTrace(**values).required_cash == 100.01
    with pytest.raises(ValidationError, match="unaffordable CASH buy"):
        ExecutionRejectionTrace(**{**values, "required_cash": 100.0})

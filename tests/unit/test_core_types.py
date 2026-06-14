from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from alpha_core import Bar, LookAheadError


def test_bar_is_frozen() -> None:
    bar = Bar(symbol="BTCUSD", ts=datetime(2024, 1, 1, tzinfo=UTC),
              open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0)
    with pytest.raises(ValidationError):
        bar.__setattr__("close", 999.0)


def test_lookahead_error_is_alpha_error() -> None:
    from alpha_core import AlphaError
    assert issubclass(LookAheadError, AlphaError)

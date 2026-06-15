from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from alpha_core import Bar

TS = datetime(2024, 1, 2, tzinfo=UTC)


def _bar(**kw: float) -> Bar:
    base = dict(symbol="X", ts=TS, open=10.0, high=11.0, low=9.0, close=10.5, volume=100.0)
    base.update(kw)
    return Bar(**base)


def test_valid_bar_constructs() -> None:
    assert _bar().high == 11.0


@pytest.mark.parametrize("kw", [
    {"high": 8.0},          # high < low
    {"low": 12.0},          # low > open/close/high
    {"close": 99.0},        # close > high
    {"open": 0.0},          # non-positive price
    {"volume": -1.0},       # negative volume
    {"high": float("nan")}, # NaN
    {"low": float("inf")},  # inf
])
def test_invalid_bar_rejected(kw: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        _bar(**kw)


# Property: any OHLC with low <= {open,close} <= high, all positive & finite, volume >= 0 constructs.
@given(
    low=st.floats(min_value=1.0, max_value=1e4, allow_nan=False, allow_infinity=False),
    spread=st.floats(min_value=0.0, max_value=1e4, allow_nan=False, allow_infinity=False),
    o_frac=st.floats(min_value=0.0, max_value=1.0),
    c_frac=st.floats(min_value=0.0, max_value=1.0),
    volume=st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False),
)
def test_consistent_ohlc_always_constructs(
    low: float, spread: float, o_frac: float, c_frac: float, volume: float
) -> None:
    high = low + spread
    bar = Bar(symbol="X", ts=TS, open=low + o_frac * spread, high=high,
              low=low, close=low + c_frac * spread, volume=volume)
    assert bar.low <= bar.open <= bar.high
    assert bar.low <= bar.close <= bar.high

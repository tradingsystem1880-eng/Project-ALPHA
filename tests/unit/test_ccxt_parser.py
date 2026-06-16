from datetime import UTC, datetime

import pytest

from alpha_core import DataError
from alpha_data.adapters.ccxt_adapter import parse_ccxt_ohlcv
from tests.fixtures.ccxt_fixtures import ccxt_ohlcv


def test_parse_ccxt_to_raw_bars_no_actions() -> None:
    result = parse_ccxt_ohlcv(ccxt_ohlcv(), "BTC/USD")
    assert result.symbol == "BTC/USD"
    assert result.actions == []  # crypto has no splits/dividends
    assert result.bars["close"].to_list() == [42500.0, 43800.0, 43500.0]
    assert result.bars["ts"].to_list()[0] == datetime(2024, 1, 1, tzinfo=UTC)


def test_parse_ccxt_fails_loud_on_bad_ohlc() -> None:
    bad = [[1704067200000, 10.0, 5.0, 9.0, 8.0, 1.0]]  # high < open
    with pytest.raises(DataError):
        parse_ccxt_ohlcv(bad, "X/Y")

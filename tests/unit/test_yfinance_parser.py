from datetime import UTC, date, datetime

import pytest

from alpha_core import ActionType, DataError
from alpha_data.adapters.yfinance_adapter import parse_yfinance_history
from tests.fixtures.yf_fixtures import aapl_like, yf_history


def test_parse_extracts_raw_bars_and_actions() -> None:
    result = parse_yfinance_history(aapl_like(), "AAPL")
    assert result.symbol == "AAPL"
    # RAW prices preserved (the pre-split 500 is NOT adjusted down)
    assert result.bars["close"].to_list() == [500.0, 129.0, 133.0]
    assert result.bars["volume"].to_list() == [1e6, 2e6, 1.5e6]
    kinds = {(a.action_type, a.ex_date): a for a in result.actions}
    split = kinds[(ActionType.SPLIT, date(2020, 8, 31))]
    assert split.ratio == 4.0 and split.announce_date is None and split.knowledge_is_estimated
    div = kinds[(ActionType.DIVIDEND, date(2020, 8, 31))]  # fixture puts the 0.82 div on the 8/31 row
    assert div.amount == pytest.approx(0.82)


def test_parse_fails_loud_on_inconsistent_ohlc() -> None:
    bad = yf_history(
        [{"Open": 10.0, "High": 5.0, "Low": 9.0, "Close": 8.0, "Volume": 1.0,
          "Dividends": 0.0, "Stock Splits": 0.0}],
        [datetime(2024, 1, 2, tzinfo=UTC)],
    )
    with pytest.raises(DataError):
        parse_yfinance_history(bad, "X")  # high < open → invalid Bar

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
    # fixture puts the 0.82 div on the 8/31 row
    div = kinds[(ActionType.DIVIDEND, date(2020, 8, 31))]
    assert div.amount == pytest.approx(0.82)


def test_parse_fails_loud_on_inconsistent_ohlc() -> None:
    bad = yf_history(
        [
            {
                "Open": 10.0,
                "High": 5.0,
                "Low": 9.0,
                "Close": 8.0,
                "Volume": 1.0,
                "Dividends": 0.0,
                "Stock Splits": 0.0,
            }
        ],
        [datetime(2024, 1, 2, tzinfo=UTC)],
    )
    with pytest.raises(DataError):
        parse_yfinance_history(bad, "X")  # high < open → invalid Bar


def test_parse_no_actions_when_all_zero() -> None:
    df = yf_history(
        [
            {
                "Open": 10.0,
                "High": 11.0,
                "Low": 9.0,
                "Close": 10.0,
                "Volume": 1.0,
                "Dividends": 0.0,
                "Stock Splits": 0.0,
            }
        ],
        [datetime(2024, 1, 2, tzinfo=UTC)],
    )
    assert parse_yfinance_history(df, "X").actions == []


def test_parse_skips_nan_action_values() -> None:
    df = yf_history(
        [
            {
                "Open": 10.0,
                "High": 11.0,
                "Low": 9.0,
                "Close": 10.0,
                "Volume": 1.0,
                "Dividends": float("nan"),
                "Stock Splits": float("nan"),
            }
        ],
        [datetime(2024, 1, 2, tzinfo=UTC)],
    )
    result = parse_yfinance_history(df, "X")
    assert result.actions == []  # NaN is not an action
    assert result.bars.height == 1


def test_parse_dividend_only() -> None:
    df = yf_history(
        [
            {
                "Open": 10.0,
                "High": 11.0,
                "Low": 9.0,
                "Close": 10.0,
                "Volume": 1.0,
                "Dividends": 0.5,
                "Stock Splits": 0.0,
            }
        ],
        [datetime(2024, 1, 2, tzinfo=UTC)],
    )
    acts = parse_yfinance_history(df, "X").actions
    assert len(acts) == 1 and acts[0].action_type.value == "dividend"


def test_parse_split_only() -> None:
    df = yf_history(
        [
            {
                "Open": 10.0,
                "High": 11.0,
                "Low": 9.0,
                "Close": 10.0,
                "Volume": 1.0,
                "Dividends": 0.0,
                "Stock Splits": 2.0,
            }
        ],
        [datetime(2024, 1, 2, tzinfo=UTC)],
    )
    acts = parse_yfinance_history(df, "X").actions
    assert len(acts) == 1 and acts[0].action_type.value == "split"


def test_parse_non_us_session_date_preserved() -> None:
    from datetime import timedelta, timezone

    tokyo = timezone(timedelta(hours=9))
    df = yf_history(
        [{"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0, "Volume": 1.0,
          "Dividends": 0.0, "Stock Splits": 2.0}],
        [datetime(2024, 3, 15, tzinfo=tokyo)],
    )
    result = parse_yfinance_history(df, "7203.T")
    assert result.bars["ts"].to_list()[0] == datetime(2024, 3, 15, tzinfo=UTC)  # not 3/14
    assert result.actions[0].ex_date == date(2024, 3, 15)  # split ex-date is the LOCAL session date

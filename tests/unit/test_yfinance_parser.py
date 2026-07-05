from datetime import UTC, date, datetime

import pytest

from alpha_core import ActionType, DataError
from alpha_data.adapters.yfinance_adapter import parse_yfinance_history
from tests.fixtures.yf_fixtures import aapl_like, yf_history


def test_parse_reconstructs_raw_bars_and_actions() -> None:
    result = parse_yfinance_history(aapl_like(), "AAPL")
    assert result.symbol == "AAPL"
    # Yahoo serves the pre-split session /4 (125); the parser reconstructs the traded 500
    assert result.bars["close"].to_list() == [500.0, 129.0, 133.0]
    assert result.bars["open"].to_list() == [500.0, 127.0, 132.0]
    assert result.bars["volume"].to_list() == [1e6, 2e6, 1.5e6]
    kinds = {(a.action_type, a.ex_date): a for a in result.actions}
    split = kinds[(ActionType.SPLIT, date(2020, 8, 31))]
    assert split.ratio == 4.0 and split.announce_date is None and split.knowledge_is_estimated
    # the 0.82 div sits ON the split ex-day (post-split basis) -> no rescale
    div = kinds[(ActionType.DIVIDEND, date(2020, 8, 31))]
    assert div.amount == pytest.approx(0.82)


def test_parse_rescales_pre_split_dividend_to_traded_basis() -> None:
    # A dividend BEFORE the split ex-date arrives split-adjusted (0.205); raw per-share cash as
    # traded that day was 0.82 = 0.205 * 4.
    df = yf_history(
        [
            {
                "Open": 125.0,
                "High": 126.0,
                "Low": 124.0,
                "Close": 125.0,
                "Volume": 4e6,
                "Dividends": 0.205,
                "Stock Splits": 0.0,
            },
            {
                "Open": 127.0,
                "High": 131.0,
                "Low": 126.0,
                "Close": 129.0,
                "Volume": 2e6,
                "Dividends": 0.0,
                "Stock Splits": 4.0,
            },
        ],
        [datetime(2020, 8, 28, tzinfo=UTC), datetime(2020, 8, 31, tzinfo=UTC)],
    )
    acts = parse_yfinance_history(df, "AAPL").actions
    div = next(a for a in acts if a.action_type is ActionType.DIVIDEND)
    assert div.amount == pytest.approx(0.82)


def test_parse_fails_loud_when_vendor_prices_are_not_split_adjusted() -> None:
    # If Yahoo ever starts serving RAW prices (500 before a 4:1 split), reconstruction would
    # corrupt the store; the discontinuity check must refuse the frame instead.
    df = yf_history(
        [
            {
                "Open": 500.0,
                "High": 505.0,
                "Low": 498.0,
                "Close": 500.0,
                "Volume": 1e6,
                "Dividends": 0.0,
                "Stock Splits": 0.0,
            },
            {
                "Open": 127.0,
                "High": 131.0,
                "Low": 126.0,
                "Close": 129.0,
                "Volume": 2e6,
                "Dividends": 0.0,
                "Stock Splits": 4.0,
            },
        ],
        [datetime(2020, 8, 28, tzinfo=UTC), datetime(2020, 8, 31, tzinfo=UTC)],
    )
    with pytest.raises(DataError, match="split reconstruction failed"):
        parse_yfinance_history(df, "AAPL")


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
        [
            {
                "Open": 100.0,
                "High": 101.0,
                "Low": 99.0,
                "Close": 100.0,
                "Volume": 1.0,
                "Dividends": 0.0,
                "Stock Splits": 2.0,
            }
        ],
        [datetime(2024, 3, 15, tzinfo=tokyo)],
    )
    result = parse_yfinance_history(df, "7203.T")
    assert result.bars["ts"].to_list()[0] == datetime(2024, 3, 15, tzinfo=UTC)  # not 3/14
    assert result.actions[0].ex_date == date(2024, 3, 15)  # split ex-date is the LOCAL session date

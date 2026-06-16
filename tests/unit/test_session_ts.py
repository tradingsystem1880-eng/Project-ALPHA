from datetime import UTC, datetime, timedelta, timezone

import pandas as pd

from alpha_data.adapters.yfinance_adapter import _session_ts

TOKYO = timezone(timedelta(hours=9))
SYDNEY = timezone(timedelta(hours=11))
NY = timezone(timedelta(hours=-4))


def test_session_ts_preserves_local_date_across_offsets() -> None:
    # local midnight in each venue must map to that SAME calendar date at 00:00 UTC
    assert _session_ts(pd.Timestamp("2024-03-15 00:00", tz=TOKYO)) == datetime(
        2024, 3, 15, tzinfo=UTC
    )
    assert _session_ts(pd.Timestamp("2024-03-15 00:00", tz=SYDNEY)) == datetime(
        2024, 3, 15, tzinfo=UTC
    )
    assert _session_ts(pd.Timestamp("2020-08-31 00:00", tz=NY)) == datetime(2020, 8, 31, tzinfo=UTC)
    assert _session_ts(pd.Timestamp("2024-01-02 00:00", tz=UTC)) == datetime(2024, 1, 2, tzinfo=UTC)


def test_session_ts_handles_naive() -> None:
    assert _session_ts(pd.Timestamp("2024-01-02 00:00")) == datetime(2024, 1, 2, tzinfo=UTC)

"""``future_session_ts``: weekday cadence for market bars, calendar cadence for crypto."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from alpha_core import DataError
from alpha_forecast import future_session_ts


def test_weekday_cadence_skips_weekend() -> None:
    # Wed 2026-06-03, Thu 04, Fri 05 — all weekdays -> next sessions Mon 08, Tue 09, Wed 10
    recent = [datetime(2026, 6, d, tzinfo=UTC) for d in (3, 4, 5)]
    out = future_session_ts(recent, 3)
    assert out == [
        datetime(2026, 6, 8, tzinfo=UTC),
        datetime(2026, 6, 9, tzinfo=UTC),
        datetime(2026, 6, 10, tzinfo=UTC),
    ]


def test_calendar_cadence_when_history_has_weekend() -> None:
    # Fri 2026-06-05, Sat 06, Sun 07 — weekend present -> crypto: +1d steps
    recent = [datetime(2026, 6, d, tzinfo=UTC) for d in (5, 6, 7)]
    out = future_session_ts(recent, 2)
    assert out == [datetime(2026, 6, 8, tzinfo=UTC), datetime(2026, 6, 9, tzinfo=UTC)]


def test_length_and_tz_aware() -> None:
    recent = [datetime(2026, 6, 5, tzinfo=UTC)]
    out = future_session_ts(recent, 10)
    assert len(out) == 10
    assert all(t.tzinfo is not None for t in out)
    assert all(b > a for a, b in zip(out, out[1:], strict=False))


def test_rejects_bad_horizon_and_empty_input() -> None:
    recent = [datetime(2026, 6, 5, tzinfo=UTC)]
    with pytest.raises(DataError, match="horizon"):
        future_session_ts(recent, 0)
    with pytest.raises(DataError, match="empty"):
        future_session_ts([], 5)


def test_rejects_naive_timestamps() -> None:
    with pytest.raises(DataError, match="tz-aware"):
        future_session_ts([datetime(2026, 6, 5)], 2)


def test_rejects_unsorted_history() -> None:
    recent = [
        datetime(2026, 6, 5, tzinfo=UTC),
        datetime(2026, 6, 4, tzinfo=UTC),
    ]
    with pytest.raises(DataError, match="sorted"):
        future_session_ts(recent, 2)


def test_weekday_cadence_from_midweek_continues_next_day() -> None:
    recent = [datetime(2026, 6, 2, tzinfo=UTC) + timedelta(days=i) for i in range(2)]  # Tue, Wed
    out = future_session_ts(recent, 2)
    assert out == [datetime(2026, 6, 4, tzinfo=UTC), datetime(2026, 6, 5, tzinfo=UTC)]

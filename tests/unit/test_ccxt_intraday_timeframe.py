"""Offline CCXT pagination, completion cutoff and contiguous UTC grids."""

from datetime import UTC, date, datetime, timedelta
from typing import Any, Self

import pytest

from alpha_core import DataError
from alpha_data.adapters import ccxt_adapter
from alpha_data.adapters.ccxt_adapter import CCXTAdapter
from alpha_data.timeframe import parse_timeframe


def fake_exchange(monkeypatch: pytest.MonkeyPatch, stamps: list[datetime]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    rows: list[list[float]] = [[int(s.timestamp() * 1000), 100, 101, 99, 100, 2] for s in stamps]

    class Exchange:
        def fetch_ohlcv(self, symbol: str, **kwargs: Any) -> list[list[float]]:
            calls.append(kwargs)
            # Return overlapping page seams, as real APIs may do.
            return rows[:2] if len(calls) == 1 else rows[1:] if len(calls) == 2 else []

    monkeypatch.setattr("ccxt.coinbase", lambda _: Exchange())
    return calls


@pytest.mark.parametrize("text", ["1h", "5m", "7m", "7h"])
def test_fetch_full_end_day_and_page_seams(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    tf = parse_timeframe(text)
    start = datetime(2024, 1, 1, tzinfo=UTC)
    stamps = [start + i * tf.duration for i in range(3)]
    calls = fake_exchange(monkeypatch, stamps)
    result = CCXTAdapter(timeframe=tf).fetch("BTC/USD", start.date(), start.date())
    assert result.bars["ts"].to_list() == stamps
    assert all(c["timeframe"] == tf.ccxt for c in calls)
    assert calls[0]["since"] == int(start.timestamp() * 1000)
    assert CCXTAdapter(timeframe=tf).name == "ccxt:coinbase"


def test_gap_names_first_missing_start(monkeypatch: pytest.MonkeyPatch) -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    fake_exchange(monkeypatch, [start, start + timedelta(hours=2)])
    with pytest.raises(DataError, match="2024-01-01T01:00:00\\+00:00"):
        CCXTAdapter(timeframe=parse_timeframe("1h")).fetch("BTC/USD", start.date(), start.date())


def test_live_interval_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    fake_exchange(monkeypatch, [start + timedelta(hours=i) for i in range(3)])

    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> Self:
            return cls(2024, 1, 1, 2, 30, tzinfo=UTC)

    monkeypatch.setattr(ccxt_adapter, "datetime", Clock)
    result = CCXTAdapter(timeframe=parse_timeframe("1h")).fetch(
        "BTC/USD", start.date(), start.date()
    )
    assert result.bars["ts"].to_list() == [start, start + timedelta(hours=1)]


def test_daily_fetch_bounds_and_versions_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    adapter = CCXTAdapter()
    monkeypatch.setattr(
        adapter, "fetch_timeframe", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    adapter.fetch("BTC/USD", date(2024, 1, 1), date(2024, 1, 3))
    assert calls == [
        (
            ("BTC/USD", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 3, tzinfo=UTC)),
            {"timeframe": "1d"},
        )
    ]
    assert (adapter.name, adapter.version, adapter.parser_version) == ("ccxt:coinbase", "2", "1")


def test_non_divisor_grid_restarts_at_midnight(monkeypatch: pytest.MonkeyPatch) -> None:
    stamps = [
        datetime(2024, 1, 1, 14, tzinfo=UTC),
        datetime(2024, 1, 1, 21, tzinfo=UTC),
        datetime(2024, 1, 2, tzinfo=UTC),
        datetime(2024, 1, 2, 7, tzinfo=UTC),
    ]
    fake_exchange(monkeypatch, stamps)
    assert (
        CCXTAdapter(timeframe=parse_timeframe("7h"))
        .fetch("BTC/USD", date(2024, 1, 1), date(2024, 1, 2))
        .bars["ts"]
        .to_list()
        == stamps
    )


def test_misaligned_bar_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_exchange(monkeypatch, [datetime(2024, 1, 1, 0, 1, tzinfo=UTC)])
    with pytest.raises(DataError, match="aligned"):
        CCXTAdapter(timeframe=parse_timeframe("5m")).fetch(
            "BTC/USD", date(2024, 1, 1), date(2024, 1, 1)
        )


def test_daily_pagination_cursor_is_unchanged() -> None:
    start = int(datetime(2024, 1, 1, 1, tzinfo=UTC).timestamp() * 1000)
    cursors = []

    def page(since: int) -> list[list[float]]:
        cursors.append(since)
        return [[start, 100, 101, 99, 100, 2]] if len(cursors) == 1 else []

    ccxt_adapter._paginate_ohlcv(page, since_ms=start, end_ms=start + 86_400_000)
    assert cursors == [start, start + 86_400_000]


def test_non_divisor_pagination_does_not_skip_midnight(monkeypatch: pytest.MonkeyPatch) -> None:
    start = datetime(2024, 1, 1, 21, tzinfo=UTC)
    midnight = datetime(2024, 1, 2, tzinfo=UTC)
    stamps = [start, midnight, midnight + timedelta(hours=7)]
    cursors = []

    class Exchange:
        def fetch_ohlcv(self, symbol: str, *, since: int, **kwargs: Any) -> list[list[float]]:
            cursors.append(since)
            remaining = [s for s in stamps if int(s.timestamp() * 1000) >= since]
            return [[int(s.timestamp() * 1000), 100, 101, 99, 100, 2] for s in remaining[:1]]

    monkeypatch.setattr("ccxt.coinbase", lambda _: Exchange())
    result = CCXTAdapter().fetch_timeframe("BTC/USD", start, stamps[-1], timeframe="7h")
    assert result.bars["ts"].to_list() == stamps
    assert cursors[1] == int(midnight.timestamp() * 1000)


def test_non_divisor_completion_uses_full_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    start = datetime(2024, 1, 1, 14, tzinfo=UTC)
    stamps = [start, start + timedelta(hours=7), datetime(2024, 1, 2, tzinfo=UTC)]
    fake_exchange(monkeypatch, stamps)

    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> Self:
            return cls(2024, 1, 2, 1, tzinfo=UTC)

    monkeypatch.setattr(ccxt_adapter, "datetime", Clock)
    result = CCXTAdapter(timeframe=parse_timeframe("7h")).fetch(
        "BTC/USD", start.date(), date(2024, 1, 2)
    )
    assert result.bars["ts"].to_list() == [start]

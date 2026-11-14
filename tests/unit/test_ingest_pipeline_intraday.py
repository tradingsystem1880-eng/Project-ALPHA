"""Receipt-backed intraday promotion uses regular-session interval intersections."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.pipeline import stage_and_promote
from alpha_data.store import ParquetStore
from alpha_data.timeframe import parse_timeframe, store_dir
from tests.unit.test_alpaca_adapter import END, START, FakeTransport, adapter, intraday_result


def session_stamps(day: date, *, half_day: bool = False) -> list[str]:
    start = datetime(day.year, day.month, day.day, 14, 30, tzinfo=UTC)
    return [(start + timedelta(minutes=5 * i)).isoformat() for i in range(42 if half_day else 78)]


def test_complete_sessions_half_day_and_extended_hours(tmp_path: Path) -> None:
    start, end = date(2026, 11, 25), date(2026, 11, 27)
    stamps = [
        "2026-11-25T09:00:00Z",
        *session_stamps(start),
        "2026-11-26T00:00:00Z",
        *session_stamps(end, half_day=True),
        "2026-11-27T19:00:00Z",
    ]
    result = intraday_result(stamps, start, end)
    store = ParquetStore(store_dir(tmp_path, parse_timeframe("5m")))
    outcome = stage_and_promote(store, result, authoritative_source="alpaca")
    report = json.loads(outcome.quality_path.read_text())
    assert report["status"] == "passed" and report["critical_errors"] == []
    assert report["extended_hours_rows"] == 3 and report["timeframe"] == "5m"
    assert report["incoming_rows"] == 123
    assert store.read_bars("SPY").equals(result.bars)
    assert not (tmp_path / "store").exists()


@pytest.mark.parametrize(
    "defect,expected",
    [
        ("bar", "intraday_gap:2026-11-25:1:2026-11-25T15:20:00+00:00"),
        ("session", "calendar_gap:2026-11-27"),
        ("misaligned", "misaligned_bar:2026-11-25T15:21:00+00:00"),
    ],
)
def test_intraday_defects_quarantine(tmp_path: Path, defect: str, expected: str) -> None:
    start, end = date(2026, 11, 25), date(2026, 11, 27)
    stamps = session_stamps(start) + session_stamps(end, half_day=True)
    if defect == "bar":
        stamps.pop(10)
    if defect == "session":
        stamps = session_stamps(start) + ["2026-11-27T09:00:00Z"]
    result = intraday_result(stamps, start, end)
    if defect == "misaligned":
        ts = result.bars["ts"].to_list()
        ts[10] += timedelta(minutes=1)
        result = replace(result, bars=result.bars.with_columns(pl.Series("ts", ts)))
    store = ParquetStore(store_dir(tmp_path, parse_timeframe("5m")))
    with pytest.raises(DataError, match="quarantined") as caught:
        stage_and_promote(store, result, authoritative_source="alpaca")
    assert expected in str(caught.value)
    quality = next((store.root / "quarantine").glob("*/*/quality.json"))
    assert expected in json.loads(quality.read_text())["critical_errors"]
    assert store.list_symbols() == []


@pytest.mark.parametrize("tf,hours", [("1h", [14, 15, 16, 17]), ("7h", [14])])
def test_intersecting_bars_need_not_start_inside_regular_hours(
    tmp_path: Path, tf: str, hours: list[int]
) -> None:
    day = date(2026, 11, 27)
    result = intraday_result([f"2026-11-27T{h:02d}:00:00Z" for h in hours], day, day, timeframe=tf)
    outcome = stage_and_promote(
        ParquetStore(store_dir(tmp_path, parse_timeframe(tf))),
        result,
        authoritative_source="alpaca",
    )
    assert json.loads(outcome.quality_path.read_text())["extended_hours_rows"] == 0


def test_daily_quality_report_unchanged(tmp_path: Path) -> None:
    result = adapter(FakeTransport()).fetch("SPY", START, END)
    outcome = stage_and_promote(
        ParquetStore(tmp_path / "store"), result, authoritative_source="alpaca"
    )
    report = json.loads(outcome.quality_path.read_text())
    assert set(report) == {
        "schema_version",
        "status",
        "provider",
        "receipt_id",
        "symbol",
        "fetched_at",
        "critical_errors",
        "warnings",
        "changed_timestamps",
        "corrections",
        "compared_rows",
        "incoming_rows",
        "canonical_rows_after_merge",
    }
    assert report["status"] == "passed" and report["incoming_rows"] == 2


def test_adjacent_winter_pulls_keep_after_hours_bars_stamped_after_utc_midnight(
    tmp_path: Path,
) -> None:
    """A 19:30 New York bar on 2026-11-24 is stamped 00:30 UTC on 2026-11-25.

    The next pull (2026-11-25..) starts at New York midnight and rightly does not contain it, so it
    must not be reported as a missing stored session (regression: UTC-date comparison).
    """
    store = ParquetStore(store_dir(tmp_path, parse_timeframe("5m")))
    day_one, day_two = date(2026, 11, 24), date(2026, 11, 25)
    first = intraday_result([*session_stamps(day_one), "2026-11-25T00:30:00Z"], day_one, day_one)
    stage_and_promote(store, first, authoritative_source="alpaca")
    second = intraday_result(session_stamps(day_two), day_two, day_two)
    outcome = stage_and_promote(store, second, authoritative_source="alpaca")
    report = json.loads(outcome.quality_path.read_text())
    assert report["status"] == "passed", report["critical_errors"]
    assert store.read_bars("SPY").height == 78 * 2 + 1

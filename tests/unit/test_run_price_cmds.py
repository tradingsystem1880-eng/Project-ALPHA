"""Verified bars for a rule test: bars show only when they hash to the run's recorded source."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from alpha_cli import _runner, run_price_cmds
from alpha_cli.spine import reserve
from alpha_data.store import ParquetStore
from alpha_data.timeframe import DAILY, store_dir

START = datetime(2020, 1, 1, tzinfo=UTC)
LAST = START + timedelta(days=59)


def _frame(days: int, *, bump_day: int | None = None) -> pl.DataFrame:
    stamps = [START + timedelta(days=i) for i in range(days)]
    prices = [100.0 + i + (5.0 if i == bump_day else 0.0) for i in range(days)]
    return pl.DataFrame(
        {
            "ts": stamps,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": [1.0] * days,
        }
    )


def _store(home: Path, frame: pl.DataFrame) -> None:
    store = ParquetStore(store_dir(home, DAILY))
    store.write_bars("AAA", frame)
    store.write_provenance("AAA", source="vendor", adapter_version="1", parser_version="1")


def _recorded(home: Path) -> str:
    bars, _ = _runner.load_bars("AAA", data_dir=home, as_of=reserve.CUTOFF)
    return _runner.source_fingerprint(bars)


def _manifest(fingerprint: str | None) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "metadata": {"symbol": "AAA"},
        "spine": {
            "store": "home",
            "data_period": {
                "first_ts": START.isoformat(),
                "last_ts": LAST.isoformat(),
            },
        },
    }
    if fingerprint is not None:
        manifest["source_fingerprint"] = fingerprint
    return manifest


def test_equal_fingerprint_draws_the_bars(tmp_path: Path) -> None:
    _store(tmp_path, _frame(60))
    status, rows = run_price_cmds.verified_bars(_manifest(_recorded(tmp_path)), data_dir=tmp_path)
    assert status == "available"
    assert len(rows) == 60
    assert rows[0]["c"] == 100.0
    assert rows[-1]["t"] == LAST.timestamp()


def test_one_changed_bar_refuses(tmp_path: Path) -> None:
    _store(tmp_path, _frame(60))
    recorded = _recorded(tmp_path)
    _store(tmp_path, _frame(60, bump_day=10))
    status, rows = run_price_cmds.verified_bars(_manifest(recorded), data_dir=tmp_path)
    assert status == "bars_changed_since_run"
    assert rows == []


def test_no_recorded_fingerprint_refuses(tmp_path: Path) -> None:
    _store(tmp_path, _frame(60))
    status, rows = run_price_cmds.verified_bars(_manifest(None), data_dir=tmp_path)
    assert status == "price_not_saved_with_run"
    assert rows == []


def test_bars_after_the_runs_last_date_are_not_returned(tmp_path: Path) -> None:
    _store(tmp_path, _frame(60))
    recorded = _recorded(tmp_path)
    _store(tmp_path, _frame(70))  # ten later bars arrive; the first sixty are unchanged
    status, rows = run_price_cmds.verified_bars(_manifest(recorded), data_dir=tmp_path)
    assert status == "available"
    assert max(row["t"] for row in rows) == LAST.timestamp()


def test_nothing_at_or_after_the_reserved_instant_is_returned(tmp_path: Path) -> None:
    before = reserve.RESERVED_INSTANT - timedelta(days=2)
    stamps = [before + timedelta(days=i) for i in range(4)]  # last two are in the held-back period
    prices = [10.0, 11.0, 12.0, 13.0]
    _store(
        tmp_path,
        pl.DataFrame(
            {
                "ts": stamps,
                "open": prices,
                "high": prices,
                "low": prices,
                "close": prices,
                "volume": [1.0] * 4,
            }
        ),
    )
    bars, _ = _runner.load_bars("AAA", data_dir=tmp_path, as_of=reserve.CUTOFF)
    manifest = _manifest(_runner.source_fingerprint(bars))
    manifest["spine"]["data_period"]["last_ts"] = stamps[-1].isoformat()  # a lying record
    status, rows = run_price_cmds.verified_bars(manifest, data_dir=tmp_path)
    assert status == "available"
    assert all(row["t"] < reserve.RESERVED_INSTANT.timestamp() for row in rows)
    assert len(rows) == 2

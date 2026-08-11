"""Exchange-calendar, wake-safe daily scheduler and immutable intent cycle."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from alpha_cli.daily_scheduler import (
    DailyInstrument,
    due_session,
    execute_cycle,
    load_schedule,
    repair_interrupted_cycle,
    scheduler_status,
    scheduler_tick,
)
from alpha_core import DataError
from alpha_data.adapters.base import DatasetIdentity, FetchReceipt, FetchResult


def _config(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "instruments": [
                    {
                        "symbol": "SPY",
                        "provider_symbol": "SPY",
                        "instrument_id": "SPY.ARCA",
                        "asset_class": "etf",
                        "venue": "ARCX",
                        "calendar": "XNYS",
                        "currency": "USD",
                        "history_start": "2024-01-02",
                        "correction_delay_minutes": 120,
                        "nav": 100000.0,
                        "strategy": "ts_momentum",
                        "strategy_params": {},
                        "lookback": 20,
                        "skip": 1,
                        "vol_window": 10,
                        "target_vol": 0.15,
                        "rebalance_every": 1,
                        "cutoff_minutes_after_open": 5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_due_session_uses_utc_calendar_and_catches_up_after_wake(tmp_path: Path) -> None:
    item = load_schedule(_config(tmp_path / "daily.json"))[0]
    assert due_session(item, datetime(2026, 8, 3, 21, 59, tzinfo=UTC)) == date(2026, 7, 31)
    assert due_session(item, datetime(2026, 8, 3, 22, 1, tzinfo=UTC)) == date(2026, 8, 3)
    assert due_session(item, datetime(2026, 8, 9, 12, 0, tzinfo=UTC)) == date(2026, 8, 7)


def test_scheduler_tick_dispatches_latest_due_work_without_elapsed_time_state(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path / "daily.json")
    calls: list[date] = []

    def fake_execute(data_dir: Path, item: DailyInstrument, session: date) -> dict[str, str]:
        del data_dir, item
        calls.append(session)
        return {"session": session.isoformat()}

    rows = scheduler_tick(
        config,
        tmp_path,
        now=datetime(2026, 8, 3, 22, 1, tzinfo=UTC),
        execute=fake_execute,
    )
    assert calls == [date(2026, 8, 3)]
    assert rows == [{"session": "2026-08-03"}]


def test_full_cycle_uses_tiingo_snapshot_nautilus_and_publishes_intent(tmp_path: Path) -> None:
    import exchange_calendars as xcals  # type: ignore[import-untyped]

    item = load_schedule(_config(tmp_path / "daily.json"))[0]
    sessions = xcals.get_calendar("XNYS").sessions_in_range("2024-01-02", "2026-08-03")
    rows = []
    for index, session in enumerate(sessions):
        close = 100.0 + index * 0.1 + (0.05 if index % 2 else -0.03)
        rows.append(
            {
                "ts": session.to_pydatetime().replace(tzinfo=UTC),
                "open": close - 0.02,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": 1000.0,
            }
        )
    bars = pl.DataFrame(
        rows,
        schema={
            "ts": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        },
    )
    raw = b"immutable-tiingo-response"
    identity = DatasetIdentity(
        symbol="SPY",
        provider="tiingo",
        provider_symbol="SPY",
        venue="ARCX",
        asset_class="etf",
        timeframe="1D",
        calendar="XNYS",
        currency="USD",
        price_basis="raw",
    )
    receipt = FetchReceipt.create(
        identity=identity,
        requested_start=date(2024, 1, 2),
        requested_end=date(2026, 8, 3),
        fetched_at=datetime(2026, 8, 3, 22, 5, tzinfo=UTC),
        adapter_version="1",
        parser_version="1",
        response_sha256=hashlib.sha256(raw).hexdigest(),
        response_bytes=len(raw),
        row_count=bars.height,
        action_count=0,
        request_metadata={"endpoint": "/tiingo/daily/SPY/prices"},
    )

    class FakeTiingo:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
            assert (symbol, start, end) == ("SPY", date(2024, 1, 2), date(2026, 8, 3))
            return FetchResult(
                symbol="SPY",
                bars=bars,
                actions=[],
                identity=identity,
                receipt=receipt,
                raw_response=raw,
            )

    outcome = execute_cycle(
        tmp_path,
        item,
        date(2026, 8, 3),
        adapter_type=FakeTiingo,
    )

    assert outcome["simulation_engine"] == "nautilus_trader"
    assert outcome["status"] == "intent_ready"
    intent_id = str(outcome["intent_id"])
    assert (tmp_path / "paper" / "intents" / f"{intent_id}.json").is_file()
    assert (tmp_path / "snapshots" / str(outcome["snapshot_id"]) / "manifest.json").is_file()
    assert (
        execute_cycle(
            tmp_path,
            item,
            date(2026, 8, 3),
            adapter_type=FakeTiingo,
        )
        == outcome
    )

    outcome_path = tmp_path / "operations" / "daily-cycles" / "SPY" / "2026-08-03.json"
    marker_path = outcome_path.with_suffix(".running")
    outcome_path.unlink()
    marker_path.write_text("interrupted", encoding="utf-8")
    repair_interrupted_cycle(tmp_path, item, date(2026, 8, 3), acknowledge=True)

    class NoNetworkOnResume:
        def __init__(self, **kwargs: object) -> None:
            del kwargs
            raise AssertionError("an immutable snapshot recovery must not refetch")

    assert (
        execute_cycle(
            tmp_path,
            item,
            date(2026, 8, 3),
            adapter_type=NoNetworkOnResume,
        )
        == outcome
    )


def test_scheduler_status_and_explicit_interruption_repair(tmp_path: Path) -> None:
    config = _config(tmp_path / "daily.json")
    item = load_schedule(config)[0]
    session = date(2026, 8, 3)
    outcome_path, marker_path = (
        tmp_path / "operations" / "daily-cycles" / "SPY" / "2026-08-03.json",
        tmp_path / "operations" / "daily-cycles" / "SPY" / "2026-08-03.running",
    )
    marker_path.parent.mkdir(parents=True)
    marker_path.write_text("interrupted", encoding="utf-8")
    rows = scheduler_status(config, tmp_path, now=datetime(2026, 8, 3, 22, 1, tzinfo=UTC))
    assert rows[0]["completed"] is False and rows[0]["interrupted"] is True
    with pytest.raises(DataError, match="explicit acknowledgement"):
        repair_interrupted_cycle(tmp_path, item, session, acknowledge=False)
    repair_interrupted_cycle(tmp_path, item, session, acknowledge=True)
    assert not marker_path.exists() and not outcome_path.exists()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"schema_version": 2, "instruments": []},
        {"schema_version": 1, "instruments": []},
        {"schema_version": 1, "instruments": ["SPY"]},
    ],
)
def test_load_schedule_rejects_invalid_documents(tmp_path: Path, payload: object) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DataError):
        load_schedule(path)


def test_load_schedule_rejects_duplicate_symbols(tmp_path: Path) -> None:
    path = _config(tmp_path / "daily.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["instruments"].append(dict(payload["instruments"][0]))
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DataError, match="duplicate symbols"):
        load_schedule(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("symbol", ""),
        ("history_start", "bad"),
        ("nav", 0),
        ("target_vol", float("nan")),
        ("strategy_params", []),
        ("asset_class", "future"),
        ("lookback", 0),
        ("symbol", ".."),
        ("strategy_params", {"bad": float("inf")}),
    ],
)
def test_load_schedule_rejects_invalid_instrument_fields(
    tmp_path: Path, field: str, value: object
) -> None:
    path = _config(tmp_path / "daily.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["instruments"][0][field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DataError):
        load_schedule(path)


def test_cycle_and_repair_reject_ambiguous_state(tmp_path: Path) -> None:
    item = load_schedule(_config(tmp_path / "daily.json"))[0]
    session = date(2026, 8, 3)
    root = tmp_path / "operations" / "daily-cycles" / "SPY"
    root.mkdir(parents=True)
    marker = root / "2026-08-03.running"
    marker.write_text("interrupted", encoding="utf-8")
    with pytest.raises(DataError, match="interrupted run"):
        execute_cycle(tmp_path, item, session)
    marker.unlink()
    (root / "2026-08-03.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="invalid daily cycle outcome"):
        execute_cycle(tmp_path, item, session)
    with pytest.raises(DataError, match="immutable"):
        repair_interrupted_cycle(tmp_path, item, session, acknowledge=True)

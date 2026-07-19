"""Durable operational paper-session journal invariants."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from alpha_cli import paper_store
from alpha_core import DataError, ExecutionEventSink

SESSION_ID = "7e19841c-8bb3-4ab8-aeed-388f56ecfcf8"
START = datetime(2026, 7, 19, 1, 2, 3, tzinfo=UTC)


def _create(data_dir: Path) -> dict[str, object]:
    return paper_store.create_session(
        data_dir,
        provider="binance",
        symbol="BTC/USDT",
        instrument_id="BTCUSDT.BINANCE",
        strategy="ts_momentum",
        strategy_params={"lookback": 126, "target_vol": 0.15},
        snapshot_id="crypto-warmup",
        pid=4321,
        session_id=SESSION_ID,
        started_at=START,
    )


def test_create_append_heartbeat_and_finish_are_durable(tmp_path: Path) -> None:
    created = _create(tmp_path)
    assert created["session_id"] == SESSION_ID
    assert created["status"] == "starting"
    assert created["sandbox"] is True
    assert created["last_sequence"] == 0
    assert created["stale"] is False

    event = paper_store.append_event(
        tmp_path,
        SESSION_ID,
        "order",
        {"client_order_id": "O-1", "quantity": 0.001},
        ts_event_ns=1_721_351_000_000_000_000,
    )
    assert event["sequence"] == 1
    assert event["event_type"] == "order"
    assert event["ts_event_ns"] == 1_721_351_000_000_000_000

    heartbeat_at = START + timedelta(seconds=5)
    running = paper_store.set_session_status(
        tmp_path, SESSION_ID, "running", pid=4321, at=heartbeat_at
    )
    assert running["status"] == "running"
    assert running["heartbeat_at"] == "2026-07-19T01:02:08.000000Z"

    ended_at = START + timedelta(minutes=2)
    finished = paper_store.finish_session(tmp_path, SESSION_ID, status="completed", at=ended_at)
    assert finished["status"] == "completed"
    assert finished["ended_at"] == "2026-07-19T01:04:03.000000Z"
    assert finished["stale"] is False

    session_path = tmp_path / "paper" / SESSION_ID / "session.json"
    persisted = json.loads(session_path.read_text(encoding="utf-8"))
    assert "stale" not in persisted  # time-dependent state is never persisted
    assert persisted["last_sequence"] == 1
    assert paper_store.read_events(tmp_path, SESSION_ID, after=0) == [event]
    assert paper_store.read_events(tmp_path, SESSION_ID, after=1) == []


def test_public_event_sink_implements_protocol_shape_and_propagates_errors(tmp_path: Path) -> None:
    _create(tmp_path)
    sink = paper_store.PaperEventSink(tmp_path, SESSION_ID)
    assert isinstance(sink, ExecutionEventSink)
    sink.emit("order", {"id": "O-1"}, ts_event_ns=123)
    assert paper_store.read_events(tmp_path, SESSION_ID)[0]["ts_event_ns"] == 123
    with pytest.raises(DataError, match="unsupported paper event type"):
        sink.emit("bar", {})


def test_stale_is_computed_only_for_nonterminal_sessions(tmp_path: Path) -> None:
    _create(tmp_path)
    paper_store.set_session_status(tmp_path, SESSION_ID, "running", at=START)
    stale = paper_store.read_session(
        tmp_path,
        SESSION_ID,
        now=START + timedelta(seconds=31),
        stale_after_seconds=30,
    )
    assert stale["stale"] is True

    done = paper_store.finish_session(
        tmp_path, SESSION_ID, status="failed", terminal_error="feed stopped", at=START
    )
    assert done["terminal_error"] == "feed stopped"
    assert (
        paper_store.read_session(
            tmp_path,
            SESSION_ID,
            now=START + timedelta(days=1),
            stale_after_seconds=1,
        )["stale"]
        is False
    )


@pytest.mark.parametrize(
    "event_type",
    ["lifecycle", "order", "fill", "rejection", "position", "reconciliation_warning"],
)
def test_only_low_volume_operational_event_types_are_supported(
    tmp_path: Path, event_type: str
) -> None:
    _create(tmp_path)
    record = paper_store.append_event(tmp_path, SESSION_ID, event_type, {"state": "ok"})
    assert record["event_type"] == event_type


@pytest.mark.parametrize("event_type", ["bar", "quote", "tick", "log", "order_book"])
def test_high_volume_or_unknown_event_types_are_rejected(tmp_path: Path, event_type: str) -> None:
    _create(tmp_path)
    with pytest.raises(DataError, match="unsupported paper event type"):
        paper_store.append_event(tmp_path, SESSION_ID, event_type, {})


@pytest.mark.parametrize(
    "payload",
    [
        {"bad": float("nan")},
        {"bad": float("inf")},
        {"nested": {"secret": "not a scalar"}},
        {"list": [1, 2]},
    ],
)
def test_event_payload_is_strict_finite_json_scalars(
    tmp_path: Path, payload: dict[str, object]
) -> None:
    _create(tmp_path)
    with pytest.raises(DataError, match="payload"):
        paper_store.append_event(tmp_path, SESSION_ID, "order", payload)


def test_orphan_atomic_event_is_recovered_after_crash(tmp_path: Path) -> None:
    _create(tmp_path)
    session_dir = tmp_path / "paper" / SESSION_ID
    orphan = {
        "schema_version": 1,
        "session_id": SESSION_ID,
        "sequence": 1,
        "event_type": "fill",
        "recorded_at": "2026-07-19T01:02:04.000000Z",
        "ts_event_ns": None,
        "payload": {"quantity": 0.001},
    }
    (session_dir / "events").mkdir()
    (session_dir / "events" / "00000000000000000001.json").write_text(
        json.dumps(orphan), encoding="utf-8"
    )

    recovered = paper_store.read_session(tmp_path, SESSION_ID)
    assert recovered["last_sequence"] == 1
    second = paper_store.append_event(tmp_path, SESSION_ID, "position", {"quantity": 0.001})
    assert second["sequence"] == 2
    assert [row["sequence"] for row in paper_store.read_events(tmp_path, SESSION_ID)] == [1, 2]


def test_atomic_event_failure_leaves_no_visible_partial_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _create(tmp_path)
    original_write = Path.write_text

    def fail_write(path: Path, content: str, **kwargs: object) -> int:
        original_write(path, "partial", encoding="utf-8")
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", fail_write)
    with pytest.raises(OSError, match="disk full"):
        paper_store.append_event(tmp_path, SESSION_ID, "order", {"id": "O-1"})
    monkeypatch.undo()

    assert paper_store.read_events(tmp_path, SESSION_ID) == []
    events_dir = tmp_path / "paper" / SESSION_ID / "events"
    assert list(events_dir.glob(".*.tmp")) == []
    assert paper_store.read_session(tmp_path, SESSION_ID)["last_sequence"] == 0


def test_event_published_before_session_pointer_failure_is_recovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _create(tmp_path)
    original_write: Callable[[Path, str], None] = paper_store.__dict__["write_text"]
    calls = 0

    def fail_session_pointer(path: Path, content: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk full")
        original_write(path, content)

    monkeypatch.setattr(paper_store, "write_text", fail_session_pointer)
    with pytest.raises(OSError, match="disk full"):
        paper_store.append_event(tmp_path, SESSION_ID, "fill", {"quantity": 0.001})
    monkeypatch.undo()

    assert paper_store.read_session(tmp_path, SESSION_ID)["last_sequence"] == 1
    assert paper_store.read_events(tmp_path, SESSION_ID)[0]["event_type"] == "fill"


def test_partial_sessions_are_ignored_and_malformed_ids_fail_safe(tmp_path: Path) -> None:
    partial = tmp_path / "paper" / "20d917a3-05f1-4c41-9b88-ce0b0917c143"
    partial.mkdir(parents=True)
    (partial / ".session.json.crash.tmp").write_text("partial", encoding="utf-8")
    (tmp_path / "paper" / "../../escape").resolve()

    assert paper_store.list_sessions(tmp_path) == []
    with pytest.raises(DataError, match="invalid paper session id"):
        paper_store.read_session(tmp_path, "../../escape")
    with pytest.raises(DataError, match="invalid paper session id"):
        paper_store.read_events(tmp_path, "NOT-A-UUID")


def test_corrupt_session_or_event_fails_loud(tmp_path: Path) -> None:
    _create(tmp_path)
    session_dir = tmp_path / "paper" / SESSION_ID
    (session_dir / "session.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="invalid paper session"):
        paper_store.read_session(tmp_path, SESSION_ID)

    # Restore the session, then publish a malformed event under a valid sequence name.
    (session_dir / "session.json").unlink()
    session_dir.rmdir()
    _create(tmp_path)
    events = session_dir / "events"
    events.mkdir()
    (events / "00000000000000000001.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="invalid paper event"):
        paper_store.read_events(tmp_path, SESSION_ID)


def test_list_sessions_is_newest_first_and_skips_non_session_directories(tmp_path: Path) -> None:
    first = _create(tmp_path)
    other_id = "65046900-74a8-4b52-89bb-5a2f7126fa7e"
    paper_store.create_session(
        tmp_path,
        provider="binance",
        symbol="ETH/USDT",
        instrument_id="ETHUSDT.BINANCE",
        strategy="breakout",
        strategy_params={},
        snapshot_id="eth-warmup",
        session_id=other_id,
        started_at=START + timedelta(minutes=1),
    )
    (tmp_path / "paper" / "notes").mkdir()

    rows = paper_store.list_sessions(tmp_path, now=START + timedelta(minutes=1))
    assert [row["session_id"] for row in rows] == [other_id, first["session_id"]]


def test_concurrent_callbacks_receive_unique_contiguous_sequences(tmp_path: Path) -> None:
    _create(tmp_path)
    sink = paper_store.PaperEventSink(tmp_path, SESSION_ID)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda number: sink.emit("order", {"number": number}), range(12)))
    events = paper_store.read_events(tmp_path, SESSION_ID)
    assert [event["sequence"] for event in events] == list(range(1, 13))


def test_live_reader_returns_stable_prefix_while_writer_appends(tmp_path: Path) -> None:
    _create(tmp_path)
    finished = threading.Event()
    failures: list[BaseException] = []

    def write() -> None:
        try:
            for number in range(100):
                paper_store.append_event(tmp_path, SESSION_ID, "order", {"number": number})
        finally:
            finished.set()

    def read() -> None:
        try:
            while not finished.is_set():
                rows = paper_store.read_events(tmp_path, SESSION_ID)
                assert [row["sequence"] for row in rows] == list(range(1, len(rows) + 1))
        except BaseException as exc:  # assertion aid from the reader thread
            failures.append(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(write)
        reader = pool.submit(read)
        writer.result()
        reader.result()

    assert failures == []
    assert len(paper_store.read_events(tmp_path, SESSION_ID)) == 100


def test_lifecycle_and_cursor_guards_fail_closed(tmp_path: Path) -> None:
    _create(tmp_path)
    with pytest.raises(DataError, match="unsupported paper session status"):
        paper_store.set_session_status(tmp_path, SESSION_ID, "bogus")  # type: ignore[arg-type]

    running_at = START + timedelta(seconds=10)
    paper_store.set_session_status(tmp_path, SESSION_ID, "running", at=running_at)
    with pytest.raises(DataError, match="invalid paper session transition"):
        paper_store.set_session_status(tmp_path, SESSION_ID, "starting", at=running_at)
    with pytest.raises(DataError, match="terminal_error is only valid"):
        paper_store.set_session_status(
            tmp_path,
            SESSION_ID,
            "running",
            terminal_error="not terminal",
            at=running_at,
        )
    with pytest.raises(DataError, match="precedes prior heartbeat"):
        paper_store.heartbeat_session(tmp_path, SESSION_ID, at=START)
    with pytest.raises(DataError, match="terminal status required"):
        paper_store.finish_session(tmp_path, SESSION_ID, status="running")  # type: ignore[arg-type]
    with pytest.raises(DataError, match="non-negative integer"):
        paper_store.append_event(tmp_path, SESSION_ID, "order", {}, ts_event_ns=-1)
    with pytest.raises(DataError, match="non-negative integer"):
        paper_store.read_events(tmp_path, SESSION_ID, after=-1)

    completed = paper_store.finish_session(
        tmp_path, SESSION_ID, status="completed", at=running_at + timedelta(seconds=1)
    )
    assert (
        paper_store.set_session_status(
            tmp_path, SESSION_ID, "completed", at=running_at + timedelta(seconds=2)
        )
        == completed
    )
    with pytest.raises(DataError, match="cannot heartbeat terminal"):
        paper_store.heartbeat_session(tmp_path, SESSION_ID)
    with pytest.raises(DataError, match="cannot append to terminal"):
        paper_store.append_event(tmp_path, SESSION_ID, "order", {})

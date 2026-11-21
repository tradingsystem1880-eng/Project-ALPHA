"""`alpha follow update`: one journal entry per new session, decided on the close, filled at the
next open, point in time. Synthetic store that grows one bar at a time; injected clock."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from alpha_cli import _runner, follow_store, follow_update
from alpha_cli.follow_journal import JournalRefusal
from alpha_cli.spine.errors import SpineError
from tests.fixtures.follow_fixtures import (
    BUY_AND_SELL,
    DAYS,
    F0,
    FIRST,
    LONG_AT_START,
    RUN,
    START,
    World,
)


def _world(tmp_path: Path, slope: float = -0.2, forward: list[float] | None = None) -> World:
    return World(tmp_path, slope, BUY_AND_SELL if forward is None else forward)


def _update(world: World, follow: str, at: datetime) -> dict[str, Any]:
    return follow_update.update_follow(world.home, follow, clock=lambda: at)


def _day(k: int) -> str:
    return DAYS[F0 + k].isoformat()


def _entries(world: World, follow: str) -> list[Any]:
    return follow_store.entries_of(world.home, follow)


def _run_days(world: World, follow: str, count: int) -> None:
    for k in range(count):
        world.grow()
        _update(world, follow, world.close_of(k))


def test_day_by_day_one_entry_per_session_and_the_fill_is_the_next_open(tmp_path: Path) -> None:
    world = _world(tmp_path)
    follow = world.start()
    assert _update(world, follow, START + timedelta(minutes=30))["status"] == "no-op"
    _run_days(world, follow, 5)
    entries = _entries(world, follow)
    assert [e.kind for e in entries] == ["start", *["bar"] * 5]
    assert [e.session_date.isoformat() for e in entries[1:]] == [_day(k) for k in range(5)]
    first, second = entries[1].payload, entries[2].payload
    assert first["decision"]["action"] == "enter"
    assert first["decision"]["words"] == "would buy at the next open"
    assert first["fills"] == []
    fill = second["fills"][0]
    assert fill["side"] == "buy" and fill["bar_ts"].startswith(_day(1))
    assert abs(fill["price"] - world.open_of(1) * 1.0002) < 0.01
    assert second["decision"]["words"] == "holding"
    assert entries[3].payload["decision"]["words"] == "holding"
    last = entries[5].payload
    assert last["decision"]["words"] == "would sell at the next open"
    assert last["book"]["pending"]["side"] == "sell"
    assert entries[1].payload["book"]["units"] == 0.0
    assert entries[2].payload["book"]["units"] > 0.0
    assert entries[2].payload["readings"].keys() >= {"fast_sma", "slow_sma"}


def test_an_update_run_twice_is_a_no_op(tmp_path: Path) -> None:
    world = _world(tmp_path)
    follow = world.start()
    world.grow()
    _update(world, follow, world.close_of(0))
    path = tmp_path / "forward" / follow / "journal.jsonl"
    before = path.read_bytes()
    again = _update(world, follow, world.close_of(0))
    assert again["status"] == "no-op"
    assert "already" in again["message"]
    assert path.read_bytes() == before


def test_a_gap_of_three_sessions_is_missed_not_normal(tmp_path: Path) -> None:
    world = _world(tmp_path)
    follow = world.start()
    for _ in range(3):
        world.grow()
    _update(world, follow, world.open_after(2) + timedelta(hours=1))
    entries = _entries(world, follow)[1:]
    assert [e.kind for e in entries] == ["missed"] * 3
    assert [e.session_date.isoformat() for e in entries] == [_day(k) for k in range(3)]
    assert entries[0].payload["would_have"] == "would buy at the next open"
    assert all(e.payload["fills"] == [] for e in entries)
    assert all(e.payload["book"]["units"] == 0.0 for e in entries)


def test_only_the_sessions_past_their_next_open_are_missed(tmp_path: Path) -> None:
    world = _world(tmp_path)
    follow = world.start()
    for _ in range(3):
        world.grow()
    _update(world, follow, world.close_of(2))
    assert [e.kind for e in _entries(world, follow)[1:]] == ["missed", "missed", "bar"]


def test_a_missing_bar_gives_a_late_entry_with_no_decision(tmp_path: Path) -> None:
    world = _world(tmp_path)
    follow = world.start()
    _update(world, follow, world.close_of(0))
    late = _entries(world, follow)[-1]
    assert late.kind == "late" and late.session_date == FIRST
    assert "decision" not in late.payload and late.bar_hashes == {}
    world.grow()
    world.grow()
    _update(world, follow, world.close_of(1))
    kinds = [e.kind for e in _entries(world, follow)]
    assert kinds == ["start", "late", "bar"]


def test_a_changed_historical_bar_breaks_the_replay_and_names_the_session(tmp_path: Path) -> None:
    world = _world(tmp_path)
    follow = world.start()
    _run_days(world, follow, 3)
    journal = tmp_path / "forward" / follow / "journal.jsonl"
    kept = journal.read_bytes()
    world.edit_close(1, world.closes[F0 + 1] - 30.0)
    world.grow()
    _update(world, follow, world.close_of(3))
    assert journal.read_bytes().startswith(kept)
    replay = _entries(world, follow)[-1].payload["replay"]
    assert replay["agrees"] is False
    assert replay["bars_changed_from"] == _day(1)
    assert _day(1) in {d["session"] for d in replay["differences"]}
    plain = _entries(world, follow)[1].payload["replay"]
    assert plain["agrees"] is True and plain["differences"] == []


def test_an_untouched_history_replays_equal(tmp_path: Path) -> None:
    world = _world(tmp_path)
    follow = world.start()
    _run_days(world, follow, 5)
    for entry in _entries(world, follow)[1:]:
        assert entry.payload["replay"]["agrees"] is True


def test_a_rule_already_long_at_the_start_keeps_the_paper_book_flat(tmp_path: Path) -> None:
    world = _world(tmp_path, slope=0.5, forward=LONG_AT_START)
    follow = world.start()
    _run_days(world, follow, 9)
    payloads = [e.payload for e in _entries(world, follow)[1:]]
    for flat in payloads[:3]:
        assert flat["book"]["units"] == 0.0 and flat["fills"] == []
        assert "paper stays flat" in flat["decision"]["words"]
    assert [p["fills"] for p in payloads[:5]] == [[]] * 5
    entry = next(i for i, p in enumerate(payloads) if p["decision"]["action"] == "enter")
    assert entry >= 5 and payloads[entry + 1]["fills"][0]["side"] == "buy"


def test_nothing_before_the_start_is_scored_or_shown(tmp_path: Path) -> None:
    world = _world(tmp_path, slope=0.5, forward=LONG_AT_START)
    follow = world.start()
    _run_days(world, follow, 6)
    text = json.dumps([e.model_dump(mode="json") for e in _entries(world, follow)[1:]])
    found = {date.fromisoformat(d) for d in re.findall(r"\d{4}-\d{2}-\d{2}", text)}
    assert found and min(found) >= FIRST
    for entry in _entries(world, follow)[1:]:
        assert entry.payload["book"]["closed_pnl_cum"] == 0.0


def _tree(home: Path) -> dict[str, tuple[int, int]]:
    return {
        str(p.relative_to(home)): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(home.rglob("*"))
        if "forward" not in p.relative_to(home).parts
    }


def test_an_update_writes_nothing_outside_forward_and_no_ledger_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.spine import ledger, run

    world = _world(tmp_path)
    follow = world.start()
    world.grow()
    calls: list[str] = []
    monkeypatch.setattr(ledger, "append_trial", lambda *a, **k: calls.append("trial"))
    monkeypatch.setattr(run, "run_idea", lambda *a, **k: calls.append("run_idea"))
    before = _tree(tmp_path)
    _update(world, follow, world.close_of(0))
    assert _tree(tmp_path) == before
    assert calls == []
    assert not (tmp_path / "ledger").exists()


def test_the_forward_path_uses_the_engine_step_of_the_rule_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = _world(tmp_path)
    follow = world.start()
    world.grow()
    seen: list[str] = []
    real = _runner.run_full_backtest

    def spy(bars: Any, spec: Any, **kw: Any) -> Any:
        seen.append(spec.strategy_name)
        return real(bars, spec, **kw)

    monkeypatch.setattr(_runner, "run_full_backtest", spy)
    _update(world, follow, world.close_of(0))
    assert "ma_crossover" in seen


def test_the_run_spec_of_a_rule_test_is_pinned(tmp_path: Path) -> None:
    """The forward path builds its spec with the rule test's own function. Pinned from main."""
    from alpha_cli.spine.run import assemble_run_spec
    from tests.fixtures.follow_fixtures import IDEA

    spec = assemble_run_spec(IDEA, "SPY", 252, 400)
    text = json.dumps(dataclasses.asdict(spec), sort_keys=True)
    assert hashlib.sha256(text.encode()).hexdigest() == PINNED_SPEC


PINNED_SPEC = "d31842b87a841fd3475481b77e7234cfc1e6b3084aa2052de051310c68ec6d94"


def test_a_follow_whose_spec_no_longer_matches_is_refused(tmp_path: Path) -> None:
    world = _world(tmp_path)
    follow = world.start()
    world.grow()
    path = tmp_path / "runs" / RUN / "spec.json"
    spec = json.loads(path.read_text())
    spec["rule"]["fast"] = 2
    path.write_text(json.dumps(spec))
    with pytest.raises(SpineError) as caught:
        _update(world, follow, world.close_of(0))
    assert caught.value.payload["code"] == "FOLLOW_SPEC_CHANGED"
    assert len(_entries(world, follow)) == 1


def test_a_stopped_follow_is_refused(tmp_path: Path) -> None:
    world = _world(tmp_path)
    follow = world.start()
    follow_store.stop_follow(tmp_path, follow, reason="test", clock=lambda: START)
    with pytest.raises((SpineError, JournalRefusal)) as caught:
        _update(world, follow, world.close_of(0))
    assert caught.value.payload["code"] == "FOLLOW_STOPPED"


def test_a_setup_follow_is_refused_in_plain_words(tmp_path: Path) -> None:
    world = _world(tmp_path)
    folder = tmp_path / "setups" / ("f" * 16)
    folder.mkdir(parents=True)
    manifest = {"find_id": "f" * 16, "spec_sha256": "9" * 64, "assets": [{"asset": "SPY"}]}
    (folder / "manifest.json").write_text(json.dumps(manifest))
    from alpha_cli import follow_source

    source = follow_source.setup_find_source(tmp_path, "f" * 16)
    facts = follow_store.start_follow(tmp_path, source, card="", size_pct=10.0, clock=lambda: START)
    with pytest.raises(SpineError) as caught:
        _update(world, str(facts["follow_id"]), world.close_of(0))
    assert caught.value.payload["code"] == "FOLLOW_UPDATE_SETUP_NOT_BUILT"
    assert "Follow a setup trade instead" in str(caught.value)


def _decisions(
    bars: list[Any], first: int
) -> dict[date, tuple[bool, tuple[tuple[str, float], ...]]]:
    from alpha_cli import follow_replay
    from tests.fixtures.follow_fixtures import IDEA

    result = follow_replay.replay(bars, IDEA, first)
    return {
        day: (row.long, tuple(sorted(row.readings.items()))) for day, row in result.sessions.items()
    }


def test_no_decision_changes_when_later_bars_arrive(tmp_path: Path) -> None:
    """For every prefix of the series, the decision for session t equals the decision computed
    when only bars up to t are stored."""
    world = _world(tmp_path, slope=0.5, forward=LONG_AT_START)
    n = 11
    world.write(n)
    bars, _ = _runner.load_bars("SPY", data_dir=tmp_path)
    full = _decisions(bars[: F0 + n], F0)
    assert len(full) == n
    for k in range(1, n + 1):
        prefix = _decisions(bars[: F0 + k], F0)
        assert prefix.keys() == set(list(full)[:k])
        assert {day: full[day] for day in prefix} == prefix


def test_a_bar_stamped_after_the_clock_is_never_used(tmp_path: Path) -> None:
    world = _world(tmp_path)
    follow = world.start()
    world.write(4)
    _update(world, follow, world.close_of(1))
    entries = _entries(world, follow)[1:]
    assert [e.session_date.isoformat() for e in entries] == [_day(0), _day(1)]
    assert max(e.payload["latest_bar_ts"] for e in entries).startswith(_day(1))


def test_the_engine_code_hash_is_in_each_entry(tmp_path: Path) -> None:
    world = _world(tmp_path)
    follow = world.start()
    _run_days(world, follow, 2)
    hashes = {e.payload["engine_code_sha256"] for e in _entries(world, follow)[1:]}
    assert len(hashes) == 1 and len(next(iter(hashes))) == 64


def test_a_changed_engine_shows_as_a_disagreeing_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import follow_replay

    world = _world(tmp_path)
    follow = world.start()
    _run_days(world, follow, 2)
    monkeypatch.setattr(follow_replay, "engine_code_sha256", lambda: "e" * 64)
    world.grow()
    _update(world, follow, world.close_of(2))
    replay = _entries(world, follow)[-1].payload["replay"]
    assert replay["agrees"] is False
    assert any(d["what"] == "engine" for d in replay["differences"])


def _crypto_world(home: Path) -> tuple[str, Callable[[int], None]]:
    """BTC/USDT, a bar every UTC day. Down history, then up: long from the first forward day."""
    import polars as pl

    from alpha_cli import follow_source
    from alpha_data.store import ParquetStore
    from tests.fixtures.follow_fixtures import IDEA

    spec = IDEA.model_copy(update={"assets": ("BTC/USDT",)})
    days = [date(2026, 6, 1) + timedelta(n) for n in range(220)]
    first = days.index(date(2026, 11, 19))
    closes = [100.0 - 0.2 * i if i < first else 70.0 + 3.0 * (i - first) for i in range(len(days))]
    rows = [
        {
            "ts": datetime(d.year, d.month, d.day, tzinfo=UTC),
            "open": closes[i - 1] if i else closes[0],
            "high": max(closes[i - 1] if i else closes[0], closes[i]),
            "low": min(closes[i - 1] if i else closes[0], closes[i]),
            "close": closes[i],
            "volume": 1.0,
        }
        for i, d in enumerate(days)
    ]
    folder = home / "runs" / RUN
    folder.mkdir(parents=True)
    spine = {"spec_sha256": spec.spec_sha256, "store": "home", "idea_card": ""}
    manifest = {"run_id": RUN, "metadata": {"symbol": "BTC/USDT"}, "spine": spine}
    (folder / "manifest.json").write_text(json.dumps(manifest))
    body = {**spec.model_dump(mode="json"), "spec_sha256": spec.spec_sha256}
    (folder / "spec.json").write_text(json.dumps(body, sort_keys=True))
    bars = ParquetStore(home / "store")
    bars.write_provenance("BTC/USDT", source="binance", adapter_version="1", parser_version="1")

    def write(forward: int) -> None:
        bars.write_bars("BTC/USDT", pl.DataFrame(rows[: first + forward]))

    write(0)
    source = follow_source.rule_test_source(home, RUN)
    facts = follow_store.start_follow(home, source, card="", size_pct=10.0, clock=lambda: START)
    return str(facts["follow_id"]), write


def test_a_crypto_follow_trades_every_day_and_labels_the_late_fill_open(tmp_path: Path) -> None:
    follow, write = _crypto_world(tmp_path)
    write(1)
    day = datetime(2026, 11, 20, 0, 30, tzinfo=UTC)
    out = follow_update.update_follow(tmp_path, follow, clock=lambda: day)
    assert out["written"][0]["kind"] == "bar"
    entry = _entries_of(tmp_path, follow)[-1]
    assert entry.payload["labels"] == ["written 0.5 h after the fill open"]
    write(3)
    later = datetime(2026, 11, 22, 5, 0, tzinfo=UTC)
    follow_update.update_follow(tmp_path, follow, clock=lambda: later)
    kinds = [(e.session_date.isoformat(), e.kind) for e in _entries_of(tmp_path, follow)[2:]]
    assert kinds == [("2026-11-20", "missed"), ("2026-11-21", "bar")]


def _entries_of(home: Path, follow: str) -> list[Any]:
    return follow_store.entries_of(home, follow)

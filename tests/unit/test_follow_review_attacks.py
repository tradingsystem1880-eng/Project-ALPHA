"""Review attacks on the follow journal and `alpha follow update`, with their own helpers.

Point in time, back-fill, late and missed sessions, the paper book and separation. Each test
names the attack it makes. The clock is injected; nothing sleeps.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from alpha_cli import follow_replay, follow_show, follow_source
from alpha_cli import follow_store as store
from alpha_cli.follow_chain import append_entry, read_entries, verify_journal
from alpha_cli.follow_journal import Entry, JournalRefusal, entry_hash_of
from alpha_cli.follow_update import update_follow
from alpha_cli.spine.errors import SpineError
from alpha_cli.spine.spec import IdeaSpec
from alpha_data.sessions import session_bounds, sessions_between
from alpha_data.store import ParquetStore

D = date(2026, 11, 2)  # a Monday after the US clocks changed (1 Nov 2026)
T = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
NY = sessions_between("XNYS", date(2026, 3, 2), date(2026, 12, 31))
RULE = {"kind": "ma_cross", "fast": 2, "slow": 4}


def _code(error: pytest.ExceptionInfo[JournalRefusal]) -> str:
    return str(error.value.payload["code"])


def _start(folder: Path, calendar: str) -> None:
    payload = {"market_calendar": calendar, "follow_id": "f"}
    append_entry(folder, kind="start", session_date=D, clock=lambda: T, payload=payload)


def _bar(folder: Path, day: date, at: datetime, payload: dict[str, object] | None = None) -> None:
    append_entry(folder, kind="bar", session_date=day, clock=lambda: at, payload=payload)


def test_a_caller_cannot_set_or_stretch_must_write_by(tmp_path: Path) -> None:
    _start(tmp_path, "XNYS")
    closes = session_bounds("XNYS", D)[1]
    opens_next = session_bounds("XNYS", date(2026, 11, 3))[0]
    late = opens_next + timedelta(minutes=1)
    with pytest.raises(JournalRefusal) as forged:
        _bar(tmp_path, D, late, {"must_write_by": (late + timedelta(days=9)).isoformat()})
    with pytest.raises(JournalRefusal) as plain:
        _bar(tmp_path, D, late)
    with pytest.raises(JournalRefusal) as early:
        _bar(tmp_path, D, closes - timedelta(minutes=1))
    assert (_code(forged), _code(plain)) == (
        "FOLLOW_DEADLINE_NOT_FROM_CALENDAR",
        "FOLLOW_BAR_TOO_LATE",
    )
    assert _code(early) == "FOLLOW_BAR_BEFORE_CLOSE"
    _bar(tmp_path, D, closes + timedelta(minutes=5))
    written = read_entries(tmp_path)[-1]
    assert written.payload["must_write_by"] == opens_next.isoformat()


def test_a_hand_written_line_with_a_stretched_deadline_breaks_verify(tmp_path: Path) -> None:
    _start(tmp_path, "XNYS")
    first = read_entries(tmp_path)[0]
    late = session_bounds("XNYS", date(2026, 11, 3))[0] + timedelta(hours=3)
    fields = {
        "seq": 2,
        "session_date": D.isoformat(),
        "written_at": late.isoformat(),
        "kind": "bar",
        "bar_hashes": {},
        "payload": {"must_write_by": (late + timedelta(days=1)).isoformat()},
        "prev_hash": first.entry_hash,
    }
    dumped = Entry.model_validate({**fields, "entry_hash": "0" * 64}).model_dump(mode="json")
    line = {**dumped, "entry_hash": entry_hash_of(dumped)}
    with (tmp_path / "journal.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(line, sort_keys=True) + "\n")
    (tmp_path / "head.json").write_text(json.dumps({"entries": 2, "head": line["entry_hash"]}))
    found = verify_journal(tmp_path).first_break
    assert found is not None and (found.seq, found.code) == (2, "FOLLOW_DEADLINE_NOT_FROM_CALENDAR")


def test_a_daily_market_bar_waits_for_00_utc_and_takes_no_deadline(tmp_path: Path) -> None:
    _start(tmp_path, "")
    midnight = datetime(2026, 11, 3, tzinfo=UTC)
    with pytest.raises(JournalRefusal) as forming:
        _bar(tmp_path, D, midnight - timedelta(seconds=1))
    with pytest.raises(JournalRefusal) as forged:
        _bar(tmp_path, D, midnight, {"must_write_by": "2030-01-01T00:00:00+00:00"})
    with pytest.raises(JournalRefusal) as late:
        _bar(tmp_path, D, midnight + timedelta(days=1, seconds=1))
    assert _code(forming) == "FOLLOW_BAR_BEFORE_CLOSE"
    assert _code(forged) == "FOLLOW_DEADLINE_NOT_FROM_CALENDAR"
    assert _code(late) == "FOLLOW_BAR_TOO_LATE"


def _chain(folder: Path) -> list[str]:
    _start(folder, "")
    for k in range(1, 5):
        day = D + timedelta(days=k)
        _bar(folder, day, datetime(day.year, day.month, day.day, 1, tzinfo=UTC) + timedelta(1))
    return (folder / "journal.jsonl").read_text(encoding="utf-8").splitlines(keepends=True)


@pytest.mark.parametrize("attack", ["edit", "delete", "reorder", "truncate", "shorter", "partial"])
def test_every_tamper_of_the_journal_file_is_named(tmp_path: Path, attack: str) -> None:
    lines = _chain(tmp_path)
    if attack == "edit":
        edited = json.loads(lines[2])
        edited["payload"]["paper"] = False
        lines[2] = json.dumps(edited, sort_keys=True) + "\n"
    elif attack == "delete":
        del lines[2]
    elif attack == "reorder":
        lines[2], lines[3] = lines[3], lines[2]
    elif attack == "truncate":
        lines = lines[:-1]
    elif attack == "partial":
        lines[-1] = lines[-1][:30]
    if attack == "shorter":
        other = tmp_path / "other"
        other.mkdir()
        lines = _chain(other)[:3]
    (tmp_path / "journal.jsonl").write_text("".join(lines), encoding="utf-8")
    assert verify_journal(tmp_path).first_break is not None


def test_a_second_start_and_a_clock_set_back_are_refused(tmp_path: Path) -> None:
    _chain(tmp_path)
    with pytest.raises(JournalRefusal) as again:
        _start(tmp_path, "")
    with pytest.raises(JournalRefusal) as back:
        _bar(tmp_path, D + timedelta(days=5), datetime(2026, 11, 7, 0, 30, tzinfo=UTC))
    assert (_code(again), _code(back)) == ("FOLLOW_SECOND_START", "FOLLOW_CLOCK_BACK")


class _Store:
    """History up to `start`, then forward bars written one at a time; opens are prior closes."""

    def __init__(self, home: Path, symbol: str, days: list[date], steps: list[float]) -> None:
        self.home, self.symbol, self.days = home, symbol, days
        self.closes = [1000.0]
        for k in range(1, len(days)):
            self.closes.append(self.closes[-1] + steps[k % len(steps)])
        self.skip: set[int] = set()
        ParquetStore(home / "store").write_provenance(
            symbol, source="alpaca", adapter_version="1", parser_version="1"
        )

    def put(self, upto: int) -> None:
        rows = []
        for i in range(upto + 1):
            if i in self.skip:
                continue
            o = self.closes[i - 1] if i else self.closes[i]
            c = self.closes[i]
            day = self.days[i]
            ts = datetime(day.year, day.month, day.day, tzinfo=UTC)
            rows.append(
                {
                    "ts": ts,
                    "open": o,
                    "high": max(o, c),
                    "low": min(o, c),
                    "close": c,
                    "volume": 5.0,
                }
            )
        ParquetStore(self.home / "store").write_bars(self.symbol, pl.DataFrame(rows))

    def follow(self, at: datetime) -> str:
        idea = IdeaSpec.model_validate({"assets": [self.symbol], "rule": RULE})
        run = self.home / "runs" / ("c" * 16)
        run.mkdir(parents=True)
        spine = {"spec_sha256": idea.spec_sha256, "store": "home", "idea_card": ""}
        manifest = {"run_id": "c" * 16, "metadata": {"symbol": self.symbol}, "spine": spine}
        (run / "manifest.json").write_text(json.dumps(manifest))
        spec = {**idea.model_dump(mode="json"), "spec_sha256": idea.spec_sha256}
        (run / "spec.json").write_text(json.dumps(spec, sort_keys=True))
        source = follow_source.rule_test_source(self.home, "c" * 16)
        facts = store.start_follow(self.home, source, card="", size_pct=50.0, clock=lambda: at)
        return str(facts["follow_id"])


STEPS = [-1.0, -1.5, -1.0, 2.0, 2.5, 3.0, -4.0, -4.0, 1.0, 1.5, -3.0]
S0 = NY.index(date(2026, 11, 2))


def _ny(home: Path) -> tuple[_Store, str]:
    world = _Store(home, "SPY", NY, STEPS)
    world.put(S0 - 1)
    return world, world.follow(datetime(2026, 11, 2, 13, 0, tzinfo=UTC))


def _after_close(i: int, minutes: int = 30) -> datetime:
    return session_bounds("XNYS", NY[i])[1] + timedelta(minutes=minutes)


def _at(i: int, minutes: int = 30) -> Callable[[], datetime]:
    when = _after_close(i, minutes)
    return lambda: when


def _snapshot(home: Path) -> dict[str, str]:
    return {
        str(p.relative_to(home)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(home.rglob("*"))
        if p.is_file() and "forward" not in p.relative_to(home).parts
    }


def test_a_forming_bar_is_never_read_as_closed(tmp_path: Path) -> None:
    world, fid = _ny(tmp_path)
    world.put(S0)  # the bar of the start session is stored at 00:00 of its date
    midday = session_bounds("XNYS", NY[S0])[0] + timedelta(hours=2)
    assert update_follow(tmp_path, fid, clock=lambda: midday)["status"] == "no-op"
    done = update_follow(tmp_path, fid, clock=lambda: _after_close(S0))
    assert [w["kind"] for w in done["written"]] == ["bar"]


def test_skipped_sessions_are_missed_with_no_fill_and_holidays_are_not_sessions(
    tmp_path: Path,
) -> None:
    world, fid = _ny(tmp_path)
    for i in range(S0, S0 + 22):
        world.put(i)
        before = _snapshot(tmp_path)
        if i % 5 == 0 or S0 + 7 <= i <= S0 + 9:
            continue  # not updated until after the next open; three in a row once
        update_follow(tmp_path, fid, clock=_at(i))
        again = update_follow(tmp_path, fid, clock=_at(i, 40))
        assert again["status"] == "no-op"
        assert _snapshot(tmp_path) == before  # nothing outside forward/ changed
    entries = store.entries_of(tmp_path, fid)
    days = [e.session_date for e in entries[1:]]
    assert days == NY[S0 : S0 + 22] and date(2026, 11, 26) not in days  # Thanksgiving
    for e in entries:
        if e.kind == "missed":
            assert e.payload["fills"] == [] and "decision" not in e.payload
        if e.kind == "bar":
            assert e.written_at <= datetime.fromisoformat(e.payload["must_write_by"])
    assert {e.kind for e in entries[1:]} == {"bar", "missed"}


def test_book_recomputes_from_fills_and_late_stays_late(tmp_path: Path) -> None:
    world, fid = _ny(tmp_path)
    world.skip = {S0 + 3}
    for i in range(S0, S0 + 15):
        world.put(i)
        update_follow(tmp_path, fid, clock=_at(i))
    world.skip = set()
    world.put(S0 + 15)
    update_follow(tmp_path, fid, clock=lambda: _after_close(S0 + 15))
    entries = store.entries_of(tmp_path, fid)[1:]
    kinds = {e.session_date: e.kind for e in entries}
    assert kinds[NY[S0 + 3]] == "late"
    cash, units, fees = 10_000.0, 0.0, 0.0
    for e in entries:
        for f in e.payload["fills"]:
            sign = 1.0 if f["side"] == "buy" else -1.0
            cash -= sign * f["units"] * f["price"] + f["fee"]
            units += sign * f["units"]
            fees += f["fee"]
        book = e.payload["book"]
        assert abs(book["cash"] - cash) < 1e-6 and abs(book["units"] - units) < 1e-9
        assert abs(book["fees_cum"] - fees) < 1e-9
    assert any(e.payload["fills"] for e in entries)


def test_a_revised_bar_shows_as_a_replay_difference_and_the_journal_is_kept(
    tmp_path: Path,
) -> None:
    world, fid = _ny(tmp_path)
    for i in range(S0, S0 + 6):
        world.put(i)
        update_follow(tmp_path, fid, clock=_at(i))
    kept = (store.folder_of(tmp_path, fid) / "journal.jsonl").read_bytes()
    world.closes[S0 + 2] += 7.0
    world.put(S0 + 6)
    out = update_follow(tmp_path, fid, clock=lambda: _after_close(S0 + 6))
    assert out["replay"]["agrees"] is False
    assert out["replay"]["bars_changed_from"] == NY[S0 + 2].isoformat()
    assert (store.folder_of(tmp_path, fid) / "journal.jsonl").read_bytes().startswith(kept)


def test_decisions_are_a_prefix_property_of_the_bars_known(tmp_path: Path) -> None:
    """Daily updates and one late catch-up see the same bars, so the same decisions."""
    daily, fid = _ny(tmp_path / "a")
    for i in range(S0, S0 + 12):
        daily.put(i)
        update_follow(tmp_path / "a", fid, clock=_at(i))
    words = {
        e.session_date: (e.payload["decision"]["long"], e.payload["readings"])
        for e in store.entries_of(tmp_path / "a", fid)
        if e.kind == "bar"
    }
    other, gid = _ny(tmp_path / "b")
    other.put(S0 + 30)  # far more bars are stored, but the clock is earlier
    for i in range(S0, S0 + 12):
        update_follow(tmp_path / "b", gid, clock=_at(i))
    again = {
        e.session_date: (e.payload["decision"]["long"], e.payload["readings"])
        for e in store.entries_of(tmp_path / "b", gid)
        if e.kind == "bar"
    }
    assert words == again and len(words) == 12


def test_a_crypto_follow_reads_no_bar_before_00_utc(tmp_path: Path) -> None:
    days = [date(2026, 3, 1) + timedelta(days=k) for k in range(280)]
    world = _Store(tmp_path, "BTC/USD", days, STEPS)
    s0 = days.index(date(2026, 11, 2))
    world.put(s0 - 1)
    fid = world.follow(datetime(2026, 11, 1, 22, 0, tzinfo=UTC))
    world.put(s0)
    at_2359 = datetime(2026, 11, 2, 23, 59, tzinfo=UTC)
    early = update_follow(tmp_path, fid, clock=lambda: at_2359)["written"]
    assert [(w["session"], w["kind"]) for w in early] == [("2026-11-01", "bar")]
    done = update_follow(tmp_path, fid, clock=lambda: at_2359 + timedelta(minutes=2))
    assert [(w["session"], w["kind"]) for w in done["written"]] == [("2026-11-02", "bar")]
    first = store.entries_of(tmp_path, fid)[0]
    assert first.payload["market_calendar"] == ""


@pytest.mark.parametrize("attack", ["toml", "rename"])
def test_an_edited_record_or_a_renamed_folder_refuses_the_update(
    tmp_path: Path, attack: str
) -> None:
    world, fid = _ny(tmp_path)
    world.put(S0)
    folder = store.folder_of(tmp_path, fid)
    target = fid
    if attack == "toml":
        record = folder / "follow.toml"
        record.write_text(record.read_text().replace("50.0", "90.0"))
    else:
        target = fid[:-1] + ("0" if fid[-1] != "0" else "1")
        folder.rename(folder.parent / target)
    with pytest.raises((JournalRefusal, SpineError)):
        update_follow(tmp_path, target, clock=lambda: _after_close(S0))


def test_show_states_the_paper_terms_and_a_rule_long_at_the_start(tmp_path: Path) -> None:
    world = _Store(tmp_path, "SPY", NY, [1.0, 2.0, 1.5])  # rising: long before the start
    world.put(S0 - 1)
    fid = world.follow(datetime(2026, 11, 2, 13, 0, tzinfo=UTC))
    for i in range(S0, S0 + 4):
        world.put(i)
        update_follow(tmp_path, fid, clock=_at(i))
    entries = store.entries_of(tmp_path, fid)
    assert all(not e.payload.get("fills") for e in entries)
    text = "\n".join(follow_show.text(follow_show.extra(entries)))
    for words in ("not compounded", "Cash dividends are booked", "Forward use; not research"):
        assert words in text
    assert "stays flat until the next entry signal" in text
    assert "profit" not in text.lower() and "Paper account" in text


def test_an_engine_change_is_named_not_a_silent_new_number(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    world, fid = _ny(tmp_path)
    for i in range(S0, S0 + 3):
        world.put(i)
        update_follow(tmp_path, fid, clock=_at(i))
    monkeypatch.setattr(follow_replay, "engine_code_sha256", lambda: "e" * 64)
    world.put(S0 + 3)
    check = update_follow(tmp_path, fid, clock=_at(S0 + 3))["replay"]
    assert check["agrees"] is False
    assert [d["session"] for d in check["differences"] if d["what"] == "engine"] == [
        NY[S0].isoformat()
    ]

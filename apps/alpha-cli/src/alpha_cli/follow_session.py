"""What every `alpha follow update` shares: the sessions to write and the loop that writes them.

A follow context (`SessionCtx`) holds the stored bars known at the clock, the market calendar,
the dividends knowable at the clock and the first forward session. The loop writes one journal
entry per session: a normal `bar`, a `late` one (the bar is not stored) or a `missed` one (written
after the next open). The rule follow (`follow_update`) and the setup follow
(`follow_setup_update`) each supply the context. Paper only. Writes only under `forward/<id>/`.
"""

from __future__ import annotations

import bisect
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from alpha_cli import follow_book as paper
from alpha_cli import follow_source
from alpha_cli import follow_store as store
from alpha_cli.follow_chain import append_entry
from alpha_cli.follow_journal import (
    CALENDAR_KEY,
    MAX_BAR_LATENESS_DAYS,
    STOPPED,
    Clock,
    Entry,
    Kind,
    session_close,
)
from alpha_cli.follow_journal import next_open as _next_open
from alpha_cli.follow_update_check import Digests, digests_of
from alpha_data.sessions import sessions_between


def _sessions(calendar: str, first: date, last: date) -> list[date]:
    """The sessions of the forward window only, or a plain-words refusal outside the calendar."""
    with follow_source.calendar_guard(calendar):
        return sessions_between(calendar, first, last)


def close_of(calendar: str | None, session: date) -> datetime:
    with follow_source.calendar_guard(calendar):
        return session_close(calendar or "", session)


def next_open(calendar: str | None, session: date) -> datetime:
    # The open after `session` is up to 14 days on: a session at the calendar's end has none.
    with follow_source.calendar_guard(calendar):
        return _next_open(calendar or "", session)


class SessionCtx:
    """The stored bars, calendar and dividends known at `now`, and the first forward session."""

    engine_sha = ""

    def __init__(self, home: Path, record: store.FollowRecord, now: datetime) -> None:
        self.record, self.now, self.asset = record, now, record.assets[0]
        self.bars, self.calendar = follow_source.forward_bars(home, self.asset, now)
        self.dividends = follow_source.forward_dividends(home, self.asset, now)
        self.units: dict[date, float] = {}
        self.dates = [b.ts.date() for b in self.bars]
        self.digests: Digests = digests_of(self.bars)
        self.first_session = self._first_session()
        self.first = bisect.bisect_left(self.dates, self.first_session)

    def _first_session(self) -> date:
        start = self.record.started_at
        days = [start.date() + timedelta(n) for n in range(15)]
        if self.calendar is not None:
            days = _sessions(self.calendar, days[0], days[-1])
        return next(s for s in days if close_of(self.calendar, s) > start)

    def expected(self) -> list[date]:
        days = [
            self.first_session + timedelta(n)
            for n in range((self.now.date() - self.first_session).days + 1)
        ]
        if self.calendar is not None:
            days = _sessions(self.calendar, self.first_session, self.now.date())
        return [s for s in days if close_of(self.calendar, s) <= self.now]

    def entry(
        self, book: paper.Book, session: date
    ) -> tuple[Kind, dict[str, Any], dict[str, str], paper.Book]:
        raise NotImplementedError

    def check(self, entries: list[Entry]) -> dict[str, Any]:
        raise NotImplementedError

    def kind_of(self, session: date) -> tuple[Kind, datetime]:
        """`missed` after the next open (crypto: a day on), `bar` when stored, else `late`."""
        opens = next_open(self.calendar, session)
        past = (
            (self.now.date() - session).days > MAX_BAR_LATENESS_DAYS
            if self.calendar is None
            else self.now > opens
        )
        stored = session in self.dates
        return ("missed" if past else ("bar" if stored else "late")), opens

    def labels(self, session: date, opens: datetime) -> list[str]:
        if self.calendar is None:
            hours = (self.now - opens).total_seconds() / 3600.0
            return [f"written {hours:.1f} h after the fill open"]
        return ["written late, before the fill"] if self.now.date() > session else []

    def dividends_for(self, book: paper.Book, session: date) -> tuple[paper.Book, list[Any]]:
        """Book the dividends of this session, then log the units held at its end."""
        book, paid = paper.dividends(
            book,
            self.dividends,
            session=session,
            units_before=lambda ex: units_before(self.units, ex),
        )
        self.units[session] = float(book["units"])
        return book, paid


def units_before(units: dict[date, float], ex_date: date) -> float:
    """The units held after the newest session before `ex_date`: the holding before its open."""
    earlier = [d for d in units if d < ex_date]
    return units[max(earlier)] if earlier else 0.0


def last_book(entries: list[Entry]) -> paper.Book:
    for entry in reversed(entries):
        if "book" in entry.payload:
            return dict(entry.payload["book"])
    return paper.new_book()


def run_update(
    home: Path, follow_id: str, *, clock: Clock, build: type[SessionCtx] | Any
) -> dict[str, Any]:
    """Write one entry per new session, or say there is nothing to write."""
    folder = store.folder_of(home, follow_id)
    record = store.load_record(folder)
    entries = store.entries_of(home, follow_id)
    if store.state_of(entries) == "stopped":
        raise follow_source.refuse(
            STOPPED,
            f"Follow {follow_id} is stopped.",
            "Start a new follow with `alpha follow start`.",
        )
    now = clock()
    ctx: SessionCtx = build(home, record, now)
    ctx.units = {
        e.session_date: float(e.payload["book"]["units"]) for e in entries if "book" in e.payload
    }
    sealed = entries[0].payload.get(CALENDAR_KEY)
    if sealed is None or sealed != (ctx.calendar or ""):
        raise follow_source.refuse(
            "FOLLOW_CALENDAR_CHANGED",
            f"The start entry names the market calendar {sealed!r}; the store now names "
            f"{ctx.calendar or ''!r}. The journal deadlines come only from the start entry.",
            "Start a new follow with `alpha follow start`.",
        )
    last = entries[-1]
    todo = [s for s in ctx.expected() if last.kind == "start" or s > last.session_date]
    check = ctx.check(entries)
    if not todo:
        waiting = last.kind == "start"
        newest = f"The newest completed session, {last.session_date}, is already in the journal."
        message = (
            "No session has closed since the follow started: waiting for its first new bar."
            if waiting
            else newest
        )
        return {
            "follow_id": follow_id,
            "status": "no-op",
            "written": [],
            "message": message,
            "replay": check,
        }
    book, written = last_book(entries), []
    for session in todo:
        kind, payload, hashes, book = ctx.entry(book, session)
        entry = append_entry(
            folder,
            kind=kind,
            session_date=session,
            clock=lambda: now,
            bar_hashes=hashes,
            payload={**payload, "replay": check},
            follow_id=follow_id,
        )
        words = payload.get("decision", {}).get("words") or payload.get("would_have", "no decision")
        written.append(
            {"seq": entry.seq, "session": session.isoformat(), "kind": kind, "words": words}
        )
    return {
        "follow_id": follow_id,
        "status": "written",
        "written": written,
        "replay": check,
        "message": f"Wrote {len(written)} entr{'y' if len(written) == 1 else 'ies'} (paper).",
    }

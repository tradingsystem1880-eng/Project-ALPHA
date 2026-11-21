"""What `alpha follow today` prints: one row per active follow, grouped. Paper only.

Reads the journals and nothing else. It never computes a decision, never calls the engine and
writes nothing. Every word comes from the newest journal entry. The market calendar is the one
the start entry sealed. The clock is passed in.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from alpha_cli import follow_source
from alpha_cli import follow_store as store
from alpha_cli.follow_journal import CALENDAR_KEY, Entry, JournalRefusal, session_close
from alpha_cli.follow_labels import exits_text, plain_readings, readings_text
from alpha_cli.spine import idea_card
from alpha_cli.spine.errors import SpineError
from alpha_data.sessions import sessions_between

GROUPS = (
    ("new_signal", "NEW SIGNAL"),
    ("open_position", "OPEN PAPER POSITION"),
    ("nothing_today", "NOTHING TODAY"),
    ("late_or_missed", "LATE OR MISSED"),
    ("waiting", "WAITING"),
)
TAIL = "Paper only. Forward use; not research. Not advice."
SESSION_KINDS = {"bar", "missed", "late"}
NAME_CHARS = 140


def newest_closed(calendar: str, now: datetime) -> date:
    """The newest session whose close is not after `now`. No calendar: a day closes at 00:00 UTC."""
    if not calendar:
        return now.date() - timedelta(days=1)
    first, last = now.date() - timedelta(days=14), now.date()
    with follow_source.calendar_guard(calendar):
        days = [
            d for d in sessions_between(calendar, first, last) if session_close(calendar, d) <= now
        ]
    return days[-1]


def _ago(calendar: str, session: date, newest: date) -> int:
    if session >= newest:
        return 0
    if not calendar:
        return (newest - session).days
    with follow_source.calendar_guard(calendar):
        return len(sessions_between(calendar, session + timedelta(days=1), newest))


def _name(home: Path, record: store.FollowRecord) -> str:
    if record.card_id:
        try:
            claim = idea_card.load(home, record.card_id).claim.strip()
        except SpineError:
            claim = ""
        if claim:
            return claim.splitlines()[0][:NAME_CHARS]
    return follow_source.source_name(home, record.kind, record.source_id)


def _paper(entries: list[Entry]) -> dict[str, Any]:
    for entry in reversed(entries):
        book = entry.payload.get("book")
        if isinstance(book, dict):
            units = float(book.get("units", 0.0))
            return {
                "open": units > 0,
                "units": units,
                "entry_price": book.get("entry_price"),
                "equity": book.get("equity"),
                "equity_pct": book.get("equity_pct", 0.0),
            }
    return {"open": False, "units": 0.0, "entry_price": None, "equity": None, "equity_pct": 0.0}


def _words(entry: Entry) -> str:
    p = entry.payload
    if entry.kind == "bar":
        return str(p.get("decision", {}).get("words", ""))
    if entry.kind == "missed":
        return f"missed: the rule would have signalled: {p.get('would_have', 'nothing recorded')}"
    return "late: the bar of this session was not stored when it was due. No decision."


def _place(
    record: store.FollowRecord, sessions: list[Entry], paper: dict[str, Any], closed: date, cal: str
) -> tuple[str, str, bool]:
    """The group, the decision in words, and whether the follow is behind the newest session."""
    if not sessions:
        if session_close(cal, closed) > record.started_at:
            return "late_or_missed", f"no entry for the newest closed session ({closed}) yet", True
        return "waiting", "waiting for its first new bar", False
    last = sessions[-1]
    if last.session_date < closed:
        said = (
            f"no entry for the newest closed session ({closed}). Last entry, {last.session_date}: "
        )
        return "late_or_missed", said + _words(last), True
    if last.kind != "bar":
        return "late_or_missed", _words(last), False
    action = last.payload.get("decision", {}).get("action")
    if action in {"enter", "exit"}:
        return "new_signal", _words(last), False
    return ("open_position" if paper["open"] else "nothing_today"), _words(last), False


def _row(
    home: Path, follow_id: str, now: datetime, cache: dict[str, date]
) -> dict[str, Any] | None:
    try:
        record = store.load_record(store.folder_of(home, follow_id))
        entries = store.entries_of(home, follow_id)
    except (SpineError, JournalRefusal):
        words = f"the journal cannot be read: run `alpha follow verify {follow_id}`"
        return {
            "follow_id": follow_id,
            "group": "late_or_missed",
            "name": follow_id,
            "asset": "",
            "decision": words,
            "behind": False,
            "calendar": None,
            "sessions_ago": None,
            "session_date": None,
            "readings": {},
            "exits": [],
            "study_labels": [],
            "paper": {},
            "entry_kind": "broken",
            "as_of_text": "cannot be read",
        }
    if store.state_of(entries) == "stopped":
        return None
    cal = str(entries[0].payload.get(CALENDAR_KEY) or "")
    closed = cache.setdefault(cal, newest_closed(cal, now))
    sessions = [e for e in entries if e.kind in SESSION_KINDS]
    paper = _paper(entries)
    group, decision, behind = _place(record, sessions, paper, closed, cal)
    last = sessions[-1] if sessions else None
    ago = None if last is None else _ago(cal, last.session_date, closed)
    when = (
        "none recorded yet"
        if last is None
        else (
            f"as of the close of {last.session_date}; "
            + ("the newest session" if ago == 0 else f"{ago} session{'s' if ago != 1 else ''} ago")
        )
    )
    return {
        "follow_id": follow_id,
        "group": group,
        "name": _name(home, record),
        "kind": record.kind,
        "card_id": record.card_id,
        "asset": record.assets[0],
        "decision": decision,
        "entry_kind": last.kind if last else "start",
        "readings": plain_readings(last.payload.get("readings", {}))
        if last and last.kind == "bar"
        else {},
        "exits": exits_text(entries[0].payload.get("setup", {}).get("exits", {})),
        "study_labels": list(entries[0].payload.get("setup", {}).get("labels", [])),
        "paper": paper,
        "session_date": last.session_date.isoformat() if last else None,
        "sessions_ago": ago,
        "as_of_text": when,
        "behind": behind,
        "calendar": cal,
        "started_at": record.started_at.isoformat(),
    }


def build(home: Path, now: datetime) -> dict[str, Any]:
    """The whole view as plain facts. Reads journals only."""
    cache: dict[str, date] = {}
    found = [r for i in store.all_ids(home) if (r := _row(home, i, now, cache)) is not None]
    order = [key for key, _ in GROUPS]
    rows = sorted(
        found, key=lambda r: (order.index(r["group"]), r.get("started_at", ""), r["follow_id"])
    )
    return {
        "as_of": now.isoformat(),
        "paper": True,
        "followed": len(rows),
        "behind": sum(1 for r in rows if r["behind"]),
        "markets": [
            {"calendar": c, "newest_closed_session": d.isoformat()}
            for c, d in sorted(cache.items())
        ],
        "groups": [
            {"key": k, "title": t, "count": sum(1 for r in rows if r["group"] == k)}
            for k, t in GROUPS
        ],
        "rows": rows,
        "notice": TAIL,
    }


def _row_text(r: dict[str, Any]) -> list[str]:
    lines = [
        f"  {r['name']}  {r['asset']}  (follow {r['follow_id']})",
        f"    {r['decision'].rstrip('.')}.",
    ]
    if r["readings"]:
        lines.append("    " + readings_text(r["readings"]))
    if r["exits"]:
        lines.append("    Exits: " + "; ".join(r["exits"]) + ".")
    p = r["paper"]
    if p:
        held = f"paper position open: {p['units']:.4g} units" if p["open"] else "paper account flat"
        lines.append(f"    {held}; equity {p['equity_pct']:+.2f}% since the start.")
    lines.append(f"    Session: {r['as_of_text']}.")
    return lines


def text(facts: dict[str, Any]) -> str:
    when = datetime.fromisoformat(facts["as_of"]).strftime("%Y-%m-%d %H:%M UTC")
    if not facts["rows"]:
        return "\n".join(
            [
                f"No active follows yet (paper), as of {when}.",
                "Start one: alpha follow start --test <run id>",
                TAIL,
            ]
        )
    names = {"": "markets that trade every day"}
    closed = "; ".join(
        f"{names.get(m['calendar'], m['calendar'])} {m['newest_closed_session']}"
        for m in facts["markets"]
    )
    lines = [
        f"Followed on paper, as of {when}.",
        f"Newest closed session: {closed}.",
        f"Behind it: {facts['behind']} of {facts['followed']} follow(s).",
    ]
    for group in facts["groups"]:
        mine = [r for r in facts["rows"] if r["group"] == group["key"]]
        if mine:
            lines += [
                "",
                f"{group['title']} ({len(mine)})",
                *[x for r in mine for x in _row_text(r)],
            ]
    return "\n".join([*lines, "", TAIL])

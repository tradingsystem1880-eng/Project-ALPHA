"""The count `alpha next` prints about follows. Light on purpose: no engine is imported.

`next_cmds.py` calls only this module, so it names no follow store module and opens nothing under
`forward/`. This module is on the guard's reader list; the counts come from `follow_today`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alpha_cli import follow_store, follow_today
from alpha_cli.follow_journal import JournalRefusal
from alpha_cli.spine.errors import SpineError


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


CLOCK = utc_now  # tests replace this


def followed_counts(home: Path) -> dict[str, Any] | None:
    """Counts of active follows by group, or None when nothing is followed."""
    try:
        facts = follow_today.build(home, CLOCK())
    except (SpineError, JournalRefusal):
        return {"active": None}  # a count and nothing else: no journal text passes this door
    if not facts["followed"]:
        return None
    by = {g["key"]: g["count"] for g in facts["groups"]}
    return {
        "active": facts["followed"],
        "new_signal": by["new_signal"],
        "open_position": by["open_position"],
        "late_or_missed": by["late_or_missed"],
    }


def follows_of_card(home: Path, card: str) -> list[dict[str, Any]]:
    """The paper follows whose frozen record names this idea card, oldest first.

    One entry per follow: its state and the count of session entries. A follow that cannot be read
    is shown as `broken`; its journal text never passes this door.
    """
    rows = []
    for row in follow_store.list_facts(home):
        if row.get("card_id") != card:
            continue
        shown = {
            "follow_id": row["follow_id"],
            "kind": row["kind"],
            "source_id": row["source_id"],
            "assets": row["assets"],
            "version": row["version"],
            "started_at": row["started_at"],
            "state": row["state"],
            "paper_account_percent": row["paper_account_percent"],
        }
        try:
            facts = follow_store.show_facts(home, row["follow_id"])
        except (SpineError, JournalRefusal):
            rows.append({**shown, "state": "broken", "sessions": 0, "stop_reason": ""})
            continue
        sessions = sum(n for kind, n in facts["entries"].items() if kind not in {"start", "stop"})
        rows.append({**shown, "sessions": sessions, "stop_reason": facts["stop_reason"]})
    return sorted(rows, key=lambda r: (r["started_at"], r["follow_id"]))


def followed_line(counts: dict[str, Any]) -> str:
    if counts.get("active") is None:
        return "Followed on paper: could not be read. See: alpha follow today"
    return (
        f"Followed on paper: {counts['active']} ({counts['new_signal']} new signal, "
        f"{counts['open_position']} open, {counts['late_or_missed']} late or missed). "
        "See: alpha follow today. As one paper account: alpha follow book"
    )

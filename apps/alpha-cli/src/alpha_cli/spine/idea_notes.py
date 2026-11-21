"""Notes and decisions of one idea. One JSON line each, appended; never edited or deleted."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alpha_cli.spine import idea_card as cards
from alpha_cli.spine.errors import SpineError

NOTE, DECISION = "note", "decision"


def _path(home: Path, card: str) -> Path:
    return home / "ideas" / "notes" / f"{card}.jsonl"


def append(home: Path, card: str, text: str, *, decision: bool = False) -> dict[str, Any]:
    identity = cards.resolve(home, card)
    text = text.strip()
    if not text:
        raise SpineError("IDEA_NOTE_EMPTY", "The note has no text.", "Write the note in words.")
    row = {
        "at": datetime.now(UTC).isoformat(),
        "text": text,
        "kind": DECISION if decision else NOTE,
    }
    path = _path(home, identity)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {"card": identity, **row}


def read(home: Path, card: str) -> list[dict[str, Any]]:
    """Notes newest first. An unreadable line is a fault, not a gap."""
    path = _path(home, card)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if not isinstance(row, dict) or not {"at", "text", "kind"} <= row.keys():
                raise ValueError("a line is not a note")
            rows.append(row)
    except (OSError, ValueError) as exc:
        raise SpineError(
            "IDEA_NOTES_UNREADABLE",
            f"The notes of idea card {card} cannot be read: {exc}",
            "Do not edit note files. Add a new note with `alpha idea note`.",
        ) from exc
    return rows[::-1]

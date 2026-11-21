"""``/api/ideas`` and ``/api/ideas/{card}``: one idea, the whole story (read-only relay).

Both routes run ``alpha idea list|file --json`` as a subprocess and relay the answer. The web
never imports ``alpha_cli``'s idea code and never opens the ideas folder. No route writes a card,
starts a test or links anything: those stay CLI commands. Sizes are bounded here: the list keeps
the newest ``MAX_CARDS`` cards, the file keeps the newest ``MAX_READINGS`` readings; the answer
says how many there were and where the kept readings start.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path

from alpha_web._catalog import _run_json
from alpha_web.api._common import data_dir
from alpha_web.api.models import IdeaFile, IdeaList

router = APIRouter(prefix="/api/ideas", tags=["ideas"])

MAX_CARDS = 500
MAX_READINGS = 200
MAX_FOLLOWS = 100
_TIMEOUT_SECONDS = 30.0
_CARD_ID = r"^[0-9a-f]{4,12}$"


def _relay(args: list[str]) -> dict[str, Any]:
    try:
        result: dict[str, Any] = _run_json(
            args, data_dir=data_dir(), timeout_seconds=_TIMEOUT_SECONDS
        )
        return result
    except RuntimeError as exc:  # the CLI's own words, or a timeout
        text = str(exc)
        if "timed out" in text:
            status = 504
        elif "There is no idea card" in text:
            status = 404
        else:
            status = 409
        raise HTTPException(status_code=status, detail=text) from exc


def _newest_first(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("saved_at") or ""), str(row.get("id") or ""))


@router.get("", response_model=IdeaList)
def list_ideas() -> dict[str, Any]:
    """Relay ``alpha idea list --json``: every card, newest first, at most ``MAX_CARDS``."""
    rows = sorted(_relay(["idea", "list", "--json"])["cards"], key=_newest_first, reverse=True)
    return {"cards": rows[:MAX_CARDS], "total": len(rows), "truncated": len(rows) > MAX_CARDS}


@router.get("/{card}", response_model=IdeaFile)
def idea_file(card: Annotated[str, Path(pattern=_CARD_ID)]) -> dict[str, Any]:
    """Relay ``alpha idea file <card> --json``; the id is checked as 4 to 12 hex first."""
    facts = _relay(["idea", "file", card, "--json"])
    readings = facts.get("readings", [])
    start = max(0, len(readings) - MAX_READINGS)
    return {
        **facts,
        "readings": readings[start:],
        "follows": facts.get("follows", [])[-MAX_FOLLOWS:],
        "readings_total": len(readings),
        "readings_shown_from": start,
    }

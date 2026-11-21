"""``/api/ideas``: the idea cards the owner has written (read-only relay).

Runs ``alpha idea list --json`` as a subprocess and relays the answer. The web backend never opens
the card folder itself, and no route writes a card: ``alpha idea new`` stays a CLI command.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from alpha_web._catalog import _run_json
from alpha_web.api._common import data_dir
from alpha_web.api.models.ideas import IdeaCardList

router = APIRouter(prefix="/api/ideas", tags=["ideas"])

_TIMEOUT_SECONDS = 30.0


@router.get("", response_model=IdeaCardList)
def list_cards() -> dict[str, Any]:
    """Relay ``alpha idea list --json``: every card with its claim and whether a test is linked."""
    try:
        result: dict[str, Any] = _run_json(
            ["idea", "list", "--json"], data_dir=data_dir(), timeout_seconds=_TIMEOUT_SECONDS
        )
        return result
    except RuntimeError as exc:  # the CLI's own words, or a timeout
        status = 504 if "timed out" in str(exc) else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc

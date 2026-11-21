"""The front screen's read of idea cards: what `alpha idea list --json` prints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class IdeaCardRow(BaseModel):
    """One idea card: its id, its claim, and whether a test is linked to it."""

    model_config = ConfigDict(extra="ignore")

    id: str
    claim: str | None = None
    tested: bool
    not_stated: list[str]


class IdeaCardList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cards: list[IdeaCardRow]

"""The Today screen's two reads: what `alpha follow today` and `alpha follow show` print.

The server relays them. Fields the screen does not show (the journal folder path) are dropped.
Paper only; nothing here is a result.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Relayed(BaseModel):
    """A command's own JSON. A field the screen does not name is dropped, never an error."""

    model_config = ConfigDict(extra="ignore")


class FollowPaper(_Relayed):
    open: bool | None = None
    units: float | None = None
    entry_price: float | None = None
    equity: float | None = None
    equity_pct: float | None = None


class FollowRow(_Relayed):
    follow_id: str
    group: str
    name: str
    asset: str
    decision: str
    entry_kind: str
    as_of_text: str
    behind: bool
    kind: str | None = None
    card_id: str | None = None
    calendar: str | None = None
    session_date: str | None = None
    sessions_ago: int | None = None
    started_at: str | None = None
    readings: dict[str, float]
    exits: list[str] = []
    study_labels: list[str] = []
    paper: FollowPaper


class FollowGroup(_Relayed):
    key: str
    title: str
    count: int


class FollowMarket(_Relayed):
    calendar: str
    newest_closed_session: str


class FollowToday(_Relayed):
    as_of: str
    paper: bool
    followed: int
    behind: int
    markets: list[FollowMarket]
    groups: list[FollowGroup]
    rows: list[FollowRow]
    notice: str


class FollowRecord(_Relayed):
    follow_id: str
    kind: str
    source_id: str
    assets: list[str]
    card_id: str
    paper_account_percent: float
    started_at: str
    version: int
    spec_sha256: str
    supersedes: str


class FollowEntryRow(_Relayed):
    session: str
    kind: str
    words: str
    fills: list[dict[str, Any]]
    readings: dict[str, float]
    equity_pct: float | None = None
    replay_agrees: bool | None = None


class FollowReplayDifference(_Relayed):
    session: str
    what: str
    detail: str


class FollowReplay(_Relayed):
    agrees: bool
    checked: int
    differences: list[FollowReplayDifference]


class FollowPaperSummary(_Relayed):
    start: float | None = None
    equity: float | None = None
    equity_pct: float | None = None
    highest: float | None = None
    lowest: float | None = None
    largest_fall_pct: float | None = None
    closed_trades: int | None = None
    fees: float | None = None
    units: float | None = None
    entry_price: float | None = None
    marked_sessions: int | None = None


class FollowShow(_Relayed):
    record: FollowRecord
    state: str
    entries: dict[str, int]
    head: str
    recent: list[FollowEntryRow]
    paper: FollowPaperSummary
    replay: FollowReplay | None = None
    reading: str
    long_at_start: bool
    waiting_for_first_bar: bool
    stop_reason: str

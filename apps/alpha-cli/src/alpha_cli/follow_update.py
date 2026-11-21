"""`alpha follow update` for a followed rule test: one journal entry per new session. Paper only.

Decide on the close of session t from the bars known at the run time. The paper fill is the open
of t+1 and is booked by the update that first sees that bar. Rules for a session that is not
written in time (market calendar, `alpha_data.sessions`; crypto trades every day):
- the session has closed and its bar is not stored: a `late` entry, no decision;
- the run is after the next session's open (crypto: more than a day after the session): a
  `missed` entry that says what the rule "would have signalled". No paper order. An older
  skipped session is written the same way, never back-filled as a normal entry;
- otherwise a normal `bar` entry. There is one entry per session.
Each run replays the frozen rule over the stored bars with the rule test's engine step and
compares the journal with it. The journal is never rewritten: the replay is a check. Reads the
newest bars only through `follow_source`. Writes only under `forward/<follow id>/`. The session
loop is `follow_session.run_update`; a followed setup trade goes to `follow_setup_update`.
"""

from __future__ import annotations

import bisect
from datetime import date, datetime
from pathlib import Path
from typing import Any

from alpha_cli import follow_book as paper
from alpha_cli import follow_replay as engine
from alpha_cli import follow_session, follow_setup_update, follow_source
from alpha_cli import follow_store as store
from alpha_cli.follow_journal import STOPPED, Clock, Entry, JournalRefusal, Kind
from alpha_cli.follow_replay import Replay
from alpha_cli.follow_session import SessionCtx, close_of, next_open
from alpha_cli.follow_update_check import check_replay
from alpha_cli.spine.errors import SpineError
from alpha_core import DataError

__all__ = ["close_of", "next_open", "update_all", "update_follow"]


class _Ctx(SessionCtx):
    def __init__(self, home: Path, record: store.FollowRecord, now: datetime) -> None:
        self.idea = follow_source.frozen_idea(home, record.source_id, record.spec_sha256)
        super().__init__(home, record, now)
        self.engine_sha = engine.engine_code_sha256()
        self.replay: Replay | None = None
        if self.first < len(self.bars):
            try:
                self.replay = engine.replay(self.bars, self.idea, self.first)
            except DataError as exc:
                raise follow_source.refuse(
                    "FOLLOW_NOT_ENOUGH_HISTORY",
                    f"Cannot replay the rule: {exc}",
                    "Store more bars before the follow's start.",
                ) from exc

    def entry(
        self, book: paper.Book, session: date
    ) -> tuple[Kind, dict[str, Any], dict[str, str], paper.Book]:
        return _entry(self, book, session)

    def check(self, entries: list[Entry]) -> dict[str, Any]:
        return check_replay(
            asset=self.asset,
            dates=self.dates,
            digests=self.digests,
            replay=self.replay,
            engine_sha=self.engine_sha,
            entries=entries,
        )


def _armed(replay: Replay | None, session: date) -> bool:
    """False while the rule has stayed long since before the start: the paper book waits for the
    next entry signal. True once the rule was not long at the start, or has been flat since."""
    if replay is None or not replay.long_before:
        return True
    return any(not d.long for day, d in replay.sessions.items() if day < session)


def _settle(ctx: _Ctx, book: paper.Book, session: date) -> tuple[paper.Book, list[dict[str, Any]]]:
    pending = book["pending"]
    if pending is None:
        return book, []
    at = bisect.bisect_right(ctx.dates, date.fromisoformat(pending["decided"]))
    if at >= len(ctx.bars) or ctx.dates[at] > session:
        return book, []
    bar = ctx.bars[at]
    hit = ctx.replay.fills.get(ctx.dates[at]) if ctx.replay else None
    slip = ctx.idea.costs.slippage_bps / 10_000.0
    sign = 1.0 if pending["side"] == "buy" else -1.0
    price, source = (hit.price, "engine") if hit else (bar.open * (1 + sign * slip), "open")
    costs = ctx.idea.costs
    book, done = paper.fill(
        book,
        price=price,
        ts=bar.ts.isoformat(),
        size_pct=ctx.record.paper_account_percent,
        fee_bps=costs.fee_bps,
    )
    return book, [{**done, "price_from": source}]


def _entry(
    ctx: _Ctx, book: paper.Book, session: date
) -> tuple[Kind, dict[str, Any], dict[str, str], paper.Book]:
    at = ctx.dates.index(session) if session in ctx.dates else None
    kind, opens = ctx.kind_of(session)
    book, fills = _settle(ctx, book, session)
    book, paid = ctx.dividends_for(book, session)
    payload: dict[str, Any] = {"session": session.isoformat(), "paper": True, "fills": fills}
    payload["dividends"] = paid
    payload["engine_code_sha256"] = ctx.engine_sha
    if kind == "late":
        payload.update(reason="the bar of this session was not stored at run time", book=book)
        return kind, payload, {}, book
    if at is None or ctx.replay is None:
        payload.update(reason="the bar of this session is not stored; no decision", book=book)
        return kind, payload, {}, book
    book = paper.mark(book, ctx.bars[at].close)
    seen = ctx.replay.sessions.get(session)
    held, words = paper.decide(
        book, long=bool(seen and seen.long), armed=_armed(ctx.replay, session), session=session
    )
    note = {} if seen else {"words": "no signal: indicators still warming up"}
    decision = {
        **words,
        **note,
        "signal": seen.signal if seen else None,
        "reason": seen.reason if seen else "",
    }
    payload.update(
        readings=seen.readings if seen else {}, latest_bar_ts=ctx.bars[-1].ts.isoformat()
    )
    if kind == "bar":
        book = held
        payload["decision"] = decision
        payload["labels"] = ctx.labels(session, opens)
    else:
        payload.update(
            would_have=decision["words"], reason="written after the next open: no paper order"
        )
    payload["book"] = book
    return kind, payload, {ctx.asset: ctx.digests[at]}, book


def update_follow(home: Path, follow_id: str, *, clock: Clock) -> dict[str, Any]:
    """Write one entry per new session of a followed rule test or setup trade."""
    record = store.load_record(store.folder_of(home, follow_id))
    if record.kind == "setup_trade":
        return follow_setup_update.update_follow(home, follow_id, clock=clock)
    if store.state_of(store.entries_of(home, follow_id)) == "stopped":
        raise follow_source.refuse(
            STOPPED,
            f"Follow {follow_id} is stopped.",
            "Start a new follow with `alpha follow start`.",
        )
    if record.kind != "rule_test":
        raise follow_source.refuse(
            "FOLLOW_UPDATE_SETUP_NOT_BUILT",
            "A setup find cannot be updated: it holds no exit rules and no trade results. "
            "Follow a setup trade instead.",
            "Run `alpha setup trade`, then `alpha follow start --trade <trade id>`.",
        )
    return follow_session.run_update(home, follow_id, clock=clock, build=_Ctx)


def update_all(home: Path, *, clock: Clock) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for follow_id in store.all_ids(home):
        try:
            record = store.load_record(store.folder_of(home, follow_id))
            if store.state_of(store.entries_of(home, follow_id)) == "stopped":
                rows.append({"follow_id": follow_id, "status": "skipped", "message": "stopped"})
            elif record.kind == "setup_find":
                rows.append(
                    {
                        "follow_id": follow_id,
                        "status": "skipped",
                        "message": "a setup find has no exit rules: follow a setup trade",
                    }
                )
            else:
                rows.append(update_follow(home, follow_id, clock=clock))
        except (SpineError, JournalRefusal) as exc:
            rows.append(
                {
                    "follow_id": follow_id,
                    "status": "refused",
                    "message": str(exc),
                    "code": exc.payload["code"],
                }
            )
    return rows

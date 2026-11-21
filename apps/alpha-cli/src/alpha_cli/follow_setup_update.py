"""`alpha follow update` for a followed setup trade: one journal entry per new session. Paper only.

The session rules are those of the rule follow (`follow_session.run_update`): one entry per
session, `late` when the bar is not stored, `missed` when written after the next open, the same
`must_write_by` window, the same hash-chained journal. The decision comes from `follow_setup`:
the study's own code on the bars known at the clock. A setup that closes on session t is an order
for the open of t+1; the exits (stop, target, time limit, opposite signal) are the study's.
Stop and target fills use the study's conservative fill prices. A missed or late session places no
paper order. The paper book mirrors a replay fill only when it holds the order (a buy) or the
position (a sell). Cash dividends are booked as in the rule follow. Long only, one asset.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from alpha_cli import follow_book as paper
from alpha_cli import follow_setup, follow_source
from alpha_cli import follow_store as store
from alpha_cli.follow_journal import Clock, Entry, Kind
from alpha_cli.follow_labels import exit_words
from alpha_cli.follow_session import SessionCtx, run_update
from alpha_cli.follow_update_check import TOLERANCE, check_replay
from alpha_core import DataError

NOTHING = "no setup today"


def _words(day: follow_setup.Day | None) -> tuple[str, str]:
    """The paper action and its plain words for a decision on the close of a session."""
    if day is None:
        return "none", "no decision"
    sold = [f for f in day.fills if f["side"] == "sell"]
    if sold:
        return "closed", f"paper position closed: {exit_words(sold[0]['reason'])}"
    if day.signal:
        return "enter", "setup found at the close: would buy at the next open"
    if day.exit_pending:
        return "exit", "opposite signal at the close: would sell at the next open"
    if day.held:
        return "hold", "holding"
    return "none", day.skipped or NOTHING


class SetupCtx(SessionCtx):
    def __init__(self, home: Path, record: store.FollowRecord, now: datetime) -> None:
        self.spec, self.costs = follow_source.frozen_setup(
            home, record.source_id, record.spec_sha256, record.assets[0]
        )
        super().__init__(home, record, now)
        self.engine_sha = follow_setup.setup_code_sha256()
        self.days: dict[date, follow_setup.Day] | None = None
        if self.first < len(self.bars):
            try:
                self.days = follow_setup.replay(
                    self.bars, self.spec, self.asset, self.costs, self.first
                )
            except (DataError, ValueError) as exc:
                raise follow_source.refuse(
                    "FOLLOW_NOT_ENOUGH_HISTORY",
                    f"Cannot replay the setup: {exc}",
                    "Store more bars before the follow's start.",
                ) from exc

    def _settle(
        self, book: paper.Book, day: follow_setup.Day | None, session: date
    ) -> tuple[paper.Book, list[dict[str, Any]]]:
        done: list[dict[str, Any]] = []
        slip = float(self.costs["slippage_bps"]) / 10_000.0
        for fill in day.fills if day else []:
            buy = fill["side"] == "buy"
            ready = (book["pending"] or {}).get("side") == "buy" if buy else book["units"] > 0
            if not ready:
                continue
            price = fill["raw_price"] * (1 + slip if buy else 1 - slip)
            book, made = paper.fill(
                {**book, "pending": {"side": fill["side"]}},
                price=price,
                ts=fill["bar_ts"],
                size_pct=self.record.paper_account_percent,
                fee_bps=float(self.costs["fee_bps"]),
            )
            done.append({**made, "raw_price": fill["raw_price"], "reason": fill["reason"]})
        return book, done

    def entry(
        self, book: paper.Book, session: date
    ) -> tuple[Kind, dict[str, Any], dict[str, str], paper.Book]:
        kind, opens = self.kind_of(session)
        at = self.dates.index(session) if session in self.dates else None
        day = self.days.get(session) if self.days and at is not None else None
        book, fills = self._settle(book, day, session)
        book, paid = self.dividends_for(book, session)
        payload: dict[str, Any] = {"session": session.isoformat(), "paper": True, "fills": fills}
        payload.update(dividends=paid, engine_code_sha256=self.engine_sha)
        if at is None or day is None:
            payload.update(reason="the bar of this session was not stored at run time", book=book)
            return kind, payload, {}, book
        book = paper.mark(book, self.bars[at].close)
        action, words = _words(day)
        readings = {"close": self.bars[at].close}
        readings.update({k: v for k, v in (("stop", day.stop), ("target", day.target)) if v})
        payload.update(readings=readings, latest_bar_ts=self.bars[-1].ts.isoformat())
        payload["setup"] = {"signal": day.signal, "skipped": day.skipped, "trade": day.trade}
        if kind == "bar":
            if day.signal:
                book = {**book, "pending": {"side": "buy", "decided": session.isoformat()}}
            payload["decision"] = {"action": action, "words": words, "long": day.held}
            payload["labels"] = self.labels(session, opens)
        else:
            payload.update(would_have=words, reason="written after the next open: no paper order")
        payload["book"] = book
        return kind, payload, {self.asset: self.digests[at]}, book

    def check(self, entries: list[Entry]) -> dict[str, Any]:
        """Bars and engine code as for a rule follow, then each entry's signal and fills against
        the replay. The journal is never rewritten."""
        report = check_replay(
            asset=self.asset,
            dates=self.dates,
            digests=self.digests,
            replay=None,
            engine_sha=self.engine_sha,
            entries=entries,
        )
        found = list(report["differences"])
        checked = 0
        for entry in (e for e in entries if e.kind == "bar" and self.days is not None):
            day = (self.days or {}).get(entry.session_date)
            checked += 1
            said = entry.payload.get("setup", {}).get("signal")
            if day is None or said != day.signal:
                found.append(_diff(entry, "decision", "the replay decides differently"))
            for fill in entry.payload.get("fills", []):
                hit = [f for f in (day.fills if day else []) if f["side"] == fill["side"]]
                if not hit or abs(hit[0]["raw_price"] - fill["raw_price"]) > TOLERANCE:
                    found.append(_diff(entry, "fill", "the replayed fill differs"))
        found.sort(key=lambda d: (d["session"], d["what"]))
        return {**report, "agrees": not found, "checked": checked, "differences": found}


def _diff(entry: Entry, what: str, detail: str) -> dict[str, str]:
    return {"session": entry.session_date.isoformat(), "what": what, "detail": detail}


def update_follow(home: Path, follow_id: str, *, clock: Clock) -> dict[str, Any]:
    """Write one entry per new session of a followed setup trade, or say there is nothing."""
    return run_update(home, follow_id, clock=clock, build=SetupCtx)

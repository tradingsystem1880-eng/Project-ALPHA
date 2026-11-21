"""What `alpha follow show` and `list` print about the journal: the last entries and the paper
equity path. Readings, not verdicts: no pass or fail, no advice. Paper only."""

from __future__ import annotations

from typing import Any

from alpha_cli.follow_book import PAPER_ACCOUNT
from alpha_cli.follow_journal import Entry
from alpha_cli.follow_labels import entry_sentence, plain_readings, readings_text

RECENT = 20
PAPER_TERMS = (
    f"Size is fixed: each paper buy uses the same share of the {PAPER_ACCOUNT:,.0f} start value. "
    "Gains and losses are not compounded, so the size does not grow or shrink.",
    "Cash dividends are booked for a position held before the ex-dividend day, on the same "
    "point-in-time basis as the rule test. Carry is not booked. The paper position is long only.",
    "Forward use; not research. These readings do not go to `alpha results`, the ledger "
    "or RD-Agent.",
)
LONG_AT_START = (
    "The rule was already long when the follow started. The paper account stays flat until "
    "the next entry signal, so it differs from the rule test at first."
)
LATE_OR_MISSED = {"late": "late: a session's bar was not stored", "missed": "missed a session"}


def _row(entry: Entry) -> dict[str, Any]:
    p = entry.payload
    words = p.get("decision", {}).get("words") or p.get("would_have") or p.get("reason", "")
    book = p.get("book", {})
    return {
        "session": entry.session_date.isoformat(),
        "kind": entry.kind,
        "words": words,
        "sentence": entry_sentence(entry.kind, p),
        "fills": p.get("fills", []),
        "dividends": p.get("dividends", []),
        "readings": plain_readings(p.get("readings", {})),
        "equity_pct": book.get("equity_pct"),
        "replay_agrees": p.get("replay", {}).get("agrees"),
    }


def _paper(entries: list[Entry]) -> dict[str, Any]:
    marked = [e.payload["book"] for e in entries if "equity_pct" in e.payload.get("book", {})]
    if not marked:
        return {}
    path = [PAPER_ACCOUNT, *(b["equity"] for b in marked)]
    peak, fall = path[0], 0.0
    for value in path:
        peak = max(peak, value)
        fall = max(fall, (peak - value) / peak * 100.0)
    last = marked[-1]
    dividends = float(last.get("dividends_cum", 0.0))
    total = last["equity"] - PAPER_ACCOUNT
    return {
        "start": PAPER_ACCOUNT,
        "dividends": dividends,
        "dividends_pct": dividends / PAPER_ACCOUNT * 100.0,
        "price_pct": (total - dividends) / PAPER_ACCOUNT * 100.0,
        "equity": last["equity"],
        "equity_pct": last["equity_pct"],
        "highest": max(path),
        "lowest": min(path),
        "largest_fall_pct": fall,
        "closed_trades": last["trades_closed"],
        "closed_pnl": last["closed_pnl_cum"],
        "fees": last["fees_cum"],
        "units": last["units"],
        "entry_price": last["entry_price"],
        "marked_sessions": len(marked),
    }


def extra(entries: list[Entry], limit: int | None = RECENT) -> dict[str, Any]:
    """The last `limit` entries (all when None), the paper equity numbers and the newest replay."""
    sessions = [e for e in entries if e.kind in {"bar", "missed", "late"}]
    replays = [e.payload["replay"] for e in sessions if "replay" in e.payload]
    shown = sessions if limit is None else sessions[-limit:]
    return {
        "recent": [_row(e) for e in shown],
        "shown": len(shown),
        "sessions": len(sessions),
        "paper": _paper(entries),
        "replay": replays[-1] if replays else None,
        "reading": reading(entries),
        "long_at_start": any(
            str(e.payload.get("decision", {}).get("words", "")).startswith("long at the start")
            for e in sessions
        ),
    }


def reading(entries: list[Entry]) -> str:
    """One state line for `follow list`."""
    sessions = [e for e in entries if e.kind in {"bar", "missed", "late"}]
    if entries[-1].kind == "stop":
        return "stopped"
    if not sessions:
        return "waiting for its first new bar"
    last = sessions[-1]
    if last.kind in LATE_OR_MISSED:
        return LATE_OR_MISSED[last.kind]
    action = last.payload.get("decision", {}).get("action")
    if action in {"enter", "exit"}:
        return f"new signal: {last.payload['decision']['words']}"
    return "open paper position" if last.payload["book"]["units"] > 0 else "nothing today"


def text(facts: dict[str, Any]) -> list[str]:
    """Lines for `follow show`, after the record lines."""
    lines: list[str] = []
    if facts["recent"]:
        lines.append(
            f"Entries (newest last): {facts['shown']} of {facts['sessions']}. "
            "Use --all to see every one, or --last N."
        )
    for r in facts["recent"]:
        pct = "" if r["equity_pct"] is None else f"  (account {r['equity_pct']:+.2f}%)"
        lines.append(f"  {r['session']}  {r['sentence']}{pct}")
        if r["readings"]:
            lines.append("    " + readings_text(r["readings"]))
    p = facts["paper"]
    if p:
        lines += [
            f"Paper account (starts at {p['start']:,.0f}, one pending order at most):",
            f"  Equity now {p['equity']:,.2f} ({p['equity_pct']:+.2f}% since the start); "
            f"lowest {p['lowest']:,.2f}, highest {p['highest']:,.2f}.",
            f"  Largest fall from a high: {p['largest_fall_pct']:.2f}%. "
            f"Closed trades: {p['closed_trades']}, fees paid {p['fees']:.2f}.",
        ]
        lines.append(
            f"  Since the start: price {p['price_pct']:+.2f}% (after fees), "
            f"dividends {p['dividends_pct']:+.2f}% ({p['dividends']:,.2f} paid)."
        )
        if p["units"] > 0:
            lines.append(
                f"  Open paper position: {p['units']:.4g} units from {p['entry_price']:.2f}."
            )
    if facts["recent"] or p:
        lines += [f"  {line}" for line in PAPER_TERMS]
    if facts.get("long_at_start"):
        lines.append(f"  {LONG_AT_START}")
    check = facts["replay"]
    if check:
        said = "agrees" if check["agrees"] else f"differs ({len(check['differences'])} place(s))"
        lines.append(
            f"Replay check at the last update: {said}; {check['checked']} session(s) compared."
        )
        lines += [f"  {d['session']}: {d['what']}: {d['detail']}" for d in check["differences"]]
    return lines

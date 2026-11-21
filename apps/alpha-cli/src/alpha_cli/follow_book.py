"""The paper account of a follow: cash, units, one pending order, and the words for a decision.

Pure arithmetic on plain dicts that go into the journal. Paper size is a percent of a paper
account (`PAPER_ACCOUNT`); it is a fixed share of that start value, not compounded. Fees are
`fee_bps` of the notional. Slippage is already in the engine's fill price. Long only, as the
rule test is today. A cash dividend is booked for a position held before the ex-dividend day, on
the same point-in-time basis as the rule test (the engine's: entitled to the units held before the
open of the ex-date session, cash credited at the pay date, only when known by that session). No
carry is booked. No pass or fail and no advice: readings only.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

from alpha_core import CorporateAction

PAPER_ACCOUNT = 10_000.0
type Book = dict[str, Any]


def new_book() -> Book:
    return {
        "cash": PAPER_ACCOUNT,
        "units": 0.0,
        "entry_ts": None,
        "entry_price": None,
        "entry_fee": 0.0,
        "pending": None,
        "closed_pnl_cum": 0.0,
        "fees_cum": 0.0,
        "trades_closed": 0,
        "equity": PAPER_ACCOUNT,
        "equity_pct": 0.0,
        "open_pnl": 0.0,
        "dividends_cum": 0.0,
        "dividends_seen": [],
        "dividends_due": [],
    }


def fill(
    book: Book, *, price: float, ts: str, size_pct: float, fee_bps: float
) -> tuple[Book, dict[str, Any]]:
    """Book the pending order at `price` (the open of the next bar). Returns the book and fill."""
    out = dict(book)
    side = str(book["pending"]["side"])
    rate = fee_bps / 10_000.0
    if side == "buy":
        units = PAPER_ACCOUNT * size_pct / 100.0 / (price * (1.0 + rate))
        fee = units * price * rate
        out.update(cash=book["cash"] - units * price - fee, units=units, entry_ts=ts)
        out.update(entry_price=price, entry_fee=fee)
    else:
        units = float(book["units"])
        fee = units * price * rate
        realised = units * (price - book["entry_price"]) - fee - book["entry_fee"]
        out.update(cash=book["cash"] + units * price - fee, units=0.0, entry_ts=None)
        out.update(entry_price=None, entry_fee=0.0)
        out.update(closed_pnl_cum=book["closed_pnl_cum"] + realised)
        out.update(trades_closed=book["trades_closed"] + 1)
    out.update(pending=None, fees_cum=book["fees_cum"] + fee)
    done = {"bar_ts": ts, "side": side, "price": price, "units": units, "fee": fee, "kind": "open"}
    return out, done


def mark(book: Book, close: float) -> Book:
    """Value the account at a close: cash plus units at the close."""
    held = float(book["units"]) > 0.0
    equity = book["cash"] + book["units"] * close
    open_pnl = book["units"] * (close - book["entry_price"]) - book["entry_fee"] if held else 0.0
    return {
        **book,
        "equity": equity,
        "equity_pct": (equity / PAPER_ACCOUNT - 1.0) * 100.0,
        "open_pnl": open_pnl,
    }


def decide(book: Book, *, long: bool, armed: bool, session: date) -> tuple[Book, dict[str, Any]]:
    """The paper action for a decision on the close of `session`. A buy or sell waits for the
    next open, so it is stored as the one pending order."""
    held = float(book["units"]) > 0.0
    if not held and not armed and long:
        action, words, side = (
            "none",
            "long at the start: paper stays flat until the next entry signal",
            None,
        )
    elif not held and long:
        action, words, side = "enter", "would buy at the next open", "buy"
    elif held and long:
        action, words, side = "hold", "holding", None
    elif held:
        action, words, side = "exit", "would sell at the next open", "sell"
    else:
        action, words, side = "none", "no signal", None
    pending = {"side": side, "decided": session.isoformat()} if side else None
    return {**book, "pending": pending}, {"action": action, "words": words, "long": long}


def dividends(
    book: Book,
    actions: Sequence[CorporateAction],
    *,
    session: date,
    units_before: Callable[[date], float],
) -> tuple[Book, list[dict[str, Any]]]:
    """Book the cash dividends of one session. Same basis as the rule test's engine.

    A dividend is taken up once, at the first session that is on or after its ex date and on or
    after the day it was known (`knowledge_time`). The units are those held before the open of
    the ex-date session (`units_before(ex_date)`: the journal's own book, never a later one). The
    cash is credited at the first session on or after the pay date (the ex date when none is
    given). Cash not yet credited is not in the equity. Returns the new book and the credited
    dividends (each with its ex date, pay date, per-unit amount, units and cash)."""
    seen = list(book.get("dividends_seen", []))
    due = [dict(d) for d in book.get("dividends_due", [])]
    for action in sorted(actions, key=lambda a: (a.ex_date, a.amount or 0.0)):
        key = f"{action.ex_date.isoformat()}|{action.amount!r}"
        if key in seen or action.knowledge_time > session or action.ex_date > session:
            continue
        seen.append(key)
        units = units_before(action.ex_date)
        if units > 0.0 and action.amount is not None:
            pay = action.pay_date if action.pay_date is not None else action.ex_date
            due.append(
                {
                    "ex_date": action.ex_date.isoformat(),
                    "pay_date": pay.isoformat(),
                    "per_unit": action.amount,
                    "units": units,
                    "cash": units * action.amount,
                }
            )
    paid = [d for d in due if date.fromisoformat(d["pay_date"]) <= session]
    cash = float(book["cash"]) + sum(d["cash"] for d in paid)
    return {
        **book,
        "cash": cash,
        "dividends_cum": float(book.get("dividends_cum", 0.0)) + sum(d["cash"] for d in paid),
        "dividends_seen": seen,
        "dividends_due": [d for d in due if d not in paid],
    }, paid

"""A paper position held over an ex-dividend date books the cash dividend, on the rule test's
point-in-time basis: units held before the ex session's open, cash at the pay date, and only a
dividend that is known. Synthetic store; injected clock."""

from __future__ import annotations

from datetime import date, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from alpha_cli import follow_book, follow_store, follow_update
from alpha_core import ActionType, CorporateAction
from alpha_data.store import ParquetStore
from tests.fixtures.follow_fixtures import BUY_AND_SELL, DAYS, F0, World

APPROX = pytest.approx(0, rel=1e-9, abs=1e-12)


def _dividend(k: int, amount: float, *, pay: int | None = None, known: int | None = None) -> Any:
    return CorporateAction(
        symbol="SPY",
        action_type=ActionType.DIVIDEND,
        ex_date=DAYS[F0 + k],
        announce_date=DAYS[F0 + (k if known is None else known)],
        pay_date=DAYS[F0 + (k if pay is None else pay)],
        amount=amount,
    )


def _store(world: World, actions: list[Any]) -> None:
    ParquetStore(world.home / "store").write_actions("SPY", actions)


def _run(world: World, follow: str, days: int) -> list[Any]:
    for k in range(days):
        world.grow()
        follow_update.update_follow(world.home, follow, clock=partial(world.close_of, k))
    return follow_store.entries_of(world.home, follow)


def test_a_dividend_inside_the_held_period_is_booked_at_its_pay_date(tmp_path: Path) -> None:
    world = World(tmp_path, -0.2, BUY_AND_SELL)
    _store(world, [_dividend(3, 0.5, pay=4, known=2)])
    entries = _run(world, world.start(), 6)
    by_session = {e.session_date: e.payload for e in entries[1:]}
    units = by_session[DAYS[F0 + 2]]["book"]["units"]
    assert units > 0
    assert by_session[DAYS[F0 + 3]]["dividends"] == []
    paid = by_session[DAYS[F0 + 4]]["dividends"]
    assert [d["cash"] for d in paid] == [pytest.approx(units * 0.5, rel=1e-9, abs=1e-12)]
    assert by_session[DAYS[F0 + 4]]["book"]["dividends_cum"] == pytest.approx(units * 0.5)
    without = by_session[DAYS[F0 + 3]]["book"]["cash"]
    assert by_session[DAYS[F0 + 4]]["book"]["cash"] == pytest.approx(without + units * 0.5)


def test_a_dividend_outside_the_held_period_is_not_booked(tmp_path: Path) -> None:
    world = World(tmp_path, -0.2, BUY_AND_SELL)
    # Ex on the day the buy fills (no units before its open), and after the sale filled.
    _store(world, [_dividend(1, 0.5), _dividend(7, 0.5)])
    entries = _run(world, world.start(), 8)
    assert all(e.payload["dividends"] == [] for e in entries[1:])
    assert entries[-1].payload["book"]["dividends_cum"] == 0.0


def test_a_dividend_known_late_is_not_booked_before_it_was_known(tmp_path: Path) -> None:
    world = World(tmp_path, -0.2, BUY_AND_SELL)
    follow = world.start()
    first = _run(world, follow, 5)
    assert all(e.payload["dividends"] == [] for e in first[1:])
    kept = {e.seq: e.entry_hash for e in first}
    _store(world, [_dividend(3, 0.5)])  # the store learns of it now: ex was session 3
    world.grow()
    follow_update.update_follow(world.home, follow, clock=lambda: world.close_of(5))
    entries = follow_store.entries_of(world.home, follow)
    assert {e.seq: e.entry_hash for e in entries[: len(first)]} == kept
    booked = entries[-1].payload["dividends"]
    units = first[3].payload["book"]["units"]  # the holding before the ex session's open
    assert [d["cash"] for d in booked] == [pytest.approx(units * 0.5, rel=1e-9, abs=1e-12)]
    assert booked[0]["ex_date"] == DAYS[F0 + 3].isoformat()


def test_a_dividend_is_booked_once() -> None:
    book = follow_book.new_book()
    book["units"] = 2.0
    action = CorporateAction(
        symbol="X", action_type=ActionType.DIVIDEND, ex_date=date(2026, 1, 5), amount=1.0
    )
    day = date(2026, 1, 6)
    once, paid = follow_book.dividends(book, [action], session=day, units_before=lambda _: 2.0)
    twice, again = follow_book.dividends(
        once, [action], session=day + timedelta(1), units_before=lambda _: 2.0
    )
    assert [d["cash"] for d in paid] == [2.0] and again == []
    assert twice["dividends_cum"] == pytest.approx(2.0, rel=1e-9, abs=1e-12)


def test_a_dividend_not_yet_known_waits() -> None:
    action = CorporateAction(
        symbol="X",
        action_type=ActionType.DIVIDEND,
        ex_date=date(2026, 1, 9),
        announce_date=date(2026, 1, 8),
        amount=1.0,
    )
    book = follow_book.new_book()
    waiting, paid = follow_book.dividends(
        book, [action], session=date(2026, 1, 7), units_before=lambda _: 1.0
    )
    assert paid == [] and waiting["dividends_seen"] == []

"""Two-clock corporate-action math (splits). See spec §6.1."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from alpha_core import ActionType, CorporateAction, DataError


def known_actions(actions: Sequence[CorporateAction], as_of: date) -> list[CorporateAction]:
    """Actions whose knowledge_time <= as_of (availability gate)."""
    return [a for a in actions if a.knowledge_time <= as_of]


def cash_dividends(actions: Sequence[CorporateAction]) -> list[CorporateAction]:
    """The DIVIDEND actions among ``actions``, in input order.

    Pulled out alongside ``split_factor`` so the two clocks stay separate: splits adjust
    the price series; dividends are decoupled cash events (spec §6.1.4) credited at
    ``pay_date`` by the engine — never folded into prices. Fails loud on a DIVIDEND
    missing its ``amount`` (mirrors ``split_factor``'s ratio guard).
    """
    out: list[CorporateAction] = []
    for a in actions:
        if a.action_type is ActionType.DIVIDEND:
            if a.amount is None:
                raise DataError(
                    f"DIVIDEND action for {a.symbol!r} has no amount (data integrity failure)"
                )
            out.append(a)
    return out


def split_factor(bar_date: date, actions: Sequence[CorporateAction]) -> float:
    """Back-adjustment multiplier for prices on ``bar_date``.

    Accepts knowledge-gated actions of any type and applies only SPLITs.
    Product of 1/ratio over every SPLIT with ex_date strictly after bar_date
    (application gate = ex_date).
    """
    factor = 1.0
    for a in actions:
        if a.action_type is ActionType.SPLIT and a.ex_date > bar_date:
            if a.ratio is None:
                raise DataError(
                    f"SPLIT action for {a.symbol!r} has no ratio (data integrity failure)"
                )
            factor /= a.ratio
    return factor

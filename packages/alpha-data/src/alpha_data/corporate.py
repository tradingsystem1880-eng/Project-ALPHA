"""Two-clock corporate-action math (splits). See spec §6.1."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from alpha_core import ActionType, CorporateAction


def known_actions(actions: Sequence[CorporateAction], as_of: date) -> list[CorporateAction]:
    """Actions whose knowledge_time <= as_of (availability gate)."""
    return [a for a in actions if a.knowledge_time <= as_of]


def split_factor(bar_date: date, splits: Sequence[CorporateAction]) -> float:
    """Back-adjustment multiplier for prices on ``bar_date``.

    Product of 1/ratio over every SPLIT with ex_date strictly after bar_date
    (application gate = ex_date). Pass only knowledge-gated actions in.
    """
    factor = 1.0
    for a in splits:
        if a.action_type is ActionType.SPLIT and a.ex_date > bar_date:
            assert a.ratio is not None  # guaranteed by CorporateAction validator
            factor /= a.ratio
    return factor

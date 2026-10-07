"""A point-in-time universe must keep names that later left, and must not know they will leave.

Two guards with the repo's leaky-twin convention: the sanctioned reader passes, a "current
constituents" reader (the classic survivorship bug) fails the same assertions.
"""

from __future__ import annotations

from datetime import date

import pytest

from alpha_core import UniverseMembership, members_as_of

pytestmark = pytest.mark.bias_guard


def _universe() -> list[UniverseMembership]:
    return [
        UniverseMembership(symbol="ALIVE", effective_from=date(2020, 1, 1)),
        UniverseMembership(
            symbol="DEAD",
            effective_from=date(2020, 1, 1),
            effective_to=date(2022, 6, 1),
            delisting_return=-0.4,
            reason="delisted",
        ),
        UniverseMembership(symbol="LATER", effective_from=date(2023, 1, 1), reason="index_add"),
    ]


def _survivors_only(memberships: list[UniverseMembership], when: date) -> list[str]:
    """The leaky twin: reads today's constituents and ignores the interval (survivorship bias)."""
    return sorted(m.symbol for m in memberships if m.effective_to is None)


def test_later_delisted_name_is_a_member_while_it_was_alive() -> None:
    when = date(2021, 6, 30)
    assert "DEAD" in members_as_of(_universe(), when)
    assert "DEAD" not in _survivors_only(_universe(), when)  # the twin leaks


def test_future_additions_are_invisible_before_their_effective_date() -> None:
    when = date(2021, 6, 30)
    assert "LATER" not in members_as_of(_universe(), when)
    assert "LATER" in _survivors_only(_universe(), when)  # the twin leaks


def test_future_poison_does_not_change_past_membership() -> None:
    """Deleting every interval edge after the cutoff must not change membership before it."""
    cutoff = date(2022, 1, 1)
    clean = _universe()
    poisoned = [
        m.model_copy(update={"effective_to": None, "delisting_return": None})
        if m.effective_to is not None and m.effective_to > cutoff
        else m
        for m in clean
        if m.effective_from <= cutoff
    ]
    for when in (date(2020, 1, 1), date(2021, 6, 30), date(2021, 12, 31)):
        assert members_as_of(clean, when) == members_as_of(poisoned, when)
    # the poison MUST change post-cutoff membership, else the guard has no discriminating power
    assert members_as_of(clean, date(2023, 6, 1)) != members_as_of(poisoned, date(2023, 6, 1))

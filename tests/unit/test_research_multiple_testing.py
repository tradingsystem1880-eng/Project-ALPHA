"""Holm correction over one immutable, preregistered secondary family."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from alpha_core import DataError
from alpha_research import (
    FrozenSecondaryFamily,
    SecondaryHypothesis,
    holm_adjust_secondary_family,
)


def test_holm_adjustment_preserves_registered_order_and_controls_family() -> None:
    family = FrozenSecondaryFamily(
        family_id="secondary-outcomes-v1",
        alpha=0.05,
        hypotheses=(
            SecondaryHypothesis("one-day", 0.01),
            SecondaryHypothesis("five-day", 0.04),
            SecondaryHypothesis("ten-day", 0.03),
        ),
    )

    adjusted = holm_adjust_secondary_family(family)

    assert [item.hypothesis_id for item in adjusted] == ["one-day", "five-day", "ten-day"]
    assert [item.adjusted_p_value for item in adjusted] == pytest.approx([0.03, 0.06, 0.06])
    assert [item.rejected for item in adjusted] == [True, False, False]
    assert family.contract_hash == family.contract_hash


def test_holm_ties_are_deterministic_and_monotone() -> None:
    family = FrozenSecondaryFamily(
        family_id="tie-family",
        alpha=0.05,
        hypotheses=(
            SecondaryHypothesis("b", 0.01),
            SecondaryHypothesis("a", 0.01),
            SecondaryHypothesis("c", 0.20),
        ),
    )

    first = holm_adjust_secondary_family(family)
    second = holm_adjust_secondary_family(family)

    assert first == second
    by_id = {item.hypothesis_id: item for item in first}
    assert by_id["a"].adjusted_p_value == pytest.approx(0.03)
    assert by_id["b"].adjusted_p_value == pytest.approx(0.03)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: SecondaryHypothesis("", 0.01),
        lambda: SecondaryHypothesis("bad", float("nan")),
        lambda: SecondaryHypothesis("bad", 1.1),
        lambda: FrozenSecondaryFamily("", (SecondaryHypothesis("a", 0.1),)),
        lambda: FrozenSecondaryFamily("family", ()),
        lambda: FrozenSecondaryFamily(
            "family",
            (SecondaryHypothesis("same", 0.1), SecondaryHypothesis("same", 0.2)),
        ),
        lambda: FrozenSecondaryFamily("family", (SecondaryHypothesis("a", 0.1),), alpha=0.5),
    ],
)
def test_frozen_secondary_family_rejects_malformed_input(factory: Callable[[], object]) -> None:
    with pytest.raises(DataError):
        factory()

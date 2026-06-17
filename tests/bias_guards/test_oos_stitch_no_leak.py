"""Walk-forward OOS stitching must not leak future data into scored windows (spec §8 gate 1/2).

Future-poison guard: corrupting equity *after* the last scored OOS bar must not change any OOS
return or metric. A non-vacuous counter-check confirms that poisoning *inside* the OOS does change
them — so the guard would actually catch a leak.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from alpha_cli._runner import walk_forward_oos

pytestmark = pytest.mark.bias_guard

# 40 equity points -> 39 returns; train 10, test 5, embargo 1 -> folds end at return index 36,
# so returns 36..38 (equity points 37..39) are never scored.
_TRAIN, _TEST, _EMBARGO = 10, 5, 1
_LAST_SCORED_EQUITY_INDEX = 36


def _curve(n: int = 40, seed: int = 1) -> list[tuple[datetime, float]]:
    vals = 100.0 * np.cumprod(1.0 + np.random.default_rng(seed).normal(0.001, 0.01, n))
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [(start + timedelta(days=i), float(v)) for i, v in enumerate(vals)]


def _oos(curve: list[tuple[datetime, float]]) -> np.ndarray:
    res = walk_forward_oos(
        curve,
        train_size=_TRAIN,
        test_size=_TEST,
        embargo=_EMBARGO,
        anchored=False,
        periods_per_year=252,
        min_train=7,
    )
    return res.oos_returns


def test_poisoning_post_oos_tail_does_not_change_scored_oos() -> None:
    curve = _curve()
    clean = _oos(curve)
    # corrupt every equity point strictly after the last scored bar with an absurd value
    poisoned = list(curve)
    for i in range(_LAST_SCORED_EQUITY_INDEX + 1, len(poisoned)):
        poisoned[i] = (poisoned[i][0], 1e9)
    assert np.array_equal(_oos(poisoned), clean)  # future bars never touch the OOS curve


def test_guard_is_non_vacuous_poisoning_inside_oos_changes_it() -> None:
    curve = _curve()
    clean = _oos(curve)
    tampered = list(curve)
    tampered[20] = (tampered[20][0], tampered[20][1] * 1.5)  # index 20 sits inside a scored window
    assert not np.array_equal(_oos(tampered), clean)  # an in-window change DOES move the OOS curve

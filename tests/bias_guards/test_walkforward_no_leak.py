"""Walk-forward folds must be strictly causal: no test index ever leaks into training.

This guards gate 2 (spec §8). A walk-forward partition that let a future (test) observation into
the training window would manufacture look-ahead before any model is even fit.
"""

from __future__ import annotations

import pytest

from alpha_validation.walkforward import walk_forward_splits

pytestmark = pytest.mark.bias_guard

# a spread of shapes: rolling/anchored, varied embargo, tight and loose fits
_CONFIGS = [
    {"n_samples": 50, "train_size": 10, "test_size": 5, "embargo": 0},
    {"n_samples": 50, "train_size": 10, "test_size": 5, "embargo": 3},
    {"n_samples": 50, "train_size": 10, "test_size": 5, "embargo": 3, "anchored": True},
    {"n_samples": 37, "train_size": 7, "test_size": 4, "embargo": 2},
    {"n_samples": 200, "train_size": 60, "test_size": 20, "embargo": 5, "anchored": True},
]


@pytest.mark.parametrize("cfg", _CONFIGS)
def test_train_strictly_precedes_test_with_embargo_gap(cfg: dict[str, int]) -> None:
    embargo = cfg.get("embargo", 0)
    splits = walk_forward_splits(**cfg)  # type: ignore[arg-type]
    assert splits  # the config must produce at least one fold
    for split in splits:
        train, test = set(split.train), set(split.test)
        assert train.isdisjoint(test)  # no shared observation
        assert max(train) < min(test)  # every train index is in the past relative to test
        gap = min(test) - max(train) - 1  # empty samples separating the blocks
        assert gap >= embargo  # the embargo buffer is honoured
        assert min(split.test) >= 0 and max(split.test) < cfg["n_samples"]  # in-bounds


def test_test_windows_tile_forward_without_overlap() -> None:
    # successive OOS windows must not overlap each other (every test observation scored once)
    splits = walk_forward_splits(100, train_size=20, test_size=10, embargo=2)
    seen: set[int] = set()
    for split in splits:
        idx = set(split.test)
        assert seen.isdisjoint(idx)
        seen |= idx

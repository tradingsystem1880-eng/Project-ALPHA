"""Purged/embargoed walk-forward splitter geometry (spec §8 gate 2)."""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_validation.walkforward import Split, walk_forward_splits


def test_rolling_fold_geometry() -> None:
    # n=20, train 5, test 3, embargo 1, rolling: test starts 6,9,12,15 -> 4 folds
    splits = walk_forward_splits(20, train_size=5, test_size=3, embargo=1)
    assert len(splits) == 4
    assert splits[0] == Split(train=range(0, 5), test=range(6, 9))  # 1-sample embargo gap [5,6)
    assert splits[1] == Split(train=range(3, 8), test=range(9, 12))  # train window rolls forward
    assert splits[3] == Split(train=range(9, 14), test=range(15, 18))


def test_anchored_train_expands_from_zero() -> None:
    splits = walk_forward_splits(20, train_size=5, test_size=3, embargo=1, anchored=True)
    assert splits[0].train == range(0, 5)
    assert splits[1].train == range(0, 8)  # anchored: train start pinned at 0, end grows
    assert splits[3].train == range(0, 14)


def test_zero_embargo_places_test_immediately_after_train() -> None:
    splits = walk_forward_splits(10, train_size=4, test_size=2, embargo=0)
    assert splits[0] == Split(train=range(0, 4), test=range(4, 6))


def test_fails_loud_when_no_fold_fits() -> None:
    with pytest.raises(DataError):
        walk_forward_splits(5, train_size=5, test_size=3, embargo=1)  # 5+1+3 > 5
    with pytest.raises(DataError):
        walk_forward_splits(20, train_size=0, test_size=3)  # train_size must be >= 1
    with pytest.raises(DataError):
        walk_forward_splits(20, train_size=5, test_size=3, embargo=-1)  # embargo must be >= 0


def test_splits_are_deterministic() -> None:
    a = walk_forward_splits(40, train_size=6, test_size=4, embargo=2)
    b = walk_forward_splits(40, train_size=6, test_size=4, embargo=2)
    assert a == b

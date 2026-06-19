"""Combinatorial Purged Cross-Validation splitter (López de Prado ch. 12)."""

from __future__ import annotations

from math import comb

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.cpcv import combinatorial_purged_splits, n_cpcv_splits


def test_fold_count_is_n_choose_k() -> None:
    splits = combinatorial_purged_splits(60, n_groups=6, n_test_groups=2)
    assert len(splits) == comb(6, 2) == 15
    assert n_cpcv_splits(6, 2) == 15


def test_train_and_test_are_disjoint_and_test_covers_its_groups() -> None:
    splits = combinatorial_purged_splits(60, n_groups=6, n_test_groups=2)
    for sp in splits:
        assert set(sp.train.tolist()).isdisjoint(sp.test.tolist())
        assert len(sp.test_groups) == 2
        assert sp.test.size == 20  # two of six equal groups over 60 samples


def test_embargo_drops_samples_after_each_test_block() -> None:
    no_embargo = combinatorial_purged_splits(60, n_groups=6, n_test_groups=1, embargo=0)
    embargoed = combinatorial_purged_splits(60, n_groups=6, n_test_groups=1, embargo=3)
    # for a single test group not at the end, the embargo removes 3 training samples after it
    fold0_no = no_embargo[0]  # tests group 0 (indices 0..9), embargo removes 10,11,12
    fold0_em = embargoed[0]
    assert fold0_em.train.size == fold0_no.train.size - 3
    assert {10, 11, 12}.isdisjoint(fold0_em.train.tolist())


def test_each_group_tested_equally_often() -> None:
    n_groups, k = 6, 2
    splits = combinatorial_purged_splits(60, n_groups=n_groups, n_test_groups=k)
    counts = {g: 0 for g in range(n_groups)}
    for sp in splits:
        for g in sp.test_groups:
            counts[g] += 1
    assert set(counts.values()) == {comb(n_groups - 1, k - 1)}  # symmetric coverage


def test_deterministic() -> None:
    a = combinatorial_purged_splits(50, n_groups=5, n_test_groups=2, embargo=2)
    b = combinatorial_purged_splits(50, n_groups=5, n_test_groups=2, embargo=2)
    for sa, sb in zip(a, b, strict=True):
        assert np.array_equal(sa.train, sb.train)
        assert np.array_equal(sa.test, sb.test)
        assert sa.test_groups == sb.test_groups


def test_fails_loud() -> None:
    with pytest.raises(DataError):
        combinatorial_purged_splits(60, n_groups=1, n_test_groups=1)
    with pytest.raises(DataError):
        combinatorial_purged_splits(60, n_groups=6, n_test_groups=6)  # k must be < n_groups
    with pytest.raises(DataError):
        combinatorial_purged_splits(60, n_groups=6, n_test_groups=2, embargo=-1)
    with pytest.raises(DataError):
        combinatorial_purged_splits(3, n_groups=6, n_test_groups=2)  # fewer samples than groups

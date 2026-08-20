"""Metamorphic relations for the causal splitters (walk-forward and CPCV).

Primary source: López de Prado, *Advances in Financial Machine Learning* (2018) ch. 7 (purging
and embargo) and ch. 12 (combinatorial purged cross-validation, C(N, k) folds). Every relation
below is a leakage or geometry property; a splitter that lets a test index precede or abut a
train index, or that produces the wrong fold count, breaks one of them.
"""

from __future__ import annotations

from math import comb

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from alpha_core import DataError
from alpha_validation.cpcv import combinatorial_purged_splits, n_cpcv_splits
from alpha_validation.walkforward import walk_forward_splits

pytestmark = pytest.mark.oracle


@given(
    st.integers(min_value=1, max_value=40),
    st.integers(min_value=1, max_value=20),
    st.integers(min_value=0, max_value=10),
    st.integers(min_value=1, max_value=8),
    st.booleans(),
)
@settings(max_examples=150, deadline=None)
def test_walk_forward_is_causal_contiguous_and_equal_sized(
    train_size: int, test_size: int, embargo: int, n_folds: int, anchored: bool
) -> None:
    n = train_size + embargo + n_folds * test_size
    splits = walk_forward_splits(
        n, train_size=train_size, test_size=test_size, embargo=embargo, anchored=anchored
    )
    assert len(splits) == n_folds
    for i, sp in enumerate(splits):
        assert len(sp.test) == test_size
        # causality with embargo: the last train index sits at least `embargo` before the test
        assert min(sp.test) - max(sp.train) - 1 >= embargo
        assert min(sp.test) - max(sp.train) - 1 == embargo  # buffer is exact, not padded
        assert set(sp.train).isdisjoint(sp.test)
        assert sp.train.start == (0 if anchored else sp.train.stop - train_size)
        if anchored:
            assert len(sp.train) >= train_size
        else:
            assert len(sp.train) == train_size
        if i:
            assert sp.test.start == splits[i - 1].test.stop  # contiguous tiling
    assert splits[-1].test.stop == n  # no remainder when n tiles exactly


def test_walk_forward_drops_a_short_trailing_remainder() -> None:
    splits = walk_forward_splits(30, train_size=10, test_size=7, embargo=0)
    assert [tuple(s.test) for s in splits] == [tuple(range(10, 17)), tuple(range(17, 24))]


def test_walk_forward_guards_fail_loud() -> None:
    with pytest.raises(DataError):
        walk_forward_splits(10, train_size=0, test_size=2)
    with pytest.raises(DataError):
        walk_forward_splits(10, train_size=5, test_size=0)
    with pytest.raises(DataError):
        walk_forward_splits(10, train_size=5, test_size=2, embargo=-1)
    with pytest.raises(DataError, match="no walk-forward fold fits"):
        walk_forward_splits(10, train_size=8, test_size=3)


@given(
    st.integers(min_value=2, max_value=8),
    st.integers(min_value=1, max_value=7),
    st.integers(min_value=0, max_value=5),
    st.integers(min_value=8, max_value=120),
)
@settings(max_examples=150, deadline=None)
def test_cpcv_count_disjointness_and_embargo(
    n_groups: int, n_test_groups: int, embargo: int, n_samples: int
) -> None:
    if not 1 <= n_test_groups < n_groups:
        with pytest.raises(DataError):
            combinatorial_purged_splits(
                n_samples, n_groups=n_groups, n_test_groups=n_test_groups, embargo=embargo
            )
        return
    splits = combinatorial_purged_splits(
        n_samples, n_groups=n_groups, n_test_groups=n_test_groups, embargo=embargo
    )
    assert len(splits) == comb(n_groups, n_test_groups) == n_cpcv_splits(n_groups, n_test_groups)
    seen: set[tuple[int, ...]] = set()
    for sp in splits:
        assert sp.test_groups not in seen
        seen.add(sp.test_groups)
        assert len(sp.test_groups) == n_test_groups
        train, test = set(sp.train.tolist()), set(sp.test.tolist())
        assert train.isdisjoint(test)
        assert np.array_equal(sp.test, np.sort(sp.test))
        assert np.array_equal(sp.train, np.sort(sp.train))
        # every index is either train, test, or in an embargo window right after a test block
        leftovers = set(range(n_samples)) - train - test
        assert len(leftovers) <= embargo * n_test_groups
        for k in leftovers:
            assert any(0 < k - t <= embargo for t in test)
        # embargo: no train index within `embargo` positions AFTER any test index
        if embargo:
            for t in test:
                assert not any(0 < j - t <= embargo for j in train)
    # every sample is a test sample in exactly C(N-1, k-1) folds
    counts = np.zeros(n_samples, dtype=int)
    for sp in splits:
        counts[sp.test] += 1
    assert np.all(counts == comb(n_groups - 1, n_test_groups - 1))


def test_cpcv_order_is_deterministic() -> None:
    a = combinatorial_purged_splits(60, n_groups=6, n_test_groups=2, embargo=2)
    b = combinatorial_purged_splits(60, n_groups=6, n_test_groups=2, embargo=2)
    assert [s.test_groups for s in a] == [s.test_groups for s in b]
    assert all(np.array_equal(x.train, y.train) for x, y in zip(a, b, strict=True))


def test_cpcv_guards_fail_loud() -> None:
    with pytest.raises(DataError):
        combinatorial_purged_splits(20, n_groups=1, n_test_groups=1)
    with pytest.raises(DataError):
        combinatorial_purged_splits(20, n_groups=4, n_test_groups=2, embargo=-1)
    with pytest.raises(DataError):
        combinatorial_purged_splits(3, n_groups=4, n_test_groups=2)

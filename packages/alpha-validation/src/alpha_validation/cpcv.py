"""Combinatorial Purged Cross-Validation (López de Prado, *Advances in Financial ML* ch. 12).

A single walk-forward path tests each observation once, so its out-of-sample Sharpe is one draw
from a wide sampling distribution — easy to over-read. CPCV partitions the timeline into ``N``
contiguous groups and tests *every* size-``k`` combination of them (``C(N, k)`` folds), purging and
embargoing the training data adjacent to each test block. That yields many overlapping OOS paths
instead of one, so the gauntlet can report the *distribution* of OOS performance, not a point.

Index-only and engine-agnostic (like ``walkforward``): each fold is integer index arrays into a
time-ordered sample. The embargo drops the ``embargo`` training observations immediately following
each test block (the forward adjacency where serial correlation would leak test into train); with
the daily, horizon-1 labels ALPHA uses, that one-sided buffer is the operative purge (see the
``walkforward`` module note). Fails loud (``DataError``) on a degenerate configuration.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from math import comb

import numpy as np
import numpy.typing as npt

from alpha_core import DataError

IndexArray = npt.NDArray[np.intp]


@dataclass(frozen=True)
class CPCVSplit:
    """One CPCV fold: the purged/embargoed train indices, the test indices, and the test groups."""

    train: IndexArray
    test: IndexArray
    test_groups: tuple[int, ...]


def combinatorial_purged_splits(
    n_samples: int,
    *,
    n_groups: int,
    n_test_groups: int,
    embargo: int = 0,
) -> list[CPCVSplit]:
    """All ``C(n_groups, n_test_groups)`` purged/embargoed CPCV folds over ``range(n_samples)``.

    The sample is split into ``n_groups`` contiguous, near-equal groups; every combination of
    ``n_test_groups`` of them forms a test set, with the remaining groups (minus an ``embargo``
    buffer after each test block) as training. Returned in deterministic combination order.

    Fails loud (``DataError``) on ``n_groups < 2``, ``n_test_groups`` outside ``[1, n_groups)``,
    negative ``embargo``, or ``n_samples < n_groups`` (which would leave an empty group).
    """
    if n_groups < 2:
        raise DataError(f"n_groups must be >= 2, got {n_groups}")
    if not 1 <= n_test_groups < n_groups:
        raise DataError(f"n_test_groups must be in [1, {n_groups}), got {n_test_groups}")
    if embargo < 0:
        raise DataError(f"embargo must be >= 0, got {embargo}")
    if n_samples < n_groups:
        raise DataError(f"n_samples ({n_samples}) must be >= n_groups ({n_groups})")

    groups = [g.astype(np.intp) for g in np.array_split(np.arange(n_samples), n_groups)]

    splits: list[CPCVSplit] = []
    for combo in itertools.combinations(range(n_groups), n_test_groups):
        test = np.concatenate([groups[i] for i in combo])
        test_set = set(test.tolist())
        embargoed: set[int] = set()
        for i in combo:
            end = int(groups[i][-1]) + 1
            embargoed.update(range(end, min(end + embargo, n_samples)))
        train = np.array(
            [k for k in range(n_samples) if k not in test_set and k not in embargoed],
            dtype=np.intp,
        )
        splits.append(CPCVSplit(train=train, test=np.sort(test), test_groups=combo))
    return splits


def n_cpcv_splits(n_groups: int, n_test_groups: int) -> int:
    """The number of folds ``combinatorial_purged_splits`` will produce: ``C(n_groups, k)``."""
    if n_groups < 2 or not 1 <= n_test_groups < n_groups:
        raise DataError(f"invalid CPCV config: n_groups={n_groups}, n_test_groups={n_test_groups}")
    return comb(n_groups, n_test_groups)

"""Purged/embargoed walk-forward splitter (spec §8 gate 2, §7 causality).

Walk-forward is the v1 out-of-sample protocol: train on a past window, test on the next, never
the reverse. Because the split is strictly causal (every train index precedes every test index),
the purge and embargo of López de Prado's CPCV collapse into a single forward buffer — ``embargo``
samples left empty between each train block and its test block — which is the only adjacency where
boundary leakage can occur. The full two-sided purge+embargo belongs to CPCV, deferred with the
parameter sweeps it serves (spec §8 note on PBO/DSR).

The splitter is index-only and engine-agnostic: it returns integer index ranges into a
time-ordered sample so the caller (the CLI gauntlet) can slice an equity curve or bar series.
"""

from __future__ import annotations

from dataclasses import dataclass

from alpha_core import DataError


@dataclass(frozen=True)
class Split:
    """One walk-forward fold as index ranges into a time-ordered sample (train precedes test)."""

    train: range
    test: range


def walk_forward_splits(
    n_samples: int,
    *,
    train_size: int,
    test_size: int,
    embargo: int = 0,
    anchored: bool = False,
) -> list[Split]:
    """Generate causal walk-forward folds over ``range(n_samples)``.

    Each fold tests a fresh ``test_size`` window; consecutive test windows are contiguous and
    advance by ``test_size``. ``embargo`` samples immediately before each test window are excluded
    from training (the leakage buffer). Training is a rolling ``train_size`` window by default, or
    an expanding window anchored at index 0 when ``anchored=True``. A trailing remainder shorter
    than ``test_size`` is dropped so every fold is equal-sized.

    Fails loud (``DataError``) on non-positive sizes, negative embargo, or a configuration too
    large to fit even one fold in ``n_samples``.
    """
    if train_size < 1:
        raise DataError(f"train_size must be >= 1, got {train_size}")
    if test_size < 1:
        raise DataError(f"test_size must be >= 1, got {test_size}")
    if embargo < 0:
        raise DataError(f"embargo must be >= 0, got {embargo}")
    first_test_start = train_size + embargo
    if first_test_start + test_size > n_samples:
        raise DataError(
            f"no walk-forward fold fits: train_size + embargo + test_size = "
            f"{first_test_start + test_size} > n_samples = {n_samples}"
        )
    splits: list[Split] = []
    test_start = first_test_start
    while test_start + test_size <= n_samples:
        train_end = test_start - embargo
        train_start = 0 if anchored else train_end - train_size
        splits.append(
            Split(
                train=range(train_start, train_end),
                test=range(test_start, test_start + test_size),
            )
        )
        test_start += test_size
    return splits

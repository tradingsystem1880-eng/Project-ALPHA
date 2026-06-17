"""Synthetic OHLCV price paths for the Tier-2 full-engine null (``alpha_cli._synth``).

Whole bars are block-bootstrapped (not close-to-close returns) so each bar's intrabar OHLC and the
close(t)->open(t+1) gap survive; only block ordering is randomized. Picked rows are re-stamped onto
the original session calendar so the feed stays chronological.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from alpha_cli._synth import synthetic_bar_paths
from alpha_core import Bar, DataError


def _bars(n: int) -> list[Bar]:
    # close encodes the original index (i -> i+1) so a synthetic path's prices reveal its provenance
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Bar(
            symbol="SYN",
            ts=start + timedelta(days=i),
            open=float(i + 1),
            high=float(i + 1),
            low=float(i + 1),
            close=float(i + 1),
            volume=1.0,
        )
        for i in range(n)
    ]


def test_shape_and_length() -> None:
    paths = synthetic_bar_paths(_bars(30), n_paths=7, mean_block=4.0, seed=0)
    assert len(paths) == 7
    assert all(len(p) == 30 for p in paths)


def test_deterministic_under_seed() -> None:
    bars = _bars(30)
    a = synthetic_bar_paths(bars, n_paths=5, mean_block=4.0, seed=42)
    b = synthetic_bar_paths(bars, n_paths=5, mean_block=4.0, seed=42)
    assert [[bar.close for bar in p] for p in a] == [[bar.close for bar in p] for p in b]


def test_timestamps_are_the_original_monotone_axis() -> None:
    bars = _bars(30)
    timeline = [b.ts for b in bars]
    for p in synthetic_bar_paths(bars, n_paths=5, mean_block=4.0, seed=1):
        assert [bar.ts for bar in p] == timeline  # re-stamped onto the real session calendar
        assert all(p[i].ts < p[i + 1].ts for i in range(len(p) - 1))  # strictly increasing


def test_large_block_is_a_single_contiguous_circular_block() -> None:
    # mirrors test_bootstrap's contiguity check: mean_block >> n -> no restarts, prices wrap mod n
    [path] = synthetic_bar_paths(_bars(20), n_paths=1, mean_block=10_000.0, seed=3)
    idx = np.array([int(bar.close) - 1 for bar in path])  # recover the original indices
    assert np.array_equal(idx[1:], (idx[:-1] + 1) % 20)  # purely contiguous wrap, no restarts


def test_fails_loud_on_too_few_bars() -> None:
    with pytest.raises(DataError):
        synthetic_bar_paths(_bars(1), n_paths=3, mean_block=2.0, seed=0)

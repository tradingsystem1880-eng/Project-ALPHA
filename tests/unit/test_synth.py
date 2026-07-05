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
    # volume encodes the original index (i -> i+1): volumes are copied per picked row, so a
    # synthetic path's volumes reveal its provenance even though prices are relative-chained
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Bar(
            symbol="SYN",
            ts=start + timedelta(days=i),
            open=float(i + 1),
            high=float(i + 1),
            low=float(i + 1),
            close=float(i + 1),
            volume=float(i + 1),
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
    # mirrors test_bootstrap's contiguity check: mean_block >> n -> no restarts, rows wrap mod n
    [path] = synthetic_bar_paths(_bars(20), n_paths=1, mean_block=10_000.0, seed=3)
    idx = np.array([int(bar.volume) - 1 for bar in path])  # recover the original indices
    assert np.array_equal(idx[1:], (idx[:-1] + 1) % 20)  # purely contiguous wrap, no restarts


def _trending_ohlcv(n: int = 120) -> list[Bar]:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    rng = np.random.default_rng(9)
    bars: list[Bar] = []
    prev_close = 100.0
    for i in range(n):
        o = prev_close * float(1.0 + rng.normal(0.0, 0.002))  # small real overnight gap
        c = o * float(1.0 + 0.01 + rng.normal(0.0, 0.004))  # strong uptrend: ~x3 over the window
        hi, lo = max(o, c) * 1.002, min(o, c) * 0.998
        bars.append(
            Bar(
                symbol="SYN",
                ts=start + timedelta(days=i),
                open=o,
                high=hi,
                low=lo,
                close=c,
                volume=float(i + 1),
            )
        )
        prev_close = c
    return bars


def test_paths_are_level_continuous_no_seam_jumps() -> None:
    # On a strongly trending series the OLD raw-row splice produced fictitious ~3x overnight
    # jumps at block seams; relative-chaining must keep every overnight move within the range
    # of gaps the real series actually exhibits.
    bars = _trending_ohlcv()
    max_real_gap = max(abs(np.log(bars[j].open / bars[j - 1].close)) for j in range(1, len(bars)))
    for path in synthetic_bar_paths(bars, n_paths=20, mean_block=5.0, seed=11):
        for i in range(1, len(path)):
            move = abs(np.log(path[i].open / path[i - 1].close))
            assert move <= max_real_gap + 1e-12  # no seam can exceed a real overnight gap


def test_continued_blocks_are_exact_scaled_copies() -> None:
    # Within a continued block the reconstruction must preserve the original bar-to-bar returns
    # exactly (only the level is rescaled).
    bars = _trending_ohlcv()
    [path] = synthetic_bar_paths(bars, n_paths=1, mean_block=10_000.0, seed=2)  # one wrapped block
    idx = [int(b.volume) - 1 for b in path]
    for i in range(1, len(path)):
        j_prev, j = idx[i - 1], idx[i]
        if j == j_prev + 1:  # contiguous step inside the block
            assert path[i].close / path[i - 1].close == pytest.approx(
                bars[j].close / bars[j_prev].close, rel=1e-12
            )


def test_fails_loud_on_too_few_bars() -> None:
    with pytest.raises(DataError):
        synthetic_bar_paths(_bars(1), n_paths=3, mean_block=2.0, seed=0)

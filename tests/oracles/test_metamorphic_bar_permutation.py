"""Metamorphic oracles for the bar permutation null (alpha_validation.bar_permutation).

Primary source: Masters, *Testing and Tuning Market Trading Systems: Algorithms in C++* (Apress
2018), ch. 7 "Permutation Tests" (companion code MCPT_BARS.CPP) — a bar permutation must preserve
the marginal distribution of the changes (here: the multiset of log gaps and the multiset of
intrabar log shapes) while destroying their order, must leave every bar up to and including the
start bar untouched so the permuted series starts from the same level, and must apply ONE shared
reordering to every market so cross-market dependence survives (upstream neurotrader888/mcpt
bar_permute.py @ 2c0d70c). A permutation that mixed gaps with intrabar moves, touched the prefix,
or drew a fresh order per market breaks a relation below.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_validation.bar_permutation import OHLC, permute_bars, permute_bars_multi

pytestmark = pytest.mark.oracle


def _bars(n: int, seed: int, drift: float = 0.001) -> OHLC:
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(drift, 0.02, size=n)))
    open_ = np.concatenate([[100.0], close[:-1] * np.exp(rng.normal(0.0, 0.005, size=n - 1))])
    high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0.0, 0.01, size=n)))
    low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0.0, 0.01, size=n)))
    return OHLC(open=open_, high=high, low=low, close=close)


def _components(bars: OHLC) -> tuple[np.ndarray, np.ndarray]:
    """Log gaps (open vs previous close) and intrabar rows (high, low, close vs open)."""
    lo, lh, ll, lc = (np.log(getattr(bars, k)) for k in ("open", "high", "low", "close"))
    gaps = lo[1:] - lc[:-1]
    intrabar = np.column_stack([lh - lo, ll - lo, lc - lo])
    return gaps, intrabar


def test_multisets_of_gaps_and_intrabar_rows_are_preserved_and_reordered() -> None:
    bars = _bars(300, 1)
    start = 20
    permuted = permute_bars(bars, start_index=start, rng=np.random.default_rng(7))
    gaps, intrabar = _components(bars)
    p_gaps, p_intrabar = _components(permuted)
    # permuted region: gaps from bar start+1 on, intrabar rows from bar start+1 on
    np.testing.assert_allclose(np.sort(p_gaps[start:]), np.sort(gaps[start:]), rtol=1e-9)
    rows = sorted(map(tuple, np.round(intrabar[start + 1 :], 12)))
    p_rows = sorted(map(tuple, np.round(p_intrabar[start + 1 :], 12)))
    assert rows == p_rows
    assert not np.allclose(p_gaps[start:], gaps[start:])
    assert not np.allclose(p_intrabar[start + 1 :], intrabar[start + 1 :])


def test_prefix_through_the_start_bar_is_byte_identical_and_the_end_level_is_preserved() -> None:
    bars = _bars(200, 2)
    start = 37
    permuted = permute_bars(bars, start_index=start, rng=np.random.default_rng(3))
    for key in ("open", "high", "low", "close"):
        assert np.array_equal(getattr(permuted, key)[: start + 1], getattr(bars, key)[: start + 1])
    # sums of the two preserved multisets fix the final close exactly
    assert permuted.close[-1] == pytest.approx(bars.close[-1], rel=1e-9)


def test_every_permuted_bar_keeps_its_ohlc_invariants() -> None:
    bars = _bars(500, 4)
    permuted = permute_bars(bars, start_index=0, rng=np.random.default_rng(11))
    assert np.all(permuted.high >= np.maximum(permuted.open, permuted.close))
    assert np.all(permuted.low <= np.minimum(permuted.open, permuted.close))
    assert np.all(permuted.low > 0.0) and np.all(np.isfinite(permuted.high))


def test_multi_market_permutation_shares_one_order() -> None:
    first, second = _bars(150, 5), _bars(150, 6, drift=-0.001)
    permuted = permute_bars_multi([first, second], start_index=10, rng=np.random.default_rng(9))
    gaps_a, intra_a = _components(first)
    gaps_b, intra_b = _components(second)
    p_gaps_a, p_intra_a = _components(permuted[0])
    p_gaps_b, p_intra_b = _components(permuted[1])
    # recover the gap order from market A and check market B received the same one
    order = [int(np.argmin(np.abs(gaps_a[10:] - g))) for g in p_gaps_a[10:]]
    np.testing.assert_allclose(p_gaps_b[10:], gaps_b[10:][order], rtol=1e-9)
    order_intra = [int(np.argmin(np.abs(intra_a[11:] - row).sum(axis=1))) for row in p_intra_a[11:]]
    np.testing.assert_allclose(p_intra_b[11:], intra_b[11:][order_intra], rtol=1e-9)
    # a single-market call with the same seed produces market A's permutation exactly
    alone = permute_bars(first, start_index=10, rng=np.random.default_rng(9))
    assert np.array_equal(alone.close, permuted[0].close)


def test_seed_determinism() -> None:
    bars = _bars(120, 8)
    a = permute_bars(bars, start_index=5, rng=np.random.default_rng(21))
    b = permute_bars(bars, start_index=5, rng=np.random.default_rng(21))
    c = permute_bars(bars, start_index=5, rng=np.random.default_rng(22))
    assert np.array_equal(a.close, b.close) and np.array_equal(a.high, b.high)
    assert not np.array_equal(a.close, c.close)

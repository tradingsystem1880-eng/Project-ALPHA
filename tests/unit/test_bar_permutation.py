"""Unit tests for the bar permutation null (alpha_validation.bar_permutation)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.bar_permutation import OHLC, permute_bars, permute_bars_multi


def _bars(n: int) -> OHLC:
    close = np.linspace(100.0, 110.0, n)
    open_ = close - 0.5
    return OHLC(open=open_, high=close + 1.0, low=open_ - 1.0, close=close)


def test_ohlc_container_validates_shape_finiteness_positivity_and_ordering() -> None:
    bars = _bars(5)
    assert bars.size == 5
    with pytest.raises(
        DataError, match=r"^OHLC arrays must be one-dimensional and share one length$"
    ):
        OHLC(open=bars.open[:4], high=bars.high, low=bars.low, close=bars.close)
    with pytest.raises(
        DataError, match=r"^OHLC arrays must be one-dimensional and share one length$"
    ):
        OHLC(open=bars.open.reshape(5, 1), high=bars.high, low=bars.low, close=bars.close)
    with pytest.raises(DataError, match=r"^OHLC prices must be finite and positive$"):
        OHLC(open=bars.open, high=bars.high, low=np.append(bars.low[:-1], 0.0), close=bars.close)
    with pytest.raises(DataError, match=r"^OHLC prices must be finite and positive$"):
        OHLC(open=bars.open, high=np.append(bars.high[:-1], np.nan), low=bars.low, close=bars.close)
    with pytest.raises(
        DataError, match=r"^bar 2 violates high >= max\(open, close\) >= min\(open, close\) >= low$"
    ):
        OHLC(
            open=bars.open,
            high=np.where(np.arange(5) == 2, 90.0, bars.high),
            low=bars.low,
            close=bars.close,
        )
    with pytest.raises(
        DataError, match=r"^bar 4 violates high >= max\(open, close\) >= min\(open, close\) >= low$"
    ):
        OHLC(
            open=bars.open,
            high=bars.high,
            low=np.where(np.arange(5) == 4, 200.0, bars.low),
            close=bars.close,
        )


def test_permutation_needs_two_bars_after_the_start_and_a_valid_start() -> None:
    bars = _bars(6)
    rng = np.random.default_rng(0)
    with pytest.raises(DataError, match=r"^start_index must be in \[0, 4\], got 5$"):
        permute_bars(bars, start_index=5, rng=rng)
    with pytest.raises(DataError, match=r"^start_index must be in \[0, 4\], got -1$"):
        permute_bars(bars, start_index=-1, rng=rng)
    assert permute_bars(bars, start_index=4, rng=rng).size == 6
    with pytest.raises(DataError, match=r"^permutation needs at least two bars, got 1$"):
        permute_bars(_bars(1), start_index=0, rng=rng)
    with pytest.raises(DataError, match=r"^permute_bars_multi needs at least one market$"):
        permute_bars_multi([], start_index=0, rng=rng)
    with pytest.raises(DataError, match=r"^every market must have 6 bars; market 1 has 5$"):
        permute_bars_multi([bars, _bars(5)], start_index=0, rng=rng)


def test_integer_prices_are_promoted_and_dtype_is_float64() -> None:
    integer_columns: dict[str, Any] = {
        "open": np.array([10, 11, 12, 13]),
        "high": np.array([11, 12, 13, 14]),
        "low": np.array([9, 10, 11, 12]),
        "close": np.array([10, 11, 12, 13]),
    }
    bars = OHLC(**integer_columns)
    permuted = permute_bars(bars, start_index=0, rng=np.random.default_rng(1))
    for key in ("open", "high", "low", "close"):
        assert getattr(permuted, key).dtype == np.float64
        assert getattr(bars, key).dtype == np.float64


def test_start_index_zero_keeps_only_the_first_bar() -> None:
    bars = _bars(50)
    permuted = permute_bars(bars, start_index=0, rng=np.random.default_rng(5))
    assert permuted.open[0] == bars.open[0] and permuted.close[0] == bars.close[0]
    assert permuted.high[0] == bars.high[0] and permuted.low[0] == bars.low[0]
    assert not np.array_equal(permuted.close[1:], bars.close[1:])
    assert permuted.close[-1] == pytest.approx(bars.close[-1], rel=1e-9)


def test_permutation_matches_a_hand_reconstruction_from_the_components() -> None:
    rng = np.random.default_rng(13)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, size=12)))
    open_ = np.concatenate([[100.0], close[:-1] * np.exp(rng.normal(0.0, 0.004, size=11))])
    bars = OHLC(
        open=open_,
        high=np.maximum(open_, close) * 1.01,
        low=np.minimum(open_, close) * 0.99,
        close=close,
    )
    start = 3
    permuted = permute_bars(bars, start_index=start, rng=np.random.default_rng(99))
    # replay the generator: intrabar order first, then gap order (upstream's draw order)
    draw = np.random.default_rng(99)
    count = 12 - start - 1
    bar_order = draw.permutation(count)
    gap_order = draw.permutation(count)
    lo, lh, ll, lc = np.log(open_), np.log(bars.high), np.log(bars.low), np.log(close)
    gaps = (lo[1:] - lc[:-1])[start:][gap_order]
    rel_h, rel_l, rel_c = ((x - lo)[start + 1 :][bar_order] for x in (lh, ll, lc))
    expected_o, expected_h, expected_l, expected_c = (np.array(a) for a in (lo, lh, ll, lc))
    prev = lc[start]
    for k in range(count):
        i = start + 1 + k
        expected_o[i] = prev + gaps[k]
        expected_h[i] = expected_o[i] + rel_h[k]
        expected_l[i] = expected_o[i] + rel_l[k]
        expected_c[i] = expected_o[i] + rel_c[k]
        prev = expected_c[i]
    np.testing.assert_allclose(np.log(permuted.open), expected_o, rtol=1e-12)
    np.testing.assert_allclose(np.log(permuted.high), expected_h, rtol=1e-12)
    np.testing.assert_allclose(np.log(permuted.low), expected_l, rtol=1e-12)
    np.testing.assert_allclose(np.log(permuted.close), expected_c, rtol=1e-12)
    # the permuted region really moved and the bar shapes were carried as whole rows
    assert not np.allclose(permuted.close[start + 1 :], close[start + 1 :])
    shapes = sorted(zip(np.round(rel_h, 12), np.round(rel_l, 12), np.round(rel_c, 12), strict=True))
    got = sorted(
        zip(
            np.round(np.log(permuted.high / permuted.open)[start + 1 :], 12),
            np.round(np.log(permuted.low / permuted.open)[start + 1 :], 12),
            np.round(np.log(permuted.close / permuted.open)[start + 1 :], 12),
            strict=True,
        )
    )
    assert shapes == got


def test_two_bars_is_the_smallest_permutable_input_and_inputs_are_copied() -> None:
    rng = np.random.default_rng(3)
    two = _bars(2)
    assert permute_bars(two, start_index=0, rng=rng).size == 2
    assert permute_bars_multi([two, two], start_index=0, rng=rng)[1].size == 2
    with pytest.raises(DataError, match=r"^permutation needs at least two bars, got 0$"):
        permute_bars(
            OHLC(open=np.empty(0), high=np.empty(0), low=np.empty(0), close=np.empty(0)),
            start_index=0,
            rng=rng,
        )
    source = np.array([10.0, 11.0, 12.0])
    bars = OHLC(open=source, high=source + 1.0, low=source - 1.0, close=source)
    source[0] = 999.0  # the container must not alias caller memory
    assert bars.open[0] == pytest.approx(10.0) and bars.close[0] == pytest.approx(10.0)

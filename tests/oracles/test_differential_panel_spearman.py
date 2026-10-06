"""Differential oracle: ``alpha_research.panel`` versus scipy and a transcribed lstsq fit.

Per-date IC must equal ``scipy.stats.spearmanr`` (average ranks on ties), quantile monotonicity
must equal Spearman of bucket index against bucket mean, and Fama-MacBeth per-date slopes must
equal an independently built ``[1, f1, f2]`` least-squares fit.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy import stats

from alpha_research.panel import cross_sectional_ic, fama_macbeth, quantile_returns

pytestmark = pytest.mark.oracle

# Integer grid so ties occur (average-rank path exercised) without float collapse.
_CELL = st.integers(min_value=-6, max_value=6).map(float)
_PAIR = st.integers(min_value=3, max_value=7).flatmap(
    lambda t: st.integers(min_value=5, max_value=10).flatmap(
        lambda n: st.tuples(
            st.lists(st.lists(_CELL, min_size=n, max_size=n), min_size=t, max_size=t),
            st.lists(st.lists(_CELL, min_size=n, max_size=n), min_size=t, max_size=t),
        ).map(lambda pair: (np.asarray(pair[0]), np.asarray(pair[1])))
    )
)


@given(_PAIR)
@settings(max_examples=80, deadline=None)
def test_per_date_ic_matches_scipy_spearmanr(pair: tuple[np.ndarray, np.ndarray]) -> None:
    signal, outcome = pair
    series = cross_sectional_ic(signal, outcome)
    for t, value in enumerate(series.values):
        if np.unique(signal[t]).size == 1 or np.unique(outcome[t]).size == 1:
            assert value is None
            continue
        expected = float(stats.spearmanr(signal[t], outcome[t]).statistic)
        assert value == pytest.approx(expected, rel=1e-9, abs=1e-12)


@given(_PAIR, st.sampled_from([2, 3, 5]))
@settings(max_examples=40, deadline=None)
def test_quantile_monotonicity_matches_scipy_on_bucket_means(
    pair: tuple[np.ndarray, np.ndarray], quantiles: int
) -> None:
    signal, outcome = pair
    report = quantile_returns(signal, outcome, quantiles=quantiles)
    means = np.asarray(report.mean_by_quantile)
    if np.unique(means).size == 1:
        assert report.monotonicity is None
        return
    expected = float(stats.spearmanr(np.arange(quantiles), means).statistic)
    assert report.monotonicity == pytest.approx(expected, rel=1e-9, abs=1e-12)


@given(st.integers(min_value=0, max_value=500))
@settings(max_examples=40, deadline=None)
def test_fama_macbeth_slopes_match_independently_transcribed_lstsq(seed: int) -> None:
    rng = np.random.default_rng(seed)
    f1 = rng.standard_normal((4, 9))
    f2 = rng.standard_normal((4, 9))
    outcome = 0.3 * f1 - 0.1 * f2 + rng.standard_normal((4, 9))
    result = fama_macbeth([f1, f2], outcome)
    per_date = []
    for t in range(4):
        design = np.column_stack([np.ones(9), f1[t], f2[t]])
        beta = np.linalg.lstsq(design, outcome[t], rcond=None)[0]
        per_date.append(beta[1:])
    expected = np.mean(per_date, axis=0)
    assert result.mean_slopes == pytest.approx(list(expected), rel=1e-9, abs=1e-12)
    std = np.std(per_date, axis=0, ddof=1)
    for k in range(2):
        assert result.t_stats[k] == pytest.approx(expected[k] / std[k] * 2.0, rel=1e-9)

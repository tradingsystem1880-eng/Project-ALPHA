"""Differential and known-truth oracles for retracement-ratio densities.

Module under test: ``alpha_research.retracements``.

Primary sources: Silverman, *Density Estimation for Statistics and Data Analysis* (1986) §2.4
for the Gaussian kernel estimator f̂(x) = (1/(n h)) Σ φ((x − xᵢ)/h); Scott, *Multivariate Density
Estimation* (1992) for the bandwidth-as-multiple-of-the-sample-standard-deviation convention that
``scipy.stats.gaussian_kde`` implements for a scalar ``bw_method`` (h = factor · s, s with
ddof=1). A wrong kernel normalisation, a population instead of sample standard deviation, or a
density evaluated on ratios rather than log ratios breaks the relations below.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from alpha_core import DataError
from alpha_research.retracements import retracement_density, retracement_ratios
from tests.oracles._reference.tolerances import FLOAT64_REL

pytestmark = pytest.mark.oracle


def _explicit_kde(samples: np.ndarray, grid: np.ndarray, factor: float) -> np.ndarray:
    h = factor * float(np.std(samples, ddof=1))
    z = (grid[:, None] - samples[None, :]) / h
    return np.asarray(np.exp(-0.5 * z**2).sum(axis=1) / (samples.size * h * math.sqrt(2 * math.pi)))


def test_density_matches_the_explicit_gaussian_sum_on_log_ratios() -> None:
    rng = np.random.default_rng(5)
    ratios = np.exp(rng.normal(-0.3, 0.4, size=200))
    result = retracement_density(ratios, bandwidth=0.2, log_grid=(-2.0, 2.0, 0.01))
    expected = _explicit_kde(np.log(ratios), result.log_ratio_grid, 0.2)
    np.testing.assert_allclose(result.density, expected, rtol=FLOAT64_REL)
    np.testing.assert_allclose(result.ratio_grid, np.exp(result.log_ratio_grid), rtol=FLOAT64_REL)
    # the density integrates to ~1 over a grid that covers the mass
    mass = float(np.trapezoid(result.density, result.log_ratio_grid))
    assert mass == pytest.approx(1.0, abs=1e-3)


def test_planted_golden_ratio_is_the_dominant_peak() -> None:
    rng = np.random.default_rng(8)
    ratios = np.concatenate(
        [np.exp(np.log(0.618) + rng.normal(0.0, 0.01, size=300)), np.exp(rng.normal(0.5, 0.6, 150))]
    )
    result = retracement_density(ratios, bandwidth=0.05)
    assert result.peak_ratios.size >= 1
    assert result.peak_ratios[0] == pytest.approx(0.618, abs=0.01)


def test_ratios_are_segment_height_quotients_and_scale_invariant() -> None:
    prices = np.array([100.0, 110.0, 103.82, 113.82, 107.64])
    ratios = retracement_ratios(prices)
    heights = np.abs(np.diff(prices))
    np.testing.assert_allclose(ratios, heights[1:] / heights[:-1], rtol=FLOAT64_REL)
    np.testing.assert_allclose(retracement_ratios(prices * 3.0 + 50.0), ratios, rtol=FLOAT64_REL)
    with pytest.raises(DataError):
        retracement_ratios(np.array([1.0, 2.0, 2.0, 3.0]))  # a zero-height segment

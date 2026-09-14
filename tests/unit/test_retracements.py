"""Unit tests for retracement-ratio densities (alpha_research.retracements)."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_research.retracements import (
    RetracementDensity,
    retracement_density,
    retracement_ratios,
)


def test_ratios_need_three_finite_extremes_and_non_zero_segments() -> None:
    assert retracement_ratios([1.0, 3.0, 2.0]).tolist() == [0.5]
    assert retracement_ratios([1, 3, 2, 4]).tolist() == [0.5, 2.0]
    with pytest.raises(DataError, match=r"^retracement ratios need at least three extremes$"):
        retracement_ratios([1.0, 2.0])
    with pytest.raises(DataError, match=r"^extreme prices must be a finite one-dimensional array$"):
        retracement_ratios([[1.0, 2.0], [3.0, 4.0]])
    with pytest.raises(DataError, match=r"^extreme prices must be a finite one-dimensional array$"):
        retracement_ratios([1.0, np.nan, 2.0])
    with pytest.raises(DataError, match=r"^segment 0 has zero height; ratios are undefined$"):
        retracement_ratios([1.0, 1.0, 2.0])


def test_density_grid_and_peaks_are_well_formed() -> None:
    rng = np.random.default_rng(1)
    ratios = np.exp(rng.normal(0.0, 0.5, size=100))
    result = retracement_density(ratios, bandwidth=0.3, log_grid=(-1.0, 1.0, 0.5))
    assert isinstance(result, RetracementDensity)
    assert result.log_ratio_grid.tolist() == [-1.0, -0.5, 0.0, 0.5]  # half-open, like arange
    assert result.density.shape == (4,) and np.all(result.density >= 0.0)
    assert result.peak_ratios.ndim == 1
    # default grid is (-3, 3) in 0.001 steps, upstream's arange
    default = retracement_density(ratios, bandwidth=0.3)
    assert default.log_ratio_grid.size == 6000
    assert default.log_ratio_grid[0] == -3.0 and default.log_ratio_grid[-1] == pytest.approx(2.999)


def test_peaks_are_ordered_by_density_and_filtered_by_prominence() -> None:
    rng = np.random.default_rng(2)
    ratios = np.concatenate(
        [
            np.exp(np.log(0.5) + rng.normal(0.0, 0.02, size=200)),
            np.exp(np.log(2.0) + rng.normal(0.0, 0.02, size=80)),
        ]
    )
    result = retracement_density(ratios, bandwidth=0.05)
    assert result.peak_ratios.size == 2
    assert result.peak_ratios[0] == pytest.approx(0.5, abs=0.02)
    assert result.peak_ratios[1] == pytest.approx(2.0, abs=0.05)
    strict = retracement_density(ratios, bandwidth=0.05, min_prominence=0.9)
    assert strict.peak_ratios.size == 1 and strict.peak_ratios[0] == pytest.approx(0.5, abs=0.02)


def test_density_rejects_degenerate_inputs() -> None:
    with pytest.raises(DataError, match=r"^retracement density needs at least two ratios$"):
        retracement_density([0.5])
    with pytest.raises(DataError, match=r"^retracement ratios must be finite and positive$"):
        retracement_density([0.5, -1.0])
    with pytest.raises(DataError, match=r"^retracement ratios must be finite and positive$"):
        retracement_density([0.5, np.inf])
    with pytest.raises(DataError, match=r"^retracement ratios are all identical; no density$"):
        retracement_density([0.5, 0.5, 0.5])
    with pytest.raises(DataError, match=r"^bandwidth must be positive, got 0.0$"):
        retracement_density([0.5, 0.7], bandwidth=0.0)
    with pytest.raises(DataError, match=r"^log_grid must satisfy start < stop with a positive"):
        retracement_density([0.5, 0.7], log_grid=(1.0, 0.0, 0.1))
    with pytest.raises(DataError, match=r"^min_prominence must be in \(0, 1\], got 0.0$"):
        retracement_density([0.5, 0.7], min_prominence=0.0)


def test_density_parameter_edges_and_default_bandwidth() -> None:
    rng = np.random.default_rng(3)
    ratios = np.exp(rng.normal(0.0, 0.5, size=60))
    with pytest.raises(DataError, match=r"^retracement ratios must be finite and positive$"):
        retracement_density(np.append(ratios, 0.0))  # zero is not positive
    with pytest.raises(DataError, match=r"^log_grid must satisfy start < stop with a positive"):
        retracement_density(ratios, log_grid=(1.0, 1.0, 0.1))  # start == stop
    with pytest.raises(DataError, match=r"^log_grid must satisfy start < stop with a positive"):
        retracement_density(ratios, log_grid=(0.0, 1.0, 0.0))  # zero step
    with pytest.raises(DataError, match=r"^min_prominence must be in \(0, 1\], got 1.5$"):
        retracement_density(ratios, min_prominence=1.5)
    full = retracement_density(ratios, bandwidth=0.3, min_prominence=1.0)  # 1.0 is allowed
    assert isinstance(full, RetracementDensity)
    default = retracement_density(ratios)
    explicit = retracement_density(ratios, bandwidth=0.01)
    np.testing.assert_array_equal(default.density, explicit.density)


def test_density_fails_loud_when_the_grid_misses_the_sample_or_parameters_are_nan() -> None:
    ratios = np.array([0.5, 0.7, 0.9])
    with pytest.raises(DataError, match=r"^log_grid does not cover the retracement ratios"):
        retracement_density(ratios, log_grid=(2.0, 3.0, 0.1))
    with pytest.raises(DataError, match=r"^bandwidth must be positive, got nan$"):
        retracement_density(ratios, bandwidth=float("nan"))
    with pytest.raises(DataError, match=r"^log_grid must satisfy start < stop with a positive"):
        retracement_density(ratios, log_grid=(0.0, float("inf"), 0.1))
    with pytest.raises(DataError, match=r"^log_grid must satisfy start < stop with a positive"):
        retracement_density(ratios, log_grid=(0.0, 1.0, float("nan")))

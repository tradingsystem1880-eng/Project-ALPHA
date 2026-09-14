"""Unit tests for rolling PCA scores (alpha_research.rolling_pca)."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_research.rolling_pca import PCAResult, pca_components, pca_scores, rolling_pca_scores


def _factor_matrix(n: int = 200, dim: int = 6, seed: int = 4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    factor = rng.normal(size=(n, 1))
    loadings = np.linspace(1.0, 2.0, dim)[None, :]
    return factor * loadings + rng.normal(0.0, 0.05, size=(n, dim)) + 10.0


def test_components_are_orthonormal_sorted_and_sign_fixed() -> None:
    matrix = _factor_matrix()
    result = pca_components(matrix, n_components=3)
    assert isinstance(result, PCAResult)
    assert result.components.shape == (3, 6)
    np.testing.assert_allclose(result.components @ result.components.T, np.eye(3), atol=1e-12)
    assert np.all(np.diff(result.explained_variance) <= 0.0)
    assert result.explained_ratio[0] > 0.99
    assert np.all(result.explained_ratio > 0.0) and result.explained_ratio.sum() <= 1.0 + 1e-12
    for component in result.components:
        assert component[np.argmax(np.abs(component))] > 0.0
    np.testing.assert_allclose(result.mean, matrix.mean(axis=0), rtol=1e-12)


def test_scores_project_centred_rows_onto_components() -> None:
    matrix = _factor_matrix()
    result = pca_components(matrix, n_components=2)
    scores = pca_scores(matrix, result)
    np.testing.assert_allclose(scores, (matrix - result.mean) @ result.components.T, rtol=1e-12)
    np.testing.assert_allclose(scores.mean(axis=0), 0.0, atol=1e-10)
    with pytest.raises(DataError, match=r"^rows have 5 columns but the PCA was fitted on 6$"):
        pca_scores(matrix[:, :5], result)


def test_rolling_scores_are_trailing_and_nan_in_warm_up() -> None:
    matrix = _factor_matrix(n=60)
    scores = rolling_pca_scores(matrix, window=20, n_components=2)
    assert scores.shape == (60, 2)
    assert np.all(np.isnan(scores[:19]))
    assert np.all(np.isfinite(scores[19:]))
    for i in (19, 33, 59):
        fitted = pca_components(matrix[i - 19 : i + 1], n_components=2)
        np.testing.assert_allclose(scores[i], pca_scores(matrix[i : i + 1], fitted)[0], rtol=1e-12)


def test_rolling_scores_skip_windows_holding_non_finite_rows() -> None:
    matrix = _factor_matrix(n=40)
    matrix[:5] = np.nan  # an RSI-style warm-up
    matrix[25, 2] = np.nan
    scores = rolling_pca_scores(matrix, window=10, n_components=1)
    assert np.all(np.isnan(scores[:14]))
    assert np.all(np.isfinite(scores[14:25]))
    assert np.all(np.isnan(scores[25:35]))
    assert np.all(np.isfinite(scores[35:]))


def test_rejects_degenerate_shapes_and_flat_windows() -> None:
    matrix = _factor_matrix(n=30)
    with pytest.raises(DataError, match=r"^PCA rows must be a two-dimensional array$"):
        pca_components(matrix[0], n_components=1)
    with pytest.raises(DataError, match=r"^PCA rows must be finite$"):
        pca_components(np.full((5, 3), np.nan), n_components=1)
    with pytest.raises(DataError, match=r"^n_components must be in \[1, 6\], got 7$"):
        pca_components(matrix, n_components=7)
    with pytest.raises(DataError, match=r"^n_components must be in \[1, 6\], got 0$"):
        pca_components(matrix, n_components=0)
    with pytest.raises(DataError, match=r"^PCA needs at least two rows$"):
        pca_components(matrix[:1], n_components=1)
    with pytest.raises(DataError, match=r"^PCA rows have zero total variance$"):
        pca_components(np.ones((5, 3)), n_components=1)
    with pytest.raises(DataError, match=r"^window must be in \[2, 30\], got 31$"):
        rolling_pca_scores(matrix, window=31, n_components=1)
    with pytest.raises(DataError, match=r"^window must be in \[2, 30\], got 1$"):
        rolling_pca_scores(matrix, window=1, n_components=1)
    with pytest.raises(DataError, match=r"^n_components must be in \[1, 6\], got 7$"):
        rolling_pca_scores(matrix, window=10, n_components=7)
    with pytest.raises(DataError, match=r"^rolling PCA rows must be a two-dimensional array$"):
        rolling_pca_scores(matrix[0], window=10, n_components=1)
    flat = np.ones((30, 3))
    flat[:15] += np.random.default_rng(0).normal(size=(15, 3))
    with pytest.raises(DataError, match=r"^PCA rows have zero total variance$"):
        rolling_pca_scores(flat, window=10, n_components=1)


def test_smallest_valid_sizes_are_accepted() -> None:
    two_rows = np.array([[1.0, 2.0, 0.5], [3.0, 1.0, 0.5]])
    result = pca_components(two_rows, n_components=1)
    assert result.explained_ratio[0] == pytest.approx(1.0)
    rows = _factor_matrix(n=12, dim=3)
    scores = rolling_pca_scores(rows, window=2, n_components=1)
    assert np.isnan(scores[0, 0]) and np.all(np.isfinite(scores[1:]))
    for i in (1, 5, 11):
        fitted = pca_components(rows[i - 1 : i + 1], n_components=1)
        assert scores[i, 0] == pytest.approx(pca_scores(rows[i : i + 1], fitted)[0, 0])


def test_score_shape_errors_report_the_offending_width() -> None:
    result = pca_components(_factor_matrix(n=20, dim=4), n_components=2)
    with pytest.raises(DataError, match=r"^rows have 4 columns but the PCA was fitted on 4$"):
        pca_scores(np.arange(4.0), result)  # one-dimensional input is still rejected
    with pytest.raises(DataError, match=r"^rows have 0 columns but the PCA was fitted on 4$"):
        pca_scores(np.float64(1.0), result)
    with pytest.raises(DataError, match=r"^rows have 5 columns but the PCA was fitted on 4$"):
        pca_scores(np.zeros((2, 3, 5)), result)
    with pytest.raises(DataError, match=r"^rows have 3 columns but the PCA was fitted on 4$"):
        pca_scores(np.zeros((2, 3)), result)


def test_sign_convention_flips_components_whose_largest_loading_is_negative() -> None:
    rng = np.random.default_rng(1)
    rows = rng.normal(size=(30, 4)) @ rng.normal(size=(4, 4))
    covariance = np.cov(rows, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    raw = eigenvectors[:, np.argsort(eigenvalues)[::-1]].T
    needs_flip = [c[np.argmax(np.abs(c))] < 0.0 for c in raw]
    assert any(needs_flip)  # the fixture exercises the flip branch
    result = pca_components(rows, n_components=4)
    for component, reference, flipped in zip(result.components, raw, needs_flip, strict=True):
        assert component[np.argmax(np.abs(component))] > 0.0
        np.testing.assert_allclose(component, -reference if flipped else reference, rtol=1e-12)

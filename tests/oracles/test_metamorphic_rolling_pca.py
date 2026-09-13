"""Metamorphic and differential oracles for rolling PCA scores (alpha_research.rolling_pca).

Primary source: Jolliffe, *Principal Component Analysis* (2nd ed., 2002), ch. 1 (principal
components are the eigenvectors of the covariance matrix ordered by eigenvalue; the eigenvalues
are the component variances) and §3.5 (the SVD of the centred data matrix yields the same
components, which the differential below exploits). Rotation invariance of the eigenvalues and
translation invariance of the scores follow from the covariance definition. A covariance taken
with the wrong ``rowvar``, an ascending eigenvalue order, or a projection onto eigenvector rows
instead of columns (the upstream script's bug) breaks a relation below.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_research.rolling_pca import pca_components, pca_scores, rolling_pca_scores
from tests.oracles._reference.tolerances import FLOAT64_REL

pytestmark = pytest.mark.oracle


def _correlated(n: int, dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    mixing = rng.normal(size=(dim, dim))
    return rng.normal(size=(n, dim)) @ mixing + rng.normal(size=dim) * 5.0


def test_components_and_variances_match_the_svd_reference() -> None:
    rows = _correlated(120, 5, 1)
    result = pca_components(rows, n_components=5)
    centred = rows - rows.mean(axis=0)
    _, singular, vt = np.linalg.svd(centred, full_matrices=False)
    variances = singular**2 / (rows.shape[0] - 1)
    np.testing.assert_allclose(result.explained_variance, variances, rtol=FLOAT64_REL)
    np.testing.assert_allclose(result.explained_ratio, variances / variances.sum(), rtol=1e-9)
    for component, reference in zip(result.components, vt, strict=True):
        # equal up to sign; the port fixes the sign by the largest loading
        assert np.allclose(component, reference, rtol=1e-8, atol=1e-10) or np.allclose(
            component, -reference, rtol=1e-8, atol=1e-10
        )
        assert component[np.argmax(np.abs(component))] > 0.0


def test_planted_single_factor_is_recovered() -> None:
    rng = np.random.default_rng(2)
    loadings = np.array([0.2, -0.5, 0.8, 0.1])
    factor = rng.normal(size=(300, 1))
    rows = factor * loadings[None, :] + rng.normal(0.0, 0.01, size=(300, 4))
    result = pca_components(rows, n_components=1)
    unit = loadings / np.linalg.norm(loadings)
    np.testing.assert_allclose(np.abs(result.components[0]), np.abs(unit), atol=0.01)
    assert result.explained_ratio[0] > 0.99
    scores = pca_scores(rows, result)[:, 0]
    assert abs(np.corrcoef(scores, factor[:, 0])[0, 1]) > 0.999


def test_variances_are_rotation_invariant_and_scores_translation_invariant() -> None:
    rows = _correlated(150, 4, 3)
    base = pca_components(rows, n_components=4)
    q, _ = np.linalg.qr(np.random.default_rng(9).normal(size=(4, 4)))
    rotated = pca_components(rows @ q, n_components=4)
    np.testing.assert_allclose(rotated.explained_variance, base.explained_variance, rtol=1e-9)
    shifted = pca_components(rows + 1000.0, n_components=2)
    np.testing.assert_allclose(
        pca_scores(rows + 1000.0, shifted),
        pca_scores(rows, pca_components(rows, n_components=2)),
        rtol=1e-6,
        atol=1e-8,
    )


def test_rolling_scores_with_a_full_window_equal_the_full_sample_projection() -> None:
    rows = _correlated(40, 3, 4)
    rolled = rolling_pca_scores(rows, window=40, n_components=2)
    assert np.all(np.isnan(rolled[:39]))
    full = pca_scores(rows, pca_components(rows, n_components=2))
    np.testing.assert_allclose(rolled[39], full[39], rtol=FLOAT64_REL)


def test_projecting_onto_eigenvector_rows_is_not_the_principal_score() -> None:
    """The upstream script used evecs[j] (a row) where evecs[:, j] (a column) is the component."""
    rows = _correlated(100, 4, 5)
    centred = rows - rows.mean(axis=0)
    evals, evecs = np.linalg.eigh(np.cov(rows, rowvar=False))
    order = np.argsort(evals)[::-1]
    evecs = evecs[:, order]
    correct = centred @ evecs[:, 0]
    wrong = centred @ evecs[0]
    scores = pca_scores(rows, pca_components(rows, n_components=1))[:, 0]
    assert np.allclose(np.abs(scores), np.abs(correct), rtol=1e-9)
    assert not np.allclose(np.abs(scores), np.abs(wrong), rtol=1e-3)
    assert pytest.approx(float(np.var(correct, ddof=1)), rel=1e-9) == float(evals[order][0])

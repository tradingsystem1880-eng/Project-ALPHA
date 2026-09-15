"""Future-poison guard for rolling PCA scores (alpha_research.rolling_pca)."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_research.rolling_pca import pca_components, pca_scores, rolling_pca_scores

pytestmark = pytest.mark.bias_guard

CUT = 150


def _rows() -> np.ndarray:
    rng = np.random.default_rng(6)
    factor = rng.normal(size=(300, 1))
    return factor * np.linspace(0.5, 1.5, 5)[None, :] + rng.normal(0.0, 0.1, size=(300, 5))


def _poison(rows: np.ndarray) -> np.ndarray:
    poisoned = rows.copy()
    tail = poisoned[CUT + 1 :].shape
    poisoned[CUT + 1 :] = np.random.default_rng(77).normal(50.0, 20.0, size=tail)
    return poisoned


def test_poisoning_rows_after_cut_leaves_scores_up_to_cut_unchanged() -> None:
    rows = _rows()
    base = rolling_pca_scores(rows, window=40, n_components=2)
    again = rolling_pca_scores(_poison(rows), window=40, n_components=2)
    assert np.array_equal(base[: CUT + 1], again[: CUT + 1], equal_nan=True)
    assert not np.array_equal(base[CUT + 1 :], again[CUT + 1 :], equal_nan=True)


def test_leaky_twin_full_sample_fit_is_caught() -> None:
    """Fitting the components on the whole sample moves the pre-cut scores."""
    rows = _rows()
    honest = pca_scores(rows, pca_components(rows, n_components=2))
    leaked = pca_scores(_poison(rows), pca_components(_poison(rows), n_components=2))
    assert not np.allclose(honest[: CUT + 1], leaked[: CUT + 1])

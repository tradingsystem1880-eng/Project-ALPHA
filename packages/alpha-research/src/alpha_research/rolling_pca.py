"""Principal components of a feature block, fitted on a trailing window only.

Provenance: github.com/neurotrader888/RSI-PCA/pca.py @ f3b9735 (MIT). Adapted: the feature
block (e.g. ``alpha_patterns.indicators.rsi_matrix``) arrives as an array; components come from
the eigendecomposition of the sample covariance (Jolliffe 2002 ch. 1), ordered by descending
eigenvalue with each component's sign fixed so its largest-magnitude loading is positive; scores
are projections onto eigenvector *columns* (upstream projected onto rows, a bug); and the rolling
variant refits on ``[i - window + 1, i]`` before scoring row ``i`` instead of fitting once on the
full sample, so a score never depends on later rows.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from alpha_core import DataError

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class PCAResult:
    mean: FloatArray  # shape (dim,)
    components: FloatArray  # shape (n_components, dim), orthonormal rows
    explained_variance: FloatArray  # eigenvalues, descending
    explained_ratio: FloatArray  # eigenvalues / total variance


def _check_components(n_components: int, dim: int) -> None:
    if n_components < 1 or n_components > dim:
        raise DataError(f"n_components must be in [1, {dim}], got {n_components}")


def pca_components(rows: npt.ArrayLike, *, n_components: int) -> PCAResult:
    """Top ``n_components`` principal components of the sample covariance of ``rows``."""
    matrix = np.asarray(rows, dtype=np.float64)
    if matrix.ndim != 2:
        raise DataError("PCA rows must be a two-dimensional array")
    if not np.all(np.isfinite(matrix)):
        raise DataError("PCA rows must be finite")
    _check_components(n_components, matrix.shape[1])
    if matrix.shape[0] < 2:
        raise DataError("PCA needs at least two rows")
    mean = matrix.mean(axis=0)
    covariance = np.cov(matrix, rowvar=False, ddof=1).reshape(matrix.shape[1], matrix.shape[1])
    total = float(np.trace(covariance))
    if total <= 0.0:
        raise DataError("PCA rows have zero total variance")
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1][:n_components]
    components = np.ascontiguousarray(eigenvectors[:, order].T)
    for component in components:
        if component[np.argmax(np.abs(component))] < 0.0:
            component *= -1.0
    variances = np.maximum(eigenvalues[order], 0.0)
    return PCAResult(
        mean=mean,
        components=components,
        explained_variance=variances,
        explained_ratio=variances / total,
    )


def pca_scores(rows: npt.ArrayLike, result: PCAResult) -> FloatArray:
    """Project centred ``rows`` onto ``result.components``; shape ``(n, n_components)``."""
    matrix = np.asarray(rows, dtype=np.float64)
    dim = result.components.shape[1]
    if matrix.ndim != 2 or matrix.shape[1] != dim:
        width = matrix.shape[-1] if matrix.ndim else 0
        raise DataError(f"rows have {width} columns but the PCA was fitted on {dim}")
    return np.asarray((matrix - result.mean) @ result.components.T, dtype=np.float64)


def rolling_pca_scores(rows: npt.ArrayLike, *, window: int, n_components: int) -> FloatArray:
    """Score of row ``i`` on components fitted to rows ``[i - window + 1, i]`` only.

    Warm-up rows and any row whose trailing window contains a non-finite value (an indicator
    warm-up, for instance) are NaN. A window with zero total variance fails loud.
    """
    matrix = np.asarray(rows, dtype=np.float64)
    if matrix.ndim != 2:
        raise DataError("rolling PCA rows must be a two-dimensional array")
    n, dim = matrix.shape
    _check_components(n_components, dim)
    if window < 2 or window > n:
        raise DataError(f"window must be in [2, {n}], got {window}")
    scores = np.full((n, n_components), np.nan, dtype=np.float64)
    finite_row = np.all(np.isfinite(matrix), axis=1)
    for i in range(window - 1, n):
        if not np.all(finite_row[i - window + 1 : i + 1]):
            continue
        block = matrix[i - window + 1 : i + 1]
        scores[i] = pca_scores(block[-1:], pca_components(block, n_components=n_components))[0]
    return scores


__all__ = ["PCAResult", "pca_components", "pca_scores", "rolling_pca_scores"]

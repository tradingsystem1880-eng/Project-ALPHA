"""Pure multi-asset portfolio-optimization primitives (fail-loud, deterministic).

Thin wrappers over ``skfolio`` that take a plain ``(n_obs, n_assets)`` simple-returns matrix and
return a long-only, fully-invested weight vector (sums to 1). Both methods are deterministic —
mean-variance is a convex program; hierarchical risk parity uses no RNG — so they fit the platform's
determinism rule. They consume only numpy + ``alpha_core`` types, keeping this package on
``alpha_core`` alone in the architecture DAG (the CLI is the sole composition seam).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from skfolio import RiskMeasure
from skfolio.optimization import HierarchicalRiskParity, MeanRisk, ObjectiveFunction

from alpha_core import DataError

FloatArray = npt.NDArray[np.float64]
ReturnsMatrix = npt.NDArray[np.float64]  # shape (n_obs, n_assets)

_SUM_TOL = 1e-6


def _as_returns_matrix(returns: npt.ArrayLike, name: str) -> ReturnsMatrix:
    arr = np.asarray(returns, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[0] < 2 or arr.shape[1] < 2:
        raise DataError(
            f"{name} needs a 2D (>=2 observations, >=2 assets) returns matrix, got {arr.shape}"
        )
    if not bool(np.all(np.isfinite(arr))):
        raise DataError(f"{name} requires finite returns")
    return arr


def _validated_weights(raw: npt.ArrayLike, name: str, n_assets: int) -> FloatArray:
    weights = np.asarray(raw, dtype=np.float64)
    if weights.shape != (n_assets,):
        raise DataError(f"{name} produced {weights.shape} weights, expected ({n_assets},)")
    if not bool(np.all(np.isfinite(weights))):
        raise DataError(f"{name} produced non-finite weights")
    if abs(float(weights.sum()) - 1.0) > _SUM_TOL:
        raise DataError(f"{name} weights must sum to 1, got {float(weights.sum())!r}")
    return weights


def min_variance_weights(returns: npt.ArrayLike) -> FloatArray:
    """Long-only minimum-variance weights from an ``(n_obs, n_assets)`` simple-returns matrix."""
    arr = _as_returns_matrix(returns, "min_variance_weights")
    model = MeanRisk(
        objective_function=ObjectiveFunction.MINIMIZE_RISK, risk_measure=RiskMeasure.VARIANCE
    )
    model.fit(arr)
    return _validated_weights(model.weights_, "min_variance_weights", arr.shape[1])


def hierarchical_risk_parity_weights(returns: npt.ArrayLike) -> FloatArray:
    """Long-only Hierarchical Risk Parity (HRP) weights from an ``(n_obs, n_assets)`` matrix.

    HRP allocates by recursive bisection of a hierarchical clustering of the assets, avoiding the
    unstable covariance inversion of classical mean-variance (López de Prado, 2016).
    """
    arr = _as_returns_matrix(returns, "hierarchical_risk_parity_weights")
    model = HierarchicalRiskParity(risk_measure=RiskMeasure.VARIANCE)
    model.fit(arr)
    return _validated_weights(model.weights_, "hierarchical_risk_parity_weights", arr.shape[1])

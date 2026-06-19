"""Project ALPHA portfolio-optimization primitives.

Pure, fail-loud, deterministic multi-asset allocators (mean-variance, HRP) over numpy returns
matrices. Depends only on ``alpha_core`` (the architecture DAG); composed by ``alpha_cli``.
"""

from __future__ import annotations

from alpha_portfolio.optimize import (
    FloatArray,
    ReturnsMatrix,
    hierarchical_risk_parity_weights,
    min_variance_weights,
)

__version__ = "0.0.0"

__all__ = [
    "FloatArray",
    "ReturnsMatrix",
    "__version__",
    "hierarchical_risk_parity_weights",
    "min_variance_weights",
]

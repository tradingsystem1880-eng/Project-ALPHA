"""Per-step close quantiles across sampled forecast paths (numpy inside, floats out)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from alpha_core import DataError
from alpha_forecast.types import ForecastResult

DEFAULT_QS: tuple[float, ...] = (0.05, 0.25, 0.5, 0.75, 0.95)


def close_quantiles(
    result: ForecastResult, qs: Sequence[float] = DEFAULT_QS
) -> dict[float, tuple[float, ...]]:
    """Per-step quantiles of the sampled close paths: ``{q: (v_step1, ..., v_stepH)}``."""
    if not qs:
        raise DataError("no quantile levels requested")
    for q in qs:
        if not 0.0 < q < 1.0:
            raise DataError(f"quantile levels must be in (0, 1), got {q}")
    arr = np.array([p.close for p in result.samples], dtype=np.float64)  # (S, H)
    return {
        float(q): tuple(float(v) for v in np.quantile(arr, q, axis=0)) for q in qs
    }

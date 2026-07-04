"""Kronos foundation-model forecasting facade.

Layer-1 package (imports ``alpha_core`` only; only ``alpha_cli`` may import it). Wraps the
vendored Kronos K-line model behind a typed, seeded, fail-loud ``Forecaster`` protocol that
returns per-sample OHLCV paths. torch/pandas stay inside this package: torch imports are lazy
(``alpha_forecast.kronos``), and the pandas edge exists only at the Kronos API boundary —
the second sanctioned pandas exception alongside the tear-sheet renderer.
"""

from __future__ import annotations

from alpha_forecast.timestamps import future_session_ts
from alpha_forecast.types import Forecaster, ForecastResult, SampledPath

__version__ = "1.0.0"

__all__ = [
    "ForecastResult",
    "Forecaster",
    "SampledPath",
    "__version__",
    "future_session_ts",
]

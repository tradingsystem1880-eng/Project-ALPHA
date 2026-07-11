"""Foundation-model bar forecasting (vendored Kronos). Imports alpha_core only.

torch is NOT imported at package import time — only when a forecaster actually runs
inference (or a model is pulled). Install the torch stack with `uv sync --group kronos`.
"""

from __future__ import annotations

from alpha_forecast.download import pull_model
from alpha_forecast.forecaster import ForecastResult, KronosForecaster
from alpha_forecast.models import (
    KRONOS_TRAINING_CUTOFF,
    MODEL_SPECS,
    ModelSpec,
    future_timestamps,
    resolve_model,
    training_overlap_warning,
)

__version__ = "1.0.0"

__all__ = [
    "KRONOS_TRAINING_CUTOFF",
    "MODEL_SPECS",
    "ForecastResult",
    "KronosForecaster",
    "ModelSpec",
    "__version__",
    "future_timestamps",
    "pull_model",
    "resolve_model",
    "training_overlap_warning",
]

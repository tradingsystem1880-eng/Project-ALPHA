"""Governed research-study composition seam."""

from __future__ import annotations

from importlib.metadata import version

from alpha_study.tables import (
    EventRowV1,
    EventTableV1,
    FactorObservationTableV1,
    FactorObservationV1,
)
from alpha_study.values import FeatureInputRefV1, FeatureValueV1

__version__ = version("alpha-study")

__all__ = [
    "EventRowV1",
    "EventTableV1",
    "FactorObservationTableV1",
    "FactorObservationV1",
    "FeatureInputRefV1",
    "FeatureValueV1",
    "__version__",
]

"""Project ALPHA core domain package."""

from __future__ import annotations

from importlib.metadata import version

from alpha_core.corporate import ActionType, CorporateAction
from alpha_core.errors import AlphaError, DataError, LookAheadError
from alpha_core.protocols import ExecutionEventSink
from alpha_core.types import (
    Bar,
    ChartAnchor,
    ChartAnnotationTrace,
    DecisionTrace,
    IndicatorTrace,
    ValidationOutcome,
)
from alpha_core.universe import UniverseMembership, members_as_of

__version__ = version("alpha-core")

__all__ = [
    "ActionType",
    "AlphaError",
    "Bar",
    "ChartAnchor",
    "ChartAnnotationTrace",
    "CorporateAction",
    "UniverseMembership",
    "members_as_of",
    "DataError",
    "DecisionTrace",
    "IndicatorTrace",
    "ExecutionEventSink",
    "LookAheadError",
    "ValidationOutcome",
    "__version__",
]

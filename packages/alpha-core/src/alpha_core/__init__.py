"""Project ALPHA core domain package."""

from __future__ import annotations

from importlib.metadata import version

from alpha_core.corporate import ActionType, CorporateAction
from alpha_core.errors import AlphaError, DataError, LookAheadError
from alpha_core.types import Bar, ValidationOutcome

__version__ = version("alpha-core")

__all__ = [
    "ActionType",
    "AlphaError",
    "Bar",
    "CorporateAction",
    "DataError",
    "LookAheadError",
    "ValidationOutcome",
    "__version__",
]

"""Project ALPHA core domain package."""
from __future__ import annotations

from alpha_core.errors import AlphaError, DataError, LookAheadError
from alpha_core.types import Bar, ValidationOutcome

__version__ = "0.0.0"

__all__ = ["AlphaError", "DataError", "LookAheadError", "Bar", "ValidationOutcome", "__version__"]

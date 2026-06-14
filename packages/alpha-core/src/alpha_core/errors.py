"""Typed error hierarchy. Never raise bare Exception; never swallow these silently."""
from __future__ import annotations


class AlphaError(Exception):
    """Base class for all Project ALPHA errors."""


class DataError(AlphaError):
    """Data ingestion, storage, or integrity failure."""


class LookAheadError(AlphaError):
    """Point-in-time access was violated — code attempted to read future data."""

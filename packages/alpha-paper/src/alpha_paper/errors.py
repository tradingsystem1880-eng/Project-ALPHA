"""Typed errors for the paper-trading subsystem."""

from __future__ import annotations

from alpha_core import AlphaError


class PaperError(AlphaError):
    """A paper-trading failure (session setup, artifact IO, live-feed/reconciliation faults)."""

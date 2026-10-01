"""Shared scalar cost conventions used by execution adapters."""

from __future__ import annotations

import math

from alpha_core.errors import DataError


def bps_rate(fee_bps: float) -> float:
    """Convert basis points to a rate using the canonical division-first convention."""
    if not math.isfinite(fee_bps) or fee_bps < 0.0:
        raise DataError(f"fee_bps must be finite and >= 0, got {fee_bps}")
    return fee_bps / 10_000.0

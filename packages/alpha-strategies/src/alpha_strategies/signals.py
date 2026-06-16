"""Time-series momentum signal (spec §7). Pure and look-ahead-safe by construction."""

from __future__ import annotations

import math
from collections.abc import Sequence

from alpha_core import DataError


def ts_momentum_signal(closes: Sequence[float], lookback: int, skip: int) -> int:
    """Sign of the trailing ``lookback``-bar return, skipping the most recent ``skip`` bars.

    Classic "12-1" momentum (``lookback≈252``, ``skip≈21``): compares the close ``skip`` bars ago
    to the close ``skip + lookback`` bars ago, returning ``+1`` (up), ``-1`` (down), or ``0``
    (flat). The most recent ``skip`` bars are deliberately excluded (short-term reversal) and never
    influence the signal. Returns ``0`` when there is insufficient history; fails loud
    (``DataError``) on bad parameters or non-positive/NaN reference prices.
    """
    if lookback < 1:
        raise DataError(f"lookback must be >= 1, got {lookback}")
    if skip < 0:
        raise DataError(f"skip must be >= 0, got {skip}")
    if len(closes) < skip + lookback + 1:
        return 0
    recent = closes[-1 - skip]
    past = closes[-1 - skip - lookback]
    for label, value in (("recent", recent), ("past", past)):
        if not math.isfinite(value) or value <= 0:
            raise DataError(
                f"ts_momentum_signal {label} reference price must be finite > 0, got {value!r}"
            )
    ret = recent / past - 1.0
    if ret > 0:
        return 1
    if ret < 0:
        return -1
    return 0

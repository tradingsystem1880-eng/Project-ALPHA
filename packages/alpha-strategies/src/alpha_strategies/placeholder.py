"""Phase-0 placeholder proving the alpha_strategies -> alpha_core dependency edge."""

from __future__ import annotations

from alpha_core.types import Bar


def signal_sign(prev_close: float, bar: Bar) -> int:
    """Trivial momentum stub: +1 if price rose, -1 if it fell, 0 if flat."""
    if bar.close > prev_close:
        return 1
    if bar.close < prev_close:
        return -1
    return 0

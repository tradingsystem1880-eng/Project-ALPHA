"""Phase-0 placeholder proving the alpha_data -> alpha_core dependency edge."""

from __future__ import annotations

from alpha_core.types import Bar


def describe(bar: Bar) -> str:
    return f"{bar.symbol}@{bar.ts.isoformat()} close={bar.close}"

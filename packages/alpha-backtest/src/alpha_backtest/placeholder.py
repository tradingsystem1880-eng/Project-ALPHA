"""Phase-0 placeholder proving the alpha_backtest -> {alpha_core, alpha_data} edges."""
from __future__ import annotations

from alpha_core.types import Bar
from alpha_data.placeholder import describe


def summarize(bar: Bar) -> str:
    return f"backtest sees: {describe(bar)}"

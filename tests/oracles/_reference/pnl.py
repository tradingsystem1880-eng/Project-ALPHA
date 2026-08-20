"""Independent equity-curve helpers shared by the P&L oracle tests.

``rederive_equity_curve`` rebuilds the equity curve from the canonical fill ledger alone,
with no engine state consulted; ``assert_curves_equal`` compares it to the engine's curve;
``scaled_bars`` produces a price-scaled copy of a bar series for scale-invariance checks.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from alpha_backtest.results import BacktestResult
from alpha_core import Bar
from tests.oracles._reference.tolerances import ENGINE_MONEY_ABS


def rederive_equity_curve(
    result: BacktestResult, bars: list[Bar], *, fee_bps: float, cash: float
) -> list[tuple[datetime, float]]:
    """Equity per session from the fill ledger alone (no engine state consulted)."""
    fills = sorted(result.fill_trace, key=lambda f: (f.ts, f.sequence_id))
    curve: list[tuple[datetime, float]] = []
    last = len(bars) - 1
    for i, bar in enumerate(bars):
        c, pos = cash, 0.0
        for f in fills:
            # a fill stamped at session t settles after the t snapshot — except the terminal one
            if f.ts < bar.ts or (i == last and f.ts <= bar.ts):
                sign = 1.0 if f.side == "BUY" else -1.0
                notional = f.quantity * f.price
                c -= sign * notional
                c -= notional * fee_bps / 10_000.0
                pos += sign * f.quantity
        curve.append((bar.ts, c + pos * bar.open))
    return curve


def assert_curves_equal(
    observed: list[tuple[datetime, float]],
    expected: list[tuple[datetime, float]],
    *,
    abs_tol: float = ENGINE_MONEY_ABS,
) -> None:
    assert [ts for ts, _ in observed] == [ts for ts, _ in expected]
    for (ts, o), (_, e) in zip(observed, expected, strict=True):
        assert o == pytest.approx(e, abs=abs_tol), f"equity mismatch at {ts}: engine {o} vs {e}"


def scaled_bars(bars: list[Bar], k: float) -> list[Bar]:
    return [
        b.model_copy(
            update={"open": b.open * k, "high": b.high * k, "low": b.low * k, "close": b.close * k}
        )
        for b in bars
    ]

"""Standard backtest result schema: the closed-trade log + the equity curve (spec §11).

This is the validatable output the Phase-3 validation gauntlet consumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Trade:
    """One closed round-trip position."""

    instrument_id: str
    side: str  # entry direction: "BUY" (long) or "SELL" (short)
    quantity: float
    entry_price: float
    exit_price: float
    entry_ts: datetime
    exit_ts: datetime
    realized_pnl: float
    realized_return: float


@dataclass(frozen=True)
class BacktestResult:
    """Outcome of a run: order/fill counts, the closed-trade log, and the equity curve.

    ``equity_curve`` is ``(timestamp, equity)`` sampled once per session (at each open), where
    ``equity = starting_cash + realized PnL + unrealized PnL`` — a net-of-fees, mark-to-market
    net-liquidation value, so an open position is valued each session rather than only on close.
    """

    orders: int
    fills: int
    trades: list[Trade]
    equity_curve: list[tuple[datetime, float]]

    @property
    def starting_equity(self) -> float:
        return self.equity_curve[0][1] if self.equity_curve else 0.0

    @property
    def final_equity(self) -> float:
        return self.equity_curve[-1][1] if self.equity_curve else 0.0

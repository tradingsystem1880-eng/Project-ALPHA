"""Engine-neutral run-result schema: the closed-trade log + the equity curve (spec §11).

Shared by the backtest harness (``alpha_backtest``) and paper trading (``alpha_paper``): both a
historical replay and a live sandbox session describe their outcome the same way — a closed-trade
log plus a per-session mark-to-market equity curve. This is also the validatable output the
validation gauntlet consumes. ``BacktestResult`` is kept as an alias of ``RunResult`` so existing
imports keep working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
class RunResult:
    """Outcome of a run: order/fill counts, the closed-trade log, and the equity curve.

    ``equity_curve`` is ``(timestamp, equity)`` sampled once per session (at each open), where
    ``equity = starting_cash + realized PnL + unrealized PnL`` — a net-of-fees, mark-to-market
    net-liquidation value, so an open position is valued each session rather than only on close.
    """

    orders: int
    fills: int
    trades: list[Trade]
    equity_curve: list[tuple[datetime, float]]
    # ts-ordered (side, quantity) of every order — the engine-neutral sequence paper must match
    order_log: list[tuple[str, float]] = field(default_factory=list)

    @property
    def starting_equity(self) -> float:
        return self.equity_curve[0][1] if self.equity_curve else 0.0

    @property
    def final_equity(self) -> float:
        return self.equity_curve[-1][1] if self.equity_curve else 0.0


# Backwards-compatible alias: the backtest harness and gauntlet historically named this
# ``BacktestResult``; the schema is engine-neutral, so paper trading reuses the same type.
BacktestResult = RunResult

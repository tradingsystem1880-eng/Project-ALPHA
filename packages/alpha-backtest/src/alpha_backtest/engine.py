"""Minimal nautilus ``BacktestEngine`` run harness for the v1 daily slice.

Configured ``bar_execution=False`` so bars drive strategy *decisions* only — fills come from the
open-priced quotes produced by ``feed.to_execution_feed``, giving the spec's "decide on close of t,
fill at open of t+1" convention. Returns a ``BacktestResult`` (counts + closed-trade log +
per-session mark-to-market equity curve).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.common.actor import Actor
from nautilus_trader.config import LoggingConfig
from nautilus_trader.core.data import Data
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide
from nautilus_trader.model.identifiers import InstrumentId, Venue
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Currency, Money
from nautilus_trader.trading.strategy import Strategy

from alpha_execution.frictions import BpsFeeModel
from alpha_execution.orders import order_signature
from alpha_execution.results import BacktestResult, Trade

_NS_PER_SECOND = 1_000_000_000


def _ns_to_dt(ns: int) -> datetime:
    return datetime.fromtimestamp(ns / _NS_PER_SECOND, tz=UTC)


def _sum_pnls(pnls: Any) -> float:
    """Sum a nautilus per-currency PnL dict to a float (single base currency in v1)."""
    return float(sum(money.as_double() for money in pnls.values()))


class _EquityRecorder(Actor):  # type: ignore[misc]  # nautilus Actor is untyped (Cython)
    """Snapshots net-liquidation equity once per session (on each open quote).

    ``equity = starting_cash + realized PnL + unrealized PnL`` — account-type-agnostic and net of
    commissions (nautilus realized PnL already nets fees), so an open position is marked to market
    each session rather than reporting realized cash only.
    """

    def __init__(self, instrument_id: InstrumentId, venue: Venue, starting_cash: float) -> None:
        super().__init__()
        self._iid = instrument_id
        self._venue = venue
        self._starting_cash = starting_cash
        self.curve: list[tuple[datetime, float]] = []

    def on_start(self) -> None:
        self.subscribe_quote_ticks(self._iid)

    def on_quote_tick(self, quote: QuoteTick) -> None:
        # Sampled after the portfolio has marked to this quote; a strategy order that fills on the
        # same quote is reflected here too (nautilus delivers the fill before this actor's handler).
        equity = (
            self._starting_cash
            + _sum_pnls(self.portfolio.realized_pnls(self._venue))
            + _sum_pnls(self.portfolio.unrealized_pnls(self._venue))
        )
        self.curve.append((_ns_to_dt(quote.ts_event), equity))


def _closed_trades(engine: BacktestEngine) -> list[Trade]:
    trades: list[Trade] = []
    for p in engine.cache.positions_closed():
        trades.append(
            Trade(
                instrument_id=str(p.instrument_id),
                side="BUY" if p.entry == OrderSide.BUY else "SELL",
                quantity=p.peak_qty.as_double(),
                entry_price=float(p.avg_px_open),
                exit_price=float(p.avg_px_close),
                entry_ts=_ns_to_dt(p.ts_opened),
                exit_ts=_ns_to_dt(p.ts_closed),
                realized_pnl=p.realized_pnl.as_double(),
                realized_return=float(p.realized_return),
            )
        )
    return trades


def run_backtest(
    instrument: Instrument,
    data: Sequence[Data],
    strategy: Strategy,
    *,
    starting_cash: float = 1_000_000.0,
    currency: Currency = USD,
    account_type: AccountType = AccountType.CASH,
    leverage: float = 1.0,
    fee_bps: float = 0.0,
) -> BacktestResult:
    """Run ``strategy`` over ``data`` for ``instrument``; return counts + trade log + equity curve.

    ``data`` should come from ``feed.to_execution_feed`` (open quotes + close-stamped decision
    bars). The venue uses a NETTING OMS with ``bar_execution=False`` so only the quotes fill orders
    — a market order decided on the close of t fills at the open of t+1. The account defaults to
    CASH (no shorting; equities are long-flat per spec §7); pass ``AccountType.MARGIN`` (where
    ``leverage`` applies) for the long-short crypto/FX path.
    """
    engine = BacktestEngine(
        config=BacktestEngineConfig(
            trader_id="BACKTESTER-001",
            logging=LoggingConfig(bypass_logging=True),
        )
    )
    engine.add_venue(
        venue=instrument.id.venue,
        oms_type=OmsType.NETTING,
        account_type=account_type,
        base_currency=currency,
        starting_balances=[Money(starting_cash, currency)],
        default_leverage=Decimal(str(leverage)),
        fee_model=BpsFeeModel(fee_bps) if fee_bps > 0 else None,
        bar_execution=False,  # bars decide; quotes fill (t+1 open) — see module docstring
    )
    recorder = _EquityRecorder(instrument.id, instrument.id.venue, starting_cash)
    engine.add_instrument(instrument)
    engine.add_data(list(data))
    engine.add_actor(recorder)
    engine.add_strategy(strategy)
    try:
        engine.run()
        orders = sorted(engine.cache.orders(), key=lambda o: o.ts_init)
        result = BacktestResult(
            orders=len(engine.trader.generate_orders_report()),
            fills=len(engine.trader.generate_order_fills_report()),
            trades=_closed_trades(engine),
            equity_curve=recorder.curve,
            order_log=[order_signature(o) for o in orders],
        )
    finally:
        engine.dispose()
    return result

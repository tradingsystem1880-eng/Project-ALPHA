"""Minimal nautilus ``BacktestEngine`` run harness for the v1 daily slice.

Configured ``bar_execution=False`` so bars drive strategy *decisions* only — fills come from the
open-priced quotes produced by ``feed.to_execution_feed``, giving the spec's "decide on close of t,
fill at open of t+1" convention. Returns a ``BacktestResult`` (counts + closed-trade log +
account-equity curve); frictions (fees/slippage) are a later increment.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.core.data import Data
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Currency, Money
from nautilus_trader.trading.strategy import Strategy

from alpha_backtest.results import BacktestResult, Trade

_NS_PER_SECOND = 1_000_000_000


def _ns_to_dt(ns: int) -> datetime:
    return datetime.fromtimestamp(ns / _NS_PER_SECOND, tz=UTC)


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


def _equity_curve(engine: BacktestEngine, venue: Venue) -> list[tuple[datetime, float]]:
    report = engine.trader.generate_account_report(venue)
    # account `total` at each state change; stable order preserves the initial balance first
    return [
        (ts.to_pydatetime(), float(total))
        for ts, total in zip(report.index, report["total"], strict=True)
    ]


def run_backtest(
    instrument: Instrument,
    data: Sequence[Data],
    strategy: Strategy,
    *,
    starting_cash: float = 1_000_000.0,
    currency: Currency = USD,
    account_type: AccountType = AccountType.CASH,
    leverage: float = 1.0,
) -> BacktestResult:
    """Run ``strategy`` over ``data`` for ``instrument``; return counts + trade log + equity curve.

    ``data`` should come from ``feed.to_execution_feed`` (open quotes + close-stamped decision
    bars). The venue uses a NETTING account and ``bar_execution=False`` so only the quotes fill
    orders — a market order decided on the close of t fills at the open of t+1. Defaults to a CASH
    account (no shorting; equities are long-flat per spec §7); pass ``AccountType.MARGIN`` for the
    long-short crypto/FX path.
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
        bar_execution=False,  # bars decide; quotes fill (t+1 open) — see module docstring
    )
    engine.add_instrument(instrument)
    engine.add_data(list(data))
    engine.add_strategy(strategy)
    try:
        engine.run()
        result = BacktestResult(
            orders=len(engine.trader.generate_orders_report()),
            fills=len(engine.trader.generate_order_fills_report()),
            trades=_closed_trades(engine),
            equity_curve=_equity_curve(engine, instrument.id.venue),
        )
    finally:
        engine.dispose()
    return result

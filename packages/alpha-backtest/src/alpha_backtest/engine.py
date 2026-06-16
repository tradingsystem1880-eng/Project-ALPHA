"""Minimal nautilus ``BacktestEngine`` run harness for the v1 daily slice.

Configured ``bar_execution=False`` so bars drive strategy *decisions* only — fills come from the
open-priced quotes produced by ``feed.to_execution_feed``, giving the spec's "decide on close of t,
fill at open of t+1" convention. The rich result schema (equity curve, trade log) is a later
increment; for now we surface order/fill counts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.core.data import Data
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Currency, Money
from nautilus_trader.trading.strategy import Strategy


@dataclass(frozen=True)
class BacktestResult:
    """Headline outcome of a run. Extended with the equity curve / trade log in a later phase."""

    orders: int
    fills: int


def run_backtest(
    instrument: Instrument,
    data: Sequence[Data],
    strategy: Strategy,
    *,
    starting_cash: float = 1_000_000.0,
    currency: Currency = USD,
) -> BacktestResult:
    """Run ``strategy`` over ``data`` for ``instrument`` and return order/fill counts.

    ``data`` should come from ``feed.to_execution_feed`` (open quotes + close-stamped decision
    bars). The venue uses a NETTING cash account and ``bar_execution=False`` so only the quotes
    fill orders — a market order decided on the close of t fills at the open of t+1.
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
        account_type=AccountType.CASH,
        base_currency=currency,
        starting_balances=[Money(starting_cash, currency)],
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
        )
    finally:
        engine.dispose()
    return result

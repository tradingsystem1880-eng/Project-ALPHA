"""Assemble a nautilus live ``TradingNode`` wired to the ``SandboxExecutionClient``.

The sandbox runs the *same* matching engine as the backtest, fed live market data — broker-free
paper trading at $0. Parity is preserved by ``bar_execution=False`` (only quotes fill, so a decision
on the close of ``t`` executes at the next live quote — the live analogue of the backtest's
open-of-``t+1`` fill).

The live data feed is injected as a factory + config so the same node serves both a real public-data
client and the offline ``FixtureLiveDataClient`` used in tests. Engines run with
``graceful_shutdown_on_exception=True`` so a fault surfaces as a logged shutdown, not nautilus's
default immediate ``os._exit``.

Known parity caveat: the sandbox client hard-codes ``MakerTakerFeeModel`` (it does not accept the
backtest's ``BpsFeeModel``), so paper commissions follow the instrument's maker/taker fees. This gap
is quantified in reconciliation (Phase 4e/4g), not silently ignored.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING

from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory
from nautilus_trader.config import LoggingConfig
from nautilus_trader.live.config import (
    LiveDataClientConfig,
    LiveDataEngineConfig,
    LiveExecEngineConfig,
    LiveRiskEngineConfig,
    TradingNodeConfig,
)
from nautilus_trader.live.factories import LiveDataClientFactory
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.enums import TradingState

from alpha_paper.config import PaperSpec

if TYPE_CHECKING:
    from nautilus_trader.model.instruments import Instrument


def build_paper_node(
    spec: PaperSpec,
    instrument: Instrument,
    *,
    data_client_name: str,
    data_client_factory: type[LiveDataClientFactory],
    data_client_config: LiveDataClientConfig,
    trader_id: str = "PAPER-001",
    log_level: str = "ERROR",
) -> TradingNode:
    """Build (but do not start) a ``TradingNode`` with a sandbox venue for ``instrument``.

    The sandbox venue is the instrument's own venue (so the instrument, its market data, and the
    matching engine all agree). The caller adds the strategy/actors via ``node.trader`` before
    running. ``starting_balances``/``base_currency`` are denominated in the instrument's quote
    currency (e.g. USDT for ``BTCUSDT``).
    """
    venue = str(instrument.id.venue)
    quote = instrument.quote_currency
    exec_config = SandboxExecutionClientConfig(
        venue=venue,
        starting_balances=[f"{spec.starting_cash} {quote}"],
        base_currency=str(quote),
        oms_type="NETTING",
        account_type=spec.account_type,
        default_leverage=Decimal(str(spec.max_leverage)),
        bar_execution=False,  # only quotes fill — preserves the backtest's t+1 execution convention
    )
    # Pre-trade RiskEngine: an optional per-order notional cap (runaway-order safety net), in whole
    # quote-currency units (nautilus types the cap as an int).
    max_notional = (
        {str(instrument.id): int(spec.max_notional_per_order)}
        if spec.max_notional_per_order is not None
        else {}
    )
    config = TradingNodeConfig(
        trader_id=trader_id,
        logging=LoggingConfig(log_level=log_level),
        data_engine=LiveDataEngineConfig(graceful_shutdown_on_exception=True),
        exec_engine=LiveExecEngineConfig(graceful_shutdown_on_exception=True),
        risk_engine=LiveRiskEngineConfig(
            graceful_shutdown_on_exception=True, max_notional_per_order=max_notional
        ),
        data_clients={data_client_name: data_client_config},
        exec_clients={venue: exec_config},
    )
    node = TradingNode(config=config)
    node.add_data_client_factory(data_client_name, data_client_factory)
    node.add_exec_client_factory(venue, SandboxLiveExecClientFactory)
    node.build()
    node.cache.add_instrument(instrument)
    return node


async def run_node_for(node: TradingNode, duration_seconds: float, *, dispose: bool = True) -> None:
    """Run ``node`` for ``duration_seconds`` then stop it cleanly.

    Used for bounded sessions and deterministic offline tests. A live, open-ended session uses the
    node's own blocking ``run()`` (which installs OS signal handlers). Pass ``dispose=False`` to
    inspect the node's cache after stopping (``dispose`` clears it); the caller then disposes.
    """
    task = asyncio.ensure_future(node.run_async())
    try:
        await asyncio.sleep(duration_seconds)
    finally:
        await node.stop_async()
        await asyncio.sleep(0.1)
        if not task.done():
            task.cancel()
        if dispose:
            node.dispose()


def halt_trading(node: TradingNode) -> None:
    """Kill-switch: set the RiskEngine HALTED so all new orders are denied (existing ones stand)."""
    node.kernel.risk_engine.set_trading_state(TradingState.HALTED)


def resume_trading(node: TradingNode) -> None:
    """Lift a halt: set the RiskEngine back to ACTIVE."""
    node.kernel.risk_engine.set_trading_state(TradingState.ACTIVE)

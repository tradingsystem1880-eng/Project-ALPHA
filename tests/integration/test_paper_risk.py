"""Phase 4g: pre-trade risk controls — a per-order notional cap and a kill-switch.

- The notional cap is verified by configuration: ``build_paper_node`` registers it on the RiskEngine
  (enforcement against cached market data is nautilus's own, separately tested, responsibility).
- The kill-switch is verified end-to-end: with trading HALTED the RiskEngine *denies* every order
  before it reaches the sandbox matcher, so a strategy that would otherwise trade gets zero fills.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from nautilus_trader.model.enums import OrderStatus

from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_core import Bar
from alpha_execution import equity_instrument
from alpha_paper.config import PaperSpec
from alpha_paper.node import build_paper_node, halt_trading, run_node_for
from alpha_strategies.ts_momentum import TimeSeriesMomentum
from tests.fixtures.paper_fixtures import (
    FixtureDataClientConfig,
    FixtureLiveDataClientFactory,
    register_fixture_events,
)


def _bars() -> list[Bar]:
    return [
        Bar(
            symbol="AAPL",
            ts=datetime(2026, 1, 1 + i, tzinfo=UTC),
            open=99.0 + 3.0 * i,
            high=104.0 + 3.0 * i,
            low=97.0 + 3.0 * i,
            close=100.0 + 3.0 * i,
            volume=1000.0,
        )
        for i in range(16)
    ]


def _strategy(instrument_id: object, bar_type: object) -> TimeSeriesMomentum:
    return TimeSeriesMomentum(
        instrument_id=instrument_id,
        bar_type=bar_type,
        lookback=5,
        skip=0,
        vol_window=3,
        rebalance_every=1,
        periods_per_year=365,
        capital=1_000_000.0,
    )


def _spec(**overrides: object) -> PaperSpec:
    base: dict[str, object] = {
        "symbol": "AAPL",
        "exchange": "sim",
        "venue": "SIM",
        "account_type": "MARGIN",
        "lookback": 5,
        "skip": 0,
        "vol_window": 3,
        "rebalance_every": 1,
        "periods_per_year": 365,
    }
    base.update(overrides)
    return PaperSpec(**base)  # type: ignore[arg-type]


def test_max_notional_cap_is_configured_on_the_risk_engine(
    paper_loop: asyncio.AbstractEventLoop,
) -> None:
    # paper_loop installs a current event loop that the TradingNode binds to at construction.
    instrument = equity_instrument("AAPL")
    register_fixture_events("risk-cap", [])
    node = build_paper_node(
        _spec(max_notional_per_order=250_000.0),
        instrument,
        data_client_name="FIXTURE",
        data_client_factory=FixtureLiveDataClientFactory,
        data_client_config=FixtureDataClientConfig(key="risk-cap"),
    )
    try:
        assert node.kernel.risk_engine.max_notional_per_order(instrument.id) == Decimal("250000")
    finally:
        node.dispose()


def test_kill_switch_halt_denies_all_orders(paper_loop: asyncio.AbstractEventLoop) -> None:
    instrument = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL", "SIM")
    register_fixture_events("risk-halt", to_execution_feed(_bars(), bar_type, slippage_bps=2.0))
    node = build_paper_node(
        _spec(),
        instrument,
        data_client_name="FIXTURE",
        data_client_factory=FixtureLiveDataClientFactory,
        data_client_config=FixtureDataClientConfig(
            key="risk-halt", feed_delay=0.2, feed_interval=0.02
        ),
    )
    strategy = _strategy(instrument.id, bar_type)
    node.trader.add_strategy(strategy)
    halt_trading(node)  # kill-switch engaged before any data flows
    cache = node.cache
    paper_loop.run_until_complete(run_node_for(node, duration_seconds=2.5, dispose=False))
    statuses = [o.status for o in cache.orders()]
    fills = strategy.fills
    node.dispose()

    assert statuses, "expected the strategy to attempt orders"
    assert all(s == OrderStatus.DENIED for s in statuses)  # all blocked by the kill-switch
    assert fills == 0  # nothing executed

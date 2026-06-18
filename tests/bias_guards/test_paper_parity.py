"""Phase 4e HEADLINE: the same strategy on the same bars emits the same orders in paper as backtest.

This is the parity guarantee that makes paper trading trustworthy: ``TimeSeriesMomentum`` runs
*unchanged* through the live sandbox ``TradingNode`` and, fed the identical execution feed, produces
a byte-identical order sequence to the backtest engine. Fees/slippage change fill *prices*, never
the order sequence (sizing uses the strategy's fixed capital + close prices), so the order logs must
match exactly. A divergence would mean paper and backtest are not the same system.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from nautilus_trader.model.enums import AccountType

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_core import Bar
from alpha_execution import equity_instrument, order_signature
from alpha_paper.config import PaperSpec
from alpha_paper.node import build_paper_node, run_node_for
from alpha_strategies.ts_momentum import TimeSeriesMomentum
from tests.fixtures.paper_fixtures import (
    FixtureDataClientConfig,
    FixtureLiveDataClientFactory,
    register_fixture_events,
)

# Small, fast strategy params; warmup floor = max(lookback+skip+1, vol_window+1) = 6.
_LOOKBACK = 5
_SKIP = 0
_VOL_WINDOW = 3
_TARGET_VOL = 0.15
_CAPITAL = 1_000_000.0
_MAX_LEVERAGE = 1.0
_REBALANCE_EVERY = 1
_PERIODS_PER_YEAR = 365
_ALLOW_SHORT = True
_SLIPPAGE_BPS = 2.0
_FEE_BPS = 1.0


def _rising_bars() -> list[Bar]:
    """A steadily rising series — enough history to warm up and trade every session."""
    bars = []
    for i in range(24):
        close = 100.0 + 3.0 * i
        bars.append(
            Bar(
                symbol="AAPL",
                ts=datetime(2026, 1, 1 + i, tzinfo=UTC),
                open=close - 1.0,
                high=close + 2.0,
                low=close - 2.0,
                close=close,
                volume=1000.0,
            )
        )
    return bars


def _strategy(instrument_id: object, bar_type: object) -> TimeSeriesMomentum:
    return TimeSeriesMomentum(
        instrument_id=instrument_id,
        bar_type=bar_type,
        lookback=_LOOKBACK,
        skip=_SKIP,
        vol_window=_VOL_WINDOW,
        target_vol=_TARGET_VOL,
        capital=_CAPITAL,
        max_leverage=_MAX_LEVERAGE,
        rebalance_every=_REBALANCE_EVERY,
        periods_per_year=_PERIODS_PER_YEAR,
        allow_short=_ALLOW_SHORT,
    )


@pytest.mark.bias_guard
def test_paper_orders_match_backtest_orders(paper_loop: asyncio.AbstractEventLoop) -> None:
    # Parity is engine-equivalence and asset-agnostic; we prove it on the integer-lot equity
    # instrument. The crypto fractional-sizing path (size_precision > 0) is exercised in Phase 4f.
    instrument = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL", "SIM")
    bars = _rising_bars()
    # The SAME execution feed drives both engines (default equity precision: price 2dp, size 0dp).
    feed = to_execution_feed(bars, bar_type, slippage_bps=_SLIPPAGE_BPS)

    # --- Backtest path (the trusted reference) ---
    backtest = run_backtest(
        instrument,
        feed,
        _strategy(instrument.id, bar_type),
        starting_cash=_CAPITAL,
        currency=instrument.quote_currency,
        account_type=AccountType.MARGIN,
        leverage=_MAX_LEVERAGE,
        fee_bps=_FEE_BPS,
    )

    # --- Paper sandbox path (the same strategy, the same feed) ---
    register_fixture_events("parity", feed)
    spec = PaperSpec(
        symbol="AAPL",
        exchange="sim",
        venue=str(instrument.id.venue),
        starting_cash=_CAPITAL,
        account_type="MARGIN",
        max_leverage=_MAX_LEVERAGE,
        fee_bps=_FEE_BPS,
        slippage_bps=_SLIPPAGE_BPS,
        lookback=_LOOKBACK,
        skip=_SKIP,
        vol_window=_VOL_WINDOW,
        target_vol=_TARGET_VOL,
        rebalance_every=_REBALANCE_EVERY,
        periods_per_year=_PERIODS_PER_YEAR,
        allow_short=_ALLOW_SHORT,
    )
    node = build_paper_node(
        spec,
        instrument,
        data_client_name="FIXTURE",
        data_client_factory=FixtureLiveDataClientFactory,
        data_client_config=FixtureDataClientConfig(
            key="parity", feed_delay=0.2, feed_interval=0.02
        ),
    )
    node.trader.add_strategy(_strategy(instrument.id, bar_type))
    cache = node.cache
    # dispose=False so the cache survives for inspection; dispose after capturing.
    # 48 events paced 0.02s apart (~1s) + warmup; 3s window leaves headroom.
    paper_loop.run_until_complete(run_node_for(node, duration_seconds=3.0, dispose=False))
    sandbox_log = [order_signature(o) for o in sorted(cache.orders(), key=lambda o: o.ts_init)]
    node.dispose()

    assert backtest.order_log, "expected the backtest to place at least one order"
    assert sandbox_log == backtest.order_log  # paper == backtest, order for order

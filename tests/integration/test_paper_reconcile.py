"""Phase 4e: realized sandbox-fill slippage reconciles with the modeled slippage_bps.

Runs ``TimeSeriesMomentum`` through the sandbox over a feed built with a known ``slippage_bps`` and
checks each filled order's average price reflects that slippage versus the session open — i.e. the
friction the backtest models is the friction the sandbox matcher realizes (within tick rounding).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_core import Bar
from alpha_execution import equity_instrument
from alpha_paper.config import PaperSpec
from alpha_paper.node import build_paper_node, run_node_for
from alpha_paper.reconcile import reconcile
from alpha_strategies.ts_momentum import TimeSeriesMomentum
from tests.fixtures.paper_fixtures import (
    FixtureDataClientConfig,
    FixtureLiveDataClientFactory,
    register_fixture_events,
)

_SLIPPAGE_BPS = 50.0  # 0.5% — comfortably larger than one tick at ~$100 so it survives rounding


def _rising_bars() -> list[Bar]:
    # Integer opens (open = 99 + 3i) so the reference open is exactly recoverable from a fill price.
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
        for i in range(20)
    ]


def test_realized_slippage_matches_modeled(paper_loop: asyncio.AbstractEventLoop) -> None:
    instrument = equity_instrument("AAPL")
    bar_type = daily_bar_type("AAPL", "SIM")
    feed = to_execution_feed(_rising_bars(), bar_type, slippage_bps=_SLIPPAGE_BPS)
    register_fixture_events("recon", feed)

    spec = PaperSpec(
        symbol="AAPL",
        exchange="sim",
        venue=str(instrument.id.venue),
        lookback=5,
        skip=0,
        vol_window=3,
        rebalance_every=1,
        periods_per_year=365,
        account_type="MARGIN",
        slippage_bps=_SLIPPAGE_BPS,
    )
    node = build_paper_node(
        spec,
        instrument,
        data_client_name="FIXTURE",
        data_client_factory=FixtureLiveDataClientFactory,
        data_client_config=FixtureDataClientConfig(key="recon", feed_delay=0.2, feed_interval=0.02),
    )
    node.trader.add_strategy(
        TimeSeriesMomentum(
            instrument_id=instrument.id,
            bar_type=bar_type,
            lookback=5,
            skip=0,
            vol_window=3,
            rebalance_every=1,
            periods_per_year=365,
            capital=1_000_000.0,
        )
    )
    cache = node.cache
    paper_loop.run_until_complete(run_node_for(node, duration_seconds=3.0, dispose=False))

    # Each filled order: recover the integer session open it filled against, then reconcile.
    s = _SLIPPAGE_BPS / 10_000.0
    fills = []
    for order in cache.orders():
        if order.avg_px is None:
            continue
        avg_px = float(order.avg_px)
        side = order.side.name
        ref_open = round(avg_px / (1.0 + s) if side == "BUY" else avg_px / (1.0 - s))
        fills.append((side, avg_px, float(ref_open)))
    node.dispose()

    assert fills, "expected at least one filled order to reconcile"
    rows = reconcile(fills, modeled_bps=_SLIPPAGE_BPS)
    for r in rows:
        assert abs(r.delta_bps) < 2.0  # realized matches modeled within tick rounding

"""Phase 4e/4f HEADLINE: same strategy + same bars → same orders in paper as in backtest.

This is the parity guarantee that makes paper trading trustworthy: ``TimeSeriesMomentum`` runs
*unchanged* through the live sandbox ``TradingNode`` and, fed the identical execution feed, produces
a byte-identical order sequence to the backtest engine. Fees/slippage change fill *prices*, never
the order sequence (sizing uses the strategy's fixed capital + close prices), so the order logs must
match exactly. A divergence would mean paper and backtest are not the same system.

Proven for both the integer-lot **equity** instrument and the fractional **crypto** instrument
(``size_precision`` 6) — the strategy rounds order quantities to the instrument's precision (4f).
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.instruments import Instrument

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_core import Bar
from alpha_execution import crypto_instrument, equity_instrument, order_signature
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


def _rising_bars(symbol: str, base: float, step: float) -> list[Bar]:
    """A steadily rising series — enough history to warm up and trade every session."""
    bars = []
    for i in range(24):
        close = base + step * i
        bars.append(
            Bar(
                symbol=symbol,
                ts=datetime(2026, 1, 1 + i, tzinfo=UTC),
                open=close - step / 3.0,
                high=close + step / 2.0,
                low=close - step / 2.0,
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


def _parity_order_logs(
    instrument: Instrument,
    bar_type: object,
    bars: list[Bar],
    *,
    size_precision: int,
    key: str,
    paper_loop: asyncio.AbstractEventLoop,
) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    """Return ``(backtest_order_log, sandbox_order_log)`` for the same strategy on the same feed."""
    feed = to_execution_feed(
        bars, bar_type, size_precision=size_precision, slippage_bps=_SLIPPAGE_BPS
    )

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
    register_fixture_events(key, feed)
    spec = PaperSpec(
        symbol=str(instrument.id.symbol),
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
        data_client_config=FixtureDataClientConfig(key=key, feed_delay=0.2, feed_interval=0.02),
    )
    node.trader.add_strategy(_strategy(instrument.id, bar_type))
    cache = node.cache
    # dispose=False so the cache survives for inspection; dispose after capturing.
    paper_loop.run_until_complete(run_node_for(node, duration_seconds=3.0, dispose=False))
    sandbox_log = [order_signature(o) for o in sorted(cache.orders(), key=lambda o: o.ts_init)]
    node.dispose()
    return backtest.order_log, sandbox_log


def _has_fractional_quantity(order_log: Sequence[tuple[str, float]]) -> bool:
    return any(qty != round(qty) for _, qty in order_log)


@pytest.mark.bias_guard
def test_paper_orders_match_backtest_orders_equity(
    paper_loop: asyncio.AbstractEventLoop,
) -> None:
    instrument = equity_instrument("AAPL")
    bars = _rising_bars("AAPL", base=100.0, step=3.0)
    backtest_log, sandbox_log = _parity_order_logs(
        instrument,
        daily_bar_type("AAPL", "SIM"),
        bars,
        size_precision=0,  # equities trade whole lots
        key="parity-equity",
        paper_loop=paper_loop,
    )
    assert backtest_log, "expected the backtest to place at least one order"
    assert sandbox_log == backtest_log  # paper == backtest, order for order


@pytest.mark.bias_guard
def test_paper_orders_match_backtest_orders_crypto(
    paper_loop: asyncio.AbstractEventLoop,
) -> None:
    instrument = crypto_instrument("BTC/USDT")
    bars = _rising_bars("BTCUSDT", base=60_000.0, step=400.0)  # realistic BTC -> fractional sizing
    backtest_log, sandbox_log = _parity_order_logs(
        instrument,
        daily_bar_type("BTCUSDT", "BINANCE"),
        bars,
        size_precision=6,  # crypto trades fractional units
        key="parity-crypto",
        paper_loop=paper_loop,
    )
    assert backtest_log, "expected the backtest to place at least one order"
    assert sandbox_log == backtest_log  # paper == backtest, order for order
    assert _has_fractional_quantity(backtest_log)  # fractional sizing actually exercised (4f)

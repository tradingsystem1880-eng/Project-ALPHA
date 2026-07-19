"""Paper-only strategy seams: safe priming and venue-aware order quantities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from alpha_backtest.feed import daily_bar_type
from alpha_backtest.instruments import crypto_instrument
from alpha_core import Bar
from alpha_strategies.ma_crossover import MovingAverageCrossover


def _bars(n: int) -> list[Bar]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Bar(
            symbol="BTC/USDT",
            ts=start + timedelta(days=i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.5 + i,
            volume=1_000.0,
        )
        for i in range(n)
    ]


def _strategy() -> MovingAverageCrossover:
    instrument = crypto_instrument("BTC/USDT", venue="BINANCE")
    return MovingAverageCrossover(
        instrument_id=instrument.id,
        bar_type=daily_bar_type("BTCUSDT", venue="BINANCE"),
        fast=2,
        slow=4,
        vol_window=3,
        rebalance_every=2,
        allow_short=True,
    )


@pytest.mark.bias_guard
def test_prime_history_warms_without_creating_an_order_target() -> None:
    strategy = _strategy()

    strategy.prime_history(_bars(5))

    assert strategy.history_size == 5
    assert strategy.eligible_bars == 2  # bars 4 and 5 preserve the live cadence
    assert strategy.pending_target is None
    assert strategy.fills == 0
    assert strategy.rejections == 0


def test_prime_history_rejects_non_monotonic_bars() -> None:
    strategy = _strategy()
    bars = _bars(3)
    bars[2] = bars[1]

    try:
        strategy.prime_history(bars)
    except ValueError as exc:
        assert "strictly increasing" in str(exc)
    else:  # pragma: no cover - assertion aid
        raise AssertionError("duplicate timestamps must fail")


def test_quantity_normalization_keeps_sim_rounding_and_honors_live_increment() -> None:
    from alpha_strategies.base import normalize_order_quantity

    # Existing SIM instruments are integer-lot and retain Python round semantics byte-for-byte.
    assert str(normalize_order_quantity(2.6, size_precision=0, size_increment=1.0)) == "3"
    assert str(normalize_order_quantity(2.4, size_precision=0, size_increment=1.0)) == "2"

    # Fractional live instruments round down to a valid increment, never exceeding the target.
    assert str(normalize_order_quantity(1.237, size_precision=3, size_increment=0.005)) == "1.235"
    assert normalize_order_quantity(0.004, size_precision=3, size_increment=0.005) is None

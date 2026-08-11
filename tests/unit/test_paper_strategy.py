"""Paper-only strategy seams: safe priming and venue-aware order quantities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from nautilus_trader.model.enums import AccountType

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import crypto_instrument
from alpha_core import Bar, DataError
from alpha_strategies.base import PaperRiskLimits
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


def test_paper_risk_limits_fail_closed_without_a_journal() -> None:
    limits = PaperRiskLimits(
        max_order_notional=5_000.0,
        max_position_notional=10_000.0,
        max_gross_notional=50_000.0,
        daily_loss_fraction=0.01,
        max_open_orders=5,
        max_quote_age_seconds=5.0,
        intent_id="a" * 64,
    )
    with pytest.raises(DataError, match="durable execution event sink"):
        _strategy().configure_paper_risk(limits)


def test_paper_risk_limits_reject_invalid_hierarchy() -> None:
    with pytest.raises(DataError, match="order notional"):
        PaperRiskLimits(
            max_order_notional=11.0,
            max_position_notional=10.0,
            max_gross_notional=50.0,
            daily_loss_fraction=0.01,
            max_open_orders=5,
            max_quote_age_seconds=5.0,
            intent_id="a" * 64,
        )


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"max_order_notional": float("nan")}, "finite and positive"),
        ({"max_position_notional": 60_000.0}, "position notional"),
        ({"daily_loss_fraction": 1.0}, "daily-loss"),
        ({"max_open_orders": 0}, "daily-loss"),
        ({"intent_id": "BAD"}, "intent id"),
        ({"account_id": "U123"}, "IBKR DU"),
        ({"expected_position_units": float("nan")}, "expected position"),
        ({"order_cutoff": datetime(2026, 8, 4)}, "timezone-aware"),
    ],
)
def test_paper_risk_limits_reject_each_unsafe_boundary(
    changes: dict[str, object], match: str
) -> None:
    valid = PaperRiskLimits(
        max_order_notional=5_000.0,
        max_position_notional=10_000.0,
        max_gross_notional=50_000.0,
        daily_loss_fraction=0.01,
        max_open_orders=5,
        max_quote_age_seconds=5.0,
        intent_id="a" * 64,
    )
    with pytest.raises(DataError, match=match):
        replace(valid, **cast(Any, changes))


class _Sink:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def emit(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        ts_event_ns: int | None = None,
    ) -> None:
        del ts_event_ns
        self.events.append((event_type, dict(payload)))


def test_reconciled_paper_intent_is_journaled_and_filled_by_same_hash() -> None:
    strategy = _strategy()
    sink = _Sink()
    strategy.set_execution_event_sink(sink)
    limits = PaperRiskLimits(
        max_order_notional=5_000.0,
        max_position_notional=10_000.0,
        max_gross_notional=50_000.0,
        daily_loss_fraction=0.01,
        max_open_orders=5,
        max_quote_age_seconds=5.0,
        intent_id="a" * 64,
    )
    strategy.configure_paper_risk(limits, reconciled=True)
    strategy.release_paper_intent(intent_id="a" * 64, target_quantity=3.0)
    bars = _bars(2)
    instrument = crypto_instrument("BTC/USDT", venue="BINANCE")

    result = run_backtest(
        instrument,
        to_execution_feed(
            bars,
            daily_bar_type("BTC/USDT", venue="BINANCE"),
            price_precision=5,
        ),
        strategy,
        starting_cash=100_000.0,
        account_type=AccountType.MARGIN,
    )

    assert result.fills == 1
    intent = next(payload for event, payload in sink.events if event == "intent")
    order = next(payload for event, payload in sink.events if event == "order")
    fill = next(payload for event, payload in sink.events if event == "fill")
    assert intent["intent_id"] == order["client_order_id"] == "a" * 64
    assert fill["client_order_id"] == "a" * 64


def test_release_rejects_wrong_intent_or_nonfinite_target() -> None:
    strategy = _strategy()
    strategy.set_execution_event_sink(_Sink())
    strategy.configure_paper_risk(
        PaperRiskLimits(
            max_order_notional=5_000.0,
            max_position_notional=10_000.0,
            max_gross_notional=50_000.0,
            daily_loss_fraction=0.01,
            max_open_orders=5,
            max_quote_age_seconds=5.0,
            intent_id="a" * 64,
        ),
        reconciled=True,
    )
    with pytest.raises(DataError, match="does not match"):
        strategy.release_paper_intent(intent_id="b" * 64, target_quantity=1.0)
    with pytest.raises(DataError, match="finite"):
        strategy.release_paper_intent(intent_id="a" * 64, target_quantity=float("nan"))


def test_reconciliation_and_release_require_configured_paper_risk() -> None:
    strategy = _strategy()
    with pytest.raises(DataError, match="not configured"):
        strategy.mark_paper_reconciled()
    with pytest.raises(DataError, match="not configured"):
        strategy.release_paper_intent(intent_id="a" * 64, target_quantity=1.0)


def test_reconciliation_seeds_order_delta_from_the_verified_overnight_position() -> None:
    strategy = _strategy()
    strategy.set_execution_event_sink(_Sink())
    strategy.configure_paper_risk(
        PaperRiskLimits(
            max_order_notional=5_000.0,
            max_position_notional=10_000.0,
            max_gross_notional=50_000.0,
            daily_loss_fraction=0.01,
            max_open_orders=5,
            max_quote_age_seconds=5.0,
            intent_id="a" * 64,
            expected_position_units=4.0,
        )
    )

    strategy.mark_paper_reconciled()

    assert strategy.net_units == 4.0


def test_paper_cancel_expiry_and_rejection_events_halt_or_journal() -> None:
    strategy = _strategy()
    sink = _Sink()
    strategy.set_execution_event_sink(sink)
    strategy.configure_paper_risk(
        PaperRiskLimits(
            max_order_notional=5_000.0,
            max_position_notional=10_000.0,
            max_gross_notional=50_000.0,
            daily_loss_fraction=0.01,
            max_open_orders=5,
            max_quote_age_seconds=5.0,
            intent_id="a" * 64,
        ),
        reconciled=True,
    )
    event = type(
        "OrderEvent",
        (),
        {
            "instrument_id": strategy._iid,  # noqa: SLF001
            "client_order_id": "a" * 64,
            "venue_order_id": "paper-1",
            "ts_event": 1,
            "reason": "rejected",
        },
    )()

    strategy.on_order_canceled(cast(Any, event))
    strategy.on_order_expired(cast(Any, event))
    strategy.on_order_rejected(event)

    assert [name for name, _ in sink.events[-3:]] == ["cancel", "expired", "rejection"]
    assert strategy.halted is True

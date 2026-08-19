from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from alpha_core import DataError
from alpha_strategies.hedged_basis import (
    HedgedBasisObservationV1,
    evaluate_hedged_basis,
    registered_hedged_basis_plan,
)


def _observation(index: int = 0) -> HedgedBasisObservationV1:
    event_time = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(hours=8 * index)
    entry_time = event_time + timedelta(hours=1)
    exit_time = event_time + timedelta(hours=8)
    return HedgedBasisObservationV1.create(
        event_time=event_time,
        event_available_at=event_time,
        entry_time=entry_time,
        entry_available_at=entry_time,
        exit_time=exit_time,
        exit_available_at=exit_time,
        bybit_perp_entry=100.0,
        bybit_perp_exit=99.0,
        binance_spot_entry=100.0,
        binance_spot_exit=100.0,
        funding_rate=0.001,
        funding_available_at=event_time,
        perp_quantity_btc=-1.0,
        spot_quantity_btc=1.0,
        input_sha256=(("binance_spot", "a" * 64), ("bybit_linear", "b" * 64)),
        event_operator_fingerprint="c" * 64,
        correction_lineage=(),
    )


def test_registered_hedged_basis_plan_is_permanently_sandbox_only() -> None:
    plan = registered_hedged_basis_plan()

    assert plan.strategy_name == "hedged_basis_crowding_v1"
    assert plan.perp_venue == "bybit"
    assert plan.spot_venue == "binance"
    assert plan.instrument == "BTCUSDT"
    assert plan.quote_asset == "USDT"
    assert plan.total_round_trip_cost_bps == 40.0
    assert plan.annualization_days == 365
    assert plan.deployment_scope == "sandbox_only"
    assert plan.paper_blocker == "UNSUPPORTED_MULTI_VENUE_PAPER"
    assert plan.places_orders is False


def test_hedged_basis_evaluation_preserves_both_legs_funding_and_costs() -> None:
    observation = _observation()
    result = evaluate_hedged_basis((observation,))

    assert result.status == "EVALUATED"
    assert result.periods_per_year == 1_095
    assert result.total_round_trip_cost_bps == 40.0
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.bybit_perp_short_return == pytest.approx(0.01)
    assert trade.binance_spot_long_return == pytest.approx(0.0)
    assert trade.funding_return == pytest.approx(0.001)
    assert trade.cost_return == pytest.approx(-0.004)
    assert trade.net_return == pytest.approx(0.007)
    assert trade.available_at == observation.exit_available_at
    assert result.cumulative_return == pytest.approx(0.007)
    assert result.input_sha256 == observation.input_sha256


def test_hedged_basis_observation_rejects_identity_availability_and_tamper() -> None:
    observation = _observation()

    assert HedgedBasisObservationV1.from_dict(observation.to_dict()) == observation

    with pytest.raises(DataError, match="delta matched"):
        replace(observation, spot_quantity_btc=0.5)
    with pytest.raises(DataError, match="causal"):
        replace(observation, entry_available_at=observation.exit_time + timedelta(seconds=1))
    with pytest.raises(DataError, match="identity"):
        replace(observation, observation_id="0" * 64)
    with pytest.raises(DataError, match="identity"):
        HedgedBasisObservationV1.from_dict({**observation.to_dict(), "bybit_perp_exit": 98.0})


def test_hedged_basis_evaluation_rejects_overlapping_or_mixed_lineage() -> None:
    first = _observation()
    overlapping = _observation(0)
    with pytest.raises(DataError, match="strictly ordered and non-overlapping"):
        evaluate_hedged_basis((first, overlapping))

    second = _observation(1)
    mixed = HedgedBasisObservationV1.create(
        **{
            **second.body(),
            "input_sha256": (("binance_spot", "d" * 64), ("bybit_linear", "b" * 64)),
        }
    )
    with pytest.raises(DataError, match="same frozen input lineage"):
        evaluate_hedged_basis((first, mixed))

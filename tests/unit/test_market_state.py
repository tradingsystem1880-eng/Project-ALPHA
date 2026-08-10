"""Contract and deterministic behavior for the shared causal market-state layer."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from alpha_core import DataError
from alpha_research.market_state import (
    MarketSessionCloseV1,
    MarketStateArtifactV1,
    MarketStateContractV1,
    condition_values_by_market_state,
    derive_market_state,
)


def _contract(*, calendar: str = "equity") -> MarketStateContractV1:
    return MarketStateContractV1(
        universe=("SPY", "QQQ", "IWM"),
        benchmark="SPY",
        calendar=calendar,
        volatility_window=3,
        trend_window=3,
        correlation_window=3,
        annualization_sessions=252 if calendar == "equity" else 365,
        volatility_thresholds=(0.10, 0.25),
        trend_threshold=0.01,
        breadth_thresholds=(1 / 3, 2 / 3),
        correlation_thresholds=(0.25, 0.75),
        minimum_state_samples=2,
    )


def _equity_observations(count: int = 10) -> list[MarketSessionCloseV1]:
    observations: list[MarketSessionCloseV1] = []
    session = date(2026, 1, 5)
    index = 0
    while len(observations) < count:
        if session.weekday() < 5:
            observations.append(
                MarketSessionCloseV1(
                    session=session,
                    available_at=datetime.combine(session, datetime.min.time(), tzinfo=UTC)
                    + timedelta(hours=21),
                    closes=(100.0 + index, 90.0 + 1.5 * index, 80.0 + 0.5 * index),
                )
            )
            index += 1
        session += timedelta(days=1)
    return observations


def test_contract_and_artifact_round_trip_with_content_identity() -> None:
    contract = _contract()
    restored_contract = MarketStateContractV1.from_dict(contract.to_dict())
    assert restored_contract == contract
    assert restored_contract.contract_sha256 == contract.contract_sha256

    artifact = derive_market_state(contract, _equity_observations())
    restored_artifact = MarketStateArtifactV1.from_dict(artifact.to_dict())
    assert restored_artifact == artifact
    assert restored_artifact.artifact_sha256 == artifact.artifact_sha256
    assert artifact.contract_sha256 == contract.contract_sha256
    assert artifact.points[-1].eligible is True
    assert artifact.points[-1].state_key.startswith("volatility=")
    assert artifact.points[-1].available_at == _equity_observations()[-1].available_at


def test_derivation_is_causal_and_labels_warmup_as_abstention() -> None:
    artifact = derive_market_state(_contract(), _equity_observations())
    assert all(point.eligible is False for point in artifact.points[:3])
    assert all(point.state_key == "unavailable" for point in artifact.points[:3])
    assert all(point.eligible is True for point in artifact.points[3:])
    assert all(point.volatility_label in {"low", "mid", "high"} for point in artifact.points[3:])
    assert all(point.trend_label in {"down", "flat", "up"} for point in artifact.points[3:])
    assert all(point.breadth_label in {"weak", "mixed", "strong"} for point in artifact.points[3:])
    assert all(point.correlation_label in {"low", "mid", "high"} for point in artifact.points[3:])


def test_conditioning_uses_explicit_pooled_fallback_for_sparse_states() -> None:
    artifact = derive_market_state(_contract(), _equity_observations(12))
    values = [float(index) for index in range(len(artifact.points))]
    rows = condition_values_by_market_state(artifact, values)
    assert rows
    assert all(row.minimum_samples == 2 for row in rows)
    assert all(row.sample_count > 0 for row in rows)
    assert all(row.used_pooled_fallback is (row.sample_count < row.minimum_samples) for row in rows)
    assert all(
        row.value_count == (row.pooled_count if row.used_pooled_fallback else row.sample_count)
        for row in rows
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload.update({"benchmark": "DIA"}), "benchmark"),
        (lambda payload: payload.update({"calendar": "mixed"}), "calendar"),
        (lambda payload: payload.update({"volatility_thresholds": [0.3, 0.1]}), "threshold"),
        (lambda payload: payload.update({"minimum_state_samples": 0}), "minimum_state_samples"),
        (lambda payload: payload.update({"extra": True}), "fields"),
    ],
)
def test_contract_rejects_unfrozen_or_invalid_semantics(mutation: object, message: str) -> None:
    payload = _contract().to_dict()
    mutation(payload)  # type: ignore[operator]
    with pytest.raises(DataError, match=message):
        MarketStateContractV1.from_dict(payload)


def test_calendar_and_availability_validation_fail_closed() -> None:
    equity = _equity_observations()
    weekend = MarketSessionCloseV1(
        session=date(2026, 1, 10),
        available_at=datetime(2026, 1, 10, 21, tzinfo=UTC),
        closes=(100.0, 100.0, 100.0),
    )
    with pytest.raises(DataError, match="weekend"):
        derive_market_state(_contract(), [*equity[:5], weekend])

    crypto = [
        MarketSessionCloseV1(
            session=date(2026, 1, 1) + timedelta(days=index),
            available_at=datetime(2026, 1, 2, tzinfo=UTC) + timedelta(days=index),
            closes=(100.0 + index, 90.0 + index, 80.0 + index),
        )
        for index in range(6)
        if index != 3
    ]
    with pytest.raises(DataError, match="consecutive"):
        derive_market_state(_contract(calendar="crypto_24_7"), crypto)

    reversed_availability = list(equity)
    reversed_availability[4] = MarketSessionCloseV1(
        session=reversed_availability[4].session,
        available_at=reversed_availability[3].available_at,
        closes=reversed_availability[4].closes,
    )
    with pytest.raises(DataError, match="available_at"):
        derive_market_state(_contract(), reversed_availability)

    wrong_width = list(equity)
    wrong_width[2] = MarketSessionCloseV1(
        session=wrong_width[2].session,
        available_at=wrong_width[2].available_at,
        closes=(100.0, 101.0),
    )
    with pytest.raises(DataError, match="universe"):
        derive_market_state(_contract(), wrong_width)

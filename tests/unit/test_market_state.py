"""Contract and deterministic behavior for the shared causal market-state layer."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal

import pytest

from alpha_core import DataError
from alpha_research.market_state import (
    MarketSessionCloseV1,
    MarketStateArtifactV1,
    MarketStateContractV1,
    condition_values_by_market_state,
    derive_market_state,
)


def _contract(*, calendar: Literal["equity", "crypto_24_7"] = "equity") -> MarketStateContractV1:
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


def _replace(payload: dict[str, object], **fields: object) -> dict[str, object]:
    return {**payload, **fields}


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"universe": ("SPY",)}, "at least two instruments"),
        ({"universe": ("SPY", "SPY", "QQQ")}, "unique canonical symbols"),
        ({"annualization_sessions": 365}, "annualization_sessions must be 252"),
        ({"volatility_thresholds": (-0.1, 0.2)}, "cannot be negative"),
        ({"trend_threshold": -0.01}, "cannot be negative"),
        ({"breadth_thresholds": (0.5, 1.5)}, r"breadth_thresholds must lie in \[0, 1\]"),
        ({"correlation_thresholds": (-2.0, 0.5)}, r"correlation_thresholds must lie in \[-1, 1\]"),
    ],
)
def test_contract_construction_fails_loud_on_each_invariant(
    fields: dict[str, object], message: str
) -> None:
    base = _contract()
    values = {
        name: getattr(base, name)
        for name in (
            "universe",
            "benchmark",
            "calendar",
            "volatility_window",
            "trend_window",
            "correlation_window",
            "annualization_sessions",
            "volatility_thresholds",
            "trend_threshold",
            "breadth_thresholds",
            "correlation_thresholds",
            "minimum_state_samples",
        )
    }
    with pytest.raises(DataError, match=message):
        MarketStateContractV1(**{**values, **fields})


def test_crypto_contract_pins_its_own_annualization() -> None:
    with pytest.raises(DataError, match="annualization_sessions must be 365"):
        MarketStateContractV1(
            universe=("BTC", "ETH"),
            benchmark="BTC",
            calendar="crypto_24_7",
            volatility_window=3,
            trend_window=3,
            correlation_window=3,
            annualization_sessions=252,
            volatility_thresholds=(0.1, 0.25),
            trend_threshold=0.01,
            breadth_thresholds=(0.3, 0.7),
            correlation_thresholds=(0.25, 0.75),
            minimum_state_samples=2,
        )


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"schema_version": 2}, "unsupported"),
        ({"universe": ["SPY", 7]}, "string array"),
        ({"contract_sha256": "0" * 64}, "does not match its semantics"),
        ({"trend_threshold": float("inf")}, "finite number"),
        ({"benchmark": ""}, "non-empty canonical string"),
        ({"volatility_thresholds": [0.1]}, "exactly two thresholds"),
    ],
)
def test_contract_from_dict_rejects_a_malformed_payload(
    fields: dict[str, object], message: str
) -> None:
    with pytest.raises(DataError, match=message):
        MarketStateContractV1.from_dict(_replace(_contract().to_dict(), **fields))


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"session": "2026-01-05"}, "must be a date"),
        ({"available_at": datetime(2026, 1, 5, 21)}, "timezone-aware"),
        ({"closes": ()}, "cannot be empty"),
        ({"closes": (100.0, 0.0, 80.0)}, "finite positive"),
        ({"closes": (100.0, float("nan"), 80.0)}, "finite positive"),
    ],
)
def test_session_close_rejects_a_malformed_observation(
    fields: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "session": date(2026, 1, 5),
        "available_at": datetime(2026, 1, 5, 21, tzinfo=UTC),
        "closes": (100.0, 90.0, 80.0),
    }
    with pytest.raises(DataError, match=message):
        MarketSessionCloseV1(**{**values, **fields})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"schema_version": 2}, "unsupported MarketStateV1 schema"),
        ({"contract": "not-an-object"}, "contract must be an object"),
        ({"contract_sha256": "0" * 64}, "does not match its contract"),
        ({"points": "not-an-array"}, "must be an object array"),
        ({"points": [1, 2]}, "must be an object array"),
        ({"artifact_sha256": "0" * 64}, "does not match its content"),
        ({"source_sha256": "nope"}, "SHA-256 digest"),
    ],
)
def test_artifact_from_dict_rejects_a_malformed_payload(
    fields: dict[str, object], message: str
) -> None:
    artifact = derive_market_state(_contract(), _equity_observations())
    with pytest.raises(DataError, match=message):
        MarketStateArtifactV1.from_dict(_replace(artifact.to_dict(), **fields))


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"session": "not-a-date"}, "invalid date or timestamp"),
        ({"eligible": 1}, "eligible must be boolean"),
        ({"available_at": "2026-01-05T21:00:00"}, "timezone-aware"),
    ],
)
def test_point_from_dict_rejects_a_malformed_payload(
    fields: dict[str, object], message: str
) -> None:
    artifact = derive_market_state(_contract(), _equity_observations())
    payload = _replace(artifact.to_dict()["points"][-1], **fields)  # type: ignore[index]
    with pytest.raises(DataError, match=message):
        MarketStateArtifactV1.from_dict(
            _replace(artifact.to_dict(), points=[payload], artifact_sha256="0" * 64)
        )


def test_an_ineligible_point_may_not_carry_a_real_state_key() -> None:
    artifact = derive_market_state(_contract(), _equity_observations())
    warmup = dict(artifact.to_dict()["points"][0])  # type: ignore[index]
    assert warmup["eligible"] is False
    warmup["state_key"] = "volatility=low|trend=up|breadth=strong|correlation=low"
    with pytest.raises(DataError, match="unavailable state_key"):
        MarketStateArtifactV1.from_dict(
            _replace(artifact.to_dict(), points=[warmup], artifact_sha256="0" * 64)
        )


def test_a_close_vector_must_match_the_frozen_universe() -> None:
    observations = _equity_observations()
    observations[2] = MarketSessionCloseV1(
        session=observations[2].session,
        available_at=observations[2].available_at,
        closes=(100.0, 90.0),
    )
    with pytest.raises(DataError, match="must match the frozen universe"):
        derive_market_state(_contract(), observations)


def test_sessions_must_strictly_increase() -> None:
    observations = _equity_observations()
    observations[3] = MarketSessionCloseV1(
        session=observations[2].session,
        available_at=observations[3].available_at,
        closes=observations[3].closes,
    )
    with pytest.raises(DataError, match="strictly increasing"):
        derive_market_state(_contract(), observations)


def test_derivation_requires_at_least_one_observation() -> None:
    with pytest.raises(DataError, match="at least one aligned session close"):
        derive_market_state(_contract(), [])


def test_a_degenerate_correlation_window_abstains_instead_of_inventing_a_state() -> None:
    """Flat prices give every pair zero variance; correlation is undefined, not zero."""
    observations = [
        MarketSessionCloseV1(
            session=obs.session, available_at=obs.available_at, closes=(100.0, 90.0, 80.0)
        )
        for obs in _equity_observations()
    ]
    artifact = derive_market_state(_contract(), observations)
    tail = artifact.points[-1]
    assert tail.eligible is False
    assert tail.average_correlation is None
    assert tail.correlation_label == "unavailable"
    assert tail.state_key == "unavailable"
    assert tail.breadth is not None, "the metrics that ARE defined stay populated"


def test_conditioning_rejects_misaligned_or_non_finite_values() -> None:
    artifact = derive_market_state(_contract(), _equity_observations())
    with pytest.raises(DataError, match="align one-for-one"):
        condition_values_by_market_state(artifact, [0.0])
    with pytest.raises(DataError, match="finite and one-dimensional"):
        condition_values_by_market_state(artifact, [float("nan")] * len(artifact.points))


def test_conditioning_returns_nothing_when_no_point_is_eligible() -> None:
    observations = [
        MarketSessionCloseV1(
            session=obs.session, available_at=obs.available_at, closes=(100.0, 90.0, 80.0)
        )
        for obs in _equity_observations()
    ]
    artifact = derive_market_state(_contract(), observations)
    assert condition_values_by_market_state(artifact, [1.0] * len(artifact.points)) == ()

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from alpha_core import DataError
from alpha_research.crypto_crowding import (
    CryptoCrowdingObservationV1,
    evaluate_crypto_crowding,
    execute_crypto_crowding_d0,
    registered_crypto_crowding_plan,
)


def _observations(
    *, event_indices: set[int] | None = None
) -> tuple[CryptoCrowdingObservationV1, ...]:
    events = event_indices or {380}
    start = datetime(2025, 1, 1, tzinfo=UTC)
    rows: list[CryptoCrowdingObservationV1] = []
    for index in range(420):
        funding_time = start + timedelta(hours=8 * index)
        is_event = index in events
        rows.append(
            CryptoCrowdingObservationV1(
                funding_time=funding_time,
                funding_available_at=funding_time,
                funding_rate=0.02 if is_event else 0.001 + index * 0.000001,
                open_interest=120.0 + index + (25.0 if is_event else 0.0),
                open_interest_available_at=funding_time,
                premium=0.002 if is_event else -0.001,
                premium_available_at=funding_time,
                entry_time=funding_time + timedelta(hours=1),
                entry_available_at=funding_time + timedelta(hours=1),
                entry_mark=100.0,
                entry_index=100.0,
                exit_time=funding_time + timedelta(hours=8),
                exit_available_at=funding_time + timedelta(hours=8),
                exit_mark=99.8 if is_event else 100.0,
                exit_index=100.0,
                long_short_ratio=1.2 if is_event else 1.0,
                recent_trend=0.01,
                recent_volatility=0.02,
                regime="normal",
                diagnostics_available_at=funding_time,
            )
        )
    return tuple(rows)


def _mature_observations() -> tuple[CryptoCrowdingObservationV1, ...]:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    rows: list[CryptoCrowdingObservationV1] = []
    for index in range(620):
        funding_time = start + timedelta(hours=8 * index)
        is_event = index >= 366 and index % 2 == 0
        rows.append(
            CryptoCrowdingObservationV1(
                funding_time=funding_time,
                funding_available_at=funding_time,
                funding_rate=0.02 if is_event else 0.001,
                open_interest=1_000.0 + index,
                open_interest_available_at=funding_time,
                premium=0.002 if is_event else -0.001,
                premium_available_at=funding_time,
                entry_time=funding_time + timedelta(hours=1),
                entry_available_at=funding_time + timedelta(hours=1),
                entry_mark=100.0,
                entry_index=100.0,
                exit_time=funding_time + timedelta(hours=8),
                exit_available_at=funding_time + timedelta(hours=8),
                exit_mark=99.8 if is_event else 100.0,
                exit_index=100.0,
                long_short_ratio=2.0 if is_event else 1.0,
                recent_trend=0.01,
                recent_volatility=0.02,
                regime="crowded" if is_event else "normal",
                diagnostics_available_at=funding_time,
            )
        )
    return tuple(rows)


def test_registered_crypto_crowding_plan_is_exact_and_content_addressed() -> None:
    plan = registered_crypto_crowding_plan()
    assert plan.bundle_id == "bybit_btcusdt_crowding_reversal_v1"
    assert plan.provider == "bybit"
    assert plan.market_type == "linear"
    assert plan.instrument == "BTCUSDT"
    assert plan.quote_asset == "USDT"
    assert plan.primary_percentile == 0.95
    assert plan.sensitivity_percentiles == (0.9, 0.975)
    assert plan.sensitivity_multiplicity == "holm_v1"
    assert len(plan.operator_fingerprint) == 64
    assert plan.to_dict()["operator_fingerprint"] == plan.operator_fingerprint
    with pytest.raises(DataError, match="registered generation"):
        replace(plan, quote_asset="USD")


def test_crypto_crowding_evaluator_detects_causal_primary_event_and_outcome() -> None:
    result = evaluate_crypto_crowding(_observations(), evidence_zone="D1")

    assert result.status == "INCONCLUSIVE"
    assert result.primary_event_count == 1
    event = result.primary_events[0]
    assert event.observation_index == 380
    assert event.funding_rate > event.funding_threshold
    assert event.open_interest_change_24h > 0
    assert event.premium > 0
    assert event.mark_minus_index_return == pytest.approx(-0.002)
    assert event.clears_practical_hurdle is True
    assert result.blockers == ("minimum_effective_events:1<50",)
    assert result.sensitivity_event_counts[0][0] == 0.9
    assert result.plan_fingerprint == registered_crypto_crowding_plan().operator_fingerprint


def test_crypto_crowding_evaluator_runs_registered_controls_and_inference() -> None:
    result = evaluate_crypto_crowding(_mature_observations(), evidence_zone="D1")

    assert result.status == "EVALUATED"
    assert result.blockers == ()
    assert result.primary_estimate is not None
    assert result.primary_estimate.estimate == pytest.approx(-0.002)
    assert result.primary_estimate.matched_pairs >= 50
    assert result.primary_estimate.effective_week_clusters >= 10
    assert result.primary_estimate.low_cluster_count is False
    assert tuple(item.percentile for item in result.sensitivity_results) == (0.9, 0.975)
    assert all(item.adjusted_p_value is not None for item in result.sensitivity_results)
    assert all(item.rejected is True for item in result.sensitivity_results)
    assert result.shifted_date_placebo is not None
    assert result.shifted_date_placebo.shift_count == 20
    assert result.shifted_date_placebo.placebo_mean == pytest.approx(0.0)
    assert result.long_short_diagnostic is not None
    assert result.long_short_diagnostic.event_mean == pytest.approx(2.0)
    assert {item.regime for item in result.regime_diagnostics} == {"crowded"}


def test_crypto_crowding_evaluator_enforces_non_overlap() -> None:
    rows = list(_observations(event_indices={380, 381, 383}))
    result = evaluate_crypto_crowding(tuple(rows), evidence_zone="D1")

    assert [event.observation_index for event in result.primary_events] == [380, 383]


def test_crypto_crowding_evaluator_rejects_future_poison_and_malformed_identity() -> None:
    rows = list(_observations())
    with pytest.raises(DataError, match="event input is not point-in-time available"):
        replace(rows[380], premium_available_at=rows[380].funding_time + timedelta(hours=2))
    with pytest.raises(DataError, match="event input is not point-in-time available"):
        replace(rows[380], diagnostics_available_at=rows[380].funding_time + timedelta(hours=1))

    with pytest.raises(DataError, match="evidence zone"):
        evaluate_crypto_crowding(_observations(), evidence_zone="D3")  # type: ignore[arg-type]


def test_crypto_crowding_evaluator_requires_complete_history_and_d2_sample() -> None:
    short = _observations()[:365]
    result = evaluate_crypto_crowding(short, evidence_zone="D1")
    assert result.primary_event_count == 0
    assert result.blockers == ("minimum_effective_events:0<50",)

    d2 = evaluate_crypto_crowding(_observations(), evidence_zone="D2")
    assert d2.status == "INCONCLUSIVE"
    assert d2.blockers == (
        "minimum_confirmation_events:1<10",
        "minimum_effective_events:1<50",
    )


def test_crypto_crowding_evaluator_rejects_noncausal_outcome_boundary() -> None:
    rows = list(_observations())
    rows[380] = replace(rows[380], exit_time=rows[380].exit_time + timedelta(hours=1))
    with pytest.raises(DataError, match="next declared funding timestamp"):
        evaluate_crypto_crowding(tuple(rows), evidence_zone="D1")


def test_crypto_crowding_d0_recomputes_every_registered_acceptance_scenario() -> None:
    result = execute_crypto_crowding_d0()

    assert result.schema == "CryptoCrowdingD0AcceptanceV1"
    assert result.operator_fingerprint == registered_crypto_crowding_plan().operator_fingerprint
    assert len(result.fixture_definition_sha256) == 64
    assert result.planted_event_count == 1
    assert result.null_event_count == 0
    assert result.confounded_event_count == 1
    assert result.confounder_recorded is True
    assert result.future_poison_rejected is True
    assert result.missing_required_suppressed is True
    assert result.correction_lineage_preserved is True
    assert result.correction_changes_result is True
    assert result.insufficient_sample_blocker is True
    assert result.passed is True
    assert result.to_dict()["real_market_evidence"] is False

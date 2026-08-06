"""Point-in-time event studies, deterministic controls, and dependence-aware inference."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from alpha_core import DataError
from alpha_research import (
    ClaimDirection,
    ConfirmationEvidence,
    ConfirmationStatus,
    EventStudyObservation,
    MatchedEventControlPair,
    MatchedEventStudy,
    PreEventCovariate,
    classify_confirmation,
    evaluate_event_association,
    evaluate_matched_association,
    match_event_controls,
    purge_overlapping_outcomes,
)
from alpha_research.event_study import _cluster_bootstrap_predictive_mean


def _observation(
    observation_id: str,
    *,
    day: datetime,
    outcome: float,
    is_event: bool,
    cluster_id: str,
    weekday: str = "Tuesday",
    available_delay: timedelta = timedelta(),
    horizon: timedelta = timedelta(hours=4),
) -> EventStudyObservation:
    event_at = day.replace(hour=10)
    event_available_at = event_at + available_delay
    outcome_start = max(event_at + timedelta(hours=1), event_available_at)
    return EventStudyObservation(
        observation_id=observation_id,
        is_event=is_event,
        event_at=event_at,
        event_available_at=event_available_at,
        outcome_start_at=outcome_start,
        outcome_end_at=outcome_start + horizon,
        outcome_available_at=outcome_start + horizon,
        outcome=outcome,
        cluster_id=cluster_id,
        covariates=(
            PreEventCovariate(
                name="weekday",
                value=weekday,
                observed_at=event_at - timedelta(days=1),
                available_at=event_at - timedelta(days=1),
            ),
        ),
    )


def test_observation_enforces_event_outcome_and_covariate_availability() -> None:
    day = datetime(2024, 1, 2, tzinfo=UTC)
    valid = _observation(
        "event-1",
        day=day,
        outcome=0.01,
        is_event=True,
        cluster_id="week-1",
        available_delay=timedelta(hours=2),
    )

    with pytest.raises(DataError, match="event availability"):
        replace(valid, outcome_start_at=valid.event_available_at - timedelta(seconds=1))
    with pytest.raises(DataError, match="outcome availability"):
        replace(valid, outcome_available_at=valid.outcome_end_at - timedelta(seconds=1))
    with pytest.raises(DataError, match="pre-event"):
        replace(
            valid,
            covariates=(
                replace(valid.covariates[0], available_at=valid.event_at + timedelta(seconds=1)),
            ),
        )


def test_overlapping_event_outcomes_are_purged_in_first_available_order() -> None:
    day = datetime(2024, 1, 2, tzinfo=UTC)
    first = _observation(
        "event-1",
        day=day,
        outcome=0.01,
        is_event=True,
        cluster_id="week-1",
        horizon=timedelta(days=2),
    )
    overlapping = _observation(
        "event-2",
        day=day + timedelta(days=1),
        outcome=0.02,
        is_event=True,
        cluster_id="week-1",
        horizon=timedelta(days=2),
    )
    later = _observation(
        "event-3",
        day=day + timedelta(days=4),
        outcome=0.03,
        is_event=True,
        cluster_id="week-2",
        horizon=timedelta(days=1),
    )

    purged = purge_overlapping_outcomes((later, overlapping, first))

    assert [item.observation_id for item in purged.observations] == ["event-1", "event-3"]
    assert purged.dropped_observation_ids == ("event-2",)
    assert purged.effective_event_count == 2


def test_cluster_bootstrap_is_deterministic_and_reports_cluster_effective_count() -> None:
    origin = datetime(2024, 1, 2, tzinfo=UTC)
    observations = tuple(
        _observation(
            f"event-{index}",
            day=origin + timedelta(days=7 * index),
            outcome=0.01 + index / 1_000,
            is_event=True,
            cluster_id=f"month-{index // 2}",
        )
        for index in range(10)
    )
    as_of = max(item.outcome_available_at for item in observations)

    first = evaluate_event_association(
        observations,
        as_of=as_of,
        n_resamples=2_000,
        seed=7,
    )
    second = evaluate_event_association(
        tuple(reversed(observations)),
        as_of=as_of,
        n_resamples=2_000,
        seed=7,
    )

    assert first == second
    assert first.method == "cluster_bootstrap_predictive_mean"
    assert first.sample_size == 10
    assert first.effective_event_count == 5
    assert first.ci_lower < first.estimate < first.ci_upper
    assert first.caveat == "Conditional predictive association; not a causal effect."


def test_future_outcomes_past_as_of_cannot_change_point_in_time_estimate() -> None:
    origin = datetime(2024, 1, 2, tzinfo=UTC)
    known = tuple(
        _observation(
            f"known-{index}",
            day=origin + timedelta(days=7 * index),
            outcome=0.01 + index / 1_000,
            is_event=True,
            cluster_id=f"known-{index}",
        )
        for index in range(6)
    )
    cutoff = max(item.outcome_available_at for item in known)
    future = _observation(
        "future",
        day=origin + timedelta(days=70),
        outcome=9_999.0,
        is_event=True,
        cluster_id="future",
    )

    baseline = evaluate_event_association(known, as_of=cutoff, n_resamples=1_000, seed=11)
    poisoned = evaluate_event_association(
        (*known, future), as_of=cutoff, n_resamples=1_000, seed=11
    )

    assert poisoned.not_yet_available_count == 1
    assert replace(poisoned, not_yet_available_count=0) == baseline


def test_planted_tuesday_effect_is_not_credited_to_double_bottom_after_matching() -> None:
    """Regression: a weekday-only return premium must not become pattern support."""
    origin = datetime(2024, 1, 2, tzinfo=UTC)  # Tuesday
    observations: list[EventStudyObservation] = []
    for index in range(20):
        effect = 0.02 + ((index % 5) - 2) / 1_000
        event_day = origin + timedelta(days=14 * index)
        control_day = event_day + timedelta(days=7)
        observations.extend(
            (
                _observation(
                    f"double-bottom-{index:02d}",
                    day=event_day,
                    outcome=effect,
                    is_event=True,
                    cluster_id=f"event-week-{index:02d}",
                ),
                _observation(
                    f"tuesday-control-{index:02d}",
                    day=control_day,
                    outcome=effect,
                    is_event=False,
                    cluster_id=f"control-week-{index:02d}",
                ),
            )
        )
    as_of = max(item.outcome_available_at for item in observations)

    unadjusted = evaluate_event_association(
        tuple(item for item in observations if item.is_event),
        as_of=as_of,
        n_resamples=4_000,
        seed=7,
    )
    matched = match_event_controls(
        tuple(observations),
        covariate_names=("weekday",),
        as_of=as_of,
    )
    adjusted = evaluate_matched_association(matched, n_resamples=4_000, seed=7)
    verdict = classify_confirmation(
        ConfirmationEvidence(
            direction=ClaimDirection.POSITIVE,
            estimate=adjusted.estimate,
            ci_lower=adjusted.ci_lower,
            ci_upper=adjusted.ci_upper,
            adjusted_p_value=adjusted.p_value,
            alpha=0.05,
            minimum_effect=0.005,
        )
    )

    assert unadjusted.ci_lower > 0.0
    assert len(matched.pairs) == 20
    assert matched.unmatched_event_ids == ()
    assert adjusted.estimate == pytest.approx(0.0, abs=1e-15)
    assert adjusted.ci_lower == pytest.approx(0.0, abs=1e-15)
    assert adjusted.ci_upper == pytest.approx(0.0, abs=1e-15)
    assert adjusted.p_value == 1.0
    assert verdict.status is ConfirmationStatus.INCONCLUSIVE


def test_matching_is_exact_deterministic_and_never_uses_post_event_covariates() -> None:
    origin = datetime(2024, 1, 2, tzinfo=UTC)
    event = _observation(
        "event",
        day=origin,
        outcome=0.02,
        is_event=True,
        cluster_id="event-cluster",
    )
    farther = _observation(
        "control-b",
        day=origin + timedelta(days=14),
        outcome=0.01,
        is_event=False,
        cluster_id="control-b",
    )
    nearer = _observation(
        "control-a",
        day=origin + timedelta(days=7),
        outcome=0.01,
        is_event=False,
        cluster_id="control-a",
    )
    as_of = farther.outcome_available_at

    result = match_event_controls(
        (farther, event, nearer),
        covariate_names=("weekday",),
        as_of=as_of,
    )

    assert result.pairs[0].control.observation_id == "control-a"
    with pytest.raises(DataError, match="declared covariate"):
        match_event_controls(
            (event, nearer),
            covariate_names=("volatility_regime",),
            as_of=as_of,
        )


def test_covariate_scalars_and_observation_invariants_fail_closed() -> None:
    observed = datetime(2024, 1, 2, tzinfo=UTC)
    with pytest.raises(DataError, match="non-empty"):
        PreEventCovariate("", "Tuesday", observed, observed)
    with pytest.raises(DataError, match="timezone-aware"):
        PreEventCovariate("weekday", "Tuesday", observed.replace(tzinfo=None), observed)
    with pytest.raises(DataError, match="cannot precede"):
        PreEventCovariate("weekday", "Tuesday", observed, observed - timedelta(seconds=1))
    with pytest.raises(DataError, match="non-empty"):
        PreEventCovariate("weekday", "", observed, observed)
    with pytest.raises(DataError, match="finite"):
        PreEventCovariate("volatility", float("nan"), observed, observed)
    with pytest.raises(DataError, match="scalar"):
        PreEventCovariate("regime", [], observed, observed)  # type: ignore[arg-type]

    assert PreEventCovariate("flag", True, observed, observed).matching_key == ("bool", "true")
    assert PreEventCovariate("count", 1, observed, observed).matching_key == ("int", "1")
    assert PreEventCovariate("value", 1.5, observed, observed).matching_key == ("float", "1.5")

    valid = _observation(
        "event",
        day=observed,
        outcome=0.01,
        is_event=True,
        cluster_id="cluster",
    )
    with pytest.raises(DataError, match="is_event"):
        replace(valid, is_event=1)  # type: ignore[arg-type]
    with pytest.raises(DataError, match="event availability"):
        replace(valid, event_available_at=valid.event_at - timedelta(seconds=1))
    with pytest.raises(DataError, match="outcome end"):
        replace(valid, outcome_end_at=valid.outcome_start_at)
    with pytest.raises(DataError, match="outcome must be finite"):
        replace(valid, outcome=float("inf"))
    with pytest.raises(DataError, match="immutable tuple"):
        replace(valid, covariates=list(valid.covariates))  # type: ignore[arg-type]
    with pytest.raises(DataError, match="names must be unique"):
        replace(valid, covariates=(valid.covariates[0], valid.covariates[0]))


def test_purging_matching_and_pair_construction_reject_invalid_inputs() -> None:
    origin = datetime(2024, 1, 2, tzinfo=UTC)
    event = _observation(
        "event",
        day=origin,
        outcome=0.02,
        is_event=True,
        cluster_id="event-cluster",
    )
    control = _observation(
        "control",
        day=origin + timedelta(days=7),
        outcome=0.01,
        is_event=False,
        cluster_id="control-cluster",
    )
    with pytest.raises(DataError, match="immutable tuple"):
        purge_overlapping_outcomes([event])  # type: ignore[arg-type]
    with pytest.raises(DataError, match="event observations only"):
        purge_overlapping_outcomes((control,))
    with pytest.raises(DataError, match="IDs must be unique"):
        purge_overlapping_outcomes((event, event))
    with pytest.raises(DataError, match="one event"):
        MatchedEventControlPair(event, event, ("weekday",))
    with pytest.raises(DataError, match="agree exactly"):
        MatchedEventControlPair(
            event,
            replace(control, covariates=(replace(control.covariates[0], value="Monday"),)),
            ("weekday",),
        )
    with pytest.raises(DataError, match="cannot overlap"):
        MatchedEventControlPair(
            event,
            replace(
                control,
                event_at=event.event_at,
                event_available_at=event.event_available_at,
                outcome_start_at=event.outcome_start_at,
                outcome_end_at=event.outcome_end_at,
                outcome_available_at=event.outcome_available_at,
                covariates=event.covariates,
            ),
            ("weekday",),
        )

    pair = MatchedEventControlPair(event, control, ("weekday",))
    study = MatchedEventStudy(
        as_of=control.outcome_available_at,
        covariate_names=("weekday",),
        pairs=(pair,),
        unmatched_event_ids=(),
        dropped_overlap_event_ids=(),
        not_yet_available_count=0,
    )
    assert study.effective_event_count == 1


def test_matching_failure_modes_and_unmatched_events_are_explicit() -> None:
    origin = datetime(2024, 1, 2, tzinfo=UTC)
    event = _observation(
        "event",
        day=origin,
        outcome=0.02,
        is_event=True,
        cluster_id="event-cluster",
    )
    control = _observation(
        "control",
        day=origin + timedelta(days=7),
        outcome=0.01,
        is_event=False,
        cluster_id="control-cluster",
    )
    as_of = control.outcome_available_at
    with pytest.raises(DataError, match="non-empty immutable"):
        match_event_controls([], covariate_names=("weekday",), as_of=as_of)  # type: ignore[arg-type]
    with pytest.raises(DataError, match="non-empty frozen"):
        match_event_controls((event, control), covariate_names=(), as_of=as_of)
    with pytest.raises(DataError, match="names must be unique"):
        match_event_controls(
            (event, control),
            covariate_names=("weekday", "weekday"),
            as_of=as_of,
        )
    with pytest.raises(DataError, match="IDs must be unique"):
        match_event_controls((event, event), covariate_names=("weekday",), as_of=as_of)
    with pytest.raises(DataError, match="at least one outcome-available event"):
        match_event_controls((control,), covariate_names=("weekday",), as_of=as_of)
    with pytest.raises(DataError, match="at least one outcome-available control"):
        match_event_controls((event,), covariate_names=("weekday",), as_of=as_of)

    monday_control = replace(control, covariates=(replace(control.covariates[0], value="Monday"),))
    unmatched = match_event_controls(
        (event, monday_control), covariate_names=("weekday",), as_of=as_of
    )
    assert unmatched.unmatched_event_ids == ("event",)


@pytest.mark.parametrize(
    ("values", "clusters", "confidence", "n_resamples", "seed", "message"),
    [
        ((), (), 0.95, 100, 7, "aligned non-empty"),
        ((0.1,), ("a", "b"), 0.95, 100, 7, "aligned non-empty"),
        ((float("nan"), 0.1), ("a", "b"), 0.95, 100, 7, "finite"),
        ((0.1, 0.2), ("a", "b"), 0.5, 100, 7, "confidence"),
        ((0.1, 0.2), ("a", "b"), 0.95, 99, 7, "n_resamples"),
        ((0.1, 0.2), ("a", "b"), 0.95, 100, -1, "seed"),
        ((0.1, 0.2), ("a", "a"), 0.95, 100, 7, "two effective"),
    ],
)
def test_cluster_bootstrap_rejects_invalid_inference_inputs(
    values: tuple[float, ...],
    clusters: tuple[str, ...],
    confidence: float,
    n_resamples: int,
    seed: int,
    message: str,
) -> None:
    with pytest.raises(DataError, match=message):
        _cluster_bootstrap_predictive_mean(
            values,
            clusters,
            confidence=confidence,
            n_resamples=n_resamples,
            seed=seed,
        )


def test_association_entrypoints_reject_wrong_populations() -> None:
    origin = datetime(2024, 1, 2, tzinfo=UTC)
    control = _observation(
        "control",
        day=origin,
        outcome=0.01,
        is_event=False,
        cluster_id="control",
    )
    with pytest.raises(DataError, match="non-empty immutable"):
        evaluate_event_association([], as_of=origin)  # type: ignore[arg-type]
    with pytest.raises(DataError, match="event observations only"):
        evaluate_event_association((control,), as_of=control.outcome_available_at)
    empty_matched = MatchedEventStudy(
        as_of=origin,
        covariate_names=("weekday",),
        pairs=(),
        unmatched_event_ids=(),
        dropped_overlap_event_ids=(),
        not_yet_available_count=0,
    )
    with pytest.raises(DataError, match="at least one matched pair"):
        evaluate_matched_association(empty_matched)

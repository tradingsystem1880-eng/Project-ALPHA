"""Event-study evaluation cannot see outcomes beyond its explicit as-of cutoff."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from alpha_research import EventStudyObservation, evaluate_event_association

pytestmark = pytest.mark.bias_guard


def _event(index: int) -> EventStudyObservation:
    event_at = datetime(2024, 1, 2, tzinfo=UTC) + index * timedelta(days=7)
    outcome_start = event_at + timedelta(hours=1)
    outcome_end = outcome_start + timedelta(hours=4)
    return EventStudyObservation(
        observation_id=f"event-{index}",
        is_event=True,
        event_at=event_at,
        event_available_at=event_at,
        outcome_start_at=outcome_start,
        outcome_end_at=outcome_end,
        outcome_available_at=outcome_end,
        outcome=0.01 + index / 1_000,
        cluster_id=f"week-{index}",
        covariates=(),
    )


def test_post_cutoff_outcome_poison_cannot_change_frozen_estimate() -> None:
    known = tuple(_event(index) for index in range(6))
    future = _event(20)
    cutoff = known[-1].outcome_available_at

    clean = evaluate_event_association((*known, future), as_of=cutoff, n_resamples=1_000, seed=7)
    poisoned = evaluate_event_association(
        (*known, replace(future, outcome=-9_999.0)),
        as_of=cutoff,
        n_resamples=1_000,
        seed=7,
    )

    assert clean.estimate == poisoned.estimate
    assert clean.standard_error == poisoned.standard_error
    assert clean.ci_lower == poisoned.ci_lower
    assert clean.ci_upper == poisoned.ci_upper
    assert clean.p_value == poisoned.p_value

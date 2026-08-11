"""Point-in-time-valid double-bottom detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from alpha_core import DataError
from alpha_research import (
    DoubleBottomSpec,
    EqualDurationResearchBars,
    ResearchBar,
    ResearchDatasetRef,
    detect_double_bottom_events,
)


def _bars(lows: list[float], *, strong_neckline: bool = True) -> EqualDurationResearchBars:
    dataset = ResearchDatasetRef(
        dataset_id="fixture",
        provider="fixture",
        provider_symbol="SPY",
        symbol="SPY",
        venue="XNYS",
        timeframe="4h",
        timezone="UTC",
        session="fixture",
        content_sha256="b" * 64,
    )
    start = datetime(2024, 1, 1, tzinfo=UTC)
    bars = tuple(
        ResearchBar(
            dataset_id="fixture",
            start=start + i * timedelta(hours=4),
            end=start + (i + 1) * timedelta(hours=4),
            available_at=start + (i + 1) * timedelta(hours=4),
            open=low + 2.0,
            high=low + (9.0 if strong_neckline and i == 4 else 2.5),
            low=low,
            close=low + 2.5,
            volume=1_000.0,
        )
        for i, low in enumerate(lows)
    )
    return EqualDurationResearchBars(dataset, bars)


_SPEC = DoubleBottomSpec(
    pivot_left=1,
    pivot_right=2,
    min_separation=3,
    max_separation=6,
    trough_tolerance=0.03,
    min_rebound=0.05,
)


def test_detector_waits_for_right_hand_confirmation_window() -> None:
    bars = _bars([101, 98, 95, 98, 100, 99, 95.5, 98, 99, 101])
    unconfirmed = _bars([101, 98, 95, 98, 100, 99, 95.5, 98])

    assert detect_double_bottom_events(unconfirmed, _SPEC) == ()
    events = detect_double_bottom_events(bars, _SPEC)

    assert len(events) == 1
    event = events[0]
    assert event.first_trough_index == 2
    assert event.second_trough_index == 6
    assert event.confirmation_index == 8
    assert event.confirmed_at == bars.bars[8].available_at
    assert event.rebound > _SPEC.min_rebound


def test_detector_is_greedy_and_emits_non_overlapping_pattern_windows() -> None:
    bars = _bars([101, 98, 95, 98, 100, 99, 95.5, 98, 99, 98, 95.2, 98, 100, 98, 95.3, 98, 99])
    events = detect_double_bottom_events(bars, _SPEC)

    assert len(events) == 2
    assert events[0].first_trough_index == 2
    assert events[0].confirmation_index == 8
    assert events[1].first_trough_index == 10
    assert events[1].confirmation_index == 16
    assert events[1].first_trough_index > events[0].confirmation_index


def test_detector_rejects_unstable_troughs_and_weak_rebounds() -> None:
    different_depth = _bars([101, 98, 95, 98, 100, 99, 89, 98, 99])
    weak_rebound = _bars([101, 98, 95, 96, 96, 97, 95.5, 98, 99], strong_neckline=False)

    assert detect_double_bottom_events(different_depth, _SPEC) == ()
    assert detect_double_bottom_events(weak_rebound, _SPEC) == ()


def test_double_bottom_spec_fails_loud_on_invalid_geometry() -> None:
    with pytest.raises(DataError, match="max_separation"):
        DoubleBottomSpec(
            pivot_left=1,
            pivot_right=1,
            min_separation=5,
            max_separation=4,
            trough_tolerance=0.03,
            min_rebound=0.05,
        )
    with pytest.raises(DataError, match="pivot_left"):
        DoubleBottomSpec(True, 1, 2, 4, 0.03, 0.05)
    with pytest.raises(DataError, match="min_rebound"):
        DoubleBottomSpec(1, 1, 2, 4, 0.03, 1.0)
    with pytest.raises(DataError, match="trough_tolerance"):
        DoubleBottomSpec(
            pivot_left=1,
            pivot_right=1,
            min_separation=2,
            max_separation=4,
            trough_tolerance=1.0,
            min_rebound=0.05,
        )

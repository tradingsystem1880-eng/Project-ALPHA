"""Future bars cannot alter already confirmed research pattern events."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from alpha_research import (
    DoubleBottomSpec,
    EqualDurationResearchBars,
    ResearchBar,
    ResearchDatasetRef,
    detect_double_bottom_events,
)

pytestmark = pytest.mark.bias_guard


def _collection(lows: list[float]) -> EqualDurationResearchBars:
    dataset = ResearchDatasetRef(
        dataset_id="future-poison",
        provider="fixture",
        provider_symbol="SPY",
        symbol="SPY",
        venue="XNYS",
        timeframe="4h",
        timezone="UTC",
        session="fixture",
        content_sha256="c" * 64,
    )
    origin = datetime(2024, 1, 1, tzinfo=UTC)
    return EqualDurationResearchBars(
        dataset,
        tuple(
            ResearchBar(
                dataset_id=dataset.dataset_id,
                start=origin + i * timedelta(hours=4),
                end=origin + (i + 1) * timedelta(hours=4),
                available_at=origin + (i + 1) * timedelta(hours=4),
                open=low + 2,
                high=low + (9 if i == 4 else 4),
                low=low,
                close=low + 2.5,
                volume=1_000,
            )
            for i, low in enumerate(lows)
        ),
    )


def test_post_confirmation_future_poison_cannot_change_confirmed_event() -> None:
    clean_lows = [101, 98, 95, 98, 100, 99, 95.5, 98, 99, 101, 102, 103]
    poisoned_lows = [*clean_lows[:9], 20, 200, 10]
    spec = DoubleBottomSpec(1, 2, 3, 6, 0.03, 0.05)

    clean = detect_double_bottom_events(_collection(clean_lows), spec)
    poisoned = detect_double_bottom_events(_collection(poisoned_lows), spec)

    assert clean[0] == poisoned[0]
    assert clean[0].confirmation_index == 8


def test_delayed_earlier_bar_moves_event_knowledge_time_forward() -> None:
    collection = _collection([101, 98, 95, 98, 100, 99, 95.5, 98, 99, 101])
    delayed_until = collection.bars[9].available_at + timedelta(hours=1)
    delayed_bars = (
        *collection.bars[:4],
        replace(collection.bars[4], available_at=delayed_until),
        *collection.bars[5:],
    )

    event = detect_double_bottom_events(
        EqualDurationResearchBars(collection.dataset, delayed_bars),
        DoubleBottomSpec(1, 2, 3, 6, 0.03, 0.05),
    )[0]

    assert event.confirmed_at == delayed_until
    assert event.confirmed_at > collection.bars[event.confirmation_index].available_at

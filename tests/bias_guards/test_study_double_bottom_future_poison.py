"""Future-poison guards for the generic double-bottom projection."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from alpha_research import (
    DoubleBottomSpec,
    EqualDurationResearchBars,
    ResearchBar,
    ResearchDatasetRef,
)
from alpha_research.artifacts import ResearchArtifactRef
from alpha_study import EventTableV1, adapt_double_bottom_events

pytestmark = pytest.mark.bias_guard
HASH = "b" * 64
SPEC = DoubleBottomSpec(1, 2, 3, 6, 0.03, 0.05)
LOWS = [101, 98, 95, 98, 100, 99, 95.5, 98, 99, 101]


def _bars(
    lows: list[float], *, future_available_at: datetime | None = None
) -> EqualDurationResearchBars:
    dataset = ResearchDatasetRef(
        dataset_id="study-future-poison",
        provider="fixture",
        provider_symbol="SPY",
        symbol="SPY",
        venue="XNYS",
        timeframe="4h",
        timezone="UTC",
        session="fixture",
        content_sha256=HASH,
    )
    origin = datetime(2024, 1, 1, tzinfo=UTC)
    bars = tuple(
        ResearchBar(
            dataset_id=dataset.dataset_id,
            start=origin + i * timedelta(hours=4),
            end=origin + (i + 1) * timedelta(hours=4),
            available_at=(
                future_available_at
                if future_available_at is not None and i >= len(LOWS)
                else origin + (i + 1) * timedelta(hours=4)
            ),
            open=low + 2,
            high=low + (9 if i == 4 else 4),
            low=low,
            close=low + 2.5,
            volume=1_000,
        )
        for i, low in enumerate(lows)
    )
    return EqualDurationResearchBars(dataset, bars)


def _artifact() -> ResearchArtifactRef:
    return ResearchArtifactRef("future-bars", "table", "application/json", HASH, 100, len(LOWS))


def _table(bars: EqualDurationResearchBars) -> EventTableV1:
    return adapt_double_bottom_events(
        bars,
        SPEC,
        study_id="study-double-bottom",
        input_artifact=_artifact(),
    )


def test_future_poison_cannot_change_confirmed_generic_rows() -> None:
    clean = _table(_bars(LOWS))
    poisoned = _table(_bars([*LOWS, 98, 95.2, 98, 100, 98, 95.3, 98, 99]))
    assert poisoned.rows[: len(clean.rows)] == clean.rows
    assert poisoned.rows[len(clean.rows) :] != ()


def test_delayed_future_bar_does_not_rewrite_prior_availability() -> None:
    cutoff = datetime(2024, 1, 3, tzinfo=UTC)
    clean = _table(_bars(LOWS))
    delayed = _table(_bars([*LOWS, 102], future_available_at=cutoff + timedelta(days=2)))
    assert clean.rows[0].available_at <= cutoff
    assert delayed.rows[0] == clean.rows[0]


def test_must_fail_leaky_twin_is_caught_by_the_guard() -> None:
    """A full-snapshot availability rewrite is the bug this guard must reject."""

    def leaky_table(bars: EqualDurationResearchBars) -> EventTableV1:
        table = _table(bars)
        if not table.rows:
            return table
        leaked_at = max(bar.available_at for bar in bars.bars)
        return EventTableV1(
            table.study_id,
            tuple(
                replace(row, available_at=leaked_at, content_sha256=None, event_id=None)
                for row in table.rows
            ),
        )

    clean = leaky_table(_bars(LOWS))
    poisoned = leaky_table(
        _bars([*LOWS, 102], future_available_at=datetime(2024, 1, 5, tzinfo=UTC))
    )
    assert poisoned.rows[:1] != clean.rows[:1]

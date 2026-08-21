"""Generic projection parity for the existing causal double-bottom operator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from alpha_core import DataError
from alpha_research import (
    DoubleBottomSpec,
    EqualDurationResearchBars,
    ResearchBar,
    ResearchDatasetRef,
    detect_double_bottom_events,
)
from alpha_research.artifacts import ResearchArtifactRef
from alpha_study import EventTableV1, adapt_double_bottom_events
from alpha_study._contracts import canonical_study_sha256

HASH = "a" * 64
SPEC = DoubleBottomSpec(1, 2, 3, 6, 0.03, 0.05)
LOWS = [101, 98, 95, 98, 100, 99, 95.5, 98, 99, 101]
PLANTED_LOWS = [
    105.0,
    103.0,
    100.0,
    95.0,
    99.0,
    101.0,
    100.0,
    95.5,
    99.0,
    101.0,
    *(102.0 + index for index in range(15)),
]
MONOTONIC_LOWS = [90.0 + index for index in range(25)]
SINGLE_TROUGH_LOWS = [105.0, 101.0, 95.0, 100.0, *(101.0 + index for index in range(21))]
D0_FIXTURE_DEFINITION = {
    "fixture": "spy_60m_double_bottom_v1",
    "fixture_version": 1,
    "planted_lows": PLANTED_LOWS,
    "monotonic_lows": MONOTONIC_LOWS,
    "single_trough_lows": SINGLE_TROUGH_LOWS,
}


def _bars(lows: list[float], *, delayed_index: int | None = None) -> EqualDurationResearchBars:
    dataset = ResearchDatasetRef(
        dataset_id="double-bottom-fixture",
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
    delayed_until = origin + timedelta(days=3)
    bars = tuple(
        ResearchBar(
            dataset_id=dataset.dataset_id,
            start=origin + i * timedelta(hours=4),
            end=origin + (i + 1) * timedelta(hours=4),
            available_at=(
                delayed_until
                if delayed_index is not None and i == delayed_index
                else origin + (i + 1) * timedelta(hours=4)
            ),
            open=low + 2.0,
            high=low + (9.0 if i == 4 else 2.5),
            low=low,
            close=low + 2.5,
            volume=1_000.0,
        )
        for i, low in enumerate(lows)
    )
    return EqualDurationResearchBars(dataset, bars)


def _artifact() -> ResearchArtifactRef:
    return ResearchArtifactRef(
        artifact_id="bars-fixture",
        kind="table",
        media_type="application/json",
        content_sha256=HASH,
        size_bytes=100,
        row_count=len(LOWS),
    )


def _d0_bars(
    lows: list[float], *, dataset_id: str, content_sha256: str
) -> EqualDurationResearchBars:
    dataset = ResearchDatasetRef(
        dataset_id=dataset_id,
        provider="alpha_synthetic_fixture",
        provider_symbol="SYNTHETIC_SPY",
        symbol="SPY",
        venue="SYNTHETIC",
        timeframe="60m",
        timezone="UTC",
        session="synthetic_equal_duration",
        content_sha256=content_sha256,
    )
    origin = datetime(2020, 1, 1, tzinfo=UTC)
    bars = tuple(
        ResearchBar(
            dataset_id=dataset.dataset_id,
            start=origin + i * timedelta(hours=1),
            end=origin + (i + 1) * timedelta(hours=1),
            available_at=origin + (i + 1) * timedelta(hours=1),
            open=low + 1.0,
            high=low + 6.0,
            low=low,
            close=low + 2.0,
            volume=1_000.0 + i,
        )
        for i, low in enumerate(lows)
    )
    return EqualDurationResearchBars(dataset, bars)


def _artifact_for(bars: EqualDurationResearchBars) -> ResearchArtifactRef:
    return ResearchArtifactRef(
        "d0-bars",
        "table",
        "application/json",
        bars.dataset.content_sha256,
        len(bars.bars),
        len(bars.bars),
    )


def test_projection_calls_legacy_operator_and_preserves_event_geometry() -> None:
    bars = _bars(LOWS)
    legacy = detect_double_bottom_events(bars, SPEC)
    table = adapt_double_bottom_events(
        bars,
        SPEC,
        study_id="study-double-bottom",
        input_artifact=_artifact(),
        asset_class="equity",
    )

    assert len(table.rows) == len(legacy) == 1
    row = table.rows[0]
    event = legacy[0]
    assert (row.event_start, row.event_end) == (event.first_trough_at, event.second_trough_at)
    assert row.printed_at == bars.bars[event.confirmation_index].end
    assert row.confirmed_at == row.available_at == event.confirmed_at
    assert row.operator_id == "double_bottom.v1"
    assert row.direction == 1
    assert {feature.feature_id for feature in row.features} == {
        "double_bottom.first_trough_index",
        "double_bottom.second_trough_index",
        "double_bottom.neckline",
        "double_bottom.rebound",
        "double_bottom.trough_difference",
    }
    assert EventTableV1.from_dict(table.to_dict()) == table


def test_negative_fixture_projects_no_events() -> None:
    bars = _bars([101, 98, 95, 98, 100, 99, 89, 98, 99])
    table = adapt_double_bottom_events(
        bars,
        SPEC,
        study_id="study-double-bottom",
        input_artifact=_artifact(),
    )
    assert table.rows == ()


@pytest.mark.parametrize(
    ("lows", "dataset_id", "content_sha256", "expected_count"),
    [
        (
            PLANTED_LOWS,
            "d0-planted",
            canonical_study_sha256(D0_FIXTURE_DEFINITION),
            1,
        ),
        (
            MONOTONIC_LOWS,
            "d0-monotonic",
            canonical_study_sha256(MONOTONIC_LOWS),
            0,
        ),
        (
            SINGLE_TROUGH_LOWS,
            "d0-single-trough",
            canonical_study_sha256(SINGLE_TROUGH_LOWS),
            0,
        ),
    ],
)
def test_exact_registered_d0_fixture_parity(
    lows: list[float], dataset_id: str, content_sha256: str, expected_count: int
) -> None:
    bars = _d0_bars(lows, dataset_id=dataset_id, content_sha256=content_sha256)
    legacy = detect_double_bottom_events(bars, SPEC)
    projected = adapt_double_bottom_events(
        bars, SPEC, study_id="d0-parity", input_artifact=_artifact_for(bars)
    )
    assert len(legacy) == len(projected.rows) == expected_count
    assert bars.dataset.dataset_id == dataset_id
    assert bars.dataset.content_sha256 == content_sha256
    if expected_count:
        event, row = legacy[0], projected.rows[0]
        assert (row.event_start, row.event_end, row.printed_at) == (
            event.first_trough_at,
            event.second_trough_at,
            bars.bars[event.confirmation_index].end,
        )
        assert row.confirmed_at == row.available_at == event.confirmed_at
        assert row.features[0].sources[0].provider == "alpha_synthetic_fixture"
        assert row.features[0].sources[0].frequency == "60m"


def test_delayed_input_moves_only_the_causal_availability_clock() -> None:
    baseline = adapt_double_bottom_events(
        _bars(LOWS), SPEC, study_id="study-double-bottom", input_artifact=_artifact()
    )
    delayed = adapt_double_bottom_events(
        _bars(LOWS, delayed_index=1),
        SPEC,
        study_id="study-double-bottom",
        input_artifact=_artifact(),
    )
    assert baseline.rows[0].event_id != delayed.rows[0].event_id
    assert delayed.rows[0].available_at == datetime(2024, 1, 4, tzinfo=UTC)
    assert all(
        feature.available_at == delayed.rows[0].available_at for feature in delayed.rows[0].features
    )


def test_invalid_lineage_fails_loud() -> None:
    with pytest.raises(DataError, match="input_artifact"):
        adapt_double_bottom_events(
            _bars(LOWS),
            SPEC,
            study_id="study-double-bottom",
            input_artifact=cast(ResearchArtifactRef, object()),
        )
    mismatched = ResearchArtifactRef(
        "other-bars", "table", "application/json", "f" * 64, 100, len(LOWS)
    )
    with pytest.raises(DataError, match="exact bar dataset"):
        adapt_double_bottom_events(
            _bars(LOWS), SPEC, study_id="study-double-bottom", input_artifact=mismatched
        )


def test_future_append_preserves_prior_projected_rows() -> None:
    clean = _bars(LOWS)
    extended = _bars([*LOWS, 102, 103])
    clean_table = adapt_double_bottom_events(
        clean, SPEC, study_id="study-double-bottom", input_artifact=_artifact()
    )
    extended_table = adapt_double_bottom_events(
        extended, SPEC, study_id="study-double-bottom", input_artifact=_artifact()
    )
    assert extended_table.rows[: len(clean_table.rows)] == clean_table.rows

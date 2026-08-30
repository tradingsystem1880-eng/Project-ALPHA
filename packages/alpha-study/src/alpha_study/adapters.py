"""Thin adapters from existing research operators to generic study contracts.

This module deliberately does not implement pattern detection or event-study statistics.  The
registered ``alpha_research`` operator remains the only source of truth; this package only binds
its output to the immutable generic table. The event-study bridge remains deferred until the
confirmation-bar versus full causal-availability mapping is resolved.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Literal

from alpha_core import DataError
from alpha_research import (
    DoubleBottomSpec,
    EqualDurationResearchBars,
    ResearchArtifactRef,
    detect_double_bottom_events,
)
from alpha_study._contracts import canonical_study_sha256
from alpha_study.authority import OperatorRegistrationV1
from alpha_study.tables import EventRowV1, EventTableV1
from alpha_study.values import FeatureInputRefV1, FeatureValueV1

AssetClass = Literal["equity", "etf", "future", "option", "fx", "crypto", "macro", "other"]


def _feature(
    *,
    feature_id: str,
    value: int | float,
    value_type: Literal["int", "float"],
    observed_at: datetime,
    available_at: datetime,
    source: FeatureInputRefV1,
    computation_sha256: str,
    unit: str,
) -> FeatureValueV1:
    return FeatureValueV1(
        feature_id=feature_id,
        role="geometry",
        value=value,
        value_type=value_type,
        observed_at=observed_at,
        available_at=available_at,
        vintage_at=observed_at,
        vintage_id=source.snapshot_id,
        sources=(source,),
        computation_sha256=computation_sha256,
        unit=unit,
        venue=source.venue,
    )


def adapt_double_bottom_events(
    bars: EqualDurationResearchBars,
    spec: DoubleBottomSpec,
    *,
    study_id: str,
    input_artifact: ResearchArtifactRef,
    asset_class: AssetClass = "other",
    entity_id: str | None = None,
    instrument_id: str | None = None,
) -> EventTableV1:
    """Project the existing causal double-bottom detector into ``EventTableV1``.

    ``input_artifact`` is an exact reference to the caller's qualified bar snapshot.  Each event
    source reference is available only when the bars used by that event are known, as reported by
    the existing detector's ``confirmed_at``.  No outcome or operational timestamp is introduced.
    """
    if not isinstance(bars, EqualDurationResearchBars):
        raise DataError("bars must be EqualDurationResearchBars")
    if not isinstance(spec, DoubleBottomSpec):
        raise DataError("spec must be DoubleBottomSpec")
    if not isinstance(input_artifact, ResearchArtifactRef):
        raise DataError("input_artifact must be a ResearchArtifactRef")
    if input_artifact.content_sha256 != bars.dataset.content_sha256:
        raise DataError("input_artifact must bind the exact bar dataset content hash")
    registration = OperatorRegistrationV1.from_registry("double_bottom.v1")
    parameter_sha256 = canonical_study_sha256(asdict(spec))
    clean_entity_id = entity_id or bars.dataset.symbol
    clean_instrument_id = instrument_id or bars.dataset.provider_symbol
    events = detect_double_bottom_events(bars, spec)
    rows: list[EventRowV1] = []
    for event in events:
        source = FeatureInputRefV1(
            artifact=input_artifact,
            input_available_at=event.confirmed_at,
            snapshot_id=bars.dataset.dataset_id,
            snapshot_manifest_sha256=bars.dataset.content_sha256,
            provider=bars.dataset.provider,
            data_family="research_bars",
            frequency=bars.dataset.timeframe,
            venue=bars.dataset.venue,
        )
        features = (
            _feature(
                feature_id="double_bottom.first_trough_index",
                value=event.first_trough_index,
                value_type="int",
                observed_at=event.first_trough_at,
                available_at=event.confirmed_at,
                source=source,
                computation_sha256=registration.implementation_code_sha256,
                unit="bar_index",
            ),
            _feature(
                feature_id="double_bottom.second_trough_index",
                value=event.second_trough_index,
                value_type="int",
                observed_at=event.second_trough_at,
                available_at=event.confirmed_at,
                source=source,
                computation_sha256=registration.implementation_code_sha256,
                unit="bar_index",
            ),
            _feature(
                feature_id="double_bottom.neckline",
                value=float(event.neckline),
                value_type="float",
                observed_at=event.second_trough_at,
                available_at=event.confirmed_at,
                source=source,
                computation_sha256=registration.implementation_code_sha256,
                unit="price",
            ),
            _feature(
                feature_id="double_bottom.rebound",
                value=float(event.rebound),
                value_type="float",
                observed_at=event.second_trough_at,
                available_at=event.confirmed_at,
                source=source,
                computation_sha256=registration.implementation_code_sha256,
                unit="ratio",
            ),
            _feature(
                feature_id="double_bottom.trough_difference",
                value=float(event.trough_difference),
                value_type="float",
                observed_at=event.second_trough_at,
                available_at=event.confirmed_at,
                source=source,
                computation_sha256=registration.implementation_code_sha256,
                unit="ratio",
            ),
        )
        rows.append(
            EventRowV1(
                study_id=study_id,
                entity_id=clean_entity_id,
                asset_class=asset_class,
                instrument_id=clean_instrument_id,
                venue=bars.dataset.venue,
                event_start=event.first_trough_at,
                event_end=event.second_trough_at,
                printed_at=bars.bars[event.confirmation_index].end,
                confirmed_at=event.confirmed_at,
                available_at=event.confirmed_at,
                direction=1,
                operator_id=registration.operator_id,
                operator_version=registration.operator_version,
                operator_code_sha256=registration.implementation_code_sha256,
                parameter_sha256=parameter_sha256,
                features=features,
                overlap_cluster_id=None,
                diagnostic_flags=(),
                parent_event_ids=(),
            )
        )
    return EventTableV1(study_id=study_id, rows=tuple(rows))


# Existing D1 constructs ``EventStudyObservation`` at the confirmation-bar anchor. That anchor
# can precede the detector's full causal ``confirmed_at`` when a left-pivot input is delayed, so
# the bridge is deliberately deferred rather than weakening either contract.
project_double_bottom_events = adapt_double_bottom_events

__all__ = [
    "adapt_double_bottom_events",
    "project_double_bottom_events",
]

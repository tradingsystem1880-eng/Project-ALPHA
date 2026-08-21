"""S3a event and factor table contract tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import cast

import pytest

from alpha_core import DataError
from alpha_research import ResearchArtifactRef
from alpha_study import (
    EventRowV1,
    EventTableV1,
    FactorObservationTableV1,
    FactorObservationV1,
    FeatureInputRefV1,
    FeatureValueV1,
)

HASH = "a" * 64
BASE = datetime(2026, 1, 1, 12, tzinfo=UTC)


def feature(
    *,
    feature_id: str = "factor.value",
    role: str = "factor",
    observed_at: datetime = BASE,
    available_at: datetime = BASE + timedelta(hours=2),
) -> FeatureValueV1:
    return FeatureValueV1(
        feature_id=feature_id,
        role=role,  # type: ignore[arg-type]
        value=1.5,
        value_type="float",
        observed_at=observed_at,
        available_at=available_at,
        vintage_at=BASE,
        vintage_id="v1",
        sources=(
            FeatureInputRefV1(
                artifact=ResearchArtifactRef("bars", "table", "application/json", HASH, 10, 1),
                input_available_at=BASE,
                snapshot_id="snap-1",
                snapshot_manifest_sha256=HASH,
                provider="tiingo",
                data_family="daily_bars",
                frequency="1d",
                venue="XNAS",
            ),
        ),
        computation_sha256=HASH,
        unit="score",
        venue="XNAS",
    )


def event(*, entity_id: str = "asset-1", start: datetime = BASE) -> EventRowV1:
    return EventRowV1(
        study_id="study-1",
        entity_id=entity_id,
        asset_class="equity",
        instrument_id="XNAS:ABC",
        venue="XNAS",
        event_start=start,
        event_end=start + timedelta(hours=1),
        printed_at=start + timedelta(hours=2),
        confirmed_at=start + timedelta(hours=3),
        available_at=start + timedelta(hours=3),
        direction=1,
        operator_id="operator.one",
        operator_version="1.0.0",
        operator_code_sha256=HASH,
        parameter_sha256=HASH,
        features=(feature(),),
        overlap_cluster_id=None,
        diagnostic_flags=("warning",),
        parent_event_ids=(),
    )


def factor(*, entity_id: str = "asset-1") -> FactorObservationV1:
    return FactorObservationV1(
        study_id="study-1",
        entity_id=entity_id,
        instrument_id="XNAS:ABC",
        factor_id="factor.value",
        cross_section_at=BASE,
        observed_at=BASE + timedelta(hours=1),
        available_at=BASE + timedelta(hours=2),
        universe_snapshot_id="universe-1",
        universe_snapshot_sha256=HASH,
        universe_available_at=BASE + timedelta(hours=1),
        value=feature(observed_at=BASE + timedelta(hours=1)),
    )


def test_event_round_trip_and_semantic_mutation_hash() -> None:
    row = event()
    assert EventRowV1.from_dict(row.to_dict()) == row
    assert cast(str, row.event_id).startswith("ev_")
    changed = event(entity_id="asset-2")
    assert changed.content_sha256 != row.content_sha256
    assert changed.event_id != row.event_id


def test_event_clocks_and_feature_availability_fail_closed() -> None:
    with pytest.raises(DataError):
        replace(event(), event_end=BASE - timedelta(seconds=1))
    with pytest.raises(DataError):
        EventRowV1.from_dict({**event().to_dict(), "available_at": BASE.isoformat()})
    with pytest.raises(DataError):
        replace(event(), asset_class=cast(object, {}))  # type: ignore[arg-type]
    with pytest.raises(DataError):
        replace(event(), direction=cast(int, {}))


def test_event_strict_hash_and_outcome_rejection() -> None:
    row = event()
    stale = row.to_dict()
    stale["event_id"] = "ev_" + "b" * 64
    with pytest.raises(DataError):
        EventRowV1.from_dict(stale)
    outcome = row.to_dict()
    outcome["outcome"] = {"return": 1.0}
    with pytest.raises(DataError):
        EventRowV1.from_dict(outcome)
    claimed = row.to_dict()
    claimed["authority"] = "verified"
    with pytest.raises(DataError):
        EventRowV1.from_dict(claimed)


def test_event_table_is_order_independent_and_rejects_duplicates_or_mismatch() -> None:
    first, second = event(), event(entity_id="asset-2")
    assert EventTableV1("study-1", (second, first)) == EventTableV1("study-1", (first, second))
    with pytest.raises(DataError):
        EventTableV1("study-1", (first, first))
    with pytest.raises(DataError):
        EventTableV1("study-2", (first,))
    assert EventTableV1.from_dict(EventTableV1("study-1", ()).to_dict()).rows == ()


def test_event_timezone_equivalence_and_canonical_children() -> None:
    shifted = event(
        start=BASE.astimezone(timezone(timedelta(hours=-4))),
    )
    assert shifted.event_id == event().event_id
    with pytest.raises(DataError):
        EventRowV1.from_dict({**event().to_dict(), "diagnostic_flags": ["warning", "warning"]})


def test_factor_round_trip_separation_and_hash() -> None:
    row = factor()
    assert FactorObservationV1.from_dict(row.to_dict()) == row
    assert cast(str, row.observation_id).startswith("fo_")
    changed = factor(entity_id="asset-2")
    assert changed.content_sha256 != row.content_sha256
    assert "event_start" not in row.to_dict()
    event_payload = event().to_dict()
    with pytest.raises(DataError):
        FactorObservationV1.from_dict(event_payload)


def test_factor_identity_clocks_and_factor_role_are_closed() -> None:
    with pytest.raises(DataError):
        replace(factor(), value=object())  # type: ignore[arg-type]
    with pytest.raises(DataError):
        replace(factor(), factor_id="different")
    with pytest.raises(DataError):
        replace(factor(), universe_available_at=BASE + timedelta(days=1))
    bad = factor().to_dict()
    bad_value = cast(dict[str, object], bad["value"])
    bad["value"] = {**bad_value, "role": "state"}
    with pytest.raises(DataError):
        FactorObservationV1.from_dict(bad)


def test_factor_table_order_duplicates_and_stale_hash() -> None:
    first, second = factor(), factor(entity_id="asset-2")
    table = FactorObservationTableV1("study-1", (second, first))
    assert table.rows == tuple(
        sorted((first, second), key=lambda row: cast(str, row.observation_id))
    )
    assert FactorObservationTableV1.from_dict(table.to_dict()) == table
    with pytest.raises(DataError):
        FactorObservationTableV1("study-1", (first, first))
    same_economic_key = replace(
        first,
        value=replace(first.value, value=2.0),
        content_sha256=None,
        observation_id=None,
    )
    with pytest.raises(DataError):
        FactorObservationTableV1("study-1", (first, same_economic_key))
    stale = table.to_dict()
    stale["content_sha256"] = "f" * 64
    with pytest.raises(DataError):
        FactorObservationTableV1.from_dict(stale)

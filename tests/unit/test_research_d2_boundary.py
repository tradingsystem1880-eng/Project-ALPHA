"""Canonical D2 boundaries bind the exact eligible evidence allocation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

from alpha_core import DataError
from alpha_research import (
    ResearchChartFingerprintV1,
    ResearchD2BoundaryV1,
    ResearchEvidenceSharesV1,
    ResearchEvidenceZoneBoundaryV1,
)

DATASET_SHA = "1" * 64
GROUPS = tuple(f"2026-01-{day:02d}|RTH" for day in range(1, 11))


def _chart() -> ResearchChartFingerprintV1:
    return ResearchChartFingerprintV1(
        instrument="SPY",
        provider="licensed-provider",
        venue="ARCX",
        timezone="America/New_York",
        session="regular_hours",
        bar_construction="fixed_60_trading_minute_bars",
        bar_duration_seconds=3_600,
        anchor="09:30 America/New_York",
        adjustment_basis="point_in_time_split_and_dividend",
        timestamp_semantics="bar_close_available",
    )


def _boundary(
    *,
    groups: tuple[str, ...] = GROUPS,
    dataset_fingerprint: str = DATASET_SHA,
    chart: ResearchChartFingerprintV1 | None = None,
    event_formula: str = "confirmable second trough within 0.5 percent of first trough",
    event_availability_timestamp: str = "second_trough_bar_close",
    primary_endpoint: str = "event_minus_matched_control_arithmetic_return",
    primary_horizon: str = "240_trading_minutes",
    outcome_overlap_embargo_groups: int = 1,
    shares: ResearchEvidenceSharesV1 | None = None,
) -> ResearchD2BoundaryV1:
    return ResearchD2BoundaryV1.from_eligible_groups(
        dataset_fingerprint=dataset_fingerprint,
        eligible_groups=groups,
        chart_fingerprint=chart or _chart(),
        event_formula=event_formula,
        event_availability_timestamp=event_availability_timestamp,
        primary_endpoint=primary_endpoint,
        primary_horizon=primary_horizon,
        outcome_overlap_embargo_groups=outcome_overlap_embargo_groups,
        shares=shares or ResearchEvidenceSharesV1(),
    )


def test_default_boundary_binds_exact_chronological_60_20_20_membership() -> None:
    boundary = _boundary()

    assert boundary.shares.to_dict() == {"D0": 0, "D1": 60, "D2": 20, "D3": 20}
    assert (boundary.d0.start_index, boundary.d0.stop_index) == (0, 0)
    assert (boundary.d1.start_index, boundary.d1.stop_index) == (0, 6)
    assert (boundary.d2.start_index, boundary.d2.stop_index) == (6, 8)
    assert (boundary.d3.start_index, boundary.d3.stop_index) == (8, 10)
    assert boundary.d2.group_count == 2
    assert boundary.d3.group_count == 2
    assert boundary.verify_eligible_groups(GROUPS)
    assert not boundary.verify_eligible_groups(tuple(reversed(GROUPS)))
    assert len(boundary.eligible_group_hashes) == len(GROUPS)
    assert len(boundary.boundary_sha256) == 64


def test_boundary_is_deterministic_and_round_trips_with_internal_hash_verification() -> None:
    first = _boundary()
    second = _boundary()

    assert first == second
    assert first.boundary_sha256 == second.boundary_sha256
    assert ResearchD2BoundaryV1.from_dict(first.to_dict()) == first
    assert first.to_dict()["boundary_sha256"] == first.boundary_sha256
    assert first.chart_fingerprint.fingerprint_sha256 == _chart().fingerprint_sha256


@pytest.mark.parametrize(
    "chart",
    [
        replace(_chart(), instrument="ES"),
        replace(_chart(), provider="other-licensed-provider"),
        replace(_chart(), venue="CME"),
        replace(_chart(), timezone="UTC"),
        replace(_chart(), session="extended_hours"),
        replace(_chart(), bar_construction="fixed_240_elapsed_minute_bars"),
        replace(_chart(), bar_duration_seconds=14_400),
        replace(_chart(), anchor="04:00 America/New_York"),
        replace(_chart(), adjustment_basis="unadjusted_point_in_time"),
        replace(_chart(), timestamp_semantics="next_bar_open_available"),
    ],
)
def test_each_chart_semantic_changes_both_chart_and_boundary_fingerprints(
    chart: ResearchChartFingerprintV1,
) -> None:
    assert chart.fingerprint_sha256 != _chart().fingerprint_sha256
    assert _boundary(chart=chart).boundary_sha256 != _boundary().boundary_sha256


@pytest.mark.parametrize(
    ("name", "changed"),
    [
        ("dataset", lambda: _boundary(dataset_fingerprint="2" * 64)),
        ("allocation", lambda: _boundary(groups=GROUPS[:6] + (GROUPS[7], GROUPS[6]) + GROUPS[8:])),
        (
            "chart",
            lambda: _boundary(
                chart=replace(_chart(), timestamp_semantics="next_bar_open_available")
            ),
        ),
        ("event formula", lambda: _boundary(event_formula="neckline breakout")),
        ("availability", lambda: _boundary(event_availability_timestamp="neckline_breakout_close")),
        ("endpoint", lambda: _boundary(primary_endpoint="raw_forward_return")),
        ("horizon", lambda: _boundary(primary_horizon="next_regular_session")),
        ("embargo", lambda: _boundary(outcome_overlap_embargo_groups=2)),
        (
            "shares",
            lambda: _boundary(
                shares=ResearchEvidenceSharesV1(d1_percent=50, d2_percent=20, d3_percent=30)
            ),
        ),
    ],
)
def test_every_required_semantic_dimension_changes_the_boundary_hash(
    name: str,
    changed: Callable[[], ResearchD2BoundaryV1],
) -> None:
    del name
    assert changed().boundary_sha256 != _boundary().boundary_sha256


def test_deserialization_rejects_an_arbitrary_hash_and_in_place_semantic_mutation() -> None:
    payload = _boundary().to_dict()
    payload["boundary_sha256"] = "f" * 64
    with pytest.raises(DataError, match="boundary_sha256 does not match"):
        ResearchD2BoundaryV1.from_dict(payload)

    payload = _boundary().to_dict()
    payload["schema_version"] = True
    with pytest.raises(DataError, match="schema_version"):
        ResearchD2BoundaryV1.from_dict(payload)

    payload = _boundary().to_dict()
    event = payload["event_definition"]
    assert isinstance(event, dict)
    event["formula"] = "mutated after owner approval"
    with pytest.raises(DataError, match="boundary_sha256 does not match"):
        ResearchD2BoundaryV1.from_dict(payload)


def test_deserialization_rejects_forged_derived_zone_boundaries_before_hash_check() -> None:
    payload = _boundary().to_dict()
    zones = payload["zones"]
    assert isinstance(zones, dict)
    d2 = zones["D2"]
    assert isinstance(d2, dict)
    d2["start_index"] = 5

    with pytest.raises(DataError, match="D2"):
        ResearchD2BoundaryV1.from_dict(payload)


def test_boundary_and_nested_contracts_are_frozen() -> None:
    boundary = _boundary()
    with pytest.raises(FrozenInstanceError):
        boundary.primary_horizon = "mutated"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        boundary.chart_fingerprint.session = "extended_hours"  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"d0_percent": 1, "d1_percent": 59, "d2_percent": 20, "d3_percent": 20},
        {"d1_percent": 61, "d2_percent": 20, "d3_percent": 19},
        {"d1_percent": 60, "d2_percent": 19, "d3_percent": 20},
    ],
)
def test_invalid_evidence_shares_fail_closed(kwargs: dict[str, int]) -> None:
    with pytest.raises(DataError, match="ResearchEvidenceSharesV1"):
        ResearchEvidenceSharesV1(**kwargs)


def test_invalid_group_and_boundary_inputs_fail_closed() -> None:
    with pytest.raises(DataError, match="at least 5"):
        _boundary(groups=GROUPS[:4])
    with pytest.raises(DataError, match="unique"):
        _boundary(groups=GROUPS[:-1] + (GROUPS[0],))
    with pytest.raises(DataError, match="dataset_fingerprint"):
        _boundary(dataset_fingerprint="caller-label")
    with pytest.raises(DataError, match="outcome_overlap_embargo_groups"):
        _boundary(outcome_overlap_embargo_groups=-1)


def test_chart_fingerprint_requires_exact_construction_and_timestamp_semantics() -> None:
    with pytest.raises(DataError, match="bar_duration_seconds"):
        replace(_chart(), bar_duration_seconds=0)
    with pytest.raises(DataError, match="timestamp_semantics"):
        replace(_chart(), timestamp_semantics=" ")


def test_boundary_text_mapping_and_schema_validation_fail_closed() -> None:
    with pytest.raises(DataError, match="control characters"):
        replace(_chart(), instrument="SPY\x01X")
    payload = _boundary().to_dict()
    payload["eligible_groups"] = []
    with pytest.raises(DataError, match="must be an object"):
        ResearchD2BoundaryV1.from_dict(payload)
    payload = _boundary().to_dict()
    payload["unexpected"] = True
    with pytest.raises(DataError, match="unexpected or missing"):
        ResearchD2BoundaryV1.from_dict(payload)

    chart = _chart().to_dict()
    chart["schema"] = "ResearchChartFingerprintV2"
    with pytest.raises(DataError, match="unsupported ResearchChartFingerprintV1"):
        ResearchChartFingerprintV1.from_dict(chart)
    chart = _chart().to_dict()
    chart["instrument"] = "ES"
    with pytest.raises(DataError, match="fingerprint_sha256"):
        ResearchChartFingerprintV1.from_dict(chart)


def test_zone_contract_rejects_invalid_zone_and_endpoint_shapes() -> None:
    with pytest.raises(DataError, match="unsupported research evidence zone"):
        ResearchEvidenceZoneBoundaryV1(
            zone="X",  # type: ignore[arg-type]
            share_percent=0,
            start_index=0,
            stop_index=0,
            group_count=0,
            membership_sha256="a" * 64,
            first_group_sha256=None,
            last_group_sha256=None,
        )
    with pytest.raises(DataError, match="empty D0"):
        ResearchEvidenceZoneBoundaryV1(
            zone="D0",
            share_percent=0,
            start_index=0,
            stop_index=0,
            group_count=0,
            membership_sha256="a" * 64,
            first_group_sha256="b" * 64,
            last_group_sha256="b" * 64,
        )
    with pytest.raises(DataError, match="non-empty D1"):
        ResearchEvidenceZoneBoundaryV1(
            zone="D1",
            share_percent=60,
            start_index=0,
            stop_index=1,
            group_count=1,
            membership_sha256="a" * 64,
            first_group_sha256=None,
            last_group_sha256=None,
        )
    zone = _boundary().d1.to_dict()
    zone["zone"] = "X"
    with pytest.raises(DataError, match="unsupported research evidence zone"):
        ResearchEvidenceZoneBoundaryV1.from_dict(zone)


def test_boundary_constructor_rejects_invalid_nested_types_and_empty_allocations() -> None:
    baseline = _boundary()
    common: dict[str, Any] = {
        "dataset_fingerprint": baseline.dataset_fingerprint,
        "event_formula": baseline.event_formula,
        "event_availability_timestamp": baseline.event_availability_timestamp,
        "primary_endpoint": baseline.primary_endpoint,
        "primary_horizon": baseline.primary_horizon,
        "outcome_overlap_embargo_groups": baseline.outcome_overlap_embargo_groups,
    }
    with pytest.raises(DataError, match="eligible groups must be unique"):
        ResearchD2BoundaryV1(
            **common,
            eligible_group_hashes=baseline.eligible_group_hashes[:-1]
            + (baseline.eligible_group_hashes[0],),
            chart_fingerprint=baseline.chart_fingerprint,
        )
    with pytest.raises(DataError, match="chart_fingerprint has the wrong type"):
        ResearchD2BoundaryV1(
            **common,
            eligible_group_hashes=baseline.eligible_group_hashes,
            chart_fingerprint={},  # type: ignore[arg-type]
        )
    with pytest.raises(DataError, match="shares has the wrong type"):
        ResearchD2BoundaryV1(
            **common,
            eligible_group_hashes=baseline.eligible_group_hashes,
            chart_fingerprint=baseline.chart_fingerprint,
            shares={},  # type: ignore[arg-type]
        )
    with pytest.raises(DataError, match="leaves D1, D2, or D3 empty"):
        _boundary(
            groups=GROUPS[:5],
            shares=ResearchEvidenceSharesV1(d1_percent=1, d2_percent=1, d3_percent=98),
        )
    with pytest.raises(DataError, match="D1 and D2 must be positive"):
        ResearchEvidenceSharesV1(d1_percent=0, d2_percent=80, d3_percent=20)
    with pytest.raises(DataError, match="ordered sequence"):
        ResearchD2BoundaryV1.from_eligible_groups(
            dataset_fingerprint=DATASET_SHA,
            eligible_groups="not-a-sequence",
            chart_fingerprint=_chart(),
            event_formula="formula",
            event_availability_timestamp="event close",
            primary_endpoint="return",
            primary_horizon="one session",
            outcome_overlap_embargo_groups=0,
        )
    with pytest.raises(DataError, match="ordered sequence"):
        baseline.verify_eligible_groups("not-a-sequence")
    assert baseline.contract_hash == baseline.boundary_sha256


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("schema", "unsupported ResearchD2BoundaryV1"),
        ("allocation", "allocation_rule"),
        ("hash_array", "must be an array"),
        ("count", "count does not match"),
        ("overlap_unit", "must be eligible_group"),
        ("ordered_hash", "ordered_groups_sha256"),
        ("zone", "serialized derived D2"),
    ],
)
def test_boundary_deserialization_recomputes_every_derived_commitment(
    mutation: str, message: str
) -> None:
    payload = _boundary().to_dict()
    eligible = payload["eligible_groups"]
    overlap = payload["outcome_overlap_embargo"]
    zones = payload["zones"]
    assert isinstance(eligible, dict)
    assert isinstance(overlap, dict)
    assert isinstance(zones, dict)
    if mutation == "schema":
        payload["schema"] = "ResearchD2BoundaryV2"
    elif mutation == "allocation":
        payload["allocation_rule"] = "caller_selected"
    elif mutation == "hash_array":
        eligible["ordered_group_hashes"] = tuple(eligible["ordered_group_hashes"])
    elif mutation == "count":
        eligible["count"] = 999
    elif mutation == "overlap_unit":
        overlap["unit"] = "bar"
    elif mutation == "ordered_hash":
        eligible["ordered_groups_sha256"] = "f" * 64
    else:
        d2 = zones["D2"]
        assert isinstance(d2, dict)
        d2["membership_sha256"] = "f" * 64
    with pytest.raises(DataError, match=message):
        ResearchD2BoundaryV1.from_dict(payload)

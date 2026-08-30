"""Strict byte-bound blind semantic-read projection tests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from alpha_core import DataError
from alpha_research._canonical import canonical_sha256
from alpha_study import (
    BlindSemanticProjectionV1,
    SemanticPointV1,
    normalize_semantic_event,
    project_blind_semantic_read,
)

HASH = "a" * 64
RUN_ID = "0123456789abcdef"
BASE = datetime(2024, 1, 1, tzinfo=UTC)


def _event(*, confirmed_at: datetime = BASE + timedelta(hours=8)) -> dict[str, object]:
    return {
        "first_trough_index": 2,
        "second_trough_index": 6,
        "confirmation_index": 8,
        "first_trough_at": (BASE + timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
        "second_trough_at": (BASE + timedelta(hours=7)).isoformat().replace("+00:00", "Z"),
        "confirmed_at": confirmed_at.isoformat().replace("+00:00", "Z"),
        "neckline": 109.0,
        "trough_difference": 0.005,
        "rebound": 0.1,
    }


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _artifacts(
    *,
    acceptance_events: list[dict[str, object]] | None = None,
    events: list[dict[str, object]] | None = None,
    chart_events: list[dict[str, object]] | None = None,
    chart_points: list[dict[str, object]] | None = None,
) -> tuple[bytes, bytes, bytes]:
    accepted = _event()
    acceptance = {
        "schema": "ResearchD0AcceptanceV1",
        "schema_version": 1,
        "run_id": RUN_ID,
        "project_id": "11111111-1111-4111-8111-111111111111",
        "research_contract_id": "rc_" + "b" * 64,
        "contract_hash": HASH,
        "dataset_hash": HASH,
        "execution_fingerprint": HASH,
        "d0_operator_fingerprint": HASH,
        "fixture_id": "alpha_synthetic_fixture",
        "fixture_version": "v1",
        "evidence_zone": "D0",
        "real_market_evidence": False,
        "eligible_for_holdout_or_execution": False,
        "measurements": {
            "planted_events": acceptance_events if acceptance_events is not None else [accepted],
            "monotonic_event_count": 0,
            "single_trough_event_count": 0,
            "topology": {
                "contract_hash": HASH,
                "forward_outcome_observations": 4,
                "rejected_boundaries": ["D1_D2", "D2_D3"],
            },
            "power": {
                "alternative_effect": 0.1,
                "minimum_effect": 0.05,
                "standard_deviation": 0.2,
                "alpha": 0.05,
                "target_power": 0.9,
                "required_observations": 10,
                "simulations": 20_000,
                "seed": 7,
                "estimated_power": 0.9,
            },
        },
    }
    chart = {
        "artifact_id": "detector-validity-series",
        "artifact_sha256": "0" * 64,
        "caveat": "synthetic",
        "chart_id": "detector-validity",
        "dataset_sha256": HASH,
        "evidence_phase": "exploratory",
        "effective_sample_size": 1.0,
        "events": chart_events if chart_events is not None else [accepted],
        "plain_language_answer": "mechanics only",
        "protocol_sha256": HASH,
        "question": "timing",
        "run_id": RUN_ID,
        "sample_size": 2,
        "schema_version": 1,
        "series": [
            {
                "label": "Synthetic low",
                "points": chart_points
                if chart_points is not None
                else [
                    {
                        "ts": (BASE + timedelta(hours=7)).isoformat().replace("+00:00", "Z"),
                        "value": 1.0,
                    },
                    {
                        "ts": (BASE + timedelta(hours=9)).isoformat().replace("+00:00", "Z"),
                        "value": 2.0,
                    },
                ],
                "series_id": "synthetic-low",
                "unit": "price",
            }
        ],
        "title": "timing",
        "uncertainty": "none",
        "watermark": "EXPLORATORY",
        "x_label": "time",
        "y_label": "value",
    }
    series = chart["series"]
    assert isinstance(series, list)
    chart["artifact_sha256"] = canonical_sha256(series[0])
    return _json(acceptance), _json(events if events is not None else [accepted]), _json(chart)


def _projection() -> BlindSemanticProjectionV1:
    acceptance, events, chart = _artifacts()
    return project_blind_semantic_read(
        acceptance_bytes=acceptance,
        events_bytes=events,
        chart_data_bytes=chart,
    )


def test_projection_is_byte_bound_masks_points_and_round_trips() -> None:
    acceptance, events, chart = _artifacts()
    value = project_blind_semantic_read(
        acceptance_bytes=acceptance,
        events_bytes=events,
        chart_data_bytes=chart,
    )
    assert value.cutoff_source == "d0_acceptance_measurement_reference"
    assert value.cutoff_confirmed_at == BASE + timedelta(hours=8)
    assert [point.point_id for point in value.visible_points] == ["synthetic-low:0"]
    assert value.masked_count == 1
    assert value.authority == "none"
    assert value.semantic_status == "unfrozen"
    assert value.lineage_verification == "not_checked"
    assert "synthetic-low:1" not in str(value.to_dict())
    assert value.acceptance_artifact_sha256 == hashlib.sha256(acceptance).hexdigest()
    assert BlindSemanticProjectionV1.from_dict(value.to_dict()) == value


def test_event_identity_and_clock_must_match_all_three_sources() -> None:
    acceptance, events, chart = _artifacts(events=[{**_event(), "confirmation_index": 9}])
    with pytest.raises(DataError, match="events event identity or clocks"):
        project_blind_semantic_read(
            acceptance_bytes=acceptance, events_bytes=events, chart_data_bytes=chart
        )
    acceptance, events, chart = _artifacts(
        chart_events=[_event(confirmed_at=BASE + timedelta(hours=9))]
    )
    with pytest.raises(DataError, match="chart-data event identity or clocks"):
        project_blind_semantic_read(
            acceptance_bytes=acceptance, events_bytes=events, chart_data_bytes=chart
        )


@pytest.mark.parametrize("which", ["acceptance_events", "events", "chart_events"])
def test_event_collections_require_exactly_one_event(which: str) -> None:
    if which == "acceptance_events":
        acceptance, events, chart = _artifacts(acceptance_events=[])
    elif which == "events":
        acceptance, events, chart = _artifacts(events=[])
    else:
        acceptance, events, chart = _artifacts(chart_events=[])
    with pytest.raises(DataError, match="exactly one event"):
        project_blind_semantic_read(
            acceptance_bytes=acceptance, events_bytes=events, chart_data_bytes=chart
        )
    if which == "acceptance_events":
        acceptance, events, chart = _artifacts(acceptance_events=[_event(), _event()])
    elif which == "events":
        acceptance, events, chart = _artifacts(events=[_event(), _event()])
    else:
        acceptance, events, chart = _artifacts(chart_events=[_event(), _event()])
    with pytest.raises(DataError, match="exactly one event"):
        project_blind_semantic_read(
            acceptance_bytes=acceptance, events_bytes=events, chart_data_bytes=chart
        )


def test_duplicate_keys_extra_fields_and_tampered_bytes_fail_loud() -> None:
    acceptance, events, chart = _artifacts()
    duplicate = b'[{"first_trough_index":2,"first_trough_index":2}]'
    with pytest.raises(DataError, match="duplicate JSON key"):
        project_blind_semantic_read(
            acceptance_bytes=acceptance, events_bytes=duplicate, chart_data_bytes=chart
        )
    acceptance_map = json.loads(acceptance)
    acceptance_map["unexpected"] = True
    with pytest.raises(DataError, match="keys are not exact"):
        project_blind_semantic_read(
            acceptance_bytes=_json(acceptance_map), events_bytes=events, chart_data_bytes=chart
        )
    changed_event = {
        **_event(),
        "confirmed_at": (BASE + timedelta(hours=9)).isoformat().replace("+00:00", "Z"),
    }
    changed_events = _json([changed_event])
    with pytest.raises(DataError, match="events event identity or clocks"):
        project_blind_semantic_read(
            acceptance_bytes=acceptance, events_bytes=changed_events, chart_data_bytes=chart
        )


def test_complete_measurements_and_internal_chart_provenance_are_required() -> None:
    acceptance, events, chart = _artifacts()
    acceptance_map = json.loads(acceptance)
    del acceptance_map["measurements"]["power"]
    with pytest.raises(DataError, match="measurements keys are not exact"):
        project_blind_semantic_read(
            acceptance_bytes=_json(acceptance_map), events_bytes=events, chart_data_bytes=chart
        )

    chart_map = json.loads(chart)
    chart_map["artifact_sha256"] = "f" * 64
    with pytest.raises(DataError, match="artifact_sha256 does not match its series"):
        project_blind_semantic_read(
            acceptance_bytes=acceptance, events_bytes=events, chart_data_bytes=_json(chart_map)
        )

    chart_map = json.loads(chart)
    chart_map["dataset_sha256"] = "b" * 64
    with pytest.raises(DataError, match="dataset provenance"):
        project_blind_semantic_read(
            acceptance_bytes=acceptance, events_bytes=events, chart_data_bytes=_json(chart_map)
        )


def test_chart_points_must_preserve_strict_source_order() -> None:
    acceptance, events, chart = _artifacts(
        chart_points=[
            {"ts": (BASE + timedelta(hours=9)).isoformat().replace("+00:00", "Z"), "value": 2.0},
            {"ts": (BASE + timedelta(hours=7)).isoformat().replace("+00:00", "Z"), "value": 1.0},
        ]
    )
    with pytest.raises(DataError, match="strictly increasing"):
        project_blind_semantic_read(
            acceptance_bytes=acceptance, events_bytes=events, chart_data_bytes=chart
        )


@pytest.mark.parametrize("value", [True, 1, "1", float("nan"), float("inf")])
def test_semantic_points_require_finite_real_float_values(value: object) -> None:
    with pytest.raises(DataError, match="finite float"):
        SemanticPointV1(point_id="p", available_at=BASE, value=cast(float, value))


def test_projection_children_are_typed_unique_and_canonically_ordered() -> None:
    point_a = SemanticPointV1(point_id="a", available_at=BASE, value=1.0)
    point_b = SemanticPointV1(point_id="b", available_at=BASE + timedelta(hours=1), value=2.0)
    with pytest.raises(DataError, match="canonical availability"):
        BlindSemanticProjectionV1(
            run_id=RUN_ID,
            acceptance_artifact_sha256=HASH,
            events_artifact_sha256=HASH,
            chart_data_artifact_sha256=HASH,
            cutoff_confirmed_at=BASE + timedelta(hours=2),
            visible_points=(point_b, point_a),
            masked_count=0,
        )
    with pytest.raises(DataError, match="unique"):
        BlindSemanticProjectionV1(
            run_id=RUN_ID,
            acceptance_artifact_sha256=HASH,
            events_artifact_sha256=HASH,
            chart_data_artifact_sha256=HASH,
            cutoff_confirmed_at=BASE + timedelta(hours=2),
            visible_points=(point_a, point_a),
            masked_count=0,
        )
    with pytest.raises(DataError, match="only SemanticPointV1"):
        BlindSemanticProjectionV1(
            run_id=RUN_ID,
            acceptance_artifact_sha256=HASH,
            events_artifact_sha256=HASH,
            chart_data_artifact_sha256=HASH,
            cutoff_confirmed_at=BASE + timedelta(hours=2),
            visible_points=cast(tuple[SemanticPointV1, ...], (object(),)),
            masked_count=0,
        )


def test_projection_wire_rejects_wrong_child_unordered_duplicate_and_tampered_hash() -> None:
    acceptance, events, chart = _artifacts(
        chart_points=[
            {"ts": (BASE + timedelta(hours=6)).isoformat().replace("+00:00", "Z"), "value": 1.0},
            {"ts": (BASE + timedelta(hours=7)).isoformat().replace("+00:00", "Z"), "value": 2.0},
        ]
    )
    source = project_blind_semantic_read(
        acceptance_bytes=acceptance, events_bytes=events, chart_data_bytes=chart
    )
    wire = source.to_dict()
    points = cast(list[dict[str, object]], wire["points"])
    wire["points"] = list(reversed(points))
    with pytest.raises(DataError, match="canonical availability"):
        BlindSemanticProjectionV1.from_dict(wire)

    wire = source.to_dict()
    points = cast(list[dict[str, object]], wire["points"])
    points[1]["point_id"] = points[0]["point_id"]
    with pytest.raises(DataError, match="unique"):
        BlindSemanticProjectionV1.from_dict(wire)

    wire = source.to_dict()
    points = cast(list[dict[str, object]], wire["points"])
    points[0] = {"not_a_point": True}
    with pytest.raises(DataError, match="keys are not exact"):
        BlindSemanticProjectionV1.from_dict(wire)

    wire = source.to_dict()
    wire["content_sha256"] = "f" * 64
    with pytest.raises(DataError, match="content_sha256"):
        BlindSemanticProjectionV1.from_dict(wire)


def test_chart_must_be_exploratory_by_phase_and_watermark() -> None:
    acceptance, events, chart = _artifacts()
    chart_map = json.loads(chart)
    chart_map["evidence_phase"] = "confirmatory"
    with pytest.raises(DataError, match="exploratory chart artifact"):
        project_blind_semantic_read(
            acceptance_bytes=acceptance, events_bytes=events, chart_data_bytes=_json(chart_map)
        )


def test_normalizer_is_closed_and_no_detector_or_caller_cutoff_is_used() -> None:
    assert normalize_semantic_event(_event()).confirmed_at == BASE + timedelta(hours=8)
    with pytest.raises(DataError, match="keys are not exact"):
        normalize_semantic_event({**_event(), "unexpected": True})
    with pytest.raises(DataError, match="finite"):
        normalize_semantic_event({**_event(), "rebound": float("nan")})


def test_output_is_deterministic_for_identical_complete_bytes() -> None:
    acceptance, events, chart = _artifacts()
    first = project_blind_semantic_read(
        acceptance_bytes=acceptance, events_bytes=events, chart_data_bytes=chart
    )
    second = project_blind_semantic_read(
        acceptance_bytes=acceptance, events_bytes=events, chart_data_bytes=chart
    )
    assert first.to_dict() == second.to_dict()

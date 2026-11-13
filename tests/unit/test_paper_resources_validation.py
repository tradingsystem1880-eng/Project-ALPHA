"""Fail-loud validation branches of the inert paper-to-resource reference records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import cast

import pytest

from alpha_cli.paper_resources import (
    bind_paper_resource_link,
    build_paper_resource_resolutions,
    parse_paper_resources,
    validate_paper_resource_resolution_records,
    validate_paper_resource_resolutions,
)
from alpha_core import DataError

DATASET = "rd_" + "f" * 64


def _anchor(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "SourceAnchorV1",
        "extraction_id": "rx_" + "c" * 64,
        "page": 3,
        "char_start": 14,
        "char_end": 42,
        "exact_text_sha256": "d" * 64,
    }
    value.update(overrides)
    return value


def _link(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "PaperResourceLinkV1",
        "kind": "dataset",
        "source_id": "rs_" + "a" * 64,
        "source_claim_id": "sc_" + "b" * 64,
        "locator_type": "url",
        "locator": "https://research.example/data.csv",
        "relation": "dataset_available",
        "relation_anchor": _anchor(),
    }
    value.update(overrides)
    return value


def _parse(*links: dict[str, object], allow_bound: bool = False) -> list[dict[str, object]]:
    return parse_paper_resources(
        {"schema": "PaperResourceLinksV1", "links": list(links)}, allow_bound=allow_bound
    )


def _bound(**overrides: object) -> dict[str, object]:
    return bind_paper_resource_link(_parse(_link(**overrides))[0], claim_revision=1)


def _request(link_id: object, family: str = "event_study") -> dict[str, object]:
    return {
        "schema": "PaperResourceMappingRequestV1",
        "resource_link_id": link_id,
        "dataset_ref_id": DATASET,
        "analysis_family": family,
    }


# --- link records ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("anchor", "message"),
    [
        (_anchor(char_start=42, char_end=42), "1..2000 characters"),
        (_anchor(char_start=0, char_end=2_001), "1..2000 characters"),
    ],
)
def test_anchor_span_must_be_bounded_and_non_empty(anchor: dict[str, object], message: str) -> None:
    with pytest.raises(DataError, match=message):
        _parse(_link(relation_anchor=anchor))


def test_anchor_span_accepts_the_two_thousand_character_ceiling() -> None:
    parsed = _parse(_link(relation_anchor=_anchor(char_start=0, char_end=2_000)))
    assert cast(dict[str, object], parsed[0]["relation_anchor"])["char_end"] == 2_000


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"relation": "code_used"}, "kind and relation disagree"),
        ({"locator_type": "doi", "locator": "doi:10.1000/xyz"}, "DOI locator is invalid"),
        ({"locator": "https://research.example/a b.csv"}, "cannot contain whitespace"),
        ({"locator": "https://research.example:99999/data.csv"}, "URL locator is invalid"),
        ({"locator": "ftp://research.example/data.csv"}, "without user information"),
        ({"locator": "https://user:secret@research.example/x"}, "without user information"),
        ({"locator": "https:///no-host"}, "without user information"),
    ],
)
def test_link_locator_and_relation_fail_loud(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(DataError, match=message):
        _parse(_link(**overrides))


def test_aware_observation_time_is_normalized_and_naive_time_is_refused() -> None:
    eastern = timezone(timedelta(hours=-5))
    observed = datetime(2026, 1, 2, 7, 30, tzinfo=eastern).isoformat()
    parsed = _parse(_link(availability_observed_at=observed))
    assert parsed[0]["availability_observed_at"] == "2026-01-02T12:30:00Z"
    explicit_none = _parse(_link(availability_observed_at=None))
    assert "availability_observed_at" not in explicit_none[0]
    with pytest.raises(DataError, match="must include a timezone"):
        _parse(_link(availability_observed_at=datetime(2026, 1, 2, 7, 30).isoformat()))


def test_claim_binding_fields_are_all_or_nothing() -> None:
    with pytest.raises(DataError, match="bound together"):
        _parse(_link(claim_revision=2), allow_bound=True)
    with pytest.raises(DataError, match="assigned by the source-pack store"):
        _parse(
            _link(claim_revision=2, claim_status="screened", link_id="prl_" + "0" * 64),
        )


def test_stored_links_require_a_complete_matching_binding() -> None:
    with pytest.raises(DataError, match="screened claim revision and link id"):
        _parse(_link(), allow_bound=True)
    bound = _bound()
    tampered = {**bound, "locator": "https://research.example/other.csv"}
    with pytest.raises(DataError, match="does not match its content"):
        _parse(tampered, allow_bound=True)
    assert _parse(bound, allow_bound=True) == [bound]


@pytest.mark.parametrize(
    ("wrapper", "message"),
    [
        ([], "exact PaperResourceLinksV1 wrapper"),
        ({"schema": "PaperResourceLinksV1"}, "exact PaperResourceLinksV1 wrapper"),
        ({"schema": "PaperResourceLinksV2", "links": []}, "schema PaperResourceLinksV1"),
        ({"schema": "PaperResourceLinksV1", "links": {}}, "bounded to 64 entries"),
        ({"schema": "PaperResourceLinksV1", "links": [{}] * 65}, "bounded to 64 entries"),
    ],
)
def test_wrapper_shape_and_bound(wrapper: object, message: str) -> None:
    with pytest.raises(DataError, match=message):
        parse_paper_resources(wrapper)


def test_links_are_returned_in_link_identity_order() -> None:
    first = _link(locator="https://research.example/a.csv")
    second = _link(locator="https://research.example/b.csv")
    assert _parse(first, second) == _parse(second, first)
    assert len(_parse(first, second)) == 2
    assert parse_paper_resources({"schema": "PaperResourceLinksV1", "links": []}) == []


@pytest.mark.parametrize("revision", [0, -1, True, cast(int, "2")])
def test_binding_requires_a_positive_integer_revision(revision: int) -> None:
    link = _parse(_link())[0]
    with pytest.raises(DataError, match="positive integer"):
        bind_paper_resource_link(link, claim_revision=revision)


def test_binding_refuses_preassigned_fields_and_invalid_links() -> None:
    link = _parse(_link())[0]
    with pytest.raises(DataError, match="assigned by the source-pack store"):
        bind_paper_resource_link({**link, "claim_status": "screened"}, claim_revision=1)
    with pytest.raises(DataError, match="binding is invalid"):
        bind_paper_resource_link({**link, "kind": "model"}, claim_revision=1)


# --- resolutions -----------------------------------------------------------------------------


def test_resolution_inputs_need_unique_well_formed_link_ids() -> None:
    bound = _bound()
    with pytest.raises(DataError, match="invalid or duplicate link ids"):
        build_paper_resource_resolutions(
            [bound, bound], [], dataset_ref_id=DATASET, planned_families={"event_study"}
        )
    with pytest.raises(DataError, match="invalid or duplicate link ids"):
        build_paper_resource_resolutions(
            [{**bound, "link_id": "prl_short"}],
            [],
            dataset_ref_id=DATASET,
            planned_families={"event_study"},
        )


def test_mapping_requests_are_validated_against_the_frozen_pack() -> None:
    bound = _bound()
    link_id = bound["link_id"]
    other = "prl_" + "9" * 64
    cases: list[tuple[list[dict[str, object]], str | None, str]] = [
        ([_request(other)], DATASET, "outside the frozen source pack"),
        ([_request(link_id), _request(link_id)], DATASET, "duplicate mapping"),
        ([_request(link_id)], None, "selected registered dataset"),
        ([_request(link_id, "astrology")], DATASET, "unregistered analysis family"),
    ]
    for requests, dataset, message in cases:
        with pytest.raises(DataError, match=message):
            build_paper_resource_resolutions(
                [bound], requests, dataset_ref_id=dataset, planned_families={"event_study"}
            )


def test_unmapped_available_dataset_is_blocked_with_a_mapping_reason() -> None:
    resolution = build_paper_resource_resolutions(
        [_bound()], [], dataset_ref_id=DATASET, planned_families={"event_study"}
    )
    assert resolution[0]["resolution"] == "blocked_data"
    assert resolution[0]["source_equivalence"] == "unknown"
    assert "no mapping to the selected registered dataset" in str(resolution[0]["reason"])


def test_access_restricted_dataset_cannot_be_mapped() -> None:
    bound = _bound(access_status="restricted")
    with pytest.raises(DataError, match="blocked_data because availability, access, or license"):
        build_paper_resource_resolutions(
            [bound],
            [_request(bound["link_id"])],
            dataset_ref_id=DATASET,
            planned_families={"event_study"},
        )


def test_resolution_validation_requires_a_list_and_matching_records() -> None:
    bound = _bound()
    with pytest.raises(DataError, match="must be a list"):
        validate_paper_resource_resolutions(
            {}, [bound], dataset_ref_id=DATASET, planned_families={"event_study"}
        )
    mapped = build_paper_resource_resolutions(
        [bound],
        [_request(bound["link_id"])],
        dataset_ref_id=DATASET,
        planned_families={"event_study"},
    )
    assert (
        validate_paper_resource_resolutions(
            mapped, [bound], dataset_ref_id=DATASET, planned_families={"event_study"}
        )
        == mapped
    )
    with pytest.raises(DataError, match="do not match their frozen inputs"):
        # A record list missing the frozen link's resolution cannot stand in for it.
        validate_paper_resource_resolutions(
            [], [bound], dataset_ref_id=DATASET, planned_families={"event_study"}
        )
    with pytest.raises(DataError, match="mapping records are invalid"):
        validate_paper_resource_resolutions(
            [{**mapped[0], "reproduction_claimed": True}],
            [bound],
            dataset_ref_id=DATASET,
            planned_families={"event_study"},
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"reason": "should not be here"}, "without a blocker"),
        ({"resource_kind": "code"}, "code resources cannot map"),
        ({"source_equivalence": "unknown"}, "cannot establish source equivalence"),
    ],
)
def test_mapped_resolution_shape_is_closed(overrides: dict[str, object], message: str) -> None:
    bound = _bound()
    mapped = build_paper_resource_resolutions(
        [bound],
        [_request(bound["link_id"])],
        dataset_ref_id=DATASET,
        planned_families={"event_study"},
    )
    with pytest.raises(DataError, match=message):
        validate_paper_resource_resolution_records(
            [{**mapped[0], **overrides}],
            dataset_ref_id=DATASET,
            planned_families={"event_study"},
        )


def test_blocked_resolution_cannot_carry_mapped_inputs() -> None:
    bound = _bound()
    blocked = build_paper_resource_resolutions(
        [bound], [], dataset_ref_id=DATASET, planned_families={"event_study"}
    )
    for overrides in (
        {"local_dataset_ref_id": DATASET},
        {"analysis_family": "event_study"},
        {"reason": None},
        {"source_equivalence": "unverified"},
    ):
        with pytest.raises(DataError, match="blocked_data records require a reason"):
            validate_paper_resource_resolution_records(
                [{**blocked[0], **overrides}],
                dataset_ref_id=DATASET,
                planned_families={"event_study"},
            )


def test_resolution_records_projection_checks_dataset_family_and_duplicates() -> None:
    bound = _bound()
    second = _bound(locator="https://research.example/second.csv")
    mapped = build_paper_resource_resolutions(
        [bound, second],
        [_request(bound["link_id"])],
        dataset_ref_id=DATASET,
        planned_families={"event_study"},
    )
    reversed_records = list(reversed(mapped))
    assert (
        validate_paper_resource_resolution_records(
            reversed_records, dataset_ref_id=DATASET, planned_families={"event_study"}
        )
        == mapped
    )
    with pytest.raises(DataError, match="must be a list"):
        validate_paper_resource_resolution_records(
            None, dataset_ref_id=DATASET, planned_families={"event_study"}
        )
    with pytest.raises(DataError, match="duplicate paper resource mapping record"):
        validate_paper_resource_resolution_records(
            [mapped[0], mapped[0]], dataset_ref_id=DATASET, planned_families={"event_study"}
        )
    with pytest.raises(DataError, match="does not match the approved contract dataset"):
        validate_paper_resource_resolution_records(
            mapped, dataset_ref_id="rd_" + "e" * 64, planned_families={"event_study"}
        )
    with pytest.raises(DataError, match="not in the approved plan"):
        validate_paper_resource_resolution_records(
            mapped, dataset_ref_id=DATASET, planned_families={"conditional_returns"}
        )


def test_observation_time_survives_binding_in_utc() -> None:
    bound = _bound(availability_observed_at=datetime(2026, 3, 1, tzinfo=UTC).isoformat())
    assert bound["availability_observed_at"] == "2026-03-01T00:00:00Z"

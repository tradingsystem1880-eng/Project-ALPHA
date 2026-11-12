from __future__ import annotations

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


def _link(*, kind: str = "dataset", **overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "PaperResourceLinkV1",
        "kind": kind,
        "source_id": "rs_" + "a" * 64,
        "source_claim_id": "sc_" + "b" * 64,
        "locator_type": "url",
        "locator": "https://research.example/data.csv",
        "relation": "dataset_available" if kind == "dataset" else "code_available",
        "relation_anchor": {
            "schema": "SourceAnchorV1",
            "extraction_id": "rx_" + "c" * 64,
            "page": 3,
            "char_start": 14,
            "char_end": 42,
            "exact_text_sha256": "d" * 64,
        },
    }
    value.update(overrides)
    return value


def _links(*, kind: str = "dataset", **overrides: object) -> list[dict[str, object]]:
    parsed = parse_paper_resources(
        {"schema": "PaperResourceLinksV1", "links": [_link(kind=kind, **overrides)]}
    )
    return [bind_paper_resource_link(parsed[0], claim_revision=2)]


def test_paper_resource_link_defaults_unknown_and_binds_verified_claim_revision() -> None:
    parsed = parse_paper_resources({"schema": "PaperResourceLinksV1", "links": [_link()]})
    bound = bind_paper_resource_link(parsed[0], claim_revision=2)
    assert bound["link_id"] == "prl_" + str(bound["link_id"])[4:]
    assert len(str(bound["link_id"])) == 68
    assert bound["claim_revision"] == 2
    assert bound["claim_status"] == "screened"
    assert bound["availability_status"] == "unknown"
    assert bound["access_status"] == "unknown"
    assert bound["license_status"] == "unknown"
    assert bound["acquisition_status"] == "not_acquired"
    assert bound["trust_label"] == "UNTRUSTED_SOURCE"
    assert "acquired_content_sha256" not in bound
    assert bind_paper_resource_link(parsed[0], claim_revision=2) == bound
    assert parse_paper_resources(
        {"schema": "PaperResourceLinksV1", "links": [bound]}, allow_bound=True
    ) == [bound]


@pytest.mark.parametrize(
    "bad_link",
    [
        {**_link(), "locator": "javascript:alert(1)"},
        {**_link(), "acquired_content_sha256": "e" * 64},
        {**_link(), "trust_label": "TRUSTED"},
        {
            **_link(),
            "relation_anchor": {
                **cast(dict[str, object], _link()["relation_anchor"]),
                "page": True,
            },
        },
    ],
)
def test_paper_resource_link_rejects_unsafe_or_unverified_fields(
    bad_link: dict[str, object],
) -> None:
    with pytest.raises(DataError, match="paper resource"):
        parse_paper_resources({"schema": "PaperResourceLinksV1", "links": [bad_link]})


def test_paper_resource_link_timestamp_is_aware_and_doi_is_inert() -> None:
    parsed = parse_paper_resources(
        {
            "schema": "PaperResourceLinksV1",
            "links": [
                _link(
                    locator_type="doi",
                    locator="10.1234/synthetic-data.v1",
                    availability_status="reported_available",
                    availability_observed_at="2026-11-07T08:00:00+10:00",
                )
            ],
        }
    )
    assert parsed[0]["locator"] == "10.1234/synthetic-data.v1"
    assert parsed[0]["availability_observed_at"] == "2026-11-06T22:00:00Z"

    with pytest.raises(DataError, match="paper resource"):
        parse_paper_resources(
            {
                "schema": "PaperResourceLinksV1",
                "links": [_link(availability_observed_at="2026-11-07T08:00:00")],
            }
        )


def test_duplicate_resource_links_are_rejected() -> None:
    with pytest.raises(DataError, match="duplicate"):
        parse_paper_resources({"schema": "PaperResourceLinksV1", "links": [_link(), _link()]})


def test_paper_resource_resolutions_map_only_registered_planned_families() -> None:
    links = _links()
    link_id = str(links[0]["link_id"])
    request = {
        "schema": "PaperResourceMappingRequestV1",
        "resource_link_id": link_id,
        "dataset_ref_id": "rd_" + "f" * 64,
        "analysis_family": "event_study",
    }
    mapped = build_paper_resource_resolutions(
        links,
        [request],
        dataset_ref_id="rd_" + "f" * 64,
        planned_families={"event_study", "conditional_returns"},
    )
    assert mapped[0]["resolution"] == "mapped"
    assert mapped[0]["analysis_family"] == "event_study"
    assert mapped[0]["reproduction_claimed"] is False
    assert mapped[0]["source_equivalence"] == "unverified"

    blocked = build_paper_resource_resolutions(
        links, [], dataset_ref_id=None, planned_families={"event_study"}
    )
    assert blocked[0]["resolution"] == "blocked_data"
    assert blocked[0]["local_dataset_ref_id"] is None
    assert blocked[0]["reproduction_claimed"] is False

    with pytest.raises(DataError, match="frozen registered analysis plan"):
        build_paper_resource_resolutions(
            links,
            [{**request, "analysis_family": "rank_ic"}],
            dataset_ref_id="rd_" + "f" * 64,
            planned_families={"event_study"},
        )
    with pytest.raises(DataError, match="selected registered dataset"):
        build_paper_resource_resolutions(
            links,
            [request],
            dataset_ref_id="rd_" + "e" * 64,
            planned_families={"event_study"},
        )


def test_paper_code_links_cannot_be_mapped_to_a_dataset() -> None:
    links = _links(kind="code")
    blocked = build_paper_resource_resolutions(
        links, [], dataset_ref_id="rd_" + "f" * 64, planned_families={"event_study"}
    )
    assert blocked[0]["resolution"] == "blocked_data"
    assert "no local code registry mapping" in str(blocked[0]["reason"])
    assert blocked[0]["linked_code_execution"] == "not_executed"

    with pytest.raises(DataError, match="code resources cannot map"):
        build_paper_resource_resolutions(
            links,
            [
                {
                    "schema": "PaperResourceMappingRequestV1",
                    "resource_link_id": links[0]["link_id"],
                    "dataset_ref_id": "rd_" + "f" * 64,
                    "analysis_family": "event_study",
                }
            ],
            dataset_ref_id="rd_" + "f" * 64,
            planned_families={"event_study"},
        )


def test_unavailable_or_restricted_link_cannot_be_mapped_and_round_trips() -> None:
    unavailable = _links(availability_status="unavailable")
    unavailable_id = str(unavailable[0]["link_id"])
    with pytest.raises(DataError, match="blocked_data"):
        build_paper_resource_resolutions(
            unavailable,
            [
                {
                    "schema": "PaperResourceMappingRequestV1",
                    "resource_link_id": unavailable_id,
                    "dataset_ref_id": "rd_" + "f" * 64,
                    "analysis_family": "event_study",
                }
            ],
            dataset_ref_id="rd_" + "f" * 64,
            planned_families={"event_study"},
        )

    blocked = build_paper_resource_resolutions(
        unavailable, [], dataset_ref_id=None, planned_families={"event_study"}
    )
    assert blocked[0]["resolution"] == "blocked_data"
    assert "unavailable" in str(blocked[0]["reason"])
    assert (
        validate_paper_resource_resolutions(
            blocked,
            unavailable,
            dataset_ref_id=None,
            planned_families={"event_study"},
        )
        == blocked
    )

    restricted = _links(license_status="restricted")
    with pytest.raises(DataError, match="blocked_data"):
        build_paper_resource_resolutions(
            restricted,
            [
                {
                    "schema": "PaperResourceMappingRequestV1",
                    "resource_link_id": restricted[0]["link_id"],
                    "dataset_ref_id": "rd_" + "f" * 64,
                    "analysis_family": "event_study",
                }
            ],
            dataset_ref_id="rd_" + "f" * 64,
            planned_families={"event_study"},
        )


def test_resolution_validation_rejects_modified_mapping_records() -> None:
    links = _links()
    blocked = build_paper_resource_resolutions(
        links, [], dataset_ref_id=None, planned_families={"event_study"}
    )
    with pytest.raises(DataError, match="paper resource mapping records"):
        validate_paper_resource_resolutions(
            [{**blocked[0], "reproduction_claimed": True}],
            links,
            dataset_ref_id=None,
            planned_families={"event_study"},
        )

    mapped = build_paper_resource_resolutions(
        links,
        [
            {
                "schema": "PaperResourceMappingRequestV1",
                "resource_link_id": links[0]["link_id"],
                "dataset_ref_id": "rd_" + "f" * 64,
                "analysis_family": "event_study",
            }
        ],
        dataset_ref_id="rd_" + "f" * 64,
        planned_families={"event_study"},
    )
    with pytest.raises(DataError, match="code resources cannot map"):
        validate_paper_resource_resolution_records(
            [{**mapped[0], "resource_kind": "code"}],
            dataset_ref_id="rd_" + "f" * 64,
            planned_families={"event_study"},
        )

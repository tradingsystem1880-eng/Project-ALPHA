"""Typed, inert paper-to-resource references for frozen research source packs."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from alpha_cli.research_analysis_plan import REGISTERED_ANALYSIS_FAMILIES
from alpha_core import DataError

_LINK_ID = re.compile(r"^prl_[0-9a-f]{64}$")
_DOI = re.compile(r"^10\.\d{4,9}/\S+$")


class _SourceAnchorReference(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True, populate_by_name=True
    )

    schema_: Literal["SourceAnchorV1"] = Field(alias="schema")
    extraction_id: str = Field(pattern=r"^rx_[0-9a-f]{64}$")
    page: StrictInt = Field(ge=1)
    char_start: StrictInt = Field(ge=0)
    char_end: StrictInt = Field(ge=1)
    exact_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _bounded_span(self) -> _SourceAnchorReference:
        if self.char_end <= self.char_start or self.char_end - self.char_start > 2_000:
            raise ValueError("anchor span must contain 1..2000 characters")
        return self


class _PaperResourceLink(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True, populate_by_name=True
    )

    schema_: Literal["PaperResourceLinkV1"] = Field(alias="schema")
    kind: Literal["dataset", "code"]
    source_id: str = Field(pattern=r"^rs_[0-9a-f]{64}$")
    source_claim_id: str = Field(pattern=r"^sc_[0-9a-f]{64}$")
    locator_type: Literal["doi", "url"]
    locator: str = Field(min_length=1, max_length=2_000)
    relation: Literal["dataset_used", "dataset_available", "code_used", "code_available"]
    relation_anchor: _SourceAnchorReference
    reported_version: str | None = Field(default=None, max_length=500)
    availability_status: Literal["unknown", "reported_available", "unavailable"] = "unknown"
    availability_observed_at: datetime | None = None
    access_status: Literal["unknown", "reported_available", "restricted", "unavailable"] = "unknown"
    license_status: Literal["unknown", "reported_open", "restricted"] = "unknown"
    acquisition_status: Literal["not_acquired"] = "not_acquired"
    trust_label: Literal["UNTRUSTED_SOURCE"] = "UNTRUSTED_SOURCE"
    claim_revision: StrictInt | None = Field(default=None, ge=1)
    claim_status: Literal["screened"] | None = None
    link_id: str | None = Field(default=None, pattern=r"^prl_[0-9a-f]{64}$")

    @field_validator("availability_observed_at")
    @classmethod
    def _aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("availability_observed_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _consistent_record(self) -> _PaperResourceLink:
        relation_kind = self.relation.split("_", maxsplit=1)[0]
        if relation_kind != self.kind:
            raise ValueError("resource kind and relation disagree")
        if self.locator_type == "doi":
            if _DOI.fullmatch(self.locator) is None:
                raise ValueError("DOI locator is invalid")
        else:
            if any(character.isspace() for character in self.locator):
                raise ValueError("URL locator cannot contain whitespace")
            try:
                parsed = urlsplit(self.locator)
                _ = parsed.port
            except ValueError as exc:
                raise ValueError("URL locator is invalid") from exc
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise ValueError("URL locator must be an HTTP(S) URL without user information")
        bound = (
            self.claim_revision is not None,
            self.claim_status is not None,
            self.link_id is not None,
        )
        if any(bound) and not all(bound):
            raise ValueError("claim revision, status, and link id must be bound together")
        return self


class _PaperResourceMappingRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True, populate_by_name=True
    )

    schema_: Literal["PaperResourceMappingRequestV1"] = Field(alias="schema")
    resource_link_id: str = Field(pattern=r"^prl_[0-9a-f]{64}$")
    dataset_ref_id: str = Field(pattern=r"^rd_[0-9a-f]{64}$")
    analysis_family: str = Field(min_length=1, max_length=100)


class _PaperResourceResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_: Literal["PaperResourceResolutionV1"] = Field(
        default="PaperResourceResolutionV1", alias="schema"
    )
    resource_link_id: str = Field(pattern=r"^prl_[0-9a-f]{64}$")
    resource_kind: Literal["dataset", "code"]
    resolution: Literal["mapped", "blocked_data"]
    local_dataset_ref_id: str | None = Field(default=None, pattern=r"^rd_[0-9a-f]{64}$")
    analysis_family: str | None = Field(default=None, min_length=1, max_length=100)
    availability_status: Literal["unknown", "reported_available", "unavailable"]
    access_status: Literal["unknown", "reported_available", "restricted", "unavailable"]
    license_status: Literal["unknown", "reported_open", "restricted"]
    source_equivalence: Literal["unknown", "unverified"]
    reproduction_claimed: Literal[False] = False
    linked_code_execution: Literal["not_executed"] = "not_executed"
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _resolution_shape(self) -> _PaperResourceResolution:
        if self.resolution == "mapped":
            if self.local_dataset_ref_id is None or self.analysis_family is None or self.reason:
                raise ValueError("mapped records require a dataset and family, without a blocker")
            if self.resource_kind != "dataset":
                raise ValueError("paper-linked code resources cannot map to a registered dataset")
            if self.source_equivalence != "unverified":
                raise ValueError("a resource mapping cannot establish source equivalence")
        elif (
            self.local_dataset_ref_id is not None
            or self.analysis_family is not None
            or not self.reason
            or self.source_equivalence != "unknown"
        ):
            raise ValueError("blocked_data records require a reason and no mapped inputs")
        return self


def _dump_link(model: _PaperResourceLink) -> dict[str, object]:
    return model.model_dump(
        mode="json",
        by_alias=True,
        exclude={"claim_revision", "claim_status", "link_id"},
        exclude_none=True,
    )


def _link_id(link: Mapping[str, object]) -> str:
    body = {key: value for key, value in link.items() if key != "link_id"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return f"prl_{hashlib.sha256(raw).hexdigest()}"


def parse_paper_resources(value: object, *, allow_bound: bool = False) -> list[dict[str, object]]:
    """Validate the versioned source-pack wrapper and return normalized link records."""
    if not isinstance(value, Mapping) or set(value) != {"schema", "links"}:
        raise DataError("paper resource links require the exact PaperResourceLinksV1 wrapper")
    if value.get("schema") != "PaperResourceLinksV1":
        raise DataError("paper resource links require schema PaperResourceLinksV1")
    raw_links = value.get("links")
    if not isinstance(raw_links, list) or len(raw_links) > 64:
        raise DataError("paper resource links must be a list bounded to 64 entries")
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    try:
        for raw_link in raw_links:
            model = _PaperResourceLink.model_validate(raw_link)
            if allow_bound:
                if (
                    model.claim_revision is None
                    or model.claim_status != "screened"
                    or not model.link_id
                ):
                    raise ValueError("stored links require a screened claim revision and link id")
            elif (
                model.claim_revision is not None or model.claim_status is not None or model.link_id
            ):
                raise ValueError("claim binding fields are assigned by the source-pack store")
            record = model.model_dump(mode="json", by_alias=True, exclude_none=True)
            if allow_bound and record.get("link_id") != _link_id(record):
                raise ValueError("stored paper resource link id does not match its content")
            identity = str(record.get("link_id") or _link_id(_dump_link(model)))
            if identity in seen:
                raise ValueError("duplicate paper resource link")
            seen.add(identity)
            normalized.append(_dump_link(model) if not allow_bound else record)
    except (TypeError, ValueError) as exc:
        raise DataError(f"paper resource link is invalid: {exc}") from exc
    return sorted(normalized, key=lambda item: str(item.get("link_id") or _link_id(item)))


def bind_paper_resource_link(
    link: Mapping[str, object], *, claim_revision: int
) -> dict[str, object]:
    """Bind a validated link to the exact owner-screened claim revision and hash it."""
    if (
        isinstance(claim_revision, bool)
        or not isinstance(claim_revision, int)
        or claim_revision < 1
    ):
        raise DataError("paper resource claim revision must be a positive integer")
    body = dict(link)
    if any(key in body for key in ("claim_revision", "claim_status", "link_id")):
        raise DataError("paper resource claim binding is assigned by the source-pack store")
    body["claim_revision"] = claim_revision
    body["claim_status"] = "screened"
    body["link_id"] = _link_id(body)
    try:
        return _PaperResourceLink.model_validate(body).model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
    except (TypeError, ValueError) as exc:
        raise DataError(f"paper resource link binding is invalid: {exc}") from exc


def build_paper_resource_resolutions(
    links: Sequence[Mapping[str, object]],
    requests: Sequence[Mapping[str, object]],
    *,
    dataset_ref_id: str | None,
    planned_families: set[str],
) -> list[dict[str, object]]:
    """Resolve explicit draft mappings; leave every unmapped/unavailable resource blocked."""
    by_id = {str(link.get("link_id")): link for link in links}
    if len(by_id) != len(links) or any(_LINK_ID.fullmatch(key) is None for key in by_id):
        raise DataError("paper resource pack has invalid or duplicate link ids")
    mapped: dict[str, _PaperResourceMappingRequest] = {}
    try:
        for raw_request in requests:
            request = _PaperResourceMappingRequest.model_validate(raw_request)
            if request.resource_link_id not in by_id:
                raise ValueError("mapping names a link outside the frozen source pack")
            if request.resource_link_id in mapped:
                raise ValueError("duplicate mapping for one paper resource link")
            if dataset_ref_id is None or request.dataset_ref_id != dataset_ref_id:
                raise ValueError("mapping must name the selected registered dataset")
            if request.analysis_family not in REGISTERED_ANALYSIS_FAMILIES:
                raise ValueError("mapping names an unregistered analysis family")
            if request.analysis_family not in planned_families:
                raise ValueError("analysis family is not in the frozen registered analysis plan")
            link = by_id[request.resource_link_id]
            if link.get("kind") != "dataset":
                raise ValueError("paper-linked code resources cannot map to a registered dataset")
            if (
                link.get("availability_status") == "unavailable"
                or link.get("access_status") in {"restricted", "unavailable"}
                or link.get("license_status") == "restricted"
            ):
                raise ValueError(
                    "resource is blocked_data because availability, access, or license "
                    "is restricted"
                )
            mapped[request.resource_link_id] = request
    except (TypeError, ValueError) as exc:
        raise DataError(f"paper resource mapping is invalid: {exc}") from exc

    output: list[dict[str, object]] = []
    for link_id, link in sorted(by_id.items()):
        resolution_request = mapped.get(link_id)
        if resolution_request is None:
            unavailable = (
                link.get("availability_status") == "unavailable"
                or link.get("access_status") in {"restricted", "unavailable"}
                or link.get("license_status") == "restricted"
            )
            if link.get("kind") == "code":
                reason = (
                    "paper-linked code reference is recorded only; no local code registry "
                    "mapping exists, and code was not acquired or executed"
                )
            elif unavailable:
                reason = (
                    "paper-linked resource is unavailable or access-restricted; "
                    "required input is blocked_data"
                )
            else:
                reason = (
                    "no mapping to the selected registered dataset and planned analysis "
                    "family; required input is blocked_data"
                )
            resolution = _PaperResourceResolution(
                resource_link_id=link_id,
                resource_kind=link["kind"],
                resolution="blocked_data",
                availability_status=link.get("availability_status", "unknown"),
                access_status=link.get("access_status", "unknown"),
                license_status=link.get("license_status", "unknown"),
                source_equivalence="unknown",
                reason=reason,
            )
        else:
            resolution = _PaperResourceResolution(
                resource_link_id=link_id,
                resource_kind=link["kind"],
                resolution="mapped",
                local_dataset_ref_id=resolution_request.dataset_ref_id,
                analysis_family=resolution_request.analysis_family,
                availability_status=link.get("availability_status", "unknown"),
                access_status=link.get("access_status", "unknown"),
                license_status=link.get("license_status", "unknown"),
                source_equivalence="unverified",
            )
        output.append(resolution.model_dump(mode="json", by_alias=True))
    return output


def validate_paper_resource_resolutions(
    value: object,
    links: Sequence[Mapping[str, object]],
    *,
    dataset_ref_id: str | None,
    planned_families: set[str],
) -> list[dict[str, object]]:
    """Recompute and compare the immutable resolution list at contract approval."""
    if not isinstance(value, list):
        raise DataError("paper resource mapping records must be a list")
    requests: list[dict[str, object]] = []
    try:
        for item in value:
            record = _PaperResourceResolution.model_validate(item)
            if record.resolution == "mapped":
                requests.append(
                    {
                        "schema": "PaperResourceMappingRequestV1",
                        "resource_link_id": record.resource_link_id,
                        "dataset_ref_id": record.local_dataset_ref_id,
                        "analysis_family": record.analysis_family,
                    }
                )
    except (TypeError, ValueError) as exc:
        raise DataError(f"paper resource mapping records are invalid: {exc}") from exc
    expected = build_paper_resource_resolutions(
        links,
        requests,
        dataset_ref_id=dataset_ref_id,
        planned_families=planned_families,
    )
    if expected != value:
        raise DataError("paper resource mapping records do not match their frozen inputs")
    return expected


def validate_paper_resource_resolution_records(
    value: object,
    *,
    dataset_ref_id: str | None,
    planned_families: set[str],
) -> list[dict[str, object]]:
    """Validate the D1-facing resolution projection without following paper references."""
    if not isinstance(value, list):
        raise DataError("paper resource mapping records must be a list")
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    try:
        for item in value:
            record = _PaperResourceResolution.model_validate(item)
            if record.resource_link_id in seen:
                raise ValueError("duplicate paper resource mapping record")
            seen.add(record.resource_link_id)
            if record.resolution == "mapped":
                if record.local_dataset_ref_id != dataset_ref_id:
                    raise ValueError("mapped dataset does not match the approved contract dataset")
                if record.analysis_family not in planned_families:
                    raise ValueError("mapped analysis family is not in the approved plan")
            normalized.append(record.model_dump(mode="json", by_alias=True))
    except (TypeError, ValueError) as exc:
        raise DataError(f"paper resource mapping records are invalid: {exc}") from exc
    return sorted(normalized, key=lambda item: str(item["resource_link_id"]))


__all__ = [
    "bind_paper_resource_link",
    "build_paper_resource_resolutions",
    "parse_paper_resources",
    "validate_paper_resource_resolution_records",
    "validate_paper_resource_resolutions",
]

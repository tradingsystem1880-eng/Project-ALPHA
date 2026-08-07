"""Canonical, content-bound evidence allocation for one sealed D2 lineage."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from alpha_core import DataError
from alpha_research._canonical import canonical_sha256

EvidenceZone = Literal["D0", "D1", "D2", "D3"]

_SCHEMA = "ResearchD2BoundaryV1"
_CHART_SCHEMA = "ResearchChartFingerprintV1"
_ALLOCATION_RULE = "eligible_groups_chronological_cumulative_floor_remainder_to_D3_v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ZONES: tuple[EvidenceZone, ...] = ("D0", "D1", "D2", "D3")


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DataError(f"{name} must be a non-empty canonical string")
    if any(ord(character) < 32 for character in value):
        raise DataError(f"{name} cannot contain control characters")
    return value


def _integer(value: object, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise DataError(f"{name} must be an integer >= {minimum}")
    return value


def _sha256(value: object, name: str) -> str:
    digest = _text(value, name)
    if _SHA256.fullmatch(digest) is None:
        raise DataError(f"{name} must be a lowercase 64-character SHA-256 digest")
    return digest


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise DataError(f"{name} must be an object")
    return cast(Mapping[str, object], value)


def _exact_keys(value: Mapping[str, object], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise DataError(f"{name} has unexpected or missing fields")


@dataclass(frozen=True, slots=True)
class ResearchChartFingerprintV1:
    """Exact chart construction whose semantics participate in the D2 boundary hash."""

    instrument: str
    provider: str
    venue: str
    timezone: str
    session: str
    bar_construction: str
    bar_duration_seconds: int
    anchor: str
    adjustment_basis: str
    timestamp_semantics: str

    def __post_init__(self) -> None:
        for name in (
            "instrument",
            "provider",
            "venue",
            "timezone",
            "session",
            "bar_construction",
            "anchor",
            "adjustment_basis",
            "timestamp_semantics",
        ):
            _text(getattr(self, name), f"ResearchChartFingerprintV1.{name}")
        _integer(
            self.bar_duration_seconds,
            "ResearchChartFingerprintV1.bar_duration_seconds",
            minimum=1,
        )

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "schema": _CHART_SCHEMA,
            "schema_version": 1,
            "instrument": self.instrument,
            "provider": self.provider,
            "venue": self.venue,
            "timezone": self.timezone,
            "session": self.session,
            "bar_construction": self.bar_construction,
            "bar_duration_seconds": self.bar_duration_seconds,
            "anchor": self.anchor,
            "adjustment_basis": self.adjustment_basis,
            "timestamp_semantics": self.timestamp_semantics,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return canonical_sha256(self._semantic_dict())

    def to_dict(self) -> dict[str, object]:
        payload = self._semantic_dict()
        payload["fingerprint_sha256"] = self.fingerprint_sha256
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ResearchChartFingerprintV1:
        _exact_keys(
            value,
            {
                "schema",
                "schema_version",
                "instrument",
                "provider",
                "venue",
                "timezone",
                "session",
                "bar_construction",
                "bar_duration_seconds",
                "anchor",
                "adjustment_basis",
                "timestamp_semantics",
                "fingerprint_sha256",
            },
            _CHART_SCHEMA,
        )
        schema_version = _integer(
            value["schema_version"], "ResearchChartFingerprintV1.schema_version", minimum=1
        )
        if value["schema"] != _CHART_SCHEMA or schema_version != 1:
            raise DataError("unsupported ResearchChartFingerprintV1 schema")
        result = cls(
            instrument=_text(value["instrument"], "chart_fingerprint.instrument"),
            provider=_text(value["provider"], "chart_fingerprint.provider"),
            venue=_text(value["venue"], "chart_fingerprint.venue"),
            timezone=_text(value["timezone"], "chart_fingerprint.timezone"),
            session=_text(value["session"], "chart_fingerprint.session"),
            bar_construction=_text(value["bar_construction"], "chart_fingerprint.bar_construction"),
            bar_duration_seconds=_integer(
                value["bar_duration_seconds"],
                "chart_fingerprint.bar_duration_seconds",
                minimum=1,
            ),
            anchor=_text(value["anchor"], "chart_fingerprint.anchor"),
            adjustment_basis=_text(value["adjustment_basis"], "chart_fingerprint.adjustment_basis"),
            timestamp_semantics=_text(
                value["timestamp_semantics"], "chart_fingerprint.timestamp_semantics"
            ),
        )
        supplied = _sha256(value["fingerprint_sha256"], "chart_fingerprint.fingerprint_sha256")
        if supplied != result.fingerprint_sha256:
            raise DataError("chart fingerprint_sha256 does not match its canonical semantics")
        return result


@dataclass(frozen=True, slots=True)
class ResearchEvidenceSharesV1:
    """Integer-percent evidence shares; synthetic D0 never consumes eligible real groups."""

    d0_percent: int = 0
    d1_percent: int = 60
    d2_percent: int = 20
    d3_percent: int = 20

    def __post_init__(self) -> None:
        shares = {
            "D0": _integer(self.d0_percent, "ResearchEvidenceSharesV1.D0"),
            "D1": _integer(self.d1_percent, "ResearchEvidenceSharesV1.D1"),
            "D2": _integer(self.d2_percent, "ResearchEvidenceSharesV1.D2"),
            "D3": _integer(self.d3_percent, "ResearchEvidenceSharesV1.D3"),
        }
        if shares["D0"] != 0:
            raise DataError("ResearchEvidenceSharesV1.D0 must remain 0 for eligible real groups")
        if shares["D1"] <= 0 or shares["D2"] <= 0:
            raise DataError("ResearchEvidenceSharesV1.D1 and D2 must be positive")
        if shares["D3"] < 20:
            raise DataError("ResearchEvidenceSharesV1.D3 must be at least 20 percent")
        if sum(shares.values()) != 100:
            raise DataError("ResearchEvidenceSharesV1 shares must sum to 100 percent")

    def to_dict(self) -> dict[str, int]:
        return {
            "D0": self.d0_percent,
            "D1": self.d1_percent,
            "D2": self.d2_percent,
            "D3": self.d3_percent,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ResearchEvidenceSharesV1:
        _exact_keys(value, set(_ZONES), "ResearchEvidenceSharesV1")
        return cls(
            d0_percent=_integer(value["D0"], "ResearchEvidenceSharesV1.D0"),
            d1_percent=_integer(value["D1"], "ResearchEvidenceSharesV1.D1"),
            d2_percent=_integer(value["D2"], "ResearchEvidenceSharesV1.D2"),
            d3_percent=_integer(value["D3"], "ResearchEvidenceSharesV1.D3"),
        )


@dataclass(frozen=True, slots=True)
class ResearchEvidenceZoneBoundaryV1:
    """One derived half-open allocation over the ordered eligible group commitments."""

    zone: EvidenceZone
    share_percent: int
    start_index: int
    stop_index: int
    group_count: int
    membership_sha256: str
    first_group_sha256: str | None
    last_group_sha256: str | None

    def __post_init__(self) -> None:
        if self.zone not in _ZONES:
            raise DataError(f"unsupported research evidence zone {self.zone!r}")
        _integer(self.share_percent, f"{self.zone}.share_percent")
        start = _integer(self.start_index, f"{self.zone}.start_index")
        stop = _integer(self.stop_index, f"{self.zone}.stop_index")
        count = _integer(self.group_count, f"{self.zone}.group_count")
        if stop < start or count != stop - start:
            raise DataError(f"{self.zone} indices and group_count are inconsistent")
        _sha256(self.membership_sha256, f"{self.zone}.membership_sha256")
        endpoints = (self.first_group_sha256, self.last_group_sha256)
        if count == 0:
            if endpoints != (None, None):
                raise DataError(f"empty {self.zone} cannot have group endpoints")
        else:
            if any(endpoint is None for endpoint in endpoints):
                raise DataError(f"non-empty {self.zone} requires both group endpoints")
            for name, endpoint in zip(("first", "last"), endpoints, strict=True):
                _sha256(endpoint, f"{self.zone}.{name}_group_sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "zone": self.zone,
            "share_percent": self.share_percent,
            "start_index": self.start_index,
            "stop_index": self.stop_index,
            "group_count": self.group_count,
            "membership_sha256": self.membership_sha256,
            "first_group_sha256": self.first_group_sha256,
            "last_group_sha256": self.last_group_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ResearchEvidenceZoneBoundaryV1:
        _exact_keys(
            value,
            {
                "zone",
                "share_percent",
                "start_index",
                "stop_index",
                "group_count",
                "membership_sha256",
                "first_group_sha256",
                "last_group_sha256",
            },
            "ResearchEvidenceZoneBoundaryV1",
        )
        zone = _text(value["zone"], "evidence zone")
        if zone not in _ZONES:
            raise DataError(f"unsupported research evidence zone {zone!r}")
        first = value["first_group_sha256"]
        last = value["last_group_sha256"]
        if first is not None:
            first = _sha256(first, f"{zone}.first_group_sha256")
        if last is not None:
            last = _sha256(last, f"{zone}.last_group_sha256")
        return cls(
            zone=zone,
            share_percent=_integer(value["share_percent"], f"{zone}.share_percent"),
            start_index=_integer(value["start_index"], f"{zone}.start_index"),
            stop_index=_integer(value["stop_index"], f"{zone}.stop_index"),
            group_count=_integer(value["group_count"], f"{zone}.group_count"),
            membership_sha256=_sha256(value["membership_sha256"], f"{zone}.membership_sha256"),
            first_group_sha256=first,
            last_group_sha256=last,
        )


def _group_hash(group: str) -> str:
    return canonical_sha256({"schema": "ResearchEligibleDateSessionGroupV1", "group_id": group})


def _membership_hash(zone: EvidenceZone, group_hashes: tuple[str, ...]) -> str:
    return canonical_sha256(
        {
            "schema": "ResearchEvidenceZoneMembershipV1",
            "zone": zone,
            "ordered_group_hashes": list(group_hashes),
        }
    )


def _zone(
    zone: EvidenceZone,
    share_percent: int,
    start: int,
    stop: int,
    all_group_hashes: tuple[str, ...],
) -> ResearchEvidenceZoneBoundaryV1:
    members = all_group_hashes[start:stop]
    return ResearchEvidenceZoneBoundaryV1(
        zone=zone,
        share_percent=share_percent,
        start_index=start,
        stop_index=stop,
        group_count=len(members),
        membership_sha256=_membership_hash(zone, members),
        first_group_sha256=members[0] if members else None,
        last_group_sha256=members[-1] if members else None,
    )


@dataclass(frozen=True, slots=True)
class ResearchD2BoundaryV1:
    """Immutable D2 commitment derived from exact research semantics and group membership."""

    dataset_fingerprint: str
    eligible_group_hashes: tuple[str, ...]
    chart_fingerprint: ResearchChartFingerprintV1
    event_formula: str
    event_availability_timestamp: str
    primary_endpoint: str
    primary_horizon: str
    outcome_overlap_embargo_groups: int
    shares: ResearchEvidenceSharesV1 = field(default_factory=ResearchEvidenceSharesV1)
    d0: ResearchEvidenceZoneBoundaryV1 = field(init=False)
    d1: ResearchEvidenceZoneBoundaryV1 = field(init=False)
    d2: ResearchEvidenceZoneBoundaryV1 = field(init=False)
    d3: ResearchEvidenceZoneBoundaryV1 = field(init=False)
    eligible_groups_sha256: str = field(init=False)
    boundary_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _sha256(self.dataset_fingerprint, "ResearchD2BoundaryV1.dataset_fingerprint")
        if not isinstance(self.eligible_group_hashes, tuple) or len(self.eligible_group_hashes) < 5:
            raise DataError("ResearchD2BoundaryV1 requires at least 5 ordered eligible groups")
        for index, digest in enumerate(self.eligible_group_hashes):
            _sha256(digest, f"ResearchD2BoundaryV1.eligible_group_hashes[{index}]")
        if len(set(self.eligible_group_hashes)) != len(self.eligible_group_hashes):
            raise DataError("ResearchD2BoundaryV1 eligible groups must be unique")
        if not isinstance(self.chart_fingerprint, ResearchChartFingerprintV1):
            raise DataError("ResearchD2BoundaryV1.chart_fingerprint has the wrong type")
        if not isinstance(self.shares, ResearchEvidenceSharesV1):
            raise DataError("ResearchD2BoundaryV1.shares has the wrong type")
        for name in (
            "event_formula",
            "event_availability_timestamp",
            "primary_endpoint",
            "primary_horizon",
        ):
            _text(getattr(self, name), f"ResearchD2BoundaryV1.{name}")
        _integer(
            self.outcome_overlap_embargo_groups,
            "ResearchD2BoundaryV1.outcome_overlap_embargo_groups",
        )

        total = len(self.eligible_group_hashes)
        d0_stop = total * self.shares.d0_percent // 100
        d1_stop = total * (self.shares.d0_percent + self.shares.d1_percent) // 100
        d2_stop = (
            total
            * (self.shares.d0_percent + self.shares.d1_percent + self.shares.d2_percent)
            // 100
        )
        boundaries = (0, d0_stop, d1_stop, d2_stop, total)
        shares = self.shares.to_dict()
        derived = tuple(
            _zone(
                zone,
                shares[zone],
                boundaries[index],
                boundaries[index + 1],
                self.eligible_group_hashes,
            )
            for index, zone in enumerate(_ZONES)
        )
        if any(item.group_count == 0 for item in derived[1:]):
            raise DataError("ResearchD2BoundaryV1 allocation leaves D1, D2, or D3 empty")
        for name, item in zip(("d0", "d1", "d2", "d3"), derived, strict=True):
            object.__setattr__(self, name, item)
        object.__setattr__(
            self,
            "eligible_groups_sha256",
            canonical_sha256(
                {
                    "schema": "ResearchEligibleGroupSequenceV1",
                    "ordered_group_hashes": list(self.eligible_group_hashes),
                }
            ),
        )
        object.__setattr__(self, "boundary_sha256", canonical_sha256(self._semantic_dict()))

    @classmethod
    def from_eligible_groups(
        cls,
        *,
        dataset_fingerprint: str,
        eligible_groups: Sequence[str],
        chart_fingerprint: ResearchChartFingerprintV1,
        event_formula: str,
        event_availability_timestamp: str,
        primary_endpoint: str,
        primary_horizon: str,
        outcome_overlap_embargo_groups: int,
        shares: ResearchEvidenceSharesV1 | None = None,
    ) -> ResearchD2BoundaryV1:
        """Hash an already chronological tuple of eligible date/session group identifiers."""

        if isinstance(eligible_groups, (str, bytes)):
            raise DataError("eligible_groups must be an ordered sequence of group identifiers")
        cleaned = tuple(
            _text(group, f"eligible_groups[{index}]") for index, group in enumerate(eligible_groups)
        )
        if len(set(cleaned)) != len(cleaned):
            raise DataError("ResearchD2BoundaryV1 eligible groups must be unique")
        return cls(
            dataset_fingerprint=dataset_fingerprint,
            eligible_group_hashes=tuple(_group_hash(group) for group in cleaned),
            chart_fingerprint=chart_fingerprint,
            event_formula=event_formula,
            event_availability_timestamp=event_availability_timestamp,
            primary_endpoint=primary_endpoint,
            primary_horizon=primary_horizon,
            outcome_overlap_embargo_groups=outcome_overlap_embargo_groups,
            shares=shares or ResearchEvidenceSharesV1(),
        )

    def verify_eligible_groups(self, eligible_groups: Sequence[str]) -> bool:
        """Verify the exact group identities and order without retaining their raw labels."""

        if isinstance(eligible_groups, (str, bytes)):
            raise DataError("eligible_groups must be an ordered sequence of group identifiers")
        hashes = tuple(
            _group_hash(_text(group, f"eligible_groups[{index}]"))
            for index, group in enumerate(eligible_groups)
        )
        return hashes == self.eligible_group_hashes

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "schema": _SCHEMA,
            "schema_version": 1,
            "allocation_rule": _ALLOCATION_RULE,
            "dataset_fingerprint": self.dataset_fingerprint,
            "eligible_groups": {
                "count": len(self.eligible_group_hashes),
                "ordered_group_hashes": list(self.eligible_group_hashes),
                "ordered_groups_sha256": self.eligible_groups_sha256,
            },
            "shares_percent": self.shares.to_dict(),
            "zones": {
                "D0": self.d0.to_dict(),
                "D1": self.d1.to_dict(),
                "D2": self.d2.to_dict(),
                "D3": self.d3.to_dict(),
            },
            "chart_fingerprint": self.chart_fingerprint.to_dict(),
            "event_definition": {
                "formula": self.event_formula,
                "availability_timestamp": self.event_availability_timestamp,
            },
            "primary_claim": {
                "endpoint": self.primary_endpoint,
                "horizon": self.primary_horizon,
            },
            "outcome_overlap_embargo": {
                "groups": self.outcome_overlap_embargo_groups,
                "unit": "eligible_group",
            },
        }

    @property
    def contract_hash(self) -> str:
        return self.boundary_sha256

    def to_dict(self) -> dict[str, object]:
        payload = self._semantic_dict()
        payload["boundary_sha256"] = self.boundary_sha256
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ResearchD2BoundaryV1:
        _exact_keys(
            value,
            {
                "schema",
                "schema_version",
                "allocation_rule",
                "dataset_fingerprint",
                "eligible_groups",
                "shares_percent",
                "zones",
                "chart_fingerprint",
                "event_definition",
                "primary_claim",
                "outcome_overlap_embargo",
                "boundary_sha256",
            },
            _SCHEMA,
        )
        schema_version = _integer(
            value["schema_version"], "ResearchD2BoundaryV1.schema_version", minimum=1
        )
        if value["schema"] != _SCHEMA or schema_version != 1:
            raise DataError("unsupported ResearchD2BoundaryV1 schema")
        if value["allocation_rule"] != _ALLOCATION_RULE:
            raise DataError("unsupported ResearchD2BoundaryV1 allocation_rule")

        eligible = _mapping(value["eligible_groups"], "eligible_groups")
        _exact_keys(
            eligible,
            {"count", "ordered_group_hashes", "ordered_groups_sha256"},
            "eligible_groups",
        )
        raw_hashes = eligible["ordered_group_hashes"]
        if not isinstance(raw_hashes, list):
            raise DataError("eligible_groups.ordered_group_hashes must be an array")
        group_hashes = tuple(
            _sha256(item, f"eligible_groups.ordered_group_hashes[{index}]")
            for index, item in enumerate(raw_hashes)
        )
        count = _integer(eligible["count"], "eligible_groups.count")
        if count != len(group_hashes):
            raise DataError("eligible_groups.count does not match ordered_group_hashes")

        chart = ResearchChartFingerprintV1.from_dict(
            _mapping(value["chart_fingerprint"], "chart_fingerprint")
        )
        shares = ResearchEvidenceSharesV1.from_dict(
            _mapping(value["shares_percent"], "shares_percent")
        )
        event = _mapping(value["event_definition"], "event_definition")
        _exact_keys(event, {"formula", "availability_timestamp"}, "event_definition")
        primary = _mapping(value["primary_claim"], "primary_claim")
        _exact_keys(primary, {"endpoint", "horizon"}, "primary_claim")
        overlap = _mapping(value["outcome_overlap_embargo"], "outcome_overlap_embargo")
        _exact_keys(overlap, {"groups", "unit"}, "outcome_overlap_embargo")
        if overlap["unit"] != "eligible_group":
            raise DataError("outcome_overlap_embargo.unit must be eligible_group")

        result = cls(
            dataset_fingerprint=_sha256(
                value["dataset_fingerprint"], "ResearchD2BoundaryV1.dataset_fingerprint"
            ),
            eligible_group_hashes=group_hashes,
            chart_fingerprint=chart,
            event_formula=_text(event["formula"], "event_definition.formula"),
            event_availability_timestamp=_text(
                event["availability_timestamp"], "event_definition.availability_timestamp"
            ),
            primary_endpoint=_text(primary["endpoint"], "primary_claim.endpoint"),
            primary_horizon=_text(primary["horizon"], "primary_claim.horizon"),
            outcome_overlap_embargo_groups=_integer(
                overlap["groups"], "outcome_overlap_embargo.groups"
            ),
            shares=shares,
        )
        ordered_sha = _sha256(
            eligible["ordered_groups_sha256"], "eligible_groups.ordered_groups_sha256"
        )
        if ordered_sha != result.eligible_groups_sha256:
            raise DataError("eligible_groups.ordered_groups_sha256 does not match group hashes")

        serialized_zones = _mapping(value["zones"], "zones")
        _exact_keys(serialized_zones, set(_ZONES), "zones")
        for zone, derived in zip(_ZONES, (result.d0, result.d1, result.d2, result.d3), strict=True):
            serialized = ResearchEvidenceZoneBoundaryV1.from_dict(
                _mapping(serialized_zones[zone], f"zones.{zone}")
            )
            if serialized != derived:
                raise DataError(f"serialized derived {zone} allocation does not match semantics")

        supplied = _sha256(value["boundary_sha256"], "ResearchD2BoundaryV1.boundary_sha256")
        if supplied != result.boundary_sha256:
            raise DataError("boundary_sha256 does not match canonical ResearchD2BoundaryV1")
        return result

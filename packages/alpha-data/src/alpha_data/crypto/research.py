"""Research eligibility projection for frozen, qualified crypto snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final, Literal

from alpha_core import DataError

from .contracts import (
    FAMILY_AUTHORITIES,
    CryptoFamily,
    CryptoQualityReportV1,
    CryptoSnapshotV1,
)

type CryptoResearchPurpose = Literal["research", "validation", "execution_price"]

_PURPOSES: Final = frozenset({"research", "validation", "execution_price"})
_SUPPLEMENTAL_FAMILIES: Final = frozenset(
    {"asset_metadata", "market_membership", "market_reference", "onchain_catalog"}
)
_PROVIDER_NATIVE_PRICE_FAMILIES: Final = frozenset(
    {
        "market_bars",
        "trades",
        "book_snapshots",
        "derivative_bars",
        "derivative_trades",
        "derivative_book_snapshots",
        "mark_bars",
        "index_bars",
        "dex_ohlcv",
    }
)


@dataclass(frozen=True)
class CryptoResearchEligibilityV1:
    snapshot_id: str
    purpose: CryptoResearchPurpose
    required_families: tuple[CryptoFamily, ...]
    qualified_families: tuple[CryptoFamily, ...]
    supplemental_families: tuple[CryptoFamily, ...]
    blockers: tuple[str, ...]
    eligible: bool
    schema_version: int = 1


@dataclass(frozen=True)
class CryptoDatasetRequirementV1:
    """Exact dataset semantics required by one registered research operator."""

    family: CryptoFamily
    provider: str
    venue: str
    market_type: str
    instrument: str
    base_asset: str | None
    quote_asset: str | None
    frequency: str
    units: str
    timestamp_convention: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        text_fields = (
            self.provider,
            self.venue,
            self.market_type,
            self.instrument,
            self.frequency,
            self.units,
            self.timestamp_convention,
        )
        if (
            self.family not in FAMILY_AUTHORITIES
            or any(not isinstance(value, str) or not value.strip() for value in text_fields)
            or any(
                value is not None and (not isinstance(value, str) or not value.strip())
                for value in (self.base_asset, self.quote_asset)
            )
            or self.schema_version != 1
        ):
            raise DataError("crypto dataset requirement is invalid")


def assess_crypto_snapshot(
    snapshot: CryptoSnapshotV1,
    *,
    quality_reports: Mapping[str, CryptoQualityReportV1],
    required_families: tuple[CryptoFamily, ...],
    purpose: CryptoResearchPurpose,
) -> CryptoResearchEligibilityV1:
    """Reverify exact membership without treating reference data as a venue price."""
    if purpose not in _PURPOSES:
        raise DataError("crypto research purpose is invalid")
    if len(set(required_families)) != len(required_families) or any(
        family not in FAMILY_AUTHORITIES for family in required_families
    ):
        raise DataError("crypto research required families are invalid")

    blockers: set[str] = set()
    qualified: set[CryptoFamily] = set()
    artifact_hashes = [member.artifact_sha256 for member in snapshot.members]
    if len(set(artifact_hashes)) != len(artifact_hashes):
        blockers.add("duplicate_snapshot_artifact")

    for member in snapshot.members:
        family = member.dataset.family
        expected_provider = FAMILY_AUTHORITIES[family]
        if member.dataset.provider != expected_provider:
            blockers.add(f"authority_mismatch:{family}:{member.dataset.provider}")
            continue
        report = quality_reports.get(member.artifact_sha256)
        if report is None:
            blockers.add(f"missing_qualification:{member.artifact_sha256}")
            continue
        if report.dataset_sha256 != member.artifact_sha256:
            blockers.add(f"qualification_hash_mismatch:{member.artifact_sha256}")
            continue
        if report.method_version not in snapshot.qualification_versions:
            blockers.add(f"qualification_version_not_frozen:{member.artifact_sha256}")
            continue
        if report.state != "qualified" or report.failures or report.warnings:
            blockers.add(f"not_qualified:{member.artifact_sha256}:{report.state}")
            continue
        qualified.add(family)

    for family in required_families:
        if family not in qualified:
            blockers.add(f"missing_required_family:{family}")
    if purpose in {"validation", "execution_price"} and not (
        qualified & _PROVIDER_NATIVE_PRICE_FAMILIES
    ):
        blockers.add("provider_native_price_required")

    qualified_families = tuple(sorted(qualified))
    supplemental = tuple(sorted(qualified & _SUPPLEMENTAL_FAMILIES))
    ordered_blockers = tuple(sorted(blockers))
    return CryptoResearchEligibilityV1(
        snapshot_id=snapshot.snapshot_id,
        purpose=purpose,
        required_families=required_families,
        qualified_families=qualified_families,
        supplemental_families=supplemental,
        blockers=ordered_blockers,
        eligible=not ordered_blockers,
    )


def require_crypto_snapshot(
    snapshot: CryptoSnapshotV1,
    *,
    quality_reports: Mapping[str, CryptoQualityReportV1],
    required_families: tuple[CryptoFamily, ...],
    purpose: CryptoResearchPurpose,
) -> CryptoResearchEligibilityV1:
    projection = assess_crypto_snapshot(
        snapshot,
        quality_reports=quality_reports,
        required_families=required_families,
        purpose=purpose,
    )
    if not projection.eligible:
        raise DataError(
            f"crypto snapshot is not research eligible: {', '.join(projection.blockers)}"
        )
    return projection


def assess_crypto_dataset_requirements(
    snapshot: CryptoSnapshotV1,
    *,
    quality_reports: Mapping[str, CryptoQualityReportV1],
    requirements: tuple[CryptoDatasetRequirementV1, ...],
    purpose: CryptoResearchPurpose,
) -> CryptoResearchEligibilityV1:
    """Require one qualified snapshot member matching every exact dataset contract."""
    families = tuple(requirement.family for requirement in requirements)
    if not requirements or len(set(families)) != len(families):
        raise DataError("crypto dataset requirements are invalid")
    projection = assess_crypto_snapshot(
        snapshot,
        quality_reports=quality_reports,
        required_families=families,
        purpose=purpose,
    )
    blockers = set(projection.blockers)
    fields = (
        "provider",
        "venue",
        "market_type",
        "instrument",
        "base_asset",
        "quote_asset",
        "frequency",
        "units",
        "timestamp_convention",
    )
    for requirement in requirements:
        members = tuple(
            member for member in snapshot.members if member.dataset.family == requirement.family
        )
        if len(members) > 1:
            blockers.add(f"duplicate_required_family:{requirement.family}")
        if len(members) != 1:
            continue
        dataset = members[0].dataset
        for field in fields:
            if getattr(dataset, field) != getattr(requirement, field):
                blockers.add(f"dataset_mismatch:{requirement.family}:{field}")
    ordered_blockers = tuple(sorted(blockers))
    return replace(
        projection,
        blockers=ordered_blockers,
        eligible=not ordered_blockers,
    )


def require_crypto_dataset_requirements(
    snapshot: CryptoSnapshotV1,
    *,
    quality_reports: Mapping[str, CryptoQualityReportV1],
    requirements: tuple[CryptoDatasetRequirementV1, ...],
    purpose: CryptoResearchPurpose,
) -> CryptoResearchEligibilityV1:
    projection = assess_crypto_dataset_requirements(
        snapshot,
        quality_reports=quality_reports,
        requirements=requirements,
        purpose=purpose,
    )
    if not projection.eligible:
        raise DataError(
            f"crypto snapshot does not satisfy exact dataset requirements: "
            f"{', '.join(projection.blockers)}"
        )
    return projection


__all__ = [
    "CryptoDatasetRequirementV1",
    "CryptoResearchEligibilityV1",
    "CryptoResearchPurpose",
    "assess_crypto_dataset_requirements",
    "assess_crypto_snapshot",
    "require_crypto_dataset_requirements",
    "require_crypto_snapshot",
]

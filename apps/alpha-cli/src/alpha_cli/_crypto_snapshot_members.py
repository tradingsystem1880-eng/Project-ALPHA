"""Shared capture equivalence, range checks, and canonical snapshot membership."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence

from alpha_cli._crypto_analysis import normalized_member
from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoQualityReportV1, CryptoSnapshotMemberV1
from alpha_data.crypto.storage import CryptoBulkStore

MemberWithQuality = tuple[CryptoSnapshotMemberV1, CryptoQualityReportV1]
_RAW_LINEAGE_ERROR = "crypto snapshot member raw lineage is missing or invalid"
_RANGE_ERROR = "crypto snapshot members of one dataset must cover disjoint observed ranges"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _raw_ids(manifest: Mapping[str, object]) -> list[str]:
    values = manifest.get("input_manifest_ids")
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise DataError(_RAW_LINEAGE_ERROR)
    return values


def capture_signature(
    manifest: Mapping[str, object], raw_by_id: Mapping[str, dict[str, object]]
) -> dict[str, object]:
    """Keep all evidence fields except the explicitly per-fetch identities and time."""
    raw_inputs: list[dict[str, object]] = []
    for raw_id in _raw_ids(manifest):
        raw = raw_by_id.get(raw_id)
        legacy_raw = raw is not None and raw.get("artifact_kind") is None
        if raw is None or not (
            raw.get("artifact_kind") == "raw"
            or (legacy_raw and str(raw.get("artifact_key", "")).startswith("raw/"))
        ):
            # Same raw-input test as CryptoBulkStore.publish_normalized, legacy raw keys included.
            raise DataError(_RAW_LINEAGE_ERROR)
        retained = {
            key: value
            for key, value in raw.items()
            if key not in {"manifest_id", "artifact_key", "receipt_id"}
        }
        receipt = retained.get("receipt")
        if isinstance(receipt, dict):
            retained["receipt"] = {
                key: value
                for key, value in receipt.items()
                if key not in {"fetched_at", "receipt_id"}
            }
        raw_inputs.append(retained)
    signature = {
        key: value
        for key, value in manifest.items()
        if key not in {"manifest_id", "input_manifest_ids"}
    }
    signature["raw_inputs"] = sorted(raw_inputs, key=_canonical)
    return signature


def _matches(member: CryptoSnapshotMemberV1, manifest: Mapping[str, object]) -> bool:
    return (
        manifest.get("artifact_kind") == "normalized"
        and manifest.get("artifact_key") == member.artifact_key
        and manifest.get("artifact_sha256") == member.artifact_sha256
        and manifest.get("dataset") == member.dataset.to_dict()
    )


def resolve_member(
    member: CryptoSnapshotMemberV1,
    normalized_manifests: Iterable[dict[str, object]],
    raw_by_id: Mapping[str, dict[str, object]],
) -> dict[str, object]:
    """Resolve identical retained captures deterministically; refuse divergent evidence."""
    candidates = [manifest for manifest in normalized_manifests if _matches(member, manifest)]
    if not candidates:
        raise DataError("crypto snapshot member manifest is missing or mismatched")
    if len(candidates) > 1:
        signature = capture_signature(candidates[0], raw_by_id)
        if any(
            capture_signature(candidate, raw_by_id) != signature for candidate in candidates[1:]
        ):
            raise DataError(
                "crypto snapshot member manifest is ambiguous; retained captures of the same "
                "bytes differ in quality, scope or source content"
            )
    return min(candidates, key=lambda manifest: str(manifest["manifest_id"]))


def canonical_order(
    members_with_quality: Iterable[MemberWithQuality],
) -> tuple[MemberWithQuality, ...]:
    """Order membership by dataset identity, observed start, then artifact hash."""
    return tuple(
        sorted(
            members_with_quality,
            key=lambda pair: (
                _canonical(pair[0].dataset.to_dict()),
                pair[1].observed_start.isoformat() if pair[1].observed_start else "",
                pair[0].artifact_sha256,
            ),
        )
    )


def check_dataset_ranges(members_with_quality: Iterable[MemberWithQuality]) -> None:
    """Require disjoint closed observed ranges for members sharing a dataset."""
    groups: dict[str, list[MemberWithQuality]] = {}
    for pair in members_with_quality:
        groups.setdefault(_canonical(pair[0].dataset.to_dict()), []).append(pair)
    for group in groups.values():
        if len(group) < 2:
            continue
        previous_end = None
        for _, quality in canonical_order(group):
            start, end = quality.observed_start, quality.observed_end
            if start is None or end is None or (previous_end is not None and start <= previous_end):
                raise DataError(_RANGE_ERROR)
            previous_end = end


def resolve_creation_members(
    store: CryptoBulkStore, manifest_ids: Sequence[str]
) -> tuple[MemberWithQuality, ...]:
    """Verify all matching active captures before admitting canonical membership."""
    requested = [normalized_member(store, manifest_id) for manifest_id in manifest_ids]
    inventory = store.metadata_inventory()
    resolved: list[MemberWithQuality] = []
    seen: set[str] = set()
    for member, _ in requested:
        candidates: list[dict[str, object]] = []
        raw_by_id: dict[str, dict[str, object]] = {}
        for metadata in inventory:
            if _matches(member, metadata):
                candidate = store.verify_manifest(metadata["manifest_id"])
                candidates.append(candidate)
                for raw_id in _raw_ids(candidate):
                    raw_by_id[raw_id] = store.verify_manifest(raw_id)
        manifest = resolve_member(member, candidates, raw_by_id)
        if member.artifact_sha256 in seen:
            raise DataError("crypto snapshot names the same capture more than once")
        seen.add(member.artifact_sha256)
        resolved.append((member, CryptoQualityReportV1.from_dict(manifest.get("quality"))))
    check_dataset_ranges(resolved)
    return canonical_order(resolved)

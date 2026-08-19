"""Reverify the qualified crypto snapshot bound to a governed research contract."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple, Protocol, cast

from alpha_core import DataError
from alpha_research import CryptoCrowdingObservationV1, ResearchD2BoundaryV2


class ResearchDatasetReader(Protocol):
    def get_research_dataset(self, ref_id: str) -> dict[str, object]: ...


class CryptoEmpiricalDataset(NamedTuple):
    ref: dict[str, object]
    snapshot_id: str
    snapshot_hash: str
    operator_fingerprint: str
    asset_master_version: str
    qualification_versions: tuple[str, ...]
    observations: tuple[CryptoCrowdingObservationV1, ...]


def _sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def load_crypto_empirical_dataset(
    store: ResearchDatasetReader, ref_id: str
) -> CryptoEmpiricalDataset:
    """Reverify one registered CryptoSnapshotV1 and compose its causal observations."""
    ref = store.get_research_dataset(ref_id)
    origin = ref.get("origin")
    if (
        ref.get("dataset_kind") != "snapshot"
        or ref.get("instrument") != "BTC"
        or ref.get("provider") != "crypto-data-house"
        or not isinstance(origin, Mapping)
        or origin.get("snapshot_schema") != "CryptoSnapshotV1"
    ):
        raise DataError("crypto crowding requires one registered CryptoSnapshotV1 BTC dataset")
    snapshot_id = origin.get("snapshot_id")
    snapshot_hash = origin.get("manifest_sha256")
    if not _sha256(snapshot_id) or not _sha256(snapshot_hash):
        raise DataError("crypto crowding registered snapshot binding is malformed")
    assert isinstance(snapshot_id, str) and isinstance(snapshot_hash, str)

    from alpha_cli.crypto_data_cmds import (  # noqa: PLC0415
        crypto_crowding_observations,
        crypto_crowding_snapshot_compatibility,
    )

    projection = crypto_crowding_snapshot_compatibility(snapshot_id)
    observations = crypto_crowding_observations(snapshot_id)
    operator_fingerprint = projection.get("operator_fingerprint")
    asset_master_version = projection.get("asset_master_version")
    versions = projection.get("qualification_versions")
    if (
        projection.get("eligible") is not True
        or projection.get("bundle_id") != "bybit_btcusdt_crowding_reversal_v1"
        or not _sha256(operator_fingerprint)
        or not isinstance(asset_master_version, str)
        or not isinstance(versions, list)
        or not versions
        or any(not isinstance(value, str) or not value for value in versions)
        or not observations
    ):
        raise DataError("crypto crowding snapshot compatibility projection is incomplete")
    assert isinstance(operator_fingerprint, str)
    return CryptoEmpiricalDataset(
        ref=ref,
        snapshot_id=snapshot_id,
        snapshot_hash=snapshot_hash,
        operator_fingerprint=operator_fingerprint,
        asset_master_version=asset_master_version,
        qualification_versions=tuple(cast(list[str], versions)),
        observations=observations,
    )


def load_crypto_empirical_d1(
    store: ResearchDatasetReader, payload: Mapping[str, object]
) -> tuple[tuple[CryptoCrowdingObservationV1, ...], ResearchD2BoundaryV2]:
    """Reload and reverify the exact snapshot and its complete V2 membership."""
    protocol = payload.get("protocol")
    section = None if not isinstance(protocol, Mapping) else protocol.get("empirical_dataset")
    if not isinstance(section, Mapping) or not isinstance(protocol, Mapping):
        raise DataError("the crypto empirical contract carries no frozen snapshot binding")
    binding = load_crypto_empirical_dataset(store, str(section.get("ref_id", "")))
    hashes = payload.get("hashes")
    frozen = None if not isinstance(hashes, Mapping) else hashes.get("data")
    if (
        frozen != binding.snapshot_id
        or section.get("content_sha256") != binding.snapshot_id
        or section.get("snapshot_id") != binding.snapshot_id
        or section.get("snapshot_hash") != binding.snapshot_hash
        or section.get("operator_fingerprint") != binding.operator_fingerprint
        or section.get("asset_master_version") != binding.asset_master_version
        or section.get("qualification_versions") != list(binding.qualification_versions)
    ):
        raise DataError("crypto snapshot no longer reproduces the approval-frozen binding")
    topology = protocol.get("evidence_topology")
    boundary_value = None if not isinstance(topology, Mapping) else topology.get("boundary")
    if not isinstance(boundary_value, Mapping):
        raise DataError("the crypto empirical contract carries no sealed evidence boundary")
    boundary = ResearchD2BoundaryV2.from_dict(boundary_value)
    groups = tuple(item.funding_time.isoformat() for item in binding.observations)
    if not boundary.verify_eligible_groups(groups):
        raise DataError("crypto snapshot membership no longer reproduces the frozen boundary")
    return binding.observations, boundary


__all__ = [
    "CryptoEmpiricalDataset",
    "load_crypto_empirical_d1",
    "load_crypto_empirical_dataset",
]

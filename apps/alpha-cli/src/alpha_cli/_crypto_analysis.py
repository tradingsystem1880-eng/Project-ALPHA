"""Artifact qualification, feature, and comparison helpers for the crypto CLI."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Final, cast

import polars as pl

from alpha_core import DataError
from alpha_data.crypto.contracts import (
    FAMILY_AUTHORITIES,
    CryptoAcquisitionScopeV1,
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    CryptoRawReceiptV1,
    CryptoSnapshotMemberV1,
)
from alpha_data.crypto.features import (
    CryptoFeatureArtifactV1,
    QualifiedCryptoFrame,
    basis_features,
    feature_frame_bytes,
    funding_features,
    liquidity_features,
    onchain_features,
    open_interest_features,
    volatility_surface_features,
)
from alpha_data.crypto.storage import CryptoBulkStore

_CASE_BOUND_EVENT_FAMILIES: Final = frozenset({"derivative_trades", "derivative_book_snapshots"})
_FEATURE_INPUT_NAMES: Final = {
    "funding": ("funding",),
    "open_interest_change": ("open_interest",),
    "basis": ("mark", "index", "premium"),
    "volatility_surface": ("quotes", "instruments"),
    "liquidity": ("pools",),
    "onchain_change": ("onchain",),
}


def feature_input_names(feature_name: str) -> tuple[str, ...] | None:
    """Return the ordered input names for one supported feature."""
    return _FEATURE_INPUT_NAMES.get(feature_name)


class LegacyUnscopedEventError(DataError):
    """Historical bytes are valid but cannot qualify as governed research evidence."""


def manifest_acquisition_scope(
    manifest: dict[str, object], dataset: CryptoDatasetIdentityV1
) -> CryptoAcquisitionScopeV1 | None:
    raw_scope = manifest.get("acquisition_scope")
    if dataset.family in _CASE_BOUND_EVENT_FAMILIES:
        try:
            return CryptoAcquisitionScopeV1.from_dict(raw_scope)
        except DataError as exc:
            raise LegacyUnscopedEventError(
                "legacy unscoped derivative event data cannot enter governed research evidence"
            ) from exc
    if raw_scope is not None:
        raise DataError("crypto acquisition scope is attached to an unsupported dataset family")
    return None


def normalized_member(
    store: CryptoBulkStore, manifest_id: str
) -> tuple[CryptoSnapshotMemberV1, CryptoQualityReportV1]:
    manifest = store.verify_manifest(manifest_id)
    if manifest.get("artifact_kind") != "normalized":
        raise DataError("crypto snapshot members must be normalized artifacts")
    dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
    quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    artifact_key, artifact_hash = manifest.get("artifact_key"), manifest.get("artifact_sha256")
    if not isinstance(artifact_key, str) or not isinstance(artifact_hash, str):
        raise DataError("crypto normalized manifest membership is invalid")
    if quality.dataset_sha256 != artifact_hash or quality.state != "qualified":
        raise DataError("crypto snapshot creation requires exact qualified artifacts")
    if dataset.provider != FAMILY_AUTHORITIES[dataset.family]:
        raise DataError("crypto normalized manifest has the wrong family authority")
    manifest_acquisition_scope(manifest, dataset)
    return (
        CryptoSnapshotMemberV1(
            dataset=dataset,
            artifact_key=artifact_key,
            artifact_sha256=artifact_hash,
        ),
        quality,
    )


def coverage_row(
    manifest: dict[str, object], *, store: CryptoBulkStore | None = None
) -> dict[str, object]:
    dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
    quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    manifest_id = manifest.get("manifest_id")
    if not isinstance(manifest_id, str):
        raise DataError("crypto normalized manifest id is invalid")
    fetched_at: str | None = None
    input_manifest_ids = manifest.get("input_manifest_ids")
    if store is not None and isinstance(input_manifest_ids, list) and input_manifest_ids:
        receipt_times: set[str] = set()
        for input_manifest_id in input_manifest_ids:
            raw_manifest = store.verify_manifest(input_manifest_id)
            raw_receipt = raw_manifest.get("receipt")
            if raw_receipt is None:
                receipt_times.clear()
                break
            receipt_times.add(CryptoRawReceiptV1.from_dict(raw_receipt).fetched_at.isoformat())
        if len(receipt_times) == 1:
            fetched_at = receipt_times.pop()
    return {
        "manifest_id": manifest_id,
        "provider": dataset.provider,
        "venue": dataset.venue,
        "market_type": dataset.market_type,
        "family": dataset.family,
        "instrument": dataset.instrument,
        "base_asset": dataset.base_asset,
        "quote_asset": dataset.quote_asset,
        "frequency": dataset.frequency,
        "units": dataset.units,
        "timestamp_convention": dataset.timestamp_convention,
        "state": quality.state,
        "failures": list(quality.failures),
        "warnings": list(quality.warnings),
        "observed_start": quality.observed_start.isoformat() if quality.observed_start else None,
        "observed_end": quality.observed_end.isoformat() if quality.observed_end else None,
        "row_count": quality.row_count,
        "artifact_sha256": quality.dataset_sha256,
        "method_version": quality.method_version,
        "fetched_at": fetched_at,
    }


def parquet_frame(store: CryptoBulkStore, manifest: dict[str, object]) -> pl.DataFrame:
    artifact_key = manifest.get("artifact_key")
    if not isinstance(artifact_key, str):
        raise DataError("crypto normalized artifact key is invalid")
    try:
        return pl.read_parquet(store.bulk_root / artifact_key)
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise DataError("crypto normalized artifact is unreadable") from exc


def qualified_feature_source(
    store: CryptoBulkStore, *, name: str, manifest_id: str
) -> QualifiedCryptoFrame:
    manifest = store.verify_manifest(manifest_id)
    if manifest.get("artifact_kind") != "normalized":
        raise DataError("crypto feature inputs must be normalized manifests")
    dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
    quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    artifact_sha256 = manifest.get("artifact_sha256")
    if not isinstance(artifact_sha256, str):
        raise DataError("crypto feature input artifact hash is invalid")
    return QualifiedCryptoFrame(
        name=name,
        dataset=dataset,
        artifact_sha256=artifact_sha256,
        quality=quality,
        frame=parquet_frame(store, manifest),
    )


def create_feature(
    store: CryptoBulkStore,
    feature_name: str,
    *,
    inputs: tuple[tuple[str, str], ...],
    available_at: datetime,
) -> dict[str, object]:
    expected = _FEATURE_INPUT_NAMES.get(feature_name)
    if expected is None:
        raise DataError("crypto feature name is unsupported")
    if tuple(name for name, _manifest_id in inputs) != expected or len(
        {manifest_id for _name, manifest_id in inputs}
    ) != len(inputs):
        raise DataError(
            f"crypto {feature_name} feature requires ordered inputs: {', '.join(expected)}"
        )
    sources = tuple(
        qualified_feature_source(store, name=name, manifest_id=manifest_id)
        for name, manifest_id in inputs
    )
    if feature_name == "funding":
        frame, artifact = funding_features(sources[0], available_at=available_at)
    elif feature_name == "open_interest_change":
        frame, artifact = open_interest_features(sources[0], available_at=available_at)
    elif feature_name == "basis":
        frame, artifact = basis_features(
            sources[0], sources[1], sources[2], available_at=available_at
        )
    elif feature_name == "volatility_surface":
        frame, artifact = volatility_surface_features(
            sources[0], sources[1], available_at=available_at
        )
    elif feature_name == "liquidity":
        frame, artifact = liquidity_features(sources[0], available_at=available_at)
    else:
        frame, artifact = onchain_features(sources[0], available_at=available_at)
    payload = feature_frame_bytes(frame)
    if hashlib.sha256(payload).hexdigest() != artifact.artifact_sha256:
        raise DataError("crypto feature payload does not match its immutable contract")
    derived = store.publish_derived(
        payload,
        derived_kind="crypto-feature",
        input_manifest_ids=tuple(manifest_id for _name, manifest_id in inputs),
        metadata={
            "feature": artifact.to_dict(),
            "input_manifest_ids_by_name": [list(item) for item in inputs],
            "research_authority": False,
            "execution_authority": False,
        },
    )
    return {
        "manifest_id": derived["manifest_id"],
        "feature_id": artifact.feature_id,
        "feature_name": artifact.feature_name,
        "method_version": artifact.method_version,
        "available_at": artifact.available_at.isoformat(),
        "row_count": artifact.row_count,
        "artifact_sha256": artifact.artifact_sha256,
        "input_count": len(inputs),
        "state": "frozen",
        "research_authority": False,
        "execution_authority": False,
        "next_action": "Bind this feature beside its exact frozen crypto snapshot.",
    }


def feature_projection(store: CryptoBulkStore, manifest: dict[str, object]) -> dict[str, object]:
    if (
        manifest.get("artifact_kind") != "derived"
        or manifest.get("derived_kind") != "crypto-feature"
        or not isinstance(manifest.get("metadata"), dict)
    ):
        raise DataError("crypto feature manifest is invalid")
    metadata = cast(dict[str, object], manifest["metadata"])
    if (
        metadata.get("research_authority") is not False
        or metadata.get("execution_authority") is not False
        or not isinstance(metadata.get("input_manifest_ids_by_name"), list)
    ):
        raise DataError("crypto feature authority metadata is invalid")
    artifact = CryptoFeatureArtifactV1.from_dict(metadata.get("feature"))
    if manifest.get("artifact_sha256") != artifact.artifact_sha256:
        raise DataError("crypto feature manifest does not match its artifact contract")
    named_inputs = cast(list[object], metadata["input_manifest_ids_by_name"])
    expected_names = _FEATURE_INPUT_NAMES[artifact.feature_name]
    lineage_ids = manifest.get("input_manifest_ids")
    if (
        tuple(name for name, _digest in artifact.input_sha256) != expected_names
        or len(named_inputs) != len(artifact.input_sha256)
        or not isinstance(lineage_ids, list)
        or len(lineage_ids) != len(named_inputs)
    ):
        raise DataError("crypto feature input lineage is incomplete")
    for item, lineage_id, (expected_name, expected_hash) in zip(
        named_inputs, lineage_ids, artifact.input_sha256, strict=True
    ):
        if (
            not isinstance(item, list)
            or len(item) != 2
            or item[0] != expected_name
            or not isinstance(item[1], str)
            or item[1] != lineage_id
            or store.verify_manifest(item[1]).get("artifact_sha256") != expected_hash
        ):
            raise DataError("crypto feature input lineage is invalid")
    manifest_id = manifest.get("manifest_id")
    if not isinstance(manifest_id, str):
        raise DataError("crypto feature manifest id is invalid")
    return {
        "manifest_id": manifest_id,
        "feature_id": artifact.feature_id,
        "feature_name": artifact.feature_name,
        "method_version": artifact.method_version,
        "available_at": artifact.available_at.isoformat(),
        "row_count": artifact.row_count,
        "artifact_sha256": artifact.artifact_sha256,
        "input_count": len(artifact.input_sha256),
        "state": "verified",
        "research_authority": False,
        "execution_authority": False,
    }


def comparison_frame(
    store: CryptoBulkStore, manifest_id: str
) -> tuple[dict[str, object], CryptoDatasetIdentityV1, CryptoQualityReportV1, pl.DataFrame]:
    manifest = store.verify_manifest(manifest_id)
    if manifest.get("artifact_kind") != "normalized":
        raise DataError("crypto comparison inputs must be normalized manifests")
    dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
    report = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    if report.state != "qualified" or report.failures or report.warnings:
        raise DataError("crypto comparison inputs must be exactly qualified")
    artifact_key = manifest.get("artifact_key")
    if not isinstance(artifact_key, str):
        raise DataError("crypto comparison artifact key is invalid")
    try:
        frame = pl.read_parquet(store.bulk_root / artifact_key)
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise DataError("crypto comparison artifact is unreadable") from exc
    if "timestamp" not in frame.columns and "open_time" in frame.columns:
        frame = frame.rename({"open_time": "timestamp"})
    return manifest, dataset, report, frame

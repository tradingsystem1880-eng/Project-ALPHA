"""Reopen committed catalog evidence before consuming a frozen custom asset master.

This verifies retained provenance, not identity derivation, historical publication,
rights, a new mapping policy, or research/execution authority. Never rebuild mappings.
"""

from __future__ import annotations

from alpha_core import DataError
from alpha_data.crypto.asset_master import AssetMaster
from alpha_data.crypto.contracts import (
    FAMILY_AUTHORITIES,
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
)
from alpha_data.crypto.storage import CryptoBulkStore


def verify_asset_master_sources(store: CryptoBulkStore, master: AssetMaster) -> None:
    """Read-only verification. Callers publishing new use hold admission_lock outside.

    Source order is the existing create contract: CoinGecko all followed by one or
    more GeckoTerminal pool catalogs. Legacy unbound masters remain decodable but
    cannot acquire retained-source verification by inference.
    """
    if len(master.source_manifest_ids) < 2:
        raise DataError(
            "crypto asset-master provenance unavailable: no complete bound catalog sources"
        )
    store.verify_readable()
    for index, manifest_id in enumerate(master.source_manifest_ids):
        store.require_active(manifest_id)
        manifest = store.verify_manifest(manifest_id)
        dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
        report = CryptoQualityReportV1.from_dict(manifest.get("quality"))
        family = "asset_metadata" if index == 0 else "dex_pools"
        if (
            manifest.get("artifact_kind") != "normalized"
            or dataset.family != family
            or dataset.provider != FAMILY_AUTHORITIES[family]
            or (index == 0 and dataset.instrument != "all")
            or report.state != "qualified"
            or report.dataset_sha256 != manifest.get("artifact_sha256")
        ):
            raise DataError(
                "crypto asset-master provenance unavailable: bound catalog is incompatible"
            )

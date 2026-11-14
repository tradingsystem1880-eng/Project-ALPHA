"""Reviewed built-in masters resolve without retained catalog provenance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli import _crypto_asset_master_sources, crypto_data_cmds
from alpha_cli.main import app
from alpha_data.crypto.asset_master import REVIEWED_NATIVE_LABELS, AssetMaster
from alpha_data.crypto.storage import Capacity, CryptoBulkStore


@pytest.mark.parametrize("label", REVIEWED_NATIVE_LABELS)
def test_builtin_asset_master_matches_reviewed_identities(label: str) -> None:
    master = _crypto_asset_master_sources.builtin_asset_master(label)
    assert master is not None
    assert master.identities == AssetMaster.with_reviewed_native_assets(label).identities
    assert master.source_manifest_ids == ()


@pytest.mark.parametrize("version", ["a" * 64, "reviewed-native-v9"])
def test_builtin_asset_master_refuses_other_versions(version: str) -> None:
    assert _crypto_asset_master_sources.builtin_asset_master(version) is None


def test_asset_master_verify_accepts_reviewed_builtin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = CryptoBulkStore(
        bulk_root=tmp_path / "bulk",
        manifest_root=tmp_path / "manifests",
        expected_volume_uuid="SYNTHETIC",
        volume_uuid=lambda _: "SYNTHETIC",
        capacity=lambda _: Capacity(2_000_000_000_000, 1_500_000_000_000),
    )
    store.bulk_root.mkdir()
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path / "control"))
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    result = CliRunner().invoke(
        app, ["crypto-data", "asset-master-verify", "reviewed-native-v1", "--json"]
    )
    assert result.exit_code == 0, result.output
    checked = json.loads(result.stdout)
    assert checked["state"] == "verified"
    assert checked["source_manifest_ids"] == []

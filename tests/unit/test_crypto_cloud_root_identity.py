"""Artificial filesystem observations exercise the cloud contract, not hosting durability."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from alpha_cli.crypto_bulk_store import configured_crypto_bulk_store
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_data.crypto import root_identity
from alpha_data.crypto.root_identity import (
    CloudBulkRootIdentityV1,
    CloudRootObservationV1,
    inspect_cloud_root,
)
from alpha_data.crypto.storage import Capacity, CryptoBulkStore


def _identity(root: Path) -> CloudBulkRootIdentityV1:
    return CloudBulkRootIdentityV1(
        root=root,
        mount_point=Path("/"),
        device_id=123,
        owner_uid=456,
        filesystem_type="ext4",
        mount_source="/dev/artificial-fixture",
        durable_hosting_reference="artificial-test-fixture-not-a-hosting-claim",
    )


def _observe(monkeypatch: pytest.MonkeyPatch, identity: CloudBulkRootIdentityV1) -> None:
    # Simulate a mounted durable device for contract tests. Production inspection is
    # separately tested to reject this disposable pytest directory.
    monkeypatch.setattr(
        root_identity,
        "inspect_cloud_root",
        lambda root: CloudRootObservationV1(
            root,
            identity.mount_point,
            identity.device_id,
            identity.owner_uid,
            identity.filesystem_type,
            identity.mount_source,
        ),
    )


def _config(root: Path, control: Path | None = None) -> dict[str, object]:
    identity = _identity(root)
    return {
        "schema": "CryptoBulkStorageConfigV1",
        "backend": "cloud_root_identity",
        "bulk_root": str(root),
        "control_root": str((control or root.parent).resolve()),
        **{key: value for key, value in identity.to_dict().items() if key != "root"},
    }


def _write_config(control: Path, root: Path) -> None:
    destination = control / "crypto" / "storage-config.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(_config(root, control)), encoding="utf-8")


def test_actual_temporary_directory_is_never_a_durable_cloud_root(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="disposable temporary"):
        inspect_cloud_root(tmp_path)


def test_symlink_ancestor_is_rejected_before_mount_inspection(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(DataError, match="symlink"):
        inspect_cloud_root(link)


def test_cloud_identity_rejects_relative_or_implicit_roots() -> None:
    for root in (Path("data/bulk"), Path("/"), Path("/srv/../bulk")):
        with pytest.raises(DataError, match="exact identity"):
            _identity(root)


@pytest.mark.parametrize(
    "defect", ["mount_point", "device_id", "owner_uid", "filesystem_type", "mount_source"]
)
def test_cloud_identity_rejects_mount_device_owner_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    expected = _identity(tmp_path)
    changes: dict[str, object] = {
        "mount_point": Path("/other"),
        "device_id": 124,
        "owner_uid": 457,
        "filesystem_type": "xfs",
        "mount_source": "/dev/replacement",
    }
    observation = CloudRootObservationV1(
        tmp_path,
        expected.mount_point,
        expected.device_id,
        expected.owner_uid,
        expected.filesystem_type,
        expected.mount_source,
    )
    changed = CloudRootObservationV1(
        root=observation.root,
        mount_point=Path("/other") if defect == "mount_point" else observation.mount_point,
        device_id=124 if defect == "device_id" else observation.device_id,
        owner_uid=457 if defect == "owner_uid" else observation.owner_uid,
        filesystem_type="xfs" if defect == "filesystem_type" else observation.filesystem_type,
        mount_source="/dev/replacement" if defect == "mount_source" else observation.mount_source,
    )
    assert changes[defect] != getattr(observation, defect)
    monkeypatch.setattr(root_identity, "inspect_cloud_root", lambda _: changed)
    with pytest.raises(DataError, match="mount/device/owner identity"):
        expected.verify(tmp_path)


def test_identity_cannot_be_reused_for_another_root(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="differs from its pinned identity"):
        _identity(tmp_path).verify(tmp_path / "other")


@pytest.mark.parametrize("filesystem", ["overlay", "tmpfs", "ramfs"])
def test_disposable_filesystems_are_not_selectable(tmp_path: Path, filesystem: str) -> None:
    with pytest.raises(DataError, match="exact identity"):
        replace(_identity(tmp_path), filesystem_type=filesystem)


def test_operator_hosting_decision_is_mandatory(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="durable-hosting decision"):
        replace(_identity(tmp_path), durable_hosting_reference="")


def test_cloud_store_preserves_capacity_reserve_and_no_uuid_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = _identity(tmp_path)
    _observe(monkeypatch, identity)

    def forbidden_uuid(_: Path) -> str:
        pytest.fail("cloud backend called Mac volume UUID probe")

    store = CryptoBulkStore(
        bulk_root=tmp_path,
        manifest_root=tmp_path / "control",
        cloud_root_identity=identity,
        volume_uuid=forbidden_uuid,
        capacity=lambda _: Capacity(total_bytes=1000, free_bytes=200),
        reserve_fraction=0.15,
        minimum_free_bytes=100,
    )
    assert store.verify_readable().free_bytes == 200
    store.verify_ready(required_bytes=50)
    with pytest.raises(DataError, match="free-space reserve"):
        store.verify_ready(required_bytes=51)
    with pytest.raises(DataError, match="exactly one identity"):
        CryptoBulkStore(
            bulk_root=tmp_path,
            manifest_root=tmp_path / "control",
            cloud_root_identity=identity,
            expected_volume_uuid="MAC-UUID",
        )


def test_retained_operator_config_reopens_without_environment_and_does_not_create_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    control, bulk = tmp_path / "control", tmp_path / "bulk"
    _write_config(control, bulk)
    _observe(monkeypatch, _identity(bulk))
    store = configured_crypto_bulk_store(control)
    assert store.bulk_root == bulk
    assert store.manifest_root == control / "crypto" / "manifests"
    assert not bulk.exists()
    with pytest.raises(DataError, match="not mounted"):
        store.verify_readable()
    bulk.mkdir()
    _observe(monkeypatch, _identity(bulk))
    assert store.verify_readable().total_bytes > 0


def test_missing_or_conflicting_configuration_fails(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="no retained operator"):
        configured_crypto_bulk_store(tmp_path)
    root = tmp_path / "bulk"
    _write_config(tmp_path, root)
    with pytest.raises(DataError, match="conflict"):
        configured_crypto_bulk_store(
            AlphaSettings(
                _env_file=None,
                data_dir=tmp_path,
                bulk_data_dir=root,
                bulk_volume_uuid="MAC-UUID",
            )
        )
    config_path = tmp_path / "crypto" / "storage-config.json"
    config_path.write_text(json.dumps({**_config(root), "device_id": True}))
    with pytest.raises(DataError, match="nonnegative integer device_id"):
        configured_crypto_bulk_store(tmp_path)


def test_config_symlinks_and_unknown_fields_fail(tmp_path: Path) -> None:
    control, bulk = tmp_path / "control", tmp_path / "bulk"
    _write_config(control, bulk)
    path = control / "crypto" / "storage-config.json"
    path.write_text(json.dumps({**_config(bulk), "trust_workspace": True}))
    with pytest.raises(DataError, match="backend/fields differ"):
        configured_crypto_bulk_store(control)
    destination = tmp_path / "external.json"
    path.rename(destination)
    path.symlink_to(destination)
    with pytest.raises(DataError, match="unsafe"):
        configured_crypto_bulk_store(control)


def test_explicit_cloud_settings_and_mac_defaults_are_distinct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    default = AlphaSettings(_env_file=None, data_dir=tmp_path)
    assert default.bulk_storage_backend == "macos_volume_uuid"
    with pytest.raises(DataError, match="not configured"):
        configured_crypto_bulk_store(default)
    settings = AlphaSettings(
        _env_file=None,
        data_dir=tmp_path,
        bulk_data_dir=tmp_path / "bulk",
        bulk_storage_backend="cloud_root_identity",
        bulk_cloud_mount_point=Path("/"),
        bulk_cloud_device_id=123,
        bulk_cloud_owner_uid=456,
        bulk_cloud_filesystem_type="ext4",
        bulk_cloud_mount_source="/dev/artificial-fixture",
        bulk_cloud_durability_reference="artificial-test-fixture-not-a-hosting-claim",
    )
    _observe(monkeypatch, _identity(tmp_path / "bulk"))
    assert configured_crypto_bulk_store(settings).cloud_root_identity == _identity(
        tmp_path / "bulk"
    )


def test_explicit_restored_cloud_root_reopens_preserved_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil
    from datetime import UTC, datetime

    from alpha_cli.crypto_price_snapshot_query import query_binance_daily_price_snapshot
    from tests.unit.test_crypto_price_snapshot_query import START, _full_discovery_fixture

    original = tmp_path / "original"
    original.mkdir()
    _, snapshot, manifest = _full_discovery_fixture(original)
    _write_config(original / "control", original / "bulk")
    _observe(monkeypatch, _identity(original / "bulk"))
    before = query_binance_daily_price_snapshot(
        snapshot,
        configured_crypto_bulk_store(original / "control"),
        normalized_manifest_id=manifest,
        start=START,
        end=datetime(2023, 1, 1, tzinfo=UTC),
        available_by=datetime(2023, 1, 1, tzinfo=UTC),
    )
    restored = tmp_path / "restored"
    shutil.copytree(original, restored)
    shutil.rmtree(original / "bulk")
    # Moving bytes never silently grants a new root identity. The copied config
    # still points at the unavailable original root until an operator rebinds it.
    with pytest.raises(DataError, match="control_root differs"):
        configured_crypto_bulk_store(restored / "control").verify_readable()
    _write_config(restored / "control", restored / "bulk")
    _observe(monkeypatch, _identity(restored / "bulk"))
    after = query_binance_daily_price_snapshot(
        snapshot,
        configured_crypto_bulk_store(restored / "control"),
        normalized_manifest_id=manifest,
        start=START,
        end=datetime(2023, 1, 1, tzinfo=UTC),
        available_by=datetime(2023, 1, 1, tzinfo=UTC),
    )
    assert before.content_sha256 == after.content_sha256
    (restored / "bulk" / snapshot.members[0].artifact_key).write_bytes(b"tampered after restore")
    with pytest.raises(DataError, match="integrity"):
        query_binance_daily_price_snapshot(
            snapshot,
            configured_crypto_bulk_store(restored / "control"),
            normalized_manifest_id=manifest,
            start=START,
            end=datetime(2023, 1, 1, tzinfo=UTC),
            available_by=datetime(2023, 1, 1, tzinfo=UTC),
        )


def test_storage_status_reports_cloud_backend_and_identity_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from alpha_cli.main import app

    control, bulk = tmp_path / "control", tmp_path / "fixture-bulk"
    bulk.mkdir()
    _write_config(control, bulk)
    _observe(monkeypatch, _identity(bulk))
    settings = AlphaSettings(_env_file=None, data_dir=control)
    monkeypatch.setattr("alpha_cli.crypto_data_cmds.AlphaSettings", lambda: settings)
    runner = CliRunner()
    result = runner.invoke(app, ["crypto-data", "storage", "--metadata-only", "--json"])
    assert result.exit_code == 0, result.output
    status = json.loads(result.stdout)
    assert status["state"] == "ready"
    assert status["identity_backend"] == "cloud_root_identity"
    assert status["bulk_root_label"] == "fixture-bulk"
    assert str(tmp_path) not in result.stdout
    bad_owner = replace(_identity(bulk), owner_uid=999)
    _observe(monkeypatch, bad_owner)
    rejected = runner.invoke(app, ["crypto-data", "storage", "--metadata-only", "--json"])
    assert rejected.exit_code == 0, rejected.output
    status = json.loads(rejected.stdout)
    assert status["state"] == "blocked"
    assert status["identity_backend"] == "cloud_root_identity"
    assert status["blocker"] == "bulk_cloud_root_identity_mismatch"
    assert "uuid" not in rejected.stdout.lower()


def test_storage_status_does_not_present_incomplete_cloud_config_as_missing_mac_uuid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from alpha_cli.main import app

    settings = AlphaSettings(
        _env_file=None,
        data_dir=tmp_path,
        bulk_storage_backend="cloud_root_identity",
        bulk_data_dir=tmp_path / "fixture-bulk",
    )
    monkeypatch.setattr("alpha_cli.crypto_data_cmds.AlphaSettings", lambda: settings)
    result = CliRunner().invoke(app, ["crypto-data", "storage", "--metadata-only", "--json"])
    assert result.exit_code == 0, result.output
    status = json.loads(result.stdout)
    assert status["state"] == "blocked"
    assert status["identity_backend"] == "cloud_root_identity"
    assert status["blocker"] == "bulk_storage_configuration_invalid"
    assert "uuid" not in result.stdout.lower()


def test_durable_bulk_never_authorizes_a_disposable_control_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    control, bulk = tmp_path / "control", tmp_path / "bulk"
    bulk.mkdir()
    _write_config(control, bulk)
    original_inspection = root_identity.inspect_cloud_root

    def inspection(root: Path) -> CloudRootObservationV1:
        if root == bulk:
            identity = _identity(bulk)
            return CloudRootObservationV1(
                bulk,
                identity.mount_point,
                identity.device_id,
                identity.owner_uid,
                identity.filesystem_type,
                identity.mount_source,
            )
        return original_inspection(root)

    monkeypatch.setattr(root_identity, "inspect_cloud_root", inspection)
    before = {str(path): path.read_bytes() for path in control.rglob("*") if path.is_file()}
    with pytest.raises(DataError, match="control_root.*disposable temporary"):
        configured_crypto_bulk_store(control)
    assert before == {str(path): path.read_bytes() for path in control.rglob("*") if path.is_file()}


@pytest.mark.parametrize("field", ["mount", "device", "owner", "filesystem", "source"])
def test_control_root_must_share_approved_bulk_mount_device_and_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    control, bulk = tmp_path / "control", tmp_path / "bulk"
    bulk.mkdir()
    _write_config(control, bulk)
    identity = _identity(bulk)

    def inspection(root: Path) -> CloudRootObservationV1:
        return CloudRootObservationV1(
            root,
            Path("/other-mount") if field == "mount" else identity.mount_point,
            124 if field == "device" else identity.device_id,
            457 if field == "owner" else identity.owner_uid,
            "xfs" if field == "filesystem" else identity.filesystem_type,
            "/dev/other" if field == "source" else identity.mount_source,
        )

    monkeypatch.setattr(root_identity, "inspect_cloud_root", inspection)
    with pytest.raises(DataError, match="control_root requires the same approved durable"):
        configured_crypto_bulk_store(control)


def test_retained_control_root_must_match_selected_canonical_data_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    control, bulk = tmp_path / "control", tmp_path / "bulk"
    _write_config(control, bulk)
    path = control / "crypto" / "storage-config.json"
    config = json.loads(path.read_text())
    config["control_root"] = str(tmp_path / "foreign-control")
    path.write_text(json.dumps(config))

    def forbidden(root: Path) -> CloudRootObservationV1:
        pytest.fail("a mismatched control directory reached filesystem admission")

    monkeypatch.setattr(root_identity, "inspect_cloud_root", forbidden)
    with pytest.raises(DataError, match="control_root differs"):
        configured_crypto_bulk_store(control)

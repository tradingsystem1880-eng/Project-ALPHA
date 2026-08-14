from __future__ import annotations

import hashlib
import json
import plistlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_data.crypto import storage
from alpha_data.crypto.contracts import (
    CryptoAcquisitionScopeV1,
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
)
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

UUID = "758CBD77-1003-3BA3-AD28-1D647F5E2A08"


def test_bulk_storage_settings_are_explicit_and_ci_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_BULK_DATA_DIR", "/Volumes/Expansion/Project-ALPHA/crypto-data")
    monkeypatch.setenv("ALPHA_BULK_VOLUME_UUID", UUID)
    settings = AlphaSettings(_env_file=None)

    assert settings.bulk_data_dir == Path("/Volumes/Expansion/Project-ALPHA/crypto-data")
    assert settings.bulk_volume_uuid == UUID

    monkeypatch.delenv("ALPHA_BULK_DATA_DIR")
    monkeypatch.delenv("ALPHA_BULK_VOLUME_UUID")
    isolated = AlphaSettings(_env_file=None)
    assert isolated.bulk_data_dir == Path("data/bulk")
    assert isolated.bulk_volume_uuid is None


def test_macos_volume_uuid_queries_containing_mount_point(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    volume = tmp_path / "Expansion"
    nested = volume / "Project-ALPHA" / "crypto-data"
    nested.mkdir(parents=True)
    monkeypatch.setattr(storage.os.path, "ismount", lambda path: Path(path) == volume)
    observed: list[list[str]] = []

    def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        observed.append(args)
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=plistlib.dumps({"VolumeUUID": UUID}),
            stderr=b"",
        )

    monkeypatch.setattr(storage.subprocess, "run", fake_run)

    assert storage.macos_volume_uuid(nested) == UUID
    assert observed == [["diskutil", "info", "-plist", str(volume)]]


def _store(tmp_path: Path, *, actual_uuid: str = UUID, free: int = 1_000_000) -> CryptoBulkStore:
    bulk = tmp_path / "bulk"
    bulk.mkdir(parents=True)
    return CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "internal" / "crypto" / "manifests",
        expected_volume_uuid=UUID,
        volume_uuid=lambda _: actual_uuid,
        capacity=lambda _: Capacity(total_bytes=2_000_000, free_bytes=free),
        reserve_fraction=0.15,
        minimum_free_bytes=100,
    )


def test_missing_or_substituted_bulk_volume_fails_closed(tmp_path: Path) -> None:
    missing = CryptoBulkStore(
        bulk_root=tmp_path / "missing",
        manifest_root=tmp_path / "internal",
        expected_volume_uuid=UUID,
        volume_uuid=lambda _: UUID,
        capacity=lambda _: Capacity(total_bytes=2_000_000, free_bytes=1_000_000),
        minimum_free_bytes=100,
    )
    with pytest.raises(DataError, match="not mounted"):
        missing.verify_ready(required_bytes=1)
    with pytest.raises(DataError, match="UUID"):
        _store(tmp_path / "wrong", actual_uuid="WRONG").verify_ready(required_bytes=1)


def test_capacity_reserve_fails_before_writing(tmp_path: Path) -> None:
    store = _store(tmp_path, free=300_050)
    with pytest.raises(DataError, match="reserve"):
        store.verify_ready(required_bytes=100)
    assert not (tmp_path / "bulk" / "raw").exists()


def test_resumable_publication_writes_external_blob_then_internal_manifest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    staging = store.begin_staging(
        provider="binance", receipt_id="r_abc", logical_name="BTCUSDT-1d.csv.gz", expected_bytes=6
    )
    staging = store.append_staging(staging, b"abc")
    staging = store.append_staging(staging, b"def")
    manifest = store.publish_staging(
        staging, expected_sha256="bef57ec7f53a6d40beb640a780a639c83bc29ac8a9816f1fc6c5c6dcd93c4721"
    )

    assert store.verify_manifest(manifest["manifest_id"]) == manifest
    assert manifest["artifact_key"] == "raw/binance/r_abc/BTCUSDT-1d.csv.gz"
    assert str(tmp_path) not in json.dumps(manifest)
    assert not store.staging_root.joinpath(staging.staging_id).exists()

    blob = store.bulk_root / manifest["artifact_key"]
    blob.write_bytes(b"tampered")
    with pytest.raises(DataError, match="integrity"):
        store.verify_manifest(manifest["manifest_id"])


def test_normalized_publication_is_bound_to_raw_input_dataset_and_quality(tmp_path: Path) -> None:
    store = _store(tmp_path)
    raw_handle = store.begin_staging(
        provider="bybit", receipt_id="r_raw", logical_name="funding.json", expected_bytes=3
    )
    raw_handle = store.append_staging(raw_handle, b"raw")
    raw = store.publish_staging(
        raw_handle,
        expected_sha256=hashlib.sha256(b"raw").hexdigest(),
    )
    payload = b"PAR1-normalized-funding"
    digest = hashlib.sha256(payload).hexdigest()
    dataset = CryptoDatasetIdentityV1(
        provider="bybit",
        venue="bybit",
        market_type="linear",
        family="funding",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="funding_interval",
        units="dimensionless_rate",
        timestamp_convention="provider_event_utc",
    )
    quality = CryptoQualityReportV1(
        dataset_sha256=digest,
        method_version="crypto-quality-v1",
        state="qualified",
        failures=(),
        warnings=(),
        observed_start=datetime(2026, 8, 14, tzinfo=UTC),
        observed_end=datetime(2026, 8, 15, tzinfo=UTC),
        row_count=2,
        correction_lineage=(),
    )

    normalized = store.publish_normalized(
        payload,
        dataset=dataset,
        input_manifest_ids=(str(raw["manifest_id"]),),
        quality=quality,
    )

    assert normalized["artifact_kind"] == "normalized"
    assert normalized["dataset"] == dataset.to_dict()
    assert normalized["quality"] == quality.to_dict()
    assert normalized["input_manifest_ids"] == [raw["manifest_id"]]
    assert store.verify_manifest(normalized["manifest_id"]) == normalized
    assert str(tmp_path) not in json.dumps(normalized)

    with pytest.raises(DataError, match="raw input manifest"):
        store.publish_normalized(
            payload,
            dataset=dataset,
            input_manifest_ids=("a" * 64,),
            quality=quality,
        )


def test_staging_metadata_resumes_exact_offset(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.begin_staging(
        provider="bybit", receipt_id="r_def", logical_name="funding.json", expected_bytes=6
    )
    store.append_staging(first, b"abc")
    resumed = store.resume_staging(first.staging_id)

    assert resumed.bytes_written == 3
    store.append_staging(resumed, b"def")
    assert store.resume_staging(first.staging_id).bytes_written == 6


def test_derivative_event_publication_requires_immutable_case_scope(tmp_path: Path) -> None:
    store = _store(tmp_path)
    raw_handle = store.begin_staging(
        provider="bybit", receipt_id="r_event", logical_name="book.json", expected_bytes=3
    )
    raw_handle = store.append_staging(raw_handle, b"raw")
    raw = store.publish_staging(
        raw_handle,
        expected_sha256=hashlib.sha256(b"raw").hexdigest(),
    )
    payload = b"PAR1-event-book"
    digest = hashlib.sha256(payload).hexdigest()
    dataset = CryptoDatasetIdentityV1(
        provider="bybit",
        venue="bybit",
        market_type="linear",
        family="derivative_book_snapshots",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="point_in_time_book",
        units="provider_native_price_quantity",
        timestamp_convention="provider_generation_utc",
    )
    quality = CryptoQualityReportV1(
        dataset_sha256=digest,
        method_version="crypto-quality-v1",
        state="qualified",
        failures=(),
        warnings=(),
        observed_start=datetime(2026, 8, 15, tzinfo=UTC),
        observed_end=datetime(2026, 8, 15, tzinfo=UTC),
        row_count=2,
        correction_lineage=(),
    )
    with pytest.raises(DataError, match="research-case scope"):
        store.publish_normalized(
            payload,
            dataset=dataset,
            input_manifest_ids=(str(raw["manifest_id"]),),
            quality=quality,
        )

    scope = CryptoAcquisitionScopeV1(
        project_id="f03802b8-df35-4f19-a90c-0b3437aa587d",
        case_revision="a" * 64,
        reason="Capture the bounded BTC event book.",
        captured_at=datetime(2026, 8, 15, tzinfo=UTC),
    )
    normalized = store.publish_normalized(
        payload,
        dataset=dataset,
        input_manifest_ids=(str(raw["manifest_id"]),),
        quality=quality,
        acquisition_scope=scope,
    )
    assert normalized["acquisition_scope"] == scope.to_dict()


def test_staging_resumes_only_when_existing_prefix_matches_exact_payload(tmp_path: Path) -> None:
    store = _store(tmp_path)
    handle = store.begin_staging(
        provider="bybit", receipt_id="r_resume", logical_name="funding.json", expected_bytes=6
    )
    handle = store.append_staging(handle, b"abc")

    completed = store.resume_payload(handle, b"abcdef")
    assert completed.bytes_written == 6

    other = store.begin_staging(
        provider="bybit", receipt_id="r_wrong", logical_name="funding.json", expected_bytes=6
    )
    other = store.append_staging(other, b"abc")
    with pytest.raises(DataError, match="prefix"):
        store.resume_payload(other, b"abXdef")


def test_publication_recovers_when_internal_manifest_write_is_interrupted(tmp_path: Path) -> None:
    store = _store(tmp_path)
    handle = store.begin_staging(
        provider="binance", receipt_id="r_retry", logical_name="bars.csv", expected_bytes=3
    )
    handle = store.append_staging(handle, b"abc")
    store.manifest_root.parent.mkdir(parents=True)
    store.manifest_root.write_text("blocks directory creation", encoding="utf-8")

    with pytest.raises(DataError, match="internal manifest"):
        store.publish_staging(
            handle,
            expected_sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )
    assert store.resume_staging(handle.staging_id).bytes_written == 3

    store.manifest_root.unlink()
    manifest = store.publish_staging(
        handle,
        expected_sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    )
    assert store.verify_manifest(manifest["manifest_id"]) == manifest


def test_tampered_staging_metadata_fails_before_publication(tmp_path: Path) -> None:
    store = _store(tmp_path)
    handle = store.begin_staging(
        provider="bybit", receipt_id="r_tamper", logical_name="options.json", expected_bytes=3
    )
    metadata = store.staging_root / handle.staging_id / "staging.json"
    raw = json.loads(metadata.read_text(encoding="utf-8"))
    raw["provider"] = "binance"
    metadata.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(DataError, match="identity"):
        store.resume_staging(handle.staging_id)


def test_cache_inventory_and_cleanup_are_confined_to_removable_cache(tmp_path: Path) -> None:
    store = _store(tmp_path)
    cache = store.bulk_root / "cache"
    cache.mkdir()
    (cache / "download.tmp").write_bytes(b"cache")
    protected = store.bulk_root / "raw" / "provider" / "receipt" / "data.json"
    protected.parent.mkdir(parents=True)
    protected.write_bytes(b"immutable")

    assert store.cache_size() == 5
    assert store.clean_cache() == 5
    assert store.cache_size() == 0
    assert protected.read_bytes() == b"immutable"


@pytest.mark.parametrize(
    "values",
    [
        {"expected_volume_uuid": ""},
        {"reserve_fraction": -0.1},
        {"reserve_fraction": 1.0},
        {"minimum_free_bytes": -1},
    ],
)
def test_storage_configuration_rejects_unsafe_values(
    tmp_path: Path, values: dict[str, object]
) -> None:
    with pytest.raises(DataError):
        CryptoBulkStore(
            bulk_root=tmp_path,
            manifest_root=tmp_path / "internal",
            **({"expected_volume_uuid": UUID} | values),  # type: ignore[arg-type]
        )


def test_storage_rejects_bad_offsets_components_and_payloads(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(DataError, match="required bulk bytes"):
        store.verify_ready(required_bytes=True)
    with pytest.raises(DataError, match="provider"):
        store.begin_staging(provider="../bad", receipt_id="r", logical_name="x", expected_bytes=1)

    handle = store.begin_staging(
        provider="binance", receipt_id="r_bounds", logical_name="bars", expected_bytes=3
    )
    with pytest.raises(DataError, match="non-empty"):
        store.append_staging(handle, b"")
    with pytest.raises(DataError, match="exceeds"):
        store.append_staging(handle, b"four")
    updated = store.append_staging(handle, b"a")
    with pytest.raises(DataError, match="stale"):
        store.append_staging(handle, b"b")
    with pytest.raises(DataError, match="incomplete"):
        store.publish_staging(updated, expected_sha256="a" * 64)


def test_manifest_errors_inventory_and_cache_cleanup(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.inventory() == ()
    assert store.clean_cache() == 0
    with pytest.raises(DataError, match="manifest id"):
        store.verify_manifest(123)
    with pytest.raises(DataError, match="unavailable"):
        store.verify_manifest("a" * 64)

    cache = store.bulk_root / "cache" / "nested"
    cache.mkdir(parents=True)
    cache.joinpath("a.bin").write_bytes(b"abc")
    assert store.clean_cache() == 3
    assert not cache.exists()


def test_publish_rejects_hash_and_existing_artifact_collisions(tmp_path: Path) -> None:
    store = _store(tmp_path)
    handle = store.begin_staging(
        provider="binance", receipt_id="r_collision", logical_name="bars", expected_bytes=3
    )
    handle = store.append_staging(handle, b"abc")
    with pytest.raises(DataError, match="hash does not match"):
        store.publish_staging(handle, expected_sha256="a" * 64)

    destination = store.bulk_root / "raw/binance/r_collision/bars"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"xyz")
    with pytest.raises(DataError, match="artifact identity collision"):
        store.publish_staging(
            handle,
            expected_sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )


def test_macos_volume_uuid_uses_plist_and_redacts_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=plistlib.dumps({"VolumeUUID": UUID.lower()}), stderr=b""
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)
    assert storage.macos_volume_uuid(tmp_path) == UUID

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout=plistlib.dumps({}), stderr=b"secret"
        ),
    )
    with pytest.raises(DataError, match="no stable UUID"):
        storage.macos_volume_uuid(tmp_path)

    def failed(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.CalledProcessError(1, "diskutil", stderr=b"private-path secret")

    monkeypatch.setattr(subprocess, "run", failed)
    with pytest.raises(DataError, match="unable to verify") as caught:
        storage.macos_volume_uuid(tmp_path)
    assert "private-path" not in str(caught.value)

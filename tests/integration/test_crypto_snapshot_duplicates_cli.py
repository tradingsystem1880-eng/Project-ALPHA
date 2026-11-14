"""Offline repeated-capture and snapshot membership regressions."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.main import app
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

runner = CliRunner()


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CryptoBulkStore:
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    result = CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=20_000_000, free_bytes=10_000_000),
        minimum_free_bytes=100,
    )
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path / "control"))
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: result)
    return result


def _acquire(
    monkeypatch: pytest.MonkeyPatch, month: int, *, day: int = 15, tail: bool = False
) -> str:
    monkeypatch.setattr(crypto_data_cmds, "_now", lambda: datetime(2026, 8, day, tzinfo=UTC))
    timestamp = int(datetime(2025, month, 1, tzinfo=UTC).timestamp() * 1000)
    row = [
        timestamp,
        "100",
        "110",
        "90",
        "105",
        "12",
        timestamp + 86_399_999,
        "1260",
        42,
        "6",
        "630",
        "0",
    ]
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            zipfile.ZipInfo(f"BTCUSDT-1d-2025-{month:02d}.csv"), ",".join(map(str, row)) + "\n"
        )
    payload = zipped.getvalue()
    monkeypatch.setattr(crypto_data_cmds, "fetch_binance_archive", lambda *_: payload)
    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_binance_checksum",
        lambda *_: f"{hashlib.sha256(payload).hexdigest()} file.zip\n".encode(),
    )
    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_binance_public_api",
        lambda *_: json.dumps(
            [row, [timestamp + 86_400_000, *row[1:6], timestamp + 172_799_999, *row[7:]]]
        ).encode(),
    )
    bounds = (
        ["--start", f"2025-{month:02d}-01T00:00:00Z", "--end", f"2025-{month:02d}-03T00:00:00Z"]
        if tail
        else ["--period", f"2025-{month:02d}"]
    )
    manifest_id = _ok(
        "acquire",
        "binance",
        "market_bars",
        "BTCUSDT",
        "--base",
        "BTC",
        "--quote",
        "USDT",
        "--category",
        "spot",
        "--frequency",
        "1d",
        *bounds,
    )["normalized_manifest_id"]
    assert isinstance(manifest_id, str)
    return manifest_id


def _ok(*args: str) -> dict[str, object]:
    result = runner.invoke(app, ["crypto-data", *args, "--json"])
    assert result.exit_code == 0, result.output
    payload: object = json.loads(result.stdout)
    assert isinstance(payload, dict)
    assert all(isinstance(key, str) for key in payload)
    return payload


def _create(*ids: str) -> str:
    snapshot_id = _ok("snapshot-create", *(arg for mid in ids for arg in ("--manifest-id", mid)))[
        "snapshot_id"
    ]
    assert isinstance(snapshot_id, str)
    return snapshot_id


def _refused(*args: str, message: str) -> None:
    result = runner.invoke(app, ["crypto-data", *args, "--json"])
    assert result.exit_code != 0, result.output
    assert message in " ".join(result.output.replace("│", "").split()), result.output


def test_repeated_download_verifies_snapshot_and_storage(
    store: CryptoBulkStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _acquire(monkeypatch, 1)
    second = _acquire(monkeypatch, 1, day=16)
    assert first != second
    assert (
        store.verify_manifest(first)["artifact_sha256"]
        == store.verify_manifest(second)["artifact_sha256"]
    )
    snapshot = _create(second)
    assert _ok("snapshot-verify", snapshot)["eligible"] is True
    assert _ok("storage-verify")["state"] == "verified"


def test_divergent_capture_refuses_creation_and_existing_snapshot(
    store: CryptoBulkStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _acquire(monkeypatch, 1)
    second = _acquire(monkeypatch, 1, day=16)
    snapshot = _create(second)
    manifest = store.verify_manifest(second)
    input_manifest_ids = manifest["input_manifest_ids"]
    assert isinstance(input_manifest_ids, list)
    assert all(isinstance(manifest_id, str) for manifest_id in input_manifest_ids)
    store.publish_normalized(
        (store.bulk_root / str(manifest["artifact_key"])).read_bytes(),
        dataset=CryptoDatasetIdentityV1.from_dict(manifest["dataset"]),
        input_manifest_ids=tuple(input_manifest_ids),
        quality=replace(
            CryptoQualityReportV1.from_dict(manifest["quality"]),
            correction_lineage=("different-source-correction",),
        ),
    )
    _refused("snapshot-create", "--manifest-id", second, message="ambiguous")
    _refused("snapshot-verify", snapshot, message="ambiguous")
    _refused("storage-verify", message="ambiguous")


@pytest.mark.parametrize("tamper_index", [0, 1])
def test_canonical_month_order_and_verification_of_every_member(
    store: CryptoBulkStore,
    monkeypatch: pytest.MonkeyPatch,
    tamper_index: int,
) -> None:
    ids = [_acquire(monkeypatch, month) for month in (1, 2)]
    snapshot = _create(*ids)
    assert _create(*reversed(ids)) == snapshot
    assert _ok("snapshot-verify", snapshot)["eligible"] is True
    manifest = store.verify_manifest(ids[tamper_index])
    (store.bulk_root / str(manifest["artifact_key"])).write_bytes(b"tampered")
    _refused("snapshot-verify", snapshot, message="integrity")


def test_duplicate_capture_ids_are_refused(
    store: CryptoBulkStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = _acquire(monkeypatch, 1), _acquire(monkeypatch, 1, day=16)
    _refused(
        "snapshot-create", "--manifest-id", first, "--manifest-id", second, message="more than once"
    )


def test_archive_and_overlapping_rest_tail_are_refused(
    store: CryptoBulkStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive, tail = _acquire(monkeypatch, 1), _acquire(monkeypatch, 1, tail=True)
    _refused(
        "snapshot-create",
        "--manifest-id",
        archive,
        "--manifest-id",
        tail,
        message="disjoint observed ranges",
    )


def test_current_month_backfill_reports_unpublished_and_succeeds(
    store: CryptoBulkStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(crypto_data_cmds, "_now", lambda: datetime(2026, 8, 15, tzinfo=UTC))
    calls: list[object] = []

    def acquire(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"normalized_manifest_id": "unused", "state": "qualified"}

    monkeypatch.setattr(crypto_data_cmds, "_backfill_acquire", acquire)
    result = _ok(
        "backfill",
        "binance",
        "market_bars",
        "--symbols",
        "BTCUSDT",
        "--quote",
        "USDT",
        "--start",
        "2026-08-01",
        "--end",
        "2026-08-15",
        "--ledger",
        "unpublished",
    )
    assert calls == []
    assert result["not_published_yet"] == ["2026-08"]
    assert result["windows_total"] == result["failed"] == result["done"] == 0

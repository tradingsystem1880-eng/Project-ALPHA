from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_data.crypto.contracts import (
    CryptoDatasetIdentityV1,
    CryptoQualityReportV1,
    CryptoRawReceiptV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
)
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

UUID = "758CBD77-1003-3BA3-AD28-1D647F5E2A08"
runner = CliRunner()


def _store(data_dir: Path, *, actual_uuid: str = UUID) -> CryptoBulkStore:
    bulk = data_dir / "bulk"
    bulk.mkdir(parents=True, exist_ok=True)
    return CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=data_dir / "crypto" / "manifests",
        expected_volume_uuid=UUID,
        volume_uuid=lambda _: actual_uuid,
        capacity=lambda _: Capacity(total_bytes=2_000_000, free_bytes=1_000_000),
        minimum_free_bytes=100,
    )


def _freeze_one_defi_tvl(
    store: CryptoBulkStore,
    data_dir: Path,
    *,
    fetched_at: datetime = datetime(2026, 1, 5, 12, tzinfo=UTC),
) -> CryptoSnapshotV1:
    dataset = CryptoDatasetIdentityV1(
        provider="defillama",
        venue="defillama",
        market_type="network",
        family="defi_tvl",
        instrument="ethereum",
        base_asset="ETH",
        quote_asset="USD",
        frequency="1d",
        units="usd",
        timestamp_convention="utc_day_start_available_next_day",
    )
    raw = b"synthetic DefiLlama response"
    receipt = CryptoRawReceiptV1.create(
        dataset=dataset,
        request=(("chain", "ethereum"),),
        fetched_at=fetched_at,
        response_sha256=hashlib.sha256(raw).hexdigest(),
        response_bytes=len(raw),
        provider_schema="defillama-v2-historical-chain-tvl",
        parser_version="defillama-chain-tvl-v1",
        pagination=(),
        upstream_checksum=None,
    )
    stage = store.begin_staging(
        provider="defillama",
        receipt_id=receipt.receipt_id,
        logical_name="defi_tvl.json",
        expected_bytes=len(raw),
    )
    stage = store.append_staging(stage, raw)
    raw_manifest = store.publish_staging(
        stage,
        expected_sha256=receipt.response_sha256,
        receipt=receipt,
    )
    days = [datetime(2026, 1, day, tzinfo=UTC) for day in (1, 2)]
    frame = pl.DataFrame(
        {
            "chain": ["ethereum", "ethereum"],
            "observed_at": days,
            "tvl_usd": [10.0, 11.0],
            "available_at": [day + timedelta(days=1) for day in days],
        },
        schema={
            "chain": pl.String(),
            "observed_at": pl.Datetime("us", "UTC"),
            "tvl_usd": pl.Float64(),
            "available_at": pl.Datetime("us", "UTC"),
        },
    )
    stream = io.BytesIO()
    frame.write_parquet(stream)
    parquet = stream.getvalue()
    artifact_hash = hashlib.sha256(parquet).hexdigest()
    quality = CryptoQualityReportV1(
        dataset_sha256=artifact_hash,
        method_version="crypto-quality-v1",
        state="qualified",
        failures=(),
        warnings=(),
        observed_start=days[0],
        observed_end=days[-1],
        row_count=2,
        correction_lineage=(),
    )
    normalized = store.publish_normalized(
        parquet,
        dataset=dataset,
        input_manifest_ids=(str(raw_manifest["manifest_id"]),),
        quality=quality,
    )
    snapshot = CryptoSnapshotV1.create(
        members=(
            CryptoSnapshotMemberV1(
                dataset=dataset,
                artifact_key=str(normalized["artifact_key"]),
                artifact_sha256=str(normalized["artifact_sha256"]),
            ),
        ),
        asset_master_version="reviewed-native-v1",
        qualification_versions=(quality.method_version,),
    )
    snapshot_root = data_dir / "crypto" / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    (snapshot_root / f"{snapshot.snapshot_id}.json").write_text(
        json.dumps(snapshot.to_dict(), sort_keys=True), encoding="utf-8"
    )
    return snapshot


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_snapshot_query_reopens_exact_id_and_preserves_frozen_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "control"
    monkeypatch.setenv("ALPHA_DATA_DIR", str(data_dir))
    store = _store(data_dir)
    snapshot = _freeze_one_defi_tvl(store, data_dir)
    before = {
        "bulk": _tree_bytes(data_dir / "bulk"),
        "manifests": _tree_bytes(data_dir / "crypto" / "manifests"),
        "snapshots": _tree_bytes(data_dir / "crypto" / "snapshots"),
    }
    monkeypatch.setattr("alpha_cli.crypto_data_cmds._bulk_store", lambda: _store(data_dir))

    result = runner.invoke(
        app,
        [
            "crypto-data",
            "snapshot-query",
            snapshot.snapshot_id,
            "--limit",
            "1",
            "--available-by",
            "2026-01-03T00:00:00Z",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["snapshot_id"] == snapshot.snapshot_id
    assert payload["units"] == "usd"
    assert payload["available_row_count"] == 2
    assert payload["returned_row_count"] == 1
    assert payload["has_more"] is True
    assert payload["next_offset"] == 1
    assert payload["dataset_sha256"] == snapshot.members[0].dataset.content_sha256
    assert payload["artifact_sha256"] == snapshot.members[0].artifact_sha256
    assert (
        payload["source_receipt"]["response_sha256"]
        == hashlib.sha256(b"synthetic DefiLlama response").hexdigest()
    )
    assert payload["source_receipt"]["provider_schema"] == "defillama-v2-historical-chain-tvl"
    assert payload["source_receipt"]["parser_version"] == "defillama-chain-tvl-v1"
    assert payload["point_in_time_claim"] is False
    assert payload["raw_capture_after_available_by"] is True
    assert payload["availability_basis"] == "defillama_next_utc_day_contract"
    assert payload["rows"] == [
        {
            "chain": "ethereum",
            "observed_at": "2026-01-01T00:00:00Z",
            "tvl_usd": 10.0,
            "available_at": "2026-01-02T00:00:00Z",
        }
    ]

    reopened = runner.invoke(
        app,
        ["crypto-data", "snapshot-query", snapshot.snapshot_id, "--json"],
    )
    assert reopened.exit_code == 0, reopened.output
    assert json.loads(reopened.stdout)["snapshot_id"] == snapshot.snapshot_id
    assert {
        "bulk": _tree_bytes(data_dir / "bulk"),
        "manifests": _tree_bytes(data_dir / "crypto" / "manifests"),
        "snapshots": _tree_bytes(data_dir / "crypto" / "snapshots"),
    } == before


def test_snapshot_query_rejects_filename_content_identity_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "control"
    monkeypatch.setenv("ALPHA_DATA_DIR", str(data_dir))
    store = _store(data_dir)
    snapshot = _freeze_one_defi_tvl(store, data_dir)
    alias_id = "b" * 64
    snapshot_path = data_dir / "crypto" / "snapshots" / f"{alias_id}.json"
    snapshot_path.write_text(json.dumps(snapshot.to_dict()), encoding="utf-8")
    monkeypatch.setattr("alpha_cli.crypto_data_cmds._bulk_store", lambda: _store(data_dir))

    result = runner.invoke(app, ["crypto-data", "snapshot-query", alias_id, "--json"])

    assert result.exit_code != 0
    assert "file identity does not match" in result.output


def test_snapshot_query_checks_volume_before_snapshot_artifact_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "control"
    monkeypatch.setenv("ALPHA_DATA_DIR", str(data_dir))
    snapshot = _freeze_one_defi_tvl(_store(data_dir), data_dir)
    wrong_volume = _store(data_dir, actual_uuid="WRONG-UUID")

    def inventory_must_not_run() -> tuple[dict[str, object], ...]:
        pytest.fail("snapshot inventory ran before bulk-volume identity verification")

    monkeypatch.setattr(wrong_volume, "inventory", inventory_must_not_run)
    monkeypatch.setattr("alpha_cli.crypto_data_cmds._bulk_store", lambda: wrong_volume)

    result = runner.invoke(app, ["crypto-data", "snapshot-query", snapshot.snapshot_id, "--json"])

    assert result.exit_code != 0
    assert "volume UUID" in result.output


def test_snapshot_query_does_not_read_unrelated_artifact_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "control"
    monkeypatch.setenv("ALPHA_DATA_DIR", str(data_dir))
    store = _store(data_dir)
    snapshot = _freeze_one_defi_tvl(store, data_dir)
    stage = store.begin_staging(
        provider="bybit", receipt_id="unrelated", logical_name="other", expected_bytes=3
    )
    stage = store.append_staging(stage, b"raw")
    manifest = store.publish_staging(stage, expected_sha256=hashlib.sha256(b"raw").hexdigest())
    (store.bulk_root / str(manifest["artifact_key"])).write_bytes(b"unrelated corruption")
    monkeypatch.setattr("alpha_cli.crypto_data_cmds._bulk_store", lambda: store)
    result = runner.invoke(app, ["crypto-data", "snapshot-query", snapshot.snapshot_id, "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["snapshot_id"] == snapshot.snapshot_id


def test_snapshot_query_manifest_selector_preserves_capture_on_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "control"
    monkeypatch.setenv("ALPHA_DATA_DIR", str(data_dir))
    store = _store(data_dir)
    snapshot = _freeze_one_defi_tvl(store, data_dir)
    monkeypatch.setattr("alpha_cli.crypto_data_cmds._bulk_store", lambda: store)
    command = ["crypto-data", "snapshot-query", snapshot.snapshot_id, "--json"]
    original = runner.invoke(app, command)
    assert original.exit_code == 0, original.output
    original_payload = json.loads(original.stdout)
    recaptured = _freeze_one_defi_tvl(
        store, data_dir, fetched_at=datetime(2026, 1, 6, 12, tzinfo=UTC)
    )
    assert recaptured.snapshot_id == snapshot.snapshot_id
    ambiguous = runner.invoke(app, command)
    assert ambiguous.exit_code == 2
    assert "ambiguous" in ambiguous.output and "--manifest-id" in ambiguous.output
    reopened = runner.invoke(
        app, command + ["--manifest-id", original_payload["normalized_manifest_id"]]
    )
    assert reopened.exit_code == 0, reopened.output
    assert json.loads(reopened.stdout) == original_payload

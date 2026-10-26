from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from alpha_cli.crypto_snapshot_query import query_defi_tvl_snapshot
from alpha_core import DataError
from alpha_data.crypto.contracts import (
    CryptoDatasetIdentityV1,
    CryptoFamily,
    CryptoQualityReportV1,
    CryptoRawReceiptV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
)
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

UUID = "758CBD77-1003-3BA3-AD28-1D647F5E2A08"
FETCHED_AT = datetime(2026, 1, 5, 12, tzinfo=UTC)


def _store(tmp_path: Path, *, actual_uuid: str = UUID) -> CryptoBulkStore:
    bulk = tmp_path / "bulk"
    bulk.mkdir(exist_ok=True)
    return CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid=UUID,
        volume_uuid=lambda _: actual_uuid,
        capacity=lambda _: Capacity(total_bytes=2_000_000, free_bytes=1_000_000),
        minimum_free_bytes=100,
    )


def _dataset(family: CryptoFamily = "defi_tvl", chain: str = "ethereum") -> CryptoDatasetIdentityV1:
    return CryptoDatasetIdentityV1(
        provider="defillama",
        venue="defillama",
        market_type="network",
        family=family,
        instrument=chain,
        base_asset="ETH",
        quote_asset="USD",
        frequency="1d",
        units="usd",
        timestamp_convention="utc_day_start_available_next_day",
    )


def _frame(
    *, values: tuple[float, ...], chain: str = "ethereum", extra_column: bool = False
) -> pl.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    days = tuple(start + timedelta(days=index) for index in range(len(values)))
    columns: dict[str, object] = {
        "chain": [chain] * len(values),
        "observed_at": list(days),
        "tvl_usd": list(values),
        "available_at": [day + timedelta(days=1) for day in days],
    }
    schema: dict[str, pl.DataType] = {
        "chain": pl.String(),
        "observed_at": pl.Datetime("us", "UTC"),
        "tvl_usd": pl.Float64(),
        "available_at": pl.Datetime("us", "UTC"),
    }
    if extra_column:
        columns["unexpected"] = ["x"] * len(values)
        schema["unexpected"] = pl.String()
    return pl.DataFrame(columns, schema=schema)


def _publish_member(
    store: CryptoBulkStore,
    *,
    values: tuple[float, ...],
    fetched_at: datetime = FETCHED_AT,
    family: CryptoFamily = "defi_tvl",
    chain: str = "ethereum",
    extra_column: bool = False,
    quality_row_count: int | None = None,
) -> tuple[CryptoSnapshotV1, dict[str, object]]:
    dataset = _dataset(family, chain)
    raw_payload = f"synthetic:{family}:{chain}:{fetched_at.isoformat()}:{values}".encode()
    receipt = CryptoRawReceiptV1.create(
        dataset=dataset,
        request=(("chain", chain),),
        fetched_at=fetched_at,
        response_sha256=hashlib.sha256(raw_payload).hexdigest(),
        response_bytes=len(raw_payload),
        provider_schema="defillama-v2-historical-chain-tvl",
        parser_version="defillama-chain-tvl-v1",
        pagination=(),
        upstream_checksum=None,
    )
    raw_stage = store.begin_staging(
        provider="defillama",
        receipt_id=receipt.receipt_id,
        logical_name="defi_tvl.json",
        expected_bytes=len(raw_payload),
    )
    raw_stage = store.append_staging(raw_stage, raw_payload)
    raw_manifest = store.publish_staging(
        raw_stage,
        expected_sha256=receipt.response_sha256,
        receipt=receipt,
    )

    frame = _frame(values=values, chain=chain, extra_column=extra_column)
    parquet_stream = io.BytesIO()
    frame.write_parquet(parquet_stream)
    parquet_payload = parquet_stream.getvalue()
    artifact_hash = hashlib.sha256(parquet_payload).hexdigest()
    quality = CryptoQualityReportV1(
        dataset_sha256=artifact_hash,
        method_version="crypto-quality-v1",
        state="qualified",
        failures=(),
        warnings=(),
        observed_start=frame["observed_at"][0],
        observed_end=frame["observed_at"][-1],
        row_count=frame.height if quality_row_count is None else quality_row_count,
        correction_lineage=(),
    )
    normalized = store.publish_normalized(
        parquet_payload,
        dataset=dataset,
        input_manifest_ids=(str(raw_manifest["manifest_id"]),),
        quality=quality,
    )
    member = CryptoSnapshotMemberV1(
        dataset=dataset,
        artifact_key=str(normalized["artifact_key"]),
        artifact_sha256=str(normalized["artifact_sha256"]),
    )
    snapshot = CryptoSnapshotV1.create(
        members=(member,),
        asset_master_version="reviewed-native-v1",
        qualification_versions=(quality.method_version,),
    )
    return snapshot, normalized


def test_query_filters_availability_and_returns_hash_bound_provenance(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snapshot, _ = _publish_member(store, values=(10.0, 11.0, 12.0))

    first = query_defi_tvl_snapshot(
        snapshot,
        store,
        available_by=datetime(2026, 1, 3, tzinfo=UTC),
        limit=1,
    )
    second = query_defi_tvl_snapshot(
        snapshot,
        store,
        available_by=datetime(2026, 1, 3, tzinfo=UTC),
        offset=1,
        limit=1,
    )

    assert first.rows[0].observed_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert first.rows[0].available_at == datetime(2026, 1, 2, tzinfo=UTC)
    assert second.rows[0].observed_at == datetime(2026, 1, 2, tzinfo=UTC)
    assert first.available_row_count == 2
    assert first.has_more is True
    assert first.next_offset == 1
    assert second.has_more is False
    assert second.next_offset is None
    assert first.units == "usd"
    assert first.source_fetched_at == FETCHED_AT
    assert first.availability_basis == "defillama_next_utc_day_contract"
    assert first.point_in_time_claim is False
    assert first.raw_capture_after_available_by is True
    assert first.artifact_sha256 == snapshot.members[0].artifact_sha256
    rendered = first.to_dict()
    assert rendered["dataset_sha256"] == snapshot.members[0].dataset.content_sha256
    assert rendered["point_in_time_claim"] is False
    receipt_payload = rendered["source_receipt"]
    assert isinstance(receipt_payload, dict)
    assert receipt_payload["parser_version"] == "defillama-chain-tvl-v1"


def test_query_rejects_unsupported_or_ambiguous_snapshot_members(tmp_path: Path) -> None:
    store = _store(tmp_path)
    unsupported, _ = _publish_member(store, values=(10.0,), family="protocol_tvl")
    with pytest.raises(DataError, match="exactly one defi_tvl"):
        query_defi_tvl_snapshot(unsupported, store)

    first, _ = _publish_member(store, values=(10.0,), chain="ethereum")
    second, _ = _publish_member(store, values=(20.0,), chain="arbitrum")
    ambiguous = CryptoSnapshotV1.create(
        members=first.members + second.members,
        asset_master_version="reviewed-native-v1",
        qualification_versions=("crypto-quality-v1",),
    )
    with pytest.raises(DataError, match="exactly one defi_tvl"):
        query_defi_tvl_snapshot(ambiguous, store)


def test_query_rejects_unexpected_schema_and_unbounded_parameters(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snapshot, _ = _publish_member(store, values=(10.0,), extra_column=True)
    with pytest.raises(DataError, match="schema"):
        query_defi_tvl_snapshot(snapshot, store)

    valid_snapshot, _ = _publish_member(store, values=(10.0,), chain="arbitrum")
    with pytest.raises(DataError, match="limit"):
        query_defi_tvl_snapshot(valid_snapshot, store, limit=1_001)
    with pytest.raises(DataError, match="offset"):
        query_defi_tvl_snapshot(valid_snapshot, store, offset=100_001)


def test_revision_replay_keeps_old_snapshot_reopenable(tmp_path: Path) -> None:
    store = _store(tmp_path)
    old_snapshot, _ = _publish_member(store, values=(10.0, 11.0))
    revised_snapshot, _ = _publish_member(
        store,
        values=(10.0, 12.0),
        fetched_at=datetime(2026, 1, 7, 9, tzinfo=UTC),
    )

    old_before = query_defi_tvl_snapshot(old_snapshot, store)
    revised = query_defi_tvl_snapshot(revised_snapshot, store)
    old_after = query_defi_tvl_snapshot(old_snapshot, store)

    assert old_snapshot.snapshot_id != revised_snapshot.snapshot_id
    assert old_before.rows[1].tvl_usd == 11.0
    assert revised.rows[1].tvl_usd == 12.0
    assert old_after.to_dict() == old_before.to_dict()
    assert old_before.source_fetched_at == FETCHED_AT
    assert revised.source_fetched_at == datetime(2026, 1, 7, 9, tzinfo=UTC)


def test_query_fails_closed_when_exact_member_hash_is_absent_or_bytes_change(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    snapshot, _ = _publish_member(store, values=(10.0,))
    member = snapshot.members[0]
    mismatched = CryptoSnapshotV1.create(
        members=(
            CryptoSnapshotMemberV1(
                dataset=member.dataset,
                artifact_key=member.artifact_key,
                artifact_sha256="b" * 64,
            ),
        ),
        asset_master_version=snapshot.asset_master_version,
        qualification_versions=snapshot.qualification_versions,
    )
    with pytest.raises(DataError, match="missing or ambiguous"):
        query_defi_tvl_snapshot(mismatched, store)

    artifact = store.bulk_root / member.artifact_key
    artifact.write_bytes(b"tampered")
    with pytest.raises(DataError, match="integrity"):
        query_defi_tvl_snapshot(snapshot, store)


def test_query_checks_the_configured_volume_identity_before_reading(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snapshot, _ = _publish_member(store, values=(10.0,))
    wrong_volume = _store(tmp_path, actual_uuid="WRONG-UUID")

    with pytest.raises(DataError, match="volume UUID"):
        query_defi_tvl_snapshot(snapshot, wrong_volume)


def test_query_caps_decompressed_row_materialization_even_with_falsified_quality_count(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    snapshot, _ = _publish_member(
        store,
        values=(10.0,) * 50_001,
        quality_row_count=1,
    )

    with pytest.raises(DataError, match="50,000-row input limit"):
        query_defi_tvl_snapshot(snapshot, store)

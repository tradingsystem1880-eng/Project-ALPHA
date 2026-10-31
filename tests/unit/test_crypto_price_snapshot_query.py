"""Artificial provider-format fixtures only; these are not real-market acceptance."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NoReturn

import pytest

from alpha_cli.crypto_price_snapshot_query import (
    BinanceDailyPriceSnapshotQueryV1,
    query_binance_daily_price_snapshot,
)
from alpha_core import DataError
from alpha_data.crypto.contracts import (
    CryptoDatasetIdentityV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
)
from alpha_data.crypto.ingestion import ingest_provider_payload
from alpha_data.crypto.providers.binance import parse_binance_klines
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

START = datetime(2020, 1, 1, tzinfo=UTC)
DAY = timedelta(days=1)
UUID = "758CBD77-1003-3BA3-AD28-1D647F5E2A08"


def _store(tmp_path: Path) -> CryptoBulkStore:
    bulk = tmp_path / "bulk"
    bulk.mkdir(exist_ok=True)
    return CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid=UUID,
        volume_uuid=lambda _: UUID,
        capacity=lambda _: Capacity(total_bytes=20_000_000, free_bytes=10_000_000),
        minimum_free_bytes=100,
    )


def _publish(
    store: CryptoBulkStore,
    *,
    closes: tuple[float, ...] = (10.0, 11.0, 12.0),
    fetched: datetime = START + 10 * DAY,
    skip: int | None = None,
) -> tuple[CryptoSnapshotV1, str]:
    dataset = CryptoDatasetIdentityV1(
        provider="binance",
        venue="binance",
        market_type="spot",
        family="market_bars",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="1d",
        units="provider_native_ohlcv",
        timestamp_convention="interval_start_utc",
    )
    rows = [
        [
            int((START + index * DAY).timestamp() * 1000),
            close,
            close + 1,
            close - 1,
            close,
            100.0,
            int((START + (index + 1) * DAY).timestamp() * 1000) - 1,
            1000.0,
            10,
            50.0,
            500.0,
            0,
        ]
        for index, close in enumerate(closes)
        if index != skip
    ]
    result = ingest_provider_payload(
        store,
        dataset=dataset,
        payload=json.dumps(rows).encode(),
        request=(
            ("symbol", "BTCUSDT"),
            ("interval", "1d"),
            ("limit", "1000"),
            ("startTime", str(rows[0][0])),
            ("endTime", str(rows[-1][0])),
        ),
        fetched_at=fetched,
        provider_schema="binance-public-rest-v1",
        parser_version="binance-archive-rest-v1",
        logical_name="daily.json",
        parser=lambda raw: parse_binance_klines(raw, source="rest_json"),
        observed_column="open_time",
        key_columns=("open_time",),
    )
    manifest = result.normalized_manifest
    snapshot = CryptoSnapshotV1.create(
        members=(
            CryptoSnapshotMemberV1(
                dataset=dataset,
                artifact_key=str(manifest["artifact_key"]),
                artifact_sha256=str(manifest["artifact_sha256"]),
            ),
        ),
        asset_master_version="reviewed-native-v1",
        qualification_versions=(result.quality.method_version,),
    )
    return snapshot, str(manifest["manifest_id"])


def _query(
    snapshot: CryptoSnapshotV1,
    store: CryptoBulkStore,
    manifest: str,
    **kwargs: datetime,
) -> BinanceDailyPriceSnapshotQueryV1:
    options = {"start": START, "end": START + 3 * DAY, "available_by": START + 3 * DAY}
    options.update(kwargs)
    return query_binance_daily_price_snapshot(
        snapshot,
        store,
        normalized_manifest_id=manifest,
        **options,
    )


def test_complete_query_is_pinned_and_explicitly_reconstructed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snapshot, manifest = _publish(store)
    result = _query(snapshot, store, manifest)
    assert [row.close for row in result.rows] == pytest.approx([10, 11, 12])
    assert result.rows[0].available_at == START + DAY
    assert result.rows[0].close_time == START + DAY - timedelta(milliseconds=1)
    document = result.to_dict()
    assert document["coverage"] == "complete_requested_utc_days"
    assert document["point_in_time_claim"] is False
    assert document["execution_authority"] is False
    assert document["raw_capture_after_available_by"] is True
    assert result.content_sha256 == _query(snapshot, store, manifest).content_sha256


def test_incomplete_range_and_unclosed_days_fail(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snapshot, manifest = _publish(store, skip=1)
    with pytest.raises(DataError, match="coverage is incomplete"):
        _query(snapshot, store, manifest)
    snapshot, manifest = _publish(store)
    with pytest.raises(DataError, match="closed-day range"):
        _query(snapshot, store, manifest, available_by=START + 2 * DAY)


def test_recapture_and_revision_do_not_change_original_reopen(tmp_path: Path) -> None:
    store = _store(tmp_path)
    old, old_manifest = _publish(store)
    before = _query(old, store, old_manifest).to_dict()
    same, recapture = _publish(store, fetched=START + 11 * DAY)
    revised, revision = _publish(store, closes=(10.0, 14.0, 12.0), fetched=START + 12 * DAY)
    assert old.snapshot_id == same.snapshot_id
    assert old_manifest != recapture
    assert revised.snapshot_id != old.snapshot_id
    assert _query(old, store, old_manifest).to_dict() == before
    assert (
        _query(same, store, recapture).source_receipts
        != _query(old, store, old_manifest).source_receipts
    )
    assert _query(revised, store, revision).rows[1].close == pytest.approx(14)
    with pytest.raises(DataError, match="binding differs"):
        _query(old, store, revision)


@pytest.mark.bias_guard
def test_future_poison_does_not_change_selected_rows_with_leaky_twin(tmp_path: Path) -> None:
    store = _store(tmp_path)
    original, manifest = _publish(store)
    poisoned, poison_manifest = _publish(store, closes=(10.0, 11.0, 999.0))
    kwargs = {"end": START + 2 * DAY, "available_by": START + 2 * DAY}
    assert (
        _query(original, store, manifest, **kwargs).rows
        == _query(poisoned, store, poison_manifest, **kwargs).rows
    )
    assert _query(original, store, manifest).rows != _query(poisoned, store, poison_manifest).rows


@pytest.mark.parametrize("defect", ["units", "venue", "market_type", "frequency"])
def test_identity_confusion_fails(tmp_path: Path, defect: str) -> None:
    store = _store(tmp_path)
    snapshot, manifest = _publish(store)
    member = snapshot.members[0]
    replacement = {"units": "USD", "venue": "coinbase", "market_type": "linear", "frequency": "1h"}[
        defect
    ]
    changed = CryptoSnapshotV1.create(
        members=(
            replace(
                member,
                dataset=CryptoDatasetIdentityV1.from_dict(
                    {**member.dataset.to_dict(), defect: replacement}
                ),
            ),
        ),
        asset_master_version=snapshot.asset_master_version,
        qualification_versions=snapshot.qualification_versions,
    )
    with pytest.raises(DataError, match="exact Binance"):
        _query(changed, store, manifest)


def test_tampered_payload_and_wrong_manifest_fail(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snapshot, manifest = _publish(store)
    with pytest.raises(DataError, match="binding differs"):
        _query(snapshot, store, "a" * 64)
    (store.bulk_root / snapshot.members[0].artifact_key).write_bytes(b"tampered")
    with pytest.raises(DataError, match="integrity"):
        _query(snapshot, store, manifest)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": START.replace(tzinfo=None)},
        {"start": START + timedelta(hours=1)},
        {"end": START},
        {"end": START + 4001 * DAY, "available_by": START + 4001 * DAY},
    ],
)
def test_bad_query_clocks_and_bounds_fail(tmp_path: Path, kwargs: dict[str, datetime]) -> None:
    store = _store(tmp_path)
    snapshot, manifest = _publish(store)
    with pytest.raises(DataError):
        _query(snapshot, store, manifest, **kwargs)


def test_raw_ceiling_is_checked_before_any_payload_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    snapshot, manifest = _publish(store)
    metadata = list(store.metadata_inventory())
    raw = next(item for item in metadata if item["artifact_kind"] == "raw")
    raw["artifact_bytes"] = 8 * 1024 * 1024 + 1
    monkeypatch.setattr(store, "metadata_inventory", lambda: tuple(metadata))

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("payload verification occurred before raw size preflight")

    monkeypatch.setattr(store, "verify_manifest", forbidden)
    with pytest.raises(DataError, match="8 MiB"):
        _query(snapshot, store, manifest)


@pytest.mark.parametrize(
    "defect,message",
    [
        ("close_clock", "candle clocks"),
        ("duplicate", "candle clocks"),
        ("nan", "invalid numeric"),
        ("negative_volume", "OHLCV"),
        ("negative_price", "OHLCV"),
        ("wrong_schema", "schema differs"),
        ("false_count", "quality/coverage"),
        ("revision", "quality/coverage"),
    ],
)
def test_independently_forged_qualified_artifacts_fail(
    tmp_path: Path, defect: str, message: str
) -> None:
    import hashlib
    import io

    import polars as pl

    from alpha_data.crypto.contracts import CryptoQualityReportV1

    store = _store(tmp_path)
    snapshot, manifest_id = _publish(store)
    manifest, payload = store.read_verified_normalized(manifest_id, max_bytes=32 * 1024 * 1024)
    frame = pl.read_parquet(io.BytesIO(payload))
    if defect == "close_clock":
        frame = frame.with_columns(pl.col("open_time").alias("close_time"))
    elif defect == "duplicate":
        frame = frame.with_columns(pl.lit(START).alias("open_time"))
    elif defect == "nan":
        frame = frame.with_columns(pl.lit(float("nan")).alias("close"))
    elif defect == "negative_volume":
        frame = frame.with_columns(pl.lit(-1.0).alias("base_volume"))
    elif defect == "negative_price":
        frame = frame.with_columns(pl.lit(-1.0).alias("low"))
    elif defect == "wrong_schema":
        frame = frame.with_columns(pl.lit("unexpected").alias("extra"))
    output = io.BytesIO()
    frame.write_parquet(output)
    data = output.getvalue()
    quality = replace(
        CryptoQualityReportV1.from_dict(manifest["quality"]),
        dataset_sha256=hashlib.sha256(data).hexdigest(),
        observed_end=frame["open_time"][-1],
        row_count=4 if defect == "false_count" else frame.height,
        correction_lineage=("a" * 64,) if defect == "revision" else (),
    )
    raw_ids = manifest["input_manifest_ids"]
    assert isinstance(raw_ids, list)
    assert all(isinstance(raw_id, str) for raw_id in raw_ids)
    changed = store.publish_normalized(
        data,
        dataset=snapshot.members[0].dataset,
        input_manifest_ids=tuple(raw_ids),
        quality=quality,
    )
    changed_snapshot = CryptoSnapshotV1.create(
        members=(
            replace(
                snapshot.members[0],
                artifact_key=str(changed["artifact_key"]),
                artifact_sha256=str(changed["artifact_sha256"]),
            ),
        ),
        asset_master_version=snapshot.asset_master_version,
        qualification_versions=snapshot.qualification_versions,
    )
    with pytest.raises(DataError, match=message):
        _query(changed_snapshot, store, str(changed["manifest_id"]))


def _full_discovery_fixture(
    tmp_path: Path,
) -> tuple[CryptoBulkStore, CryptoSnapshotV1, str]:
    """1096 artificial daily native-format observations, actually split over two pages."""
    from alpha_data.crypto.ingestion import ingest_provider_pages

    store = _store(tmp_path)
    dataset = CryptoDatasetIdentityV1(
        provider="binance",
        venue="binance",
        market_type="spot",
        family="market_bars",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="1d",
        units="provider_native_ohlcv",
        timestamp_convention="interval_start_utc",
    )
    end = datetime(2023, 1, 1, tzinfo=UTC)
    end_ms = int(end.timestamp() * 1000) - 1
    rows = [
        [
            int((START + index * DAY).timestamp() * 1000),
            100.0 + index / 10,
            101.0 + index / 10,
            99.0 + index / 10,
            100.0 + index / 10,
            100.0,
            int((START + (index + 1) * DAY).timestamp() * 1000) - 1,
            1000.0,
            10,
            50.0,
            500.0,
            0,
        ]
        for index in range((end - START).days)
    ]
    pages = tuple(
        (
            json.dumps(rows[offset : offset + 1000]).encode(),
            (
                ("symbol", "BTCUSDT"),
                ("interval", "1d"),
                ("limit", "1000"),
                ("startTime", str(rows[offset][0])),
                ("endTime", str(end_ms)),
            ),
            (f"page={page_number}", f"next_start={rows[1000][0] if offset == 0 else 'terminal'}"),
        )
        for page_number, offset in enumerate((0, 1000), 1)
    )
    result = ingest_provider_pages(
        store,
        dataset=dataset,
        pages=pages,
        fetched_at=end + DAY,
        provider_schema="binance-public-rest-v1",
        parser_version="binance-archive-rest-v1",
        logical_name="daily.bin",
        parser=lambda raw: parse_binance_klines(raw, source="rest_json"),
        observed_column="open_time",
        key_columns=("open_time",),
        expected_cadence=DAY,
        period_start_timestamps=True,
    )
    manifest = result.normalized_manifest
    snapshot = CryptoSnapshotV1.create(
        members=(
            CryptoSnapshotMemberV1(
                dataset=dataset,
                artifact_key=str(manifest["artifact_key"]),
                artifact_sha256=str(manifest["artifact_sha256"]),
            ),
        ),
        asset_master_version="reviewed-native-v1",
        qualification_versions=(result.quality.method_version,),
    )
    return store, snapshot, str(manifest["manifest_id"])


def _full_discovery_query(tmp_path: Path) -> BinanceDailyPriceSnapshotQueryV1:
    """Reusable artificial query for typed study binding; no real-market acceptance."""
    store, snapshot, manifest = _full_discovery_fixture(tmp_path)
    return query_binance_daily_price_snapshot(
        snapshot,
        store,
        normalized_manifest_id=manifest,
        start=START,
        end=datetime(2023, 1, 1, tzinfo=UTC),
        available_by=datetime(2023, 1, 1, tzinfo=UTC),
    )


def test_full_discovery_query_has_two_realistic_bounded_pages(tmp_path: Path) -> None:
    query = _full_discovery_query(tmp_path)
    assert len(query.rows) == 1096
    assert len(query.source_receipts) == 2
    assert query.rows[0].open_time == START
    assert query.rows[-1].available_at == datetime(2023, 1, 1, tzinfo=UTC)
    assert query.rows[1000].open_time == START + 1000 * DAY
    assert all(dict(receipt.request)["limit"] == "1000" for receipt in query.source_receipts)
    assert query.to_dict()["point_in_time_claim"] is False


def test_independent_restored_store_reopens_exact_discovery_query(tmp_path: Path) -> None:
    import shutil

    original_root = tmp_path / "original"
    original_root.mkdir()
    store, snapshot, manifest = _full_discovery_fixture(original_root)
    options = {
        "start": START,
        "end": datetime(2023, 1, 1, tzinfo=UTC),
        "available_by": datetime(2023, 1, 1, tzinfo=UTC),
    }
    before = query_binance_daily_price_snapshot(
        snapshot, store, normalized_manifest_id=manifest, **options
    )
    restored_root = tmp_path / "restored"
    shutil.copytree(original_root, restored_root)
    restored = _store(restored_root)
    after = query_binance_daily_price_snapshot(
        snapshot, restored, normalized_manifest_id=manifest, **options
    )
    assert after.content_sha256 == before.content_sha256
    assert after.to_dict() == before.to_dict()

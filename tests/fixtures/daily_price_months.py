"""Synthetic monthly Binance archive payloads; no real-market evidence."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta

from alpha_data.crypto.contracts import (
    CryptoDatasetIdentityV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
)
from alpha_data.crypto.ingestion import CryptoIngestionResultV1, ingest_provider_payload
from alpha_data.crypto.providers.binance import parse_binance_archive_zip, parse_binance_klines
from alpha_data.crypto.storage import CryptoBulkStore

DAY = timedelta(days=1)


def month_start(year: int, month: int) -> datetime:
    return datetime(year + (month - 1) // 12, (month - 1) % 12 + 1, 1, tzinfo=UTC)


def publish_month(
    store: CryptoBulkStore,
    year: int,
    month: int,
    *,
    instrument: str = "BTCUSDT",
    fetched: datetime | None = None,
    price: float = 100.0,
    start: datetime | None = None,
    end: datetime | None = None,
    request: dict[str, str] | None = None,
    rest: bool = False,
) -> CryptoIngestionResultV1:
    start = start or month_start(year, month)
    end = end or month_start(year, month + 1)
    dataset = CryptoDatasetIdentityV1(
        provider="binance",
        venue="binance",
        market_type="spot",
        family="market_bars",
        instrument=instrument,
        base_asset=instrument.removesuffix("USDT"),
        quote_asset="USDT",
        frequency="1d",
        units="provider_native_ohlcv",
        timestamp_convention="interval_start_utc",
    )
    rows = [
        [
            int((start + index * DAY).timestamp() * 1000),
            price,
            price + 1,
            price - 1,
            price,
            100.0,
            int((start + (index + 1) * DAY).timestamp() * 1000) - 1,
            1000.0,
            10,
            50.0,
            500.0,
            0,
        ]
        for index in range((end - start).days)
    ]
    if rest:
        payload = json.dumps(rows).encode()
        request = request or {
            "symbol": instrument,
            "interval": "1d",
            "limit": "1000",
            "startTime": str(rows[0][0]),
            "endTime": str(rows[-1][0]),
        }
    else:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                zipfile.ZipInfo(f"{instrument}-1d-{year}-{month:02d}.csv"),
                "".join(",".join(map(str, row)) + "\n" for row in rows),
            )
        payload = buffer.getvalue()
        request = request or {
            "family": "klines",
            "interval": "1d",
            "market": "spot",
            "period": f"{year}-{month:02d}",
            "symbol": instrument,
        }
    return ingest_provider_payload(
        store,
        dataset=dataset,
        payload=payload,
        request=tuple(sorted(request.items())),
        fetched_at=fetched or end + DAY,
        provider_schema="binance-public-rest-v1" if rest else "binance-public-archive-v1",
        parser_version="binance-archive-rest-v1" if rest else "binance-archive-v1",
        logical_name="market_bars.json" if rest else "market_bars.zip",
        upstream_checksum=None if rest else hashlib.sha256(payload).hexdigest(),
        parser=(lambda raw: parse_binance_klines(raw, source="rest_json"))
        if rest
        else parse_binance_archive_zip,
        observed_column="open_time",
        key_columns=("open_time",),
        expected_cadence=DAY,
        period_start_timestamps=True,
    )


def snapshot_for(*results: CryptoIngestionResultV1) -> CryptoSnapshotV1:
    return CryptoSnapshotV1.create(
        members=tuple(
            CryptoSnapshotMemberV1(
                dataset=CryptoDatasetIdentityV1.from_dict(result.normalized_manifest["dataset"]),
                artifact_key=str(result.normalized_manifest["artifact_key"]),
                artifact_sha256=str(result.normalized_manifest["artifact_sha256"]),
            )
            for result in results
        ),
        asset_master_version="reviewed-native-v1",
        qualification_versions=tuple(sorted({result.quality.method_version for result in results})),
    )


def manifest_ids(*results: CryptoIngestionResultV1) -> tuple[str, ...]:
    return tuple(str(result.normalized_manifest["manifest_id"]) for result in results)

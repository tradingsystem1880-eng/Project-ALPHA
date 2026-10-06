"""Exact archive chart identity, integrity, and completed-bar cutoff behavior."""

import hashlib
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from alpha_cli._chart_data import chart_datasets, load_chart_dataset
from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1
from alpha_data.crypto.storage import CryptoBulkStore
from tests.unit.test_crypto_storage import _store


def archive(tmp_path: Path) -> tuple[CryptoBulkStore, dict[str, Any], dict[str, Any], datetime]:
    store = _store(tmp_path)
    raw = store.begin_staging(
        provider="bybit", receipt_id="chart-raw", logical_name="bars.json", expected_bytes=3
    )
    raw = store.append_staging(raw, b"raw")
    parent = store.publish_staging(raw, expected_sha256=hashlib.sha256(b"raw").hexdigest())
    start = datetime(2026, 9, 1, tzinfo=UTC)
    frame = pl.DataFrame(
        {
            "timestamp": [start, start + timedelta(hours=1)],
            "open": [10.0, 11.0],
            "high": [12.0, 13.0],
            "low": [9.0, 10.0],
            "close": [11.0, 12.0],
            "volume": [100.0, 200.0],
            "category": ["linear"] * 2,
            "symbol": ["BTCUSDT"] * 2,
            "family": ["trade"] * 2,
            "volume_unit_rule": ["base_coin"] * 2,
        }
    )
    stream = io.BytesIO()
    frame.write_parquet(stream)
    payload = stream.getvalue()
    dataset = CryptoDatasetIdentityV1(
        provider="bybit",
        venue="bybit",
        market_type="linear",
        family="derivative_bars",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="1h",
        units="quote_price",
        timestamp_convention="interval_start_utc",
    )
    quality = CryptoQualityReportV1(
        dataset_sha256=hashlib.sha256(payload).hexdigest(),
        method_version="crypto-quality-v1",
        state="qualified",
        failures=(),
        warnings=(),
        observed_start=start,
        observed_end=start + timedelta(hours=1),
        row_count=2,
        correction_lineage=(),
    )
    manifest = store.publish_normalized(
        payload, dataset=dataset, input_manifest_ids=(str(parent["manifest_id"]),), quality=quality
    )
    return store, manifest, parent, start


@pytest.mark.bias_guard
def test_archive_hourly_chart_excludes_unfinished_future_bar(tmp_path: Path) -> None:
    store, manifest, _, start = archive(tmp_path)
    bars, provenance = load_chart_dataset(
        store,
        str(manifest["manifest_id"]),
        symbol="BTCUSDT",
        as_of=start + timedelta(hours=1, minutes=30),
    )
    assert len(bars) == 1
    assert bars[0].close == 11
    assert provenance["market_type"] == "linear"
    assert provenance["timeframe"] == "1H"
    assert provenance["volume_unit"] == "base"


@pytest.mark.parametrize(
    ("frequency", "expected"),
    [("4h", "4H"), ("3d", "3D"), ("1w", "1W")],
)
def test_archive_chart_supports_native_multi_day_and_intraday_intervals(
    tmp_path: Path, frequency: str, expected: str
) -> None:
    from dataclasses import replace

    store, manifest, parent, start = archive(tmp_path)
    dataset = replace(CryptoDatasetIdentityV1.from_dict(manifest["dataset"]), frequency=frequency)
    quality = replace(
        CryptoQualityReportV1.from_dict(manifest["quality"]),
        observed_end=start + timedelta(hours=1),
    )
    payload = (store.bulk_root / str(manifest["artifact_key"])).read_bytes()
    updated = store.publish_normalized(
        payload, dataset=dataset, input_manifest_ids=(str(parent["manifest_id"]),), quality=quality
    )
    _, provenance = load_chart_dataset(
        store, str(updated["manifest_id"]), symbol="BTCUSDT", as_of=start + timedelta(days=10)
    )
    assert provenance["timeframe"] == expected


def test_archive_discovery_does_not_verify_artifacts_or_probe_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, manifest, _, _ = archive(tmp_path)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("discovery performed expensive verification")

    monkeypatch.setattr(store, "verify_manifest", forbidden)
    monkeypatch.setattr(store, "verify_ready", forbidden)
    rows = chart_datasets(store)
    assert len(rows) == 1
    assert rows[0]["manifest_id"] == manifest["manifest_id"]
    assert rows[0]["manifest_ids"] == [manifest["manifest_id"]]
    assert rows[0]["verification"] == "metadata_only"


@pytest.mark.parametrize("conflict", [False, True])
def test_archive_chart_combines_matching_boundary_bars_and_rejects_conflicts(
    tmp_path: Path, conflict: bool
) -> None:
    from dataclasses import replace

    store, manifest, parent, start = archive(tmp_path)
    dataset = CryptoDatasetIdentityV1.from_dict(manifest["dataset"])
    quality = replace(
        CryptoQualityReportV1.from_dict(manifest["quality"]),
        observed_start=start + timedelta(hours=1),
        observed_end=start + timedelta(hours=2),
    )
    payload = io.BytesIO()
    pl.DataFrame(
        {
            "timestamp": [start + timedelta(hours=1), start + timedelta(hours=2)],
            "open": [11.0, 12.0],
            "high": [13.0, 14.0],
            "low": [10.0, 11.0],
            "close": [99.0 if conflict else 12.0, 13.0],
            "volume": [200.0, 300.0],
            "category": ["linear"] * 2,
            "symbol": ["BTCUSDT"] * 2,
            "family": ["trade"] * 2,
            "volume_unit_rule": ["base_coin"] * 2,
        }
    ).write_parquet(payload)
    store.publish_normalized(
        payload.getvalue(),
        dataset=dataset,
        input_manifest_ids=(str(parent["manifest_id"]),),
        quality=replace(quality, dataset_sha256=hashlib.sha256(payload.getvalue()).hexdigest()),
    )
    group = chart_datasets(store)[0]
    assert group["manifest_count"] == 2
    if conflict:
        with pytest.raises(DataError, match="segments disagree"):
            load_chart_dataset(store, str(group["manifest_id"]), symbol="BTCUSDT")
    else:
        bars, _ = load_chart_dataset(store, str(group["manifest_id"]), symbol="BTCUSDT")
        assert [bar.close for bar in bars] == [11, 12, 13]


@pytest.mark.parametrize("failure", ["symbol", "artifact", "parent"])
def test_archive_chart_rejects_wrong_identity_or_tampering(tmp_path: Path, failure: str) -> None:
    store, manifest, parent, _ = archive(tmp_path)
    if failure != "symbol":
        target = parent if failure == "parent" else manifest
        (store.bulk_root / str(target["artifact_key"])).write_bytes(b"bad")
    with pytest.raises(DataError):
        load_chart_dataset(
            store,
            str(manifest["manifest_id"]),
            symbol="ETHUSDT" if failure == "symbol" else "BTCUSDT",
        )


@pytest.mark.parametrize("field,value", [("venue", "other"), ("units", "unknown")])
def test_archive_rejects_unsupported_identity_units(tmp_path: Path, field: str, value: str) -> None:
    from copy import deepcopy

    from alpha_cli._chart_data import _identity

    _, manifest, _, _ = archive(tmp_path)
    invalid = deepcopy(manifest)
    invalid["dataset"][field] = value
    with pytest.raises(DataError, match="not supported"):
        _identity(invalid)


def test_archive_rejects_verified_but_unreadable_parquet(tmp_path: Path) -> None:
    from dataclasses import replace

    store, manifest, parent, _ = archive(tmp_path)
    payload = b"not a parquet file"
    dataset = CryptoDatasetIdentityV1.from_dict(manifest["dataset"])
    quality = replace(
        CryptoQualityReportV1.from_dict(manifest["quality"]),
        dataset_sha256=hashlib.sha256(payload).hexdigest(),
    )
    invalid = store.publish_normalized(
        payload, dataset=dataset, input_manifest_ids=(str(parent["manifest_id"]),), quality=quality
    )
    with pytest.raises(DataError, match="not readable Parquet"):
        load_chart_dataset(store, str(invalid["manifest_id"]), symbol="BTCUSDT")


@pytest.mark.bias_guard
def test_binance_daily_archive_requires_a_completed_day(tmp_path: Path) -> None:
    from dataclasses import replace

    store, manifest, _, start = archive(tmp_path)
    payload = io.BytesIO()
    pl.DataFrame(
        {
            "open_time": [start, start + timedelta(days=1)],
            "open": [10.0, 11.0],
            "high": [12.0, 13.0],
            "low": [9.0, 10.0],
            "close": [11.0, 12.0],
            "base_volume": [100.0, 200.0],
        }
    ).write_parquet(payload)
    raw = store.begin_staging(
        provider="binance", receipt_id="binance-chart", logical_name="bars.zip", expected_bytes=3
    )
    raw = store.append_staging(raw, b"raw")
    parent = store.publish_staging(raw, expected_sha256=hashlib.sha256(b"raw").hexdigest())
    dataset = replace(
        CryptoDatasetIdentityV1.from_dict(manifest["dataset"]),
        provider="binance",
        venue="binance",
        market_type="spot",
        family="market_bars",
        frequency="1d",
        units="provider_native_ohlcv",
    )
    quality = replace(
        CryptoQualityReportV1.from_dict(manifest["quality"]),
        dataset_sha256=hashlib.sha256(payload.getvalue()).hexdigest(),
        observed_end=start + timedelta(days=1),
    )
    daily = store.publish_normalized(
        payload.getvalue(),
        dataset=dataset,
        input_manifest_ids=(str(parent["manifest_id"]),),
        quality=quality,
    )
    bars, provenance = load_chart_dataset(
        store, str(daily["manifest_id"]), symbol="BTCUSDT", as_of=start + timedelta(days=1)
    )
    assert len(bars) == 1
    assert bars[0].close == 11
    assert provenance["timeframe"] == "1D"
    assert provenance["volume_unit"] == "base"

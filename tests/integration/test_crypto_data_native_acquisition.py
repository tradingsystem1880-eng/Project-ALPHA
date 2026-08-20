from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.main import app
from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoFamily
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

runner = CliRunner()


def _manifest(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


@pytest.mark.parametrize(
    ("family", "csv_name", "csv_payload", "expected_frequency"),
    (
        (
            "trades",
            "BTCUSDT-trades-2025-01.csv",
            b"51175358,17.8018,5.69,101.292242,1735689600010866,True,True\n",
            "trade_events",
        ),
        (
            "aggregate_trades",
            "BTCUSDT-aggTrades-2025-01.csv",
            b"26129,0.01633102,4.70443515,27781,27781,1735689600010866,true\n",
            "aggregate_trade_events",
        ),
    ),
)
def test_binance_trade_archive_families_acquire_with_exact_native_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    family: CryptoFamily,
    csv_name: str,
    csv_payload: bytes,
    expected_frequency: str,
) -> None:
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    store = CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=20_000_000, free_bytes=10_000_000),
        minimum_free_bytes=100,
    )
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(
        crypto_data_cmds,
        "_now",
        lambda: datetime.fromisoformat("2026-08-15T00:00:00+00:00"),
    )
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(csv_name, csv_payload)
    archive_payload = zipped.getvalue()
    monkeypatch.setattr(crypto_data_cmds, "fetch_binance_archive", lambda *_args: archive_payload)
    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_binance_checksum",
        lambda *_args: f"{hashlib.sha256(archive_payload).hexdigest()} file.zip\n".encode(),
    )

    result = runner.invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "binance",
            family,
            "BTCUSDT",
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--category",
            "spot",
            "--period",
            "2025-01",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["state"] == "qualified"
    manifest = _manifest(store.verify_manifest(receipt["normalized_manifest_id"]))
    assert manifest["dataset"]["family"] == family
    assert manifest["dataset"]["frequency"] == expected_frequency
    raw_manifest = _manifest(store.verify_manifest(receipt["raw_manifest_id"]))
    assert (
        raw_manifest["receipt"]["upstream_checksum"] == hashlib.sha256(archive_payload).hexdigest()
    )


def test_binance_book_snapshot_acquires_as_point_in_time_non_execution_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    store = CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=20_000_000, free_bytes=10_000_000),
        minimum_free_bytes=100,
    )
    fetched_at = datetime.fromisoformat("2026-08-15T00:00:00+00:00")
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(crypto_data_cmds, "_now", lambda: fetched_at)
    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_binance_public_api",
        lambda *_args: b'{"lastUpdateId":42,"bids":[["90000","1.5"]],"asks":[["90001","0.5"]]}',
    )

    result = runner.invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "binance",
            "book_snapshots",
            "BTCUSDT",
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--category",
            "spot",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["state"] == "qualified"
    assert receipt["execution_authority"] is False
    manifest = _manifest(store.verify_manifest(receipt["normalized_manifest_id"]))
    assert manifest["dataset"]["family"] == "book_snapshots"
    assert manifest["dataset"]["frequency"] == "point_in_time_book"
    assert manifest["dataset"]["timestamp_convention"] == "fetch_knowledge_utc"


def test_binance_market_membership_acquires_active_venue_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    store = CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=20_000_000, free_bytes=10_000_000),
        minimum_free_bytes=100,
    )
    fetched_at = datetime.fromisoformat("2026-08-15T00:00:00+00:00")
    payload = json.dumps(
        {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": True,
                }
            ]
        }
    ).encode()
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(crypto_data_cmds, "_now", lambda: fetched_at)
    monkeypatch.setattr(crypto_data_cmds, "fetch_binance_public_api", lambda *_args: payload)

    result = runner.invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "binance",
            "market_membership",
            "spot",
            "--base",
            "ALL",
            "--quote",
            "ALL",
            "--category",
            "spot",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["state"] == "qualified"
    manifest = _manifest(store.verify_manifest(receipt["normalized_manifest_id"]))
    assert manifest["dataset"]["family"] == "market_membership"
    assert manifest["dataset"]["provider"] == "binance"
    frame = pl.read_parquet(store.bulk_root / manifest["artifact_key"])
    assert frame.select("symbol", "contract_type").rows() == [("BTCUSDT", "SPOT")]


def test_binance_archive_and_rest_tail_freeze_both_resources_and_reconcile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    store = CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=20_000_000, free_bytes=10_000_000),
        minimum_free_bytes=100,
    )
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(
        crypto_data_cmds,
        "_now",
        lambda: datetime.fromisoformat("2026-08-15T00:00:00+00:00"),
    )
    archived_row = b"1738195200000,100,110,90,105,12,1738281599999,1260,42,6,630,0\n"
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BTCUSDT-1d-2025-01.csv", archived_row)
    archive_payload = zipped.getvalue()
    tail_payload = json.dumps(
        [
            [
                1738195200000,
                "100",
                "110",
                "90",
                "105",
                "12",
                1738281599999,
                "1260",
                42,
                "6",
                "630",
                "0",
            ],
            [
                1738281600000,
                "105",
                "115",
                "100",
                "110",
                "10",
                1738367999999,
                "1100",
                30,
                "5",
                "550",
                "0",
            ],
        ]
    ).encode()
    monkeypatch.setattr(crypto_data_cmds, "fetch_binance_archive", lambda *_args: archive_payload)
    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_binance_checksum",
        lambda *_args: f"{hashlib.sha256(archive_payload).hexdigest()} file.zip\n".encode(),
    )
    monkeypatch.setattr(crypto_data_cmds, "fetch_binance_public_api", lambda *_args: tail_payload)

    result = runner.invoke(
        app,
        [
            "crypto-data",
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
            "--period",
            "2025-01",
            "--start",
            "2025-01-30T00:00:00Z",
            "--end",
            "2025-01-31T00:00:00Z",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["state"] == "qualified"
    assert receipt["raw_page_count"] == 2
    manifest = _manifest(store.verify_manifest(receipt["normalized_manifest_id"]))
    assert manifest["quality"]["row_count"] == 2
    assert manifest["input_manifest_ids"] == receipt["raw_manifest_ids"]
    archive_raw = _manifest(store.verify_manifest(receipt["raw_manifest_ids"][0]))
    tail_raw = _manifest(store.verify_manifest(receipt["raw_manifest_ids"][1]))
    assert (
        archive_raw["receipt"]["upstream_checksum"] == hashlib.sha256(archive_payload).hexdigest()
    )
    assert tail_raw["receipt"]["upstream_checksum"] is None


def test_changed_binance_archive_is_versioned_and_quarantined_as_unexplained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    store = CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=20_000_000, free_bytes=10_000_000),
        minimum_free_bytes=100,
    )
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(
        crypto_data_cmds,
        "_now",
        lambda: datetime.fromisoformat("2026-08-15T00:00:00+00:00"),
    )

    def zipped(close: str) -> bytes:
        output = io.BytesIO()
        row = (
            f"1704067200000,42000,43000,41000,{close},12.5,1704153599999,531250,42,6.1,259250,0\n"
        ).encode()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("BTCUSDT-1d-2024-01.csv", row)
        return output.getvalue()

    first_payload, second_payload = zipped("42500"), zipped("42600")
    current: list[bytes] = []
    payloads = iter((first_payload, second_payload))

    def fetch_archive(*_args: object) -> bytes:
        return current[0]

    def fetch_checksum(*_args: object) -> bytes:
        current[:] = [next(payloads)]
        return f"{hashlib.sha256(current[0]).hexdigest()} file.zip\n".encode()

    monkeypatch.setattr(crypto_data_cmds, "fetch_binance_archive", fetch_archive)
    monkeypatch.setattr(crypto_data_cmds, "fetch_binance_checksum", fetch_checksum)
    command = [
        "crypto-data",
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
        "--period",
        "2024-01",
        "--json",
    ]

    first = runner.invoke(app, command)
    second = runner.invoke(app, command)

    assert first.exit_code == 0, first.output
    assert json.loads(first.stdout)["state"] == "qualified"
    assert second.exit_code == 0, second.output
    second_receipt = json.loads(second.stdout)
    assert second_receipt["state"] == "quarantined"
    manifest = _manifest(store.verify_manifest(second_receipt["normalized_manifest_id"]))
    assert manifest["quality"]["failures"] == ["unexplained_provider_revision"]
    assert manifest["quality"]["correction_lineage"] == [hashlib.sha256(first_payload).hexdigest()]


def test_bybit_bounded_open_interest_follows_cursors_and_freezes_each_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    store = CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=2_000_000, free_bytes=1_000_000),
        minimum_free_bytes=100,
    )
    calls: list[dict[str, str | int]] = []

    def fetch(_endpoint: str, params: dict[str, str | int]) -> bytes:
        calls.append(dict(params))
        cursor = params.get("cursor")
        timestamp = "1786748400000" if cursor else "1786752000000"
        body: dict[str, object] = {
            "category": "linear",
            "symbol": "BTCUSDT",
            "list": [{"openInterest": "100", "timestamp": timestamp}],
        }
        if cursor is None:
            body["nextPageCursor"] = "cursor-a"
        return json.dumps({"retCode": 0, "time": 1_786_752_000_000, "result": body}).encode()

    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(crypto_data_cmds, "fetch_bybit_public", fetch)
    monkeypatch.setattr(
        crypto_data_cmds,
        "_now",
        lambda: datetime.fromisoformat("2026-08-15T00:00:00+00:00"),
    )

    result = runner.invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "bybit",
            "open_interest",
            "BTCUSDT",
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--frequency",
            "1h",
            "--start",
            "2026-08-14T00:00:00Z",
            "--end",
            "2026-08-15T00:00:00Z",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert calls == [
        {
            "category": "linear",
            "symbol": "BTCUSDT",
            "intervalTime": "1h",
            "limit": 200,
            "startTime": 1_786_665_600_000,
            "endTime": 1_786_752_000_000,
        },
        {
            "category": "linear",
            "symbol": "BTCUSDT",
            "intervalTime": "1h",
            "limit": 200,
            "startTime": 1_786_665_600_000,
            "endTime": 1_786_752_000_000,
            "cursor": "cursor-a",
        },
    ]
    assert receipt["raw_page_count"] == 2
    assert len(receipt["raw_manifest_ids"]) == 2
    assert receipt["state"] == "qualified"
    assert len(store.inventory()) == 3


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        ("2026-08-14T00:00:00Z", None, "together"),
        ("2026-08-15T00:00:00Z", "2026-08-14T00:00:00Z", "later than start"),
    ],
)
def test_bybit_range_fails_closed_when_incomplete_or_inverted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    start: str | None,
    end: str | None,
    message: str,
) -> None:
    # The range check must be reached, so the store is stubbed like every other
    # test here; otherwise bulk-volume validation answers first and the
    # assertion below passes or fails on the ambient environment instead.
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    store = CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=20_000_000, free_bytes=10_000_000),
        minimum_free_bytes=100,
    )
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    args = [
        "crypto-data",
        "acquire",
        "bybit",
        "open_interest",
        "BTCUSDT",
        "--base",
        "BTC",
        "--quote",
        "USDT",
    ]
    if start is not None:
        args.extend(["--start", start])
    if end is not None:
        args.extend(["--end", end])
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert message in result.output


def test_bybit_bounded_pages_reject_observations_outside_requested_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetched_at = datetime.fromisoformat("2026-08-15T00:00:00+00:00")
    plan = crypto_data_cmds._bybit_plan(
        "open_interest",
        "BTCUSDT",
        base="BTC",
        quote="USDT",
        category="linear",
        frequency="1h",
        start="2026-08-14T00:00:00Z",
        end="2026-08-15T00:00:00Z",
        fetched_at=fetched_at,
    )
    payload = json.dumps(
        {
            "retCode": 0,
            "time": 1_786_752_000_000,
            "result": {
                "category": "linear",
                "symbol": "BTCUSDT",
                "list": [{"openInterest": "100", "timestamp": "1786665599000"}],
            },
        }
    ).encode()
    monkeypatch.setattr(crypto_data_cmds, "fetch_bybit_public", lambda *_args: payload)

    with pytest.raises(DataError, match="outside the exact requested range"):
        crypto_data_cmds._fetch_bybit_pages(plan, follow_cursors=True)


def test_binance_tail_rejects_mixed_rows_outside_requested_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start_ms = 1_786_665_600_000
    end_ms = start_ms + 3_600_000
    payload = json.dumps(
        [
            [
                start_ms - 3_600_000,
                "100",
                "110",
                "90",
                "105",
                "12",
                start_ms - 1,
                "1260",
                42,
                "6",
                "630",
                "0",
            ],
            [
                start_ms,
                "105",
                "115",
                "100",
                "110",
                "10",
                end_ms - 1,
                "1100",
                30,
                "5",
                "550",
                "0",
            ],
        ]
    ).encode()
    monkeypatch.setattr(crypto_data_cmds, "fetch_binance_public_api", lambda *_args: payload)

    with pytest.raises(DataError, match="outside the exact requested range"):
        crypto_data_cmds._fetch_binance_tail_pages(
            category="spot",
            symbol="BTCUSDT",
            frequency="1h",
            start_ms=start_ms,
            end_ms=end_ms,
        )

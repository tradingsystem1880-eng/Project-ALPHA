from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.main import app
from alpha_data.crypto.contracts import FAMILY_AUTHORITIES
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

runner = CliRunner()


def test_crypto_data_catalog_is_family_authoritative_and_human_readable() -> None:
    result = runner.invoke(app, ["crypto-data", "catalog", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert {row["family"]: row["provider"] for row in payload["families"]} == FAMILY_AUTHORITIES
    assert payload["automatic_fallback"] is False
    assert payload["execution_authority"] is False
    assert payload["next_action"] == "Check storage before estimating or acquiring data."


def test_crypto_data_estimate_is_bounded_and_rejects_unbounded_tick_mirrors() -> None:
    result = runner.invoke(
        app,
        [
            "crypto-data",
            "estimate",
            "option_quotes",
            "--instruments",
            "3",
            "--days",
            "30",
            "--frequency",
            "1h",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    estimate = json.loads(result.stdout)
    assert estimate["provider"] == "bybit"
    assert estimate["estimated_bytes"] > 0
    assert estimate["bounded"] is True
    assert estimate["estimate_only"] is True

    rejected = runner.invoke(
        app,
        [
            "crypto-data",
            "estimate",
            "trades",
            "--instruments",
            "51",
            "--days",
            "365",
            "--frequency",
            "tick",
        ],
    )
    assert rejected.exit_code != 0
    assert "bounded research windows" in rejected.output


def test_crypto_data_storage_projection_is_safe_when_not_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = tmp_path / "private-user-folder" / "bulk"
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path / "control"))
    monkeypatch.setenv("ALPHA_BULK_DATA_DIR", str(private))
    monkeypatch.setenv("ALPHA_BULK_VOLUME_UUID", "")

    result = runner.invoke(app, ["crypto-data", "storage", "--json"])

    assert result.exit_code == 0, result.output
    status = json.loads(result.stdout)
    assert status["state"] == "blocked"
    assert status["blocker"] == "bulk_volume_uuid_not_configured"
    assert status["bulk_root_label"] == "bulk"
    assert str(tmp_path) not in result.stdout


def test_crypto_data_asset_identity_uses_reviewed_native_mapping_not_ticker_join() -> None:
    btc = runner.invoke(
        app,
        ["crypto-data", "asset", "BTC", "--as-of", "2026-08-15T00:00:00Z", "--json"],
    )
    assert btc.exit_code == 0, btc.output
    identity = json.loads(btc.stdout)
    assert identity["coingecko_id"] == "bitcoin"
    assert identity["network"] == "bitcoin"
    assert identity["native_asset"] is True

    unknown = runner.invoke(
        app,
        ["crypto-data", "asset", "DOGE", "--as-of", "2026-08-15T00:00:00Z"],
    )
    assert unknown.exit_code != 0
    assert "reviewed native mapping" in unknown.output


def test_crypto_data_acquire_freezes_one_bounded_bybit_family_offline(
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
    payload = json.dumps(
        {
            "retCode": 0,
            "time": 1_786_752_000_000,
            "result": {
                "category": "linear",
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "fundingRate": "0.0001",
                        "fundingRateTimestamp": "1786752000000",
                    }
                ],
            },
        }
    ).encode()
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path / "control"))
    monkeypatch.setattr(crypto_data_cmds, "fetch_bybit_public", lambda *_args, **_kwargs: payload)
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
            "funding",
            "BTCUSDT",
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["state"] == "qualified"
    assert receipt["provider"] == "bybit"
    assert receipt["family"] == "funding"
    assert receipt["raw_manifest_id"] != receipt["normalized_manifest_id"]
    assert receipt["next_action"] == "Create or extend a frozen crypto snapshot."
    assert len(store.inventory()) == 2

    created = runner.invoke(
        app,
        [
            "crypto-data",
            "snapshot-create",
            "--manifest-id",
            receipt["normalized_manifest_id"],
            "--json",
        ],
    )
    assert created.exit_code == 0, created.output
    snapshot = json.loads(created.stdout)
    assert snapshot["member_count"] == 1
    assert snapshot["families"] == ["funding"]

    verified = runner.invoke(
        app,
        [
            "crypto-data",
            "snapshot-verify",
            snapshot["snapshot_id"],
            "--required-family",
            "funding",
            "--purpose",
            "research",
            "--json",
        ],
    )
    assert verified.exit_code == 0, verified.output
    verification = json.loads(verified.stdout)
    assert verification["eligible"] is True
    assert verification["blockers"] == []

    coverage = runner.invoke(app, ["crypto-data", "coverage", "--json"])
    assert coverage.exit_code == 0, coverage.output
    coverage_payload = json.loads(coverage.stdout)
    assert coverage_payload["items"][0]["family"] == "funding"
    assert coverage_payload["items"][0]["state"] == "qualified"
    assert coverage_payload["canonical_next_action"] == "Select qualified families for a snapshot."

    quality = runner.invoke(
        app,
        [
            "crypto-data",
            "quality",
            receipt["normalized_manifest_id"],
            "--json",
        ],
    )
    assert quality.exit_code == 0, quality.output
    assert json.loads(quality.stdout)["quality"]["state"] == "qualified"


def test_crypto_data_acquires_each_non_bybit_authority_offline(
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
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path / "control"))
    monkeypatch.setenv("ALPHA_COINGECKO_API_KEY", "injected-only-for-test")
    monkeypatch.setattr(
        crypto_data_cmds,
        "_now",
        lambda: datetime.fromisoformat("2026-08-15T00:00:00+00:00"),
    )

    csv = b"1704067200000,42000,43000,41000,42500,12.5,1704153599999,531250,42,6.1,259250,0\n"
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BTCUSDT-1d-2024-01.csv", csv)
    binance_payload = zipped.getvalue()
    monkeypatch.setattr(crypto_data_cmds, "fetch_binance_archive", lambda *_args: binance_payload)
    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_binance_checksum",
        lambda *_args: f"{hashlib.sha256(binance_payload).hexdigest()} file.zip\n".encode(),
    )

    coingecko_payload = json.dumps(
        [
            {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "current_price": 60_000,
                "market_cap": 1_200_000,
                "market_cap_rank": 1,
                "fully_diluted_valuation": None,
                "total_volume": 100,
                "circulating_supply": 20,
                "total_supply": 21,
                "max_supply": 21,
                "last_updated": "2026-08-14T00:00:00Z",
            }
        ]
    ).encode()
    monkeypatch.setattr(crypto_data_cmds, "fetch_coingecko_demo", lambda *_args: coingecko_payload)

    gecko_payload = json.dumps(
        {
            "data": [
                {
                    "id": "eth_0xpool",
                    "type": "pool",
                    "attributes": {
                        "address": "0xPool",
                        "name": "USDC / WETH",
                        "pool_created_at": "2021-12-30T20:32:10Z",
                        "base_token_price_usd": "1.0",
                        "quote_token_price_usd": "2000",
                        "reserve_in_usd": "4558978.84",
                        "volume_usd": {"h24": "39081025"},
                        "transactions": {"h24": {"buys": 8, "sells": 7}},
                    },
                    "relationships": {
                        "base_token": {"data": {"id": "eth_0xbase", "type": "token"}},
                        "quote_token": {"data": {"id": "eth_0xquote", "type": "token"}},
                        "dex": {"data": {"id": "uniswap_v3", "type": "dex"}},
                    },
                }
            ]
        }
    ).encode()
    monkeypatch.setattr(
        crypto_data_cmds, "fetch_geckoterminal_public", lambda *_args: gecko_payload
    )

    coinmetrics_payload = json.dumps(
        {
            "data": [
                {
                    "asset": "btc",
                    "time": "2026-08-14T00:00:00Z",
                    "AdrActCnt": "123",
                    "AdrActCnt-status": "reviewed",
                }
            ]
        }
    ).encode()
    monkeypatch.setattr(
        crypto_data_cmds, "fetch_coinmetrics_community", lambda *_args: coinmetrics_payload
    )

    commands = (
        [
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
        ],
        [
            "coingecko",
            "market_reference",
            "bitcoin",
            "--base",
            "BTC",
            "--quote",
            "USD",
        ],
        [
            "geckoterminal",
            "dex_pools",
            "ethereum",
            "--base",
            "ETH",
            "--quote",
            "USDC",
            "--network",
            "eth",
        ],
        [
            "coinmetrics",
            "onchain_metrics",
            "btc",
            "--base",
            "BTC",
            "--quote",
            "USD",
            "--frequency",
            "1d",
            "--metrics",
            "AdrActCnt",
            "--start",
            "2026-08-14",
            "--end",
            "2026-08-15",
        ],
    )
    for command in commands:
        result = runner.invoke(app, ["crypto-data", "acquire", *command, "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["state"] == "qualified"

    assert len(store.inventory()) == 8
    inventory_json = json.dumps(store.inventory())
    assert "injected-only-for-test" not in inventory_json

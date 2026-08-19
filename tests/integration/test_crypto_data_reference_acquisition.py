from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from urllib.request import Request

import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.main import app
from alpha_data.adapters.ccxt_adapter import CCXTAdapter, parse_ccxt_ohlcv
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

runner = CliRunner()


def _manifest(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


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
    monkeypatch.setattr(crypto_data_cmds, "_pause_geckoterminal_page", lambda: None)
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
    coingecko_detail_payload = json.dumps(
        {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "categories": ["Layer 1"],
            "genesis_date": "2009-01-03",
        }
    ).encode()

    def fetch_coingecko(request: Request) -> bytes:
        return (
            coingecko_detail_payload if "/coins/bitcoin?" in request.full_url else coingecko_payload
        )

    monkeypatch.setattr(crypto_data_cmds, "fetch_coingecko_demo", fetch_coingecko)

    def fetch_geckoterminal(url: str) -> bytes:
        page = int(url.split("page=")[1].split("&", 1)[0])
        pools = []
        for offset in range(20):
            index = (page - 1) * 20 + offset
            pools.append(
                {
                    "id": f"eth_0xpool{index}",
                    "type": "pool",
                    "attributes": {
                        "address": f"0xpool{index}",
                        "name": f"TOKEN{index} / WETH",
                        "pool_created_at": "2021-12-30T20:32:10Z",
                        "base_token_price_usd": "1.0",
                        "quote_token_price_usd": "2000",
                        "reserve_in_usd": "4558978.84",
                        "volume_usd": {"h24": "39081025"},
                        "transactions": {"h24": {"buys": 8, "sells": 7}},
                    },
                    "relationships": {
                        "base_token": {"data": {"id": f"eth_0xbase{index}", "type": "token"}},
                        "quote_token": {"data": {"id": "eth_0xquote", "type": "token"}},
                        "dex": {"data": {"id": "uniswap_v3", "type": "dex"}},
                    },
                }
            )
        return json.dumps({"data": pools}).encode()

    monkeypatch.setattr(crypto_data_cmds, "fetch_geckoterminal_public", fetch_geckoterminal)

    coinmetrics_timeseries_payload = json.dumps(
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
    coinmetrics_catalog_page_1 = json.dumps(
        {
            "data": [
                {
                    "asset": "btc",
                    "metrics": [{"metric": "AdrActCnt", "frequencies": [{"frequency": "1d"}]}],
                }
            ],
            "next_page_token": "next-1",
        }
    ).encode()
    coinmetrics_catalog_page_2 = json.dumps(
        {
            "data": [
                {
                    "asset": "eth",
                    "metrics": [{"metric": "TxCnt", "frequencies": [{"frequency": "1d"}]}],
                }
            ]
        }
    ).encode()

    def fetch_coinmetrics(url: str) -> bytes:
        if "catalog-all" not in url:
            return coinmetrics_timeseries_payload
        return (
            coinmetrics_catalog_page_2
            if "next_page_token=next-1" in url
            else coinmetrics_catalog_page_1
        )

    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_coinmetrics_community",
        fetch_coinmetrics,
    )
    comparison_result = parse_ccxt_ohlcv(
        [[1_704_067_200_000, 49_000.0, 51_000.0, 48_000.0, 50_000.0, 1_000.0]],
        "BTC/USDT",
    )
    monkeypatch.setattr(
        CCXTAdapter,
        "fetch_timeframe",
        lambda _self, _symbol, _start, _end, *, timeframe: comparison_result,
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
            "coingecko",
            "asset_metadata",
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
            "onchain_catalog",
            "community",
            "--base",
            "ALL",
            "--quote",
            "USD",
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
        [
            "ccxt:coinbase",
            "comparison_bars",
            "BTC/USDT",
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--category",
            "spot",
            "--frequency",
            "1d",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-01",
        ],
    )
    receipts: dict[str, dict[str, object]] = {}
    for command in commands:
        result = runner.invoke(app, ["crypto-data", "acquire", *command, "--json"])
        assert result.exit_code == 0, result.output
        receipt = json.loads(result.stdout)
        assert receipt["state"] == "qualified"
        receipts[str(receipt["family"])] = receipt

    assert receipts["onchain_catalog"]["raw_page_count"] == 2
    raw_manifest_ids = receipts["onchain_catalog"]["raw_manifest_ids"]
    assert isinstance(raw_manifest_ids, list)
    raw_catalog_page = _manifest(store.verify_manifest(str(raw_manifest_ids[0])))
    request_pairs = raw_catalog_page["receipt"]["request"]
    assert isinstance(request_pairs, list)
    assert dict(request_pairs)["page_size"] == "1000"
    assert len(store.inventory()) == 19
    inventory_json = json.dumps(store.inventory())
    assert "injected-only-for-test" not in inventory_json

    capabilities = runner.invoke(app, ["crypto-data", "capabilities", "--json"])
    assert capabilities.exit_code == 0, capabilities.output
    capability_payload = json.loads(capabilities.stdout)
    assert capability_payload["provider_probe_performed"] is False
    assert capability_payload["automatic_fallback"] is False
    by_family = {item["family"]: item for item in capability_payload["items"]}
    assert by_family["market_bars"]["verification_state"] == "receipt_verified"
    assert by_family["market_bars"]["qualification_state"] == "qualified"
    assert by_family["open_interest"]["verification_state"] == "not_verified"
    assert by_family["comparison_bars"]["verification_state"] == "receipt_verified"
    assert by_family["comparison_bars"]["qualification_state"] == "qualified"

    compared = runner.invoke(
        app,
        [
            "crypto-data",
            "compare",
            "--primary-manifest-id",
            str(receipts["market_bars"]["normalized_manifest_id"]),
            "--comparison-manifest-id",
            str(receipts["comparison_bars"]["normalized_manifest_id"]),
            "--warning-bps",
            "100",
            "--quarantine-bps",
            "500",
            "--json",
        ],
    )
    assert compared.exit_code == 0, compared.output
    comparison = json.loads(compared.stdout)
    assert comparison["state"] == "quarantined"
    assert comparison["automatic_substitution"] is False
    assert comparison["execution_authority"] is False
    derived = store.verify_manifest(comparison["manifest_id"])
    assert derived["artifact_kind"] == "derived"
    assert derived["input_manifest_ids"] == [
        receipts["market_bars"]["normalized_manifest_id"],
        receipts["comparison_bars"]["normalized_manifest_id"],
    ]


def test_public_reference_catalogs_freeze_every_ordered_page(
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

    def market_row(index: int) -> dict[str, object]:
        return {
            "id": f"coin-{index}",
            "symbol": f"c{index}",
            "name": f"Coin {index}",
            "current_price": float(index + 1),
            "market_cap": float(10_000 - index),
            "market_cap_rank": index + 1,
            "fully_diluted_valuation": None,
            "total_volume": 100.0,
            "circulating_supply": 20.0,
            "total_supply": 21.0,
            "max_supply": 21.0,
            "last_updated": "2026-08-14T00:00:00Z",
        }

    coin_pages: list[int] = []

    def fetch_coingecko(request: Request) -> bytes:
        url = request.full_url
        page = int(url.split("page=")[1].split("&", 1)[0])
        coin_pages.append(page)
        if page == 1:
            rows = [market_row(index) for index in range(250)]
        else:
            moved_asset = market_row(249)
            moved_asset["last_updated"] = "2026-08-14T00:01:00Z"
            rows = [moved_asset, market_row(250)]
        return json.dumps(rows).encode()

    monkeypatch.setattr(crypto_data_cmds, "fetch_coingecko_demo", fetch_coingecko)
    coingecko = runner.invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "coingecko",
            "market_reference",
            "all",
            "--base",
            "ALL",
            "--quote",
            "USD",
            "--json",
        ],
    )
    assert coingecko.exit_code == 0, coingecko.output
    coingecko_receipt = json.loads(coingecko.stdout)
    assert coin_pages == [1, 2]
    assert coingecko_receipt["raw_page_count"] == 2
    coingecko_manifest = _manifest(
        store.verify_manifest(coingecko_receipt["normalized_manifest_id"])
    )
    assert coingecko_manifest["quality"]["row_count"] == 252
    assert coingecko_manifest["quality"]["state"] == "qualified"
    assert coingecko_manifest["dataset"]["instrument"] == "all"
    assert coingecko_manifest["dataset"]["base_asset"] is None

    def pool_page(page: int) -> bytes:
        rows = []
        for offset in range(20):
            index = (page - 1) * 20 + offset
            rows.append(
                {
                    "id": f"eth_0xpool{index}",
                    "type": "pool",
                    "attributes": {
                        "address": f"0xpool{index}",
                        "name": f"TOKEN{index} / WETH",
                        "pool_created_at": "2021-12-30T20:32:10Z",
                        "base_token_price_usd": "1.0",
                        "quote_token_price_usd": "2000",
                        "reserve_in_usd": "4558978.84",
                        "volume_usd": {"h24": "39081025"},
                        "transactions": {"h24": {"buys": 8, "sells": 7}},
                    },
                    "relationships": {
                        "base_token": {"data": {"id": f"eth_0xbase{index}", "type": "token"}},
                        "quote_token": {"data": {"id": "eth_0xquote", "type": "token"}},
                        "dex": {"data": {"id": "uniswap_v3", "type": "dex"}},
                    },
                }
            )
        return json.dumps({"data": rows}).encode()

    pool_pages: list[int] = []
    page_pauses: list[float] = []

    def fetch_gecko(url: str) -> bytes:
        page = int(url.split("page=")[1].split("&", 1)[0])
        pool_pages.append(page)
        return pool_page(page)

    monkeypatch.setattr(crypto_data_cmds, "fetch_geckoterminal_public", fetch_gecko)
    monkeypatch.setattr(
        crypto_data_cmds, "_pause_geckoterminal_page", lambda: page_pauses.append(2.1)
    )
    gecko = runner.invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "geckoterminal",
            "dex_pools",
            "eth",
            "--base",
            "ETH",
            "--quote",
            "USD",
            "--network",
            "eth",
            "--json",
        ],
    )
    assert gecko.exit_code == 0, gecko.output
    gecko_receipt = json.loads(gecko.stdout)
    assert pool_pages == [1, 2, 3, 4, 5]
    assert page_pauses == [2.1, 2.1, 2.1, 2.1]
    assert gecko_receipt["raw_page_count"] == 5
    gecko_manifest = _manifest(store.verify_manifest(gecko_receipt["normalized_manifest_id"]))
    assert gecko_manifest["quality"]["row_count"] == 100

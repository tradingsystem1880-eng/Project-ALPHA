from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast
from urllib.request import Request

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.control_store import research_case_revision
from alpha_cli.main import app
from alpha_core import DataError
from alpha_data.adapters.ccxt_adapter import CCXTAdapter, parse_ccxt_ohlcv
from alpha_data.crypto.contracts import FAMILY_AUTHORITIES, CryptoDatasetIdentityV1, CryptoFamily
from alpha_data.crypto.ingestion import ingest_provider_payload
from alpha_data.crypto.profiles import CryptoCoverageProfileV1, CryptoCoverageTaskV1
from alpha_data.crypto.providers.binance import parse_binance_exchange_info, parse_binance_klines
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

runner = CliRunner()


def _manifest(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_coinmetrics_catalog_rejects_a_repeated_pagination_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = json.dumps(
        {
            "data": [
                {
                    "asset": "btc",
                    "metrics": [{"metric": "AdrActCnt", "frequencies": [{"frequency": "1d"}]}],
                }
            ],
            "next_page_token": "repeated-cursor",
        }
    ).encode()
    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_coinmetrics_community",
        lambda _url: payload,
    )

    with pytest.raises(DataError, match="catalog cursor repeated"):
        crypto_data_cmds._fetch_non_bybit(
            "coinmetrics",
            "onchain_catalog",
            "community",
            tmp_path,
            base="ALL",
            quote="USD",
            category="network",
            frequency="catalog_snapshot",
            period=None,
            network=None,
            pool_address=None,
            metrics=None,
            start=None,
            end=None,
            fetched_at=datetime.fromisoformat("2026-08-15T00:00:00+00:00"),
        )


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


def test_crypto_storage_inventory_verify_and_confirmed_cache_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = CryptoBulkStore(
        bulk_root=tmp_path / "bulk",
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=2_000_000, free_bytes=1_000_000),
        minimum_free_bytes=100,
    )
    store.bulk_root.mkdir()
    cache = store.bulk_root / "cache"
    cache.mkdir()
    (cache / "temporary.bin").write_bytes(b"cache")
    protected = store.bulk_root / "normalized" / "protected.parquet"
    protected.parent.mkdir()
    protected.write_bytes(b"protected")
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(crypto_data_cmds, "_snapshot_root", lambda: tmp_path / "snapshots")

    inventory = runner.invoke(app, ["crypto-data", "storage-inventory", "--json"])
    verified = runner.invoke(app, ["crypto-data", "storage-verify", "--json"])
    refused = runner.invoke(app, ["crypto-data", "cache-clean", "--json"])
    cleaned = runner.invoke(app, ["crypto-data", "cache-clean", "--confirm", "--json"])

    assert inventory.exit_code == 0, inventory.output
    assert json.loads(inventory.stdout)["cache_bytes"] == 5
    assert verified.exit_code == 0, verified.output
    assert json.loads(verified.stdout)["manifest_count"] == 0
    assert refused.exit_code != 0
    assert "--confirm" in refused.output
    assert cleaned.exit_code == 0, cleaned.output
    assert json.loads(cleaned.stdout)["removed_bytes"] == 5
    assert protected.read_bytes() == b"protected"


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


def test_cross_provider_asset_master_freezes_verifies_and_binds_snapshot(
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
    monkeypatch.setattr(crypto_data_cmds, "_asset_master_root", lambda: tmp_path / "masters")
    monkeypatch.setattr(crypto_data_cmds, "_snapshot_root", lambda: tmp_path / "snapshots")
    monkeypatch.setenv("ALPHA_COINGECKO_API_KEY", "fixture-key")
    monkeypatch.setattr(
        crypto_data_cmds,
        "_now",
        lambda: datetime.fromisoformat("2026-08-15T00:00:00+00:00"),
    )
    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_coingecko_demo",
        lambda *_args: json.dumps(
            [
                {
                    "id": "usd-coin",
                    "symbol": "usdc",
                    "name": "USDC",
                    "platforms": {"ethereum": "0xUSDC"},
                }
            ]
        ).encode(),
    )
    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_geckoterminal_public",
        lambda url: json.dumps(
            {
                "data": [
                    {
                        "id": f"eth_0xPool{index}",
                        "type": "pool",
                        "attributes": {
                            "address": f"0xPool{index}",
                            "name": "USDC / WETH" if index == 0 else f"TOKEN{index} / WETH",
                            "pool_created_at": "2021-12-30T20:32:10Z",
                            "base_token_price_usd": "1",
                            "quote_token_price_usd": "2000",
                            "reserve_in_usd": "1000000",
                            "volume_usd": {"h24": "10000"},
                            "transactions": {"h24": {"buys": 8, "sells": 7}},
                        },
                        "relationships": {
                            "base_token": {
                                "data": {
                                    "id": "eth_0xUSDC" if index == 0 else f"eth_token{index}",
                                    "type": "token",
                                }
                            },
                            "quote_token": {"data": {"id": f"eth_weth{index}", "type": "token"}},
                            "dex": {"data": {"id": "uniswap_v3", "type": "dex"}},
                        },
                    }
                    for index in range(
                        (int(url.split("page=")[1].split("&", 1)[0]) - 1) * 20,
                        int(url.split("page=")[1].split("&", 1)[0]) * 20,
                    )
                ]
            }
        ).encode(),
    )
    coingecko = runner.invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "coingecko",
            "asset_metadata",
            "all",
            "--base",
            "BTC",
            "--quote",
            "USD",
            "--json",
        ],
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
    assert coingecko.exit_code == 0, coingecko.output
    assert gecko.exit_code == 0, gecko.output
    cg_manifest = json.loads(coingecko.stdout)["normalized_manifest_id"]
    gt_manifest = json.loads(gecko.stdout)["normalized_manifest_id"]
    created = runner.invoke(
        app,
        [
            "crypto-data",
            "asset-master-create",
            "--coingecko-manifest-id",
            cg_manifest,
            "--geckoterminal-manifest-id",
            gt_manifest,
            "--json",
        ],
    )
    assert created.exit_code == 0, created.output
    master = json.loads(created.stdout)
    assert master["contract_identity_count"] == 1
    assert master["ticker_join_allowed"] is False

    verified = runner.invoke(
        app,
        [
            "crypto-data",
            "asset-master-verify",
            master["asset_master_version"],
            "--json",
        ],
    )
    snapshot = runner.invoke(
        app,
        [
            "crypto-data",
            "snapshot-create",
            "--manifest-id",
            gt_manifest,
            "--asset-master-version",
            master["asset_master_version"],
            "--json",
        ],
    )
    assert verified.exit_code == 0, verified.output
    assert snapshot.exit_code == 0, snapshot.output
    snapshot_payload = json.loads(snapshot.stdout)
    assert snapshot_payload["asset_master_version"] == master["asset_master_version"]
    integrity_snapshot, integrity_eligible = crypto_data_cmds._integrity_verified_snapshot(
        snapshot_payload["snapshot_id"]
    )
    assert integrity_snapshot.snapshot_id == snapshot_payload["snapshot_id"]
    assert integrity_eligible is True
    listed_masters = runner.invoke(app, ["crypto-data", "asset-masters", "--json"])
    assert listed_masters.exit_code == 0, listed_masters.output
    assert json.loads(listed_masters.stdout)["count"] == 2
    contract = runner.invoke(
        app,
        [
            "crypto-data",
            "asset-contract",
            "ethereum",
            "0xusdc",
            "--asset-master-version",
            master["asset_master_version"],
            "--as-of",
            "2026-08-15T00:00:00Z",
            "--json",
        ],
    )
    assert contract.exit_code == 0, contract.output
    assert json.loads(contract.stdout)["coingecko_id"] == "usd-coin"

    master_path = tmp_path / "masters" / f"{master['asset_master_version']}.json"
    master_path.write_text(master_path.read_text().replace("usd-coin", "forged"))
    rejected = runner.invoke(
        app,
        ["crypto-data", "asset-master-verify", master["asset_master_version"]],
    )
    assert rejected.exit_code != 0
    assert "version" in rejected.output


def test_bybit_option_normalization_selects_exact_quote_asset() -> None:
    payload = json.dumps(
        {
            "retCode": 0,
            "time": 1_786_752_000_000,
            "result": {
                "category": "option",
                "list": [
                    {
                        "symbol": "BTC-25JUN27-150000-C-USDT",
                        "bid1Price": "1",
                        "ask1Price": "2",
                    }
                ],
            },
        }
    ).encode()

    usdt = crypto_data_cmds._option_quote_frame(
        payload,
        fetched_at_ms=1_786_752_000_000,
        base="BTC",
        quote="USDT",
    )
    assert usdt.height == 1
    with pytest.raises(DataError, match="requested base and quote"):
        crypto_data_cmds._option_quote_frame(
            payload,
            fetched_at_ms=1_786_752_000_000,
            base="BTC",
            quote="USD",
        )


def test_bybit_option_families_require_truthful_option_category() -> None:
    fetched_at = datetime.fromisoformat("2026-08-15T00:00:00+00:00")
    for family in ("option_instruments", "option_quotes", "historical_volatility"):
        plan = crypto_data_cmds._bybit_plan(
            family,
            "BTC-OPTIONS",
            base="BTC",
            quote="USDT",
            category="option",
            frequency="1h",
            start=None,
            end=None,
            fetched_at=fetched_at,
        )
        assert plan.dataset.market_type == "option"
        assert plan.params["category"] == "option"
        with pytest.raises(DataError, match="requires the option category"):
            crypto_data_cmds._bybit_plan(
                family,
                "BTC-OPTIONS",
                base="BTC",
                quote="USDT",
                category="linear",
                frequency="1h",
                start=None,
                end=None,
                fetched_at=fetched_at,
            )


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

    registered = runner.invoke(
        app,
        [
            "research",
            "data",
            "register-crypto",
            snapshot["snapshot_id"],
            "--symbol",
            "BTC",
            "--json",
        ],
    )
    assert registered.exit_code == 0, registered.output
    research_ref = json.loads(registered.stdout)
    assert research_ref["dataset_kind"] == "snapshot"
    assert research_ref["instrument"] == "BTC"
    assert research_ref["provider"] == "crypto-data-house"
    assert research_ref["research_only"] is True
    assert research_ref["origin"]["snapshot_id"] == snapshot["snapshot_id"]
    assert len(research_ref["origin"]["manifest_sha256"]) == 64
    assert research_ref["origin"]["snapshot_schema"] == "CryptoSnapshotV1"

    coverage = runner.invoke(app, ["crypto-data", "coverage", "--json"])
    assert coverage.exit_code == 0, coverage.output
    coverage_payload = json.loads(coverage.stdout)
    assert coverage_payload["items"][0]["family"] == "funding"
    assert coverage_payload["items"][0]["state"] == "qualified"
    assert coverage_payload["items"][0]["fetched_at"] == "2026-08-15T00:00:00+00:00"
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

    raw_manifest = store.verify_manifest(receipt["raw_manifest_id"])
    (store.bulk_root / str(raw_manifest["artifact_key"])).write_bytes(b"tampered")
    rejected = runner.invoke(
        app,
        [
            "research",
            "data",
            "register-crypto",
            snapshot["snapshot_id"],
            "--symbol",
            "BTC",
            "--json",
        ],
    )
    assert rejected.exit_code != 0
    assert "integrity" in rejected.output


def test_bybit_missing_stage_three_families_acquire_and_qualify_offline(
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
    calls: list[tuple[str, dict[str, str | int]]] = []

    def fetch(endpoint: str, params: dict[str, str | int]) -> bytes:
        result: dict[str, object]
        calls.append((endpoint, dict(params)))
        if endpoint == "instruments":
            if params["category"] == "option":
                result = {
                    "category": "option",
                    "list": [
                        {
                            "symbol": "BTC-28AUG26-100000-C-USDT",
                            "optionsType": "Call",
                            "status": "Trading",
                            "baseCoin": "BTC",
                            "quoteCoin": "USDT",
                            "settleCoin": "USDT",
                            "launchTime": "1780000000000",
                            "deliveryTime": "1787875200000",
                            "priceFilter": {"tickSize": "0.1"},
                            "lotSizeFilter": {"qtyStep": "0.01"},
                        }
                    ],
                    "nextPageCursor": "",
                }
            else:
                result = {
                    "category": "linear",
                    "list": [
                        {
                            "symbol": "BTCUSDT",
                            "contractType": "LinearPerpetual",
                            "status": "Trading",
                            "baseCoin": "BTC",
                            "quoteCoin": "USDT",
                            "settleCoin": "USDT",
                            "launchTime": "1585526400000",
                            "deliveryTime": "0",
                            "fundingInterval": 480,
                            "priceFilter": {"tickSize": "0.1"},
                            "lotSizeFilter": {"qtyStep": "0.001"},
                        }
                    ],
                    "nextPageCursor": "",
                }
        elif endpoint == "trade_kline":
            result = {
                "category": "linear",
                "symbol": "BTCUSDT",
                "list": [["1786748400000", "10", "12", "9", "11", "4", "44"]],
            }
        elif endpoint == "recent_trades":
            result = {
                "category": "linear",
                "list": [
                    {
                        "execId": "trade-1",
                        "symbol": "BTCUSDT",
                        "price": "11",
                        "size": "0.5",
                        "side": "Buy",
                        "time": "1786751999000",
                        "isBlockTrade": False,
                        "isRPITrade": False,
                    }
                ],
            }
        elif endpoint == "orderbook":
            result = {
                "s": "BTCUSDT",
                "b": [["10", "2"]],
                "a": [["11", "3"]],
                "ts": 1_786_751_999_000,
                "u": 7,
                "seq": 8,
                "cts": 1_786_751_998_000,
            }
        elif endpoint == "long_short_ratio":
            result = {
                "category": "linear",
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "buyRatio": "0.55",
                        "sellRatio": "0.45",
                        "timestamp": "1786748400000",
                    }
                ],
                "nextPageCursor": "",
            }
        else:  # pragma: no cover - assertion below identifies unexpected routing
            raise AssertionError(endpoint)
        return json.dumps({"retCode": 0, "time": 1_786_752_000_000, "result": result}).encode()

    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(crypto_data_cmds, "fetch_bybit_public", fetch)
    monkeypatch.setattr(
        crypto_data_cmds,
        "_now",
        lambda: datetime.fromisoformat("2026-08-15T00:00:00+00:00"),
    )
    case_id = "f03802b8-df35-4f19-a90c-0b3437aa587d"
    case = {
        "project_id": case_id,
        "active_contract_id": "contract-1",
        "phase": "exploration",
        "execution_state": "approved",
        "source_pack_id": "pack-1",
    }
    revision = research_case_revision(case)
    monkeypatch.setattr(
        crypto_data_cmds,
        "_control_store",
        lambda: type("CaseStore", (), {"research_case_summary": lambda _self, _id: case})(),
    )

    families = (
        ("instrument_catalog", "linear"),
        ("derivative_bars", "BTCUSDT"),
        ("long_short_ratio", "BTCUSDT"),
        ("derivative_trades", "BTCUSDT"),
        ("derivative_book_snapshots", "BTCUSDT"),
    )
    for family, instrument in families:
        args = [
            "crypto-data",
            "acquire",
            "bybit",
            family,
            instrument,
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--category",
            "linear",
            "--frequency",
            "1h",
        ]
        if family in {"derivative_trades", "derivative_book_snapshots"}:
            args.extend(
                (
                    "--case-id",
                    case_id,
                    "--expected-case-revision",
                    revision,
                    "--reason",
                    "Capture the bounded BTC event cross-section.",
                )
            )
        args.append("--json")
        result = runner.invoke(
            app,
            args,
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["state"] == "qualified"

    assert [endpoint for endpoint, _ in calls] == [
        "instruments",
        "trade_kline",
        "long_short_ratio",
        "recent_trades",
        "orderbook",
    ]
    assert len(store.inventory()) == 10

    option_catalog = runner.invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "bybit",
            "instrument_catalog",
            "option",
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--category",
            "option",
            "--json",
        ],
    )
    assert option_catalog.exit_code == 0, option_catalog.output
    assert json.loads(option_catalog.stdout)["state"] == "qualified"
    assert calls[-1][0] == "instruments"
    assert calls[-1][1]["category"] == "option"
    assert len(store.inventory()) == 12


def test_point_in_time_acquisition_uses_network_completion_as_knowledge_time(
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
            "time": 1_786_752_001_000,
            "result": {
                "s": "BTCUSDT",
                "b": [["10", "2"]],
                "a": [["11", "3"]],
                "ts": 1_786_752_001_000,
                "u": 7,
                "seq": 8,
                "cts": 1_786_752_000_900,
            },
        }
    ).encode()
    clocks = iter(
        (
            datetime.fromisoformat("2026-08-15T00:00:00+00:00"),
            datetime.fromisoformat("2026-08-15T00:00:02+00:00"),
        )
    )
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(crypto_data_cmds, "fetch_bybit_public", lambda *_args, **_kwargs: payload)
    monkeypatch.setattr(crypto_data_cmds, "_now", lambda: next(clocks))
    case_id = "f03802b8-df35-4f19-a90c-0b3437aa587d"
    case = {
        "project_id": case_id,
        "active_contract_id": "contract-1",
        "phase": "exploration",
        "execution_state": "approved",
        "source_pack_id": "pack-1",
    }
    revision = research_case_revision(case)
    monkeypatch.setattr(
        crypto_data_cmds,
        "_control_store",
        lambda: type("CaseStore", (), {"research_case_summary": lambda _self, _id: case})(),
    )

    result = runner.invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "bybit",
            "derivative_book_snapshots",
            "BTCUSDT",
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--category",
            "linear",
            "--case-id",
            case_id,
            "--expected-case-revision",
            revision,
            "--reason",
            "Capture the bounded BTC event book.",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["state"] == "qualified"


def test_derivative_event_capture_fails_before_network_without_case_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fetch(*_args: object, **_kwargs: object) -> bytes:
        nonlocal called
        called = True
        return b"{}"

    monkeypatch.setattr(crypto_data_cmds, "fetch_bybit_public", fetch)
    result = runner.invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "bybit",
            "derivative_trades",
            "BTCUSDT",
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--category",
            "linear",
            "--json",
        ],
    )

    assert result.exit_code != 0
    assert "--case-id" in result.output
    assert called is False


def test_bybit_spot_bars_are_diagnostic_only_and_cannot_enter_a_snapshot(
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
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(
        crypto_data_cmds,
        "_now",
        lambda: datetime.fromisoformat("2026-08-15T00:00:00+00:00"),
    )
    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_bybit_public",
        lambda *_args, **_kwargs: json.dumps(
            {
                "retCode": 0,
                "time": 1_786_752_000_000,
                "result": {
                    "category": "spot",
                    "symbol": "BTCUSDT",
                    "list": [["1786665600000", "10", "12", "9", "11", "4", "44"]],
                },
            }
        ).encode(),
    )

    acquired = runner.invoke(
        app,
        [
            "crypto-data",
            "acquire",
            "bybit",
            "comparison_bars",
            "BTCUSDT",
            "--base",
            "BTC",
            "--quote",
            "USDT",
            "--category",
            "spot",
            "--frequency",
            "1d",
            "--start",
            "2026-08-14T00:00:00Z",
            "--end",
            "2026-08-14T23:59:59Z",
            "--json",
        ],
    )

    assert acquired.exit_code == 0, acquired.output
    receipt = json.loads(acquired.stdout)
    manifest = _manifest(store.verify_manifest(receipt["normalized_manifest_id"]))
    assert manifest["dataset"]["provider"] == "bybit"
    assert manifest["dataset"]["family"] == "comparison_bars"
    rejected = runner.invoke(
        app,
        [
            "crypto-data",
            "snapshot-create",
            "--manifest-id",
            receipt["normalized_manifest_id"],
            "--json",
        ],
    )
    assert rejected.exit_code != 0
    assert "wrong family authority" in rejected.output


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
    monkeypatch.setattr(crypto_data_cmds, "fetch_coingecko_demo", lambda *_args: coingecko_payload)

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
    assert len(store.inventory()) == 17
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
        rows = [market_row(index) for index in range(250)] if page == 1 else [market_row(250)]
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
    assert coingecko_manifest["quality"]["row_count"] == 251
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


def test_coverage_profile_create_pages_and_rejects_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    as_of = datetime.fromisoformat("2026-08-15T00:00:00+00:00")
    empty_catalog = pl.DataFrame(
        schema={
            "status": pl.String,
            "contract_type": pl.String,
            "symbol": pl.String,
            "base_coin": pl.String,
            "quote_coin": pl.String,
            "launch_time": pl.Datetime(time_zone="UTC"),
            "delivery_time": pl.Datetime(time_zone="UTC"),
        }
    )
    linear = pl.DataFrame(
        {
            "status": ["Trading"],
            "contract_type": ["LinearPerpetual"],
            "symbol": ["BTCUSDT"],
            "base_coin": ["BTC"],
            "quote_coin": ["USDT"],
            "launch_time": [datetime.fromisoformat("2020-01-01T00:00:00+00:00")],
            "delivery_time": [None],
        }
    )
    options = pl.DataFrame(
        {
            "status": ["Trading"],
            "symbol": ["BTC-30AUG26-100000-C-USDT"],
            "base_coin": ["BTC"],
            "quote_coin": ["USDT"],
            "launch_time": [datetime.fromisoformat("2026-01-01T00:00:00+00:00")],
            "delivery_time": [datetime.fromisoformat("2026-08-30T00:00:00+00:00")],
        }
    )
    option_quotes = pl.DataFrame({"open_interest": [10.0, 20.0]})
    coinmetrics_catalog = pl.DataFrame(
        {
            "asset": ["btc", "eth"],
            "metric": ["AdrActCnt", "TxCnt"],
            "family": ["addresses", "transactions"],
            "frequency": ["1d", "1d"],
            "fetched_at": [as_of - timedelta(minutes=1)] * 2,
        }
    )
    binance_symbols: dict[str, str] = {
        "spot": "BTCUSDT",
        "linear": "ETHUSDT",
        "inverse": "BTCUSD_PERP",
    }
    binance_memberships = {
        category: pl.DataFrame(
            {
                "fetched_at": [as_of - timedelta(minutes=1)],
                "category": [category],
                "symbol": [binance_symbols[category]],
                "status": ["TRADING"],
                "contract_type": ["SPOT" if category == "spot" else "PERPETUAL"],
                "base_asset": ["ETH" if category == "linear" else "BTC"],
                "quote_asset": ["USD" if category == "inverse" else "USDT"],
                "onboard_time": [None],
                "delivery_time": [None],
                "contract_size": [100.0 if category == "inverse" else None],
            }
        )
        for category in ("spot", "linear", "inverse")
    }
    sources: dict[
        tuple[str, str, str | None, str | None, str | None],
        tuple[str, object, pl.DataFrame],
    ] = {
        ("bybit", "instrument_catalog", "linear", None, None): ("a" * 64, None, linear),
        ("bybit", "instrument_catalog", "inverse", None, None): (
            "b" * 64,
            None,
            empty_catalog,
        ),
        ("bybit", "instrument_catalog", "option", None, None): ("c" * 64, None, options),
        ("bybit", "option_quotes", None, "BTC", "USDT"): (
            "d" * 64,
            None,
            option_quotes,
        ),
        ("coinmetrics", "onchain_catalog", "community", None, None): (
            "2" * 64,
            None,
            coinmetrics_catalog,
        ),
        **{
            ("binance", "market_membership", category, None, None): (
                digest * 64,
                None,
                binance_memberships[category],
            )
            for category, digest in (("spot", "e"), ("linear", "f"), ("inverse", "1"))
        },
    }

    class ProfileStore:
        def verify_ready(self, *, required_bytes: int) -> None:
            assert required_bytes == 0

        def inventory(self) -> tuple[dict[str, object], ...]:
            return ()

    def latest_source(
        _store: object,
        *,
        provider: str,
        family: str,
        as_of: datetime,
        instrument: str | None = None,
        base_asset: str | None = None,
        quote_asset: str | None = None,
    ) -> tuple[str, object, pl.DataFrame]:
        assert as_of == datetime.fromisoformat("2026-08-15T00:00:00+00:00")
        return sources[(provider, family, instrument, base_asset, quote_asset)]

    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", ProfileStore)
    monkeypatch.setattr(crypto_data_cmds, "_latest_profile_source", latest_source)
    monkeypatch.setattr(crypto_data_cmds, "_coverage_profile_root", lambda: tmp_path / "profiles")
    monkeypatch.setattr(crypto_data_cmds, "_now", lambda: as_of)
    created = runner.invoke(
        app,
        [
            "crypto-data",
            "profile-create",
            "--as-of",
            as_of.isoformat(),
            "--json",
        ],
    )
    assert created.exit_code == 0, created.output
    created_payload = json.loads(created.stdout)
    assert created_payload["task_count"] == 31
    assert created_payload["counts_by_provider"]["binance"] == 6
    assert len(created_payload["binance_hourly_missing_scopes"]) == 3
    assert created_payload["counts_by_cadence"]["five_minute"] == 1
    assert created_payload["execution_authority"] is False
    future = runner.invoke(
        app,
        [
            "crypto-data",
            "profile-create",
            "--as-of",
            "2100-01-01T00:00:00+00:00",
            "--json",
        ],
    )
    assert future.exit_code != 0
    assert "cannot be in the future" in future.output

    profile_id = created_payload["profile_id"]
    shown = runner.invoke(
        app,
        [
            "crypto-data",
            "profile-show",
            profile_id,
            "--offset",
            "0",
            "--limit",
            "2",
            "--json",
        ],
    )
    assert shown.exit_code == 0, shown.output
    shown_payload = json.loads(shown.stdout)
    assert len(shown_payload["items"]) == 2
    assert shown_payload["has_more"] is True
    assert shown_payload["next_offset"] == 2
    listed_profiles = runner.invoke(app, ["crypto-data", "profiles", "--json"])
    assert listed_profiles.exit_code == 0, listed_profiles.output
    assert json.loads(listed_profiles.stdout)["count"] == 1
    filtered = runner.invoke(
        app,
        [
            "crypto-data",
            "profile-show",
            profile_id,
            "--provider",
            "binance",
            "--family",
            "market_bars",
            "--frequency",
            "1d",
            "--limit",
            "100",
            "--json",
        ],
    )
    assert filtered.exit_code == 0, filtered.output
    filtered_payload = json.loads(filtered.stdout)
    assert filtered_payload["filtered_count"] == 3
    assert {item["instrument"] for item in filtered_payload["items"]} == {
        "BTCUSDT",
        "ETHUSDT",
        "BTCUSD_PERP",
    }

    path = tmp_path / "profiles" / f"{profile_id}.json"
    path.write_text(path.read_text().replace('"frequency": "1h"', '"frequency": "4h"', 1))
    rejected = runner.invoke(app, ["crypto-data", "profile-show", profile_id, "--json"])
    assert rejected.exit_code != 0
    assert "identity" in rejected.output


def test_liquidity_freeze_requires_complete_exact_daily_scope(
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
    membership_payload = json.dumps(
        {
            "symbols": [
                {
                    "symbol": symbol,
                    "status": "TRADING",
                    "baseAsset": base,
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": True,
                }
                for symbol, base in (("AAAUSDT", "AAA"), ("BBBUSDT", "BBB"))
            ]
        }
    ).encode()
    membership = ingest_provider_payload(
        store,
        dataset=CryptoDatasetIdentityV1(
            provider="binance",
            venue="binance",
            market_type="spot",
            family="market_membership",
            instrument="spot",
            base_asset=None,
            quote_asset=None,
            frequency="catalog_snapshot",
            units="provider_native_market_identity",
            timestamp_convention="provider_observation_utc",
        ),
        payload=membership_payload,
        request=(),
        fetched_at=fetched_at,
        provider_schema="fixture",
        parser_version="fixture-v1",
        logical_name="membership.json",
        parser=lambda payload: parse_binance_exchange_info(
            payload, category="spot", fetched_at=fetched_at
        ),
        observed_column="fetched_at",
        key_columns=("category", "symbol"),
        availability_column="fetched_at",
    )
    bar_manifest_ids: list[str] = []
    for index, (symbol, base, quote_volume) in enumerate(
        (("AAAUSDT", "AAA", 10.0), ("BBBUSDT", "BBB", 20.0))
    ):
        payload = json.dumps(
            [
                [
                    1_786_665_600_000,
                    "1",
                    "2",
                    "0.5",
                    "1.5",
                    str(quote_volume),
                    1_786_751_999_999,
                    str(quote_volume),
                    10 + index,
                    "1",
                    "1",
                ]
            ]
        ).encode()
        result = ingest_provider_payload(
            store,
            dataset=CryptoDatasetIdentityV1(
                provider="binance",
                venue="binance",
                market_type="spot",
                family="market_bars",
                instrument=symbol,
                base_asset=base,
                quote_asset="USDT",
                frequency="1d",
                units="provider_native_ohlcv",
                timestamp_convention="interval_start_utc",
            ),
            payload=payload,
            request=(("symbol", symbol),),
            fetched_at=fetched_at,
            provider_schema="fixture",
            parser_version="fixture-v1",
            logical_name="bars.json",
            parser=lambda value: parse_binance_klines(value, source="rest_json"),
            observed_column="open_time",
            key_columns=("open_time",),
            period_start_timestamps=True,
        )
        bar_manifest_ids.append(str(result.normalized_manifest["manifest_id"]))
    tasks = (
        CryptoCoverageTaskV1(
            provider="binance",
            family="market_membership",
            instrument="spot",
            base_asset=None,
            quote_asset=None,
            category="spot",
            frequency="catalog_snapshot",
            cadence="daily",
        ),
        *tuple(
            CryptoCoverageTaskV1(
                provider="binance",
                family="market_bars",
                instrument=symbol,
                base_asset=base,
                quote_asset="USDT",
                category="spot",
                frequency="1d",
                cadence="daily",
            )
            for symbol, base in (("AAAUSDT", "AAA"), ("BBBUSDT", "BBB"))
        ),
    )
    profile = CryptoCoverageProfileV1.create(
        as_of=fetched_at,
        source_manifest_ids=(str(membership.normalized_manifest["manifest_id"]),),
        tasks=tasks,
    )
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(crypto_data_cmds, "_coverage_profile_root", lambda: tmp_path / "profiles")
    crypto_data_cmds._write_coverage_profile(profile)

    frozen = runner.invoke(
        app,
        [
            "crypto-data",
            "liquidity-freeze",
            profile.profile_id,
            "--category",
            "spot",
            "--quote-asset",
            "USDT",
            "--session",
            "2026-08-14",
            "--limit",
            "1",
            "--json",
        ],
    )
    assert frozen.exit_code == 0, frozen.output
    payload = json.loads(frozen.stdout)
    assert payload["universe_count"] == 2
    assert payload["selected_count"] == 1
    derived = _manifest(store.verify_manifest(payload["manifest_id"]))
    assert derived["metadata"]["method_version"] == "binance-prior-day-liquidity-v1"
    assert pl.read_parquet(store.bulk_root / derived["artifact_key"])["symbol"].to_list() == [
        "BBBUSDT"
    ]

    case_id = "f03802b8-df35-4f19-a90c-0b3437aa587d"
    case = {
        "project_id": case_id,
        "active_contract_id": "contract-1",
        "phase": "exploration",
        "execution_state": "approved",
        "source_pack_id": "pack-1",
    }
    revision = research_case_revision(case)
    monkeypatch.setattr(
        crypto_data_cmds,
        "_control_store",
        lambda: type("CaseStore", (), {"research_case_summary": lambda _self, _id: case})(),
    )
    monkeypatch.setattr(
        crypto_data_cmds,
        "_now",
        lambda: datetime.fromisoformat("2026-08-15T00:01:00+00:00"),
    )
    selected = runner.invoke(
        app,
        [
            "crypto-data",
            "profile-select-one-minute",
            profile.profile_id,
            "--case-id",
            case_id,
            "--expected-case-revision",
            revision,
            "--market",
            "spot:AAAUSDT",
            "--reason",
            "Inspect a bounded one-minute event window.",
            "--json",
        ],
    )
    assert selected.exit_code == 0, selected.output
    selection = json.loads(selected.stdout)
    assert selection["selected_count"] == 1
    selected_profile = crypto_data_cmds._read_coverage_profile(selection["profile_id"])
    assert any(
        task.instrument == "AAAUSDT" and task.frequency == "1m" for task in selected_profile.tasks
    )
    selection_manifest = _manifest(store.verify_manifest(selection["selection_manifest_id"]))
    assert selection_manifest["metadata"]["project_id"] == case_id
    assert selection_manifest["metadata"]["execution_authority"] is False

    stale = runner.invoke(
        app,
        [
            "crypto-data",
            "profile-select-one-minute",
            profile.profile_id,
            "--case-id",
            case_id,
            "--expected-case-revision",
            "stale",
            "--market",
            "spot:AAAUSDT",
            "--reason",
            "Inspect a bounded one-minute event window.",
            "--json",
        ],
    )
    assert stale.exit_code != 0
    assert "changed before" in stale.output
    with pytest.raises(DataError, match="1 to 50"):
        crypto_data_cmds._select_one_minute_profile(
            profile,
            case_id=case_id,
            expected_case_revision=revision,
            markets=tuple(f"spot:MARKET{index}" for index in range(51)),
            reason="Bounded selection.",
        )

    (store.manifest_root / f"{payload['manifest_id']}.json").unlink()
    (store.manifest_root / f"{bar_manifest_ids[1]}.json").unlink()
    incomplete = runner.invoke(
        app,
        [
            "crypto-data",
            "liquidity-freeze",
            profile.profile_id,
            "--category",
            "spot",
            "--quote-asset",
            "USDT",
            "--session",
            "2026-08-14",
            "--json",
        ],
    )
    assert incomplete.exit_code != 0
    assert "incomplete for 1 of 2" in incomplete.output


def test_feature_create_persists_and_reverifies_exact_lineage(
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
    now = datetime.fromisoformat("2026-08-15T00:00:00+00:00")
    source = ingest_provider_payload(
        store,
        dataset=CryptoDatasetIdentityV1(
            provider="bybit",
            venue="bybit",
            market_type="linear",
            family="funding",
            instrument="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            frequency="funding_interval",
            units="provider_native_rate",
            timestamp_convention="provider_event_utc",
        ),
        payload=b"fixture-funding",
        request=(("symbol", "BTCUSDT"),),
        fetched_at=now,
        provider_schema="fixture",
        parser_version="fixture-v1",
        logical_name="funding.json",
        parser=lambda _payload: pl.DataFrame(
            {
                "timestamp": [now - timedelta(hours=2), now - timedelta(hours=1)],
                "funding_rate": [0.001, -0.0005],
            }
        ),
        observed_column="timestamp",
        key_columns=("timestamp",),
    )
    source_id = str(source.normalized_manifest["manifest_id"])
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(crypto_data_cmds, "_now", lambda: now)

    created = runner.invoke(
        app,
        [
            "crypto-data",
            "feature-create",
            "funding",
            "--input",
            f"funding={source_id}",
            "--json",
        ],
    )
    assert created.exit_code == 0, created.output
    payload = json.loads(created.stdout)
    assert payload["state"] == "frozen"
    assert payload["research_authority"] is False
    assert payload["execution_authority"] is False
    manifest = _manifest(store.verify_manifest(payload["manifest_id"]))
    assert manifest["derived_kind"] == "crypto-feature"
    assert manifest["input_manifest_ids"] == [source_id]
    assert manifest["metadata"]["feature"]["artifact_sha256"] == manifest["artifact_sha256"]

    shown = runner.invoke(
        app,
        ["crypto-data", "feature-show", payload["manifest_id"], "--json"],
    )
    assert shown.exit_code == 0, shown.output
    assert json.loads(shown.stdout)["state"] == "verified"
    listed = runner.invoke(app, ["crypto-data", "features", "--json"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.stdout)["count"] == 1

    duplicated = runner.invoke(
        app,
        [
            "crypto-data",
            "feature-create",
            "funding",
            "--input",
            f"funding={source_id}",
            "--input",
            f"funding={source_id}",
        ],
    )
    assert duplicated.exit_code == 2
    assert "requires inputs: funding" in duplicated.output


def test_coverage_batch_checkpoints_and_resumes_only_the_unfinished_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_at = datetime.fromisoformat("2026-08-15T00:00:00+00:00")
    families: tuple[CryptoFamily, ...] = ("asset_metadata", "market_reference")
    tasks = tuple(
        CryptoCoverageTaskV1(
            provider="coingecko",
            family=family,
            instrument="all",
            base_asset=None,
            quote_asset="USD" if family == "market_reference" else None,
            category=None,
            frequency="point_in_time_reference"
            if family == "market_reference"
            else "catalog_snapshot",
            cadence="daily",
        )
        for family in families
    )
    profile = CryptoCoverageProfileV1.create(
        as_of=run_at,
        source_manifest_ids=("a" * 64,),
        tasks=tasks,
    )
    monkeypatch.setattr(crypto_data_cmds, "_coverage_profile_root", lambda: tmp_path / "profiles")
    monkeypatch.setattr(crypto_data_cmds, "_coverage_batch_root", lambda: tmp_path / "batches")
    crypto_data_cmds._write_coverage_profile(profile)

    class BatchStore:
        def verify_manifest(self, manifest_id: str) -> dict[str, object]:
            assert manifest_id == "a" * 64
            return {"manifest_id": manifest_id}

    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", BatchStore)
    monkeypatch.setattr(crypto_data_cmds, "_now", lambda: run_at)
    calls: list[str] = []
    fail_second = True

    def acquire_result(
        _provider: str, family: str, *_args: object, **_kwargs: object
    ) -> dict[str, object]:
        nonlocal fail_second
        calls.append(family)
        if family == "market_reference" and fail_second:
            raise DataError("fixture provider outage")
        digest = "b" * 64 if family == "asset_metadata" else "c" * 64
        return {
            "family": family,
            "normalized_manifest_id": digest,
            "execution_authority": False,
        }

    monkeypatch.setattr(crypto_data_cmds, "_acquire_result", acquire_result)
    failed = runner.invoke(
        app,
        [
            "crypto-data",
            "profile-run",
            profile.profile_id,
            "--cadence",
            "daily",
            "--limit",
            "2",
            "--confirm",
            "--json",
        ],
    )
    assert failed.exit_code != 0
    assert "stopped on" in failed.output
    batches = tuple((tmp_path / "batches").iterdir())
    assert len(batches) == 1
    batch_id = batches[0].name
    checkpoint = json.loads((batches[0] / "checkpoint.json").read_text())
    assert checkpoint["state"] == "failed"
    assert checkpoint["next_index"] == 1
    assert len(checkpoint["results"]) == 1
    assert calls == ["asset_metadata", "market_reference"]

    failed_list = runner.invoke(app, ["crypto-data", "profile-batches", "--json"])
    assert failed_list.exit_code == 0, failed_list.output
    failed_item = json.loads(failed_list.stdout)["items"][0]
    assert failed_item["error"] == "fixture provider outage"
    assert failed_item["recovery_action"] == "Resolve the provider or data blocker, then resume."

    fail_second = False
    resumed = runner.invoke(
        app,
        ["crypto-data", "profile-resume", batch_id, "--confirm", "--json"],
    )
    assert resumed.exit_code == 0, resumed.output
    payload = json.loads(resumed.stdout)
    assert payload["state"] == "completed"
    assert payload["completed_count"] == 2
    assert calls == ["asset_metadata", "market_reference", "market_reference"]

    listed = runner.invoke(app, ["crypto-data", "profile-batches", "--json"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.stdout)["items"][0]["state"] == "completed"

    checkpoint_path = batches[0] / "checkpoint.json"
    checkpoint_path.write_text(
        checkpoint_path.read_text().replace('"next_index": 2', '"next_index": 1')
    )
    rejected = runner.invoke(
        app,
        ["crypto-data", "profile-resume", batch_id, "--confirm", "--json"],
    )
    assert rejected.exit_code != 0
    assert "integrity" in rejected.output


def test_binance_daily_profile_task_uses_only_previous_complete_utc_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = CryptoCoverageTaskV1(
        provider="binance",
        family="market_bars",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        category="spot",
        frequency="1d",
        cadence="daily",
    )
    captured: dict[str, object] = {}

    def acquire_result(*args: object, **kwargs: object) -> dict[str, object]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"normalized_manifest_id": "a" * 64}

    monkeypatch.setattr(crypto_data_cmds, "_acquire_result", acquire_result)
    crypto_data_cmds._run_profile_task(
        task,
        run_at=datetime.fromisoformat("2026-08-15T13:45:00+00:00"),
    )

    assert captured["kwargs"]["start"] == "2026-08-14T00:00:00+00:00"  # type: ignore[index]
    assert captured["kwargs"]["end"] == "2026-08-14T23:59:59.999000+00:00"  # type: ignore[index]

    hourly = CryptoCoverageTaskV1(
        provider="binance",
        family="market_bars",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        category="spot",
        frequency="1h",
        cadence="hourly",
    )
    crypto_data_cmds._run_profile_task(
        hourly,
        run_at=datetime.fromisoformat("2026-08-15T13:45:00+00:00"),
    )
    assert captured["kwargs"]["start"] == "2026-08-15T12:00:00+00:00"  # type: ignore[index]
    assert captured["kwargs"]["end"] == "2026-08-15T12:59:59.999000+00:00"  # type: ignore[index]


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
    start: str | None, end: str | None, message: str
) -> None:
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

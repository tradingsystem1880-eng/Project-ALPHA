from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.control_store import research_case_revision
from alpha_cli.main import app
from alpha_core import DataError
from alpha_data.crypto.contracts import FAMILY_AUTHORITIES
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


def test_bybit_price_bars_declare_interval_start_and_completion_rule() -> None:
    plan = crypto_data_cmds._bybit_plan(
        "mark_bars",
        "BTCUSDT",
        base="BTC",
        quote="USDT",
        category="linear",
        frequency="1h",
        start=None,
        end=None,
        fetched_at=datetime.fromisoformat("2026-08-15T00:00:00+00:00"),
    )

    assert plan.dataset.timestamp_convention == "interval_start_utc"
    assert plan.expected_cadence_seconds == 3_600
    assert plan.period_start_timestamps is True


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

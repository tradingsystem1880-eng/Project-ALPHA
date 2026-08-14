from __future__ import annotations

import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.main import app
from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoFamily
from alpha_data.crypto.ingestion import ingest_provider_payload
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

runner = CliRunner()


def test_crypto_storage_projection_covers_ready_and_exact_blocker_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = type(
        "Settings",
        (),
        {
            "bulk_data_dir": tmp_path / "Expansion" / "crypto-data",
            "data_dir": tmp_path / "control",
            "bulk_volume_uuid": "TEST-UUID",
        },
    )()
    monkeypatch.setattr("alpha_cli.crypto_data_cmds.AlphaSettings", lambda: settings)

    class ReadyStore:
        reserve_fraction = 0.15
        minimum_free_bytes = 100

        def __init__(self, **_kwargs: object) -> None:
            pass

        def verify_ready(self, *, required_bytes: int) -> Capacity:
            assert required_bytes == 0
            return Capacity(total_bytes=1_000, free_bytes=800)

        def inventory(self) -> tuple[dict[str, object], ...]:
            return ({"artifact_kind": "normalized", "artifact_bytes": 12},)

        def cache_size(self) -> int:
            return 7

    monkeypatch.setattr("alpha_cli.crypto_data_cmds.CryptoBulkStore", ReadyStore)
    ready = runner.invoke(app, ["crypto-data", "storage", "--json"])
    assert ready.exit_code == 0, ready.output
    assert json.loads(ready.stdout)["state"] == "ready"

    class BlockedStore(ReadyStore):
        def verify_ready(self, *, required_bytes: int) -> Capacity:
            raise DataError("crypto bulk volume UUID does not match")

    monkeypatch.setattr("alpha_cli.crypto_data_cmds.CryptoBulkStore", BlockedStore)
    blocked = runner.invoke(app, ["crypto-data", "storage", "--json"])
    assert blocked.exit_code == 0, blocked.output
    assert json.loads(blocked.stdout)["blocker"] == "bulk_volume_uuid_mismatch"
    assert {
        crypto_data_cmds._storage_blocker(message)
        for message in (
            "volume not mounted",
            "bad UUID",
            "reserve breached",
            "not writable",
            "other",
        )
    } == {
        "bulk_volume_not_mounted",
        "bulk_volume_uuid_mismatch",
        "bulk_storage_reserve_blocked",
        "bulk_volume_not_writable",
        "bulk_storage_verification_failed",
    }

    invalid_frequency = runner.invoke(
        app, ["crypto-data", "estimate", "market_bars", "--frequency", "2h"]
    )
    assert invalid_frequency.exit_code != 0
    one_minute = runner.invoke(
        app,
        [
            "crypto-data",
            "estimate",
            "market_bars",
            "--frequency",
            "1m",
            "--instruments",
            "51",
        ],
    )
    assert one_minute.exit_code != 0


def test_geckoterminal_pool_history_and_transactions_build_exact_offline_plans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ohlcv = json.dumps(
        {
            "data": {"attributes": {"ohlcv_list": [[1_786_665_600, 1, 2, 0.5, 1.5, 10]]}},
            "meta": {
                "base": {"address": "0xBase"},
                "quote": {"address": "0xQuote"},
            },
        }
    ).encode()
    trades = json.dumps(
        {
            "data": [
                {
                    "id": "eth_trade_1",
                    "type": "trade",
                    "attributes": {
                        "block_number": 1,
                        "tx_hash": "0xabc",
                        "from_token_amount": "1",
                        "to_token_amount": "2",
                        "price_from_in_usd": "2",
                        "price_to_in_usd": "1",
                        "block_timestamp": "2026-08-14T00:00:00Z",
                        "kind": "buy",
                        "volume_in_usd": "2",
                        "from_token_address": "0xBase",
                        "to_token_address": "0xQuote",
                    },
                }
            ]
        }
    ).encode()
    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_geckoterminal_public",
        lambda url: trades if url.endswith("/trades") else ohlcv,
    )
    fetched_at = datetime.fromisoformat("2026-08-15T00:00:00+00:00")
    for family, frequency, expected_endpoint in (
        ("dex_ohlcv", "1h", "ohlcv"),
        ("dex_transactions", "transaction_events", "trades"),
    ):
        fetched = crypto_data_cmds._fetch_non_bybit(
            "geckoterminal",
            cast(CryptoFamily, family),
            "0xPool",
            tmp_path,
            base="TOKEN",
            quote="USD",
            category="spot",
            frequency=frequency,
            period=None,
            network="eth",
            pool_address="0xPool",
            metrics=None,
            start=None,
            end=None,
            fetched_at=fetched_at,
        )
        assert isinstance(fetched, crypto_data_cmds._FetchedAcquisition)
        assert fetched.plan.endpoint == expected_endpoint
        assert fetched.plan.parser(fetched.payload).height == 1

    with pytest.raises(DataError, match="pool-address"):
        crypto_data_cmds._fetch_non_bybit(
            "geckoterminal",
            "dex_ohlcv",
            "0xPool",
            tmp_path,
            base="TOKEN",
            quote="USD",
            category="spot",
            frequency="1h",
            period=None,
            network="eth",
            pool_address=None,
            metrics=None,
            start=None,
            end=None,
            fetched_at=fetched_at,
        )
    with pytest.raises(DataError, match="frequency"):
        crypto_data_cmds._fetch_non_bybit(
            "geckoterminal",
            "dex_ohlcv",
            "0xPool",
            tmp_path,
            base="TOKEN",
            quote="USD",
            category="spot",
            frequency="5m",
            period=None,
            network="eth",
            pool_address="0xPool",
            metrics=None,
            start=None,
            end=None,
            fetched_at=fetched_at,
        )
    with pytest.raises(DataError, match="not authoritative"):
        crypto_data_cmds._fetch_non_bybit(
            "geckoterminal",
            "market_bars",
            "0xPool",
            tmp_path,
            base="TOKEN",
            quote="USD",
            category="spot",
            frequency="1h",
            period=None,
            network="eth",
            pool_address="0xPool",
            metrics=None,
            start=None,
            end=None,
            fetched_at=fetched_at,
        )


def test_latest_profile_and_hourly_sources_are_selected_from_immutable_artifacts(
    tmp_path: Path,
) -> None:
    store = CryptoBulkStore(
        bulk_root=tmp_path / "bulk",
        manifest_root=tmp_path / "control" / "crypto" / "manifests",
        expected_volume_uuid="TEST-UUID",
        volume_uuid=lambda _: "TEST-UUID",
        capacity=lambda _: Capacity(total_bytes=20_000_000, free_bytes=10_000_000),
        minimum_free_bytes=100,
    )
    store.bulk_root.mkdir()
    fetched_at = datetime.fromisoformat("2026-08-14T00:00:00+00:00")
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
            units="dimensionless_rate",
            timestamp_convention="provider_event_utc",
        ),
        payload=b"funding-source",
        request=(),
        fetched_at=fetched_at,
        provider_schema="fixture",
        parser_version="fixture-v1",
        logical_name="funding.json",
        parser=lambda _payload: pl.DataFrame(
            {"timestamp": [fetched_at], "available_at": [fetched_at], "funding_rate": [0.001]}
        ),
        observed_column="timestamp",
        key_columns=("timestamp",),
        availability_column="available_at",
    )
    source_id, dataset, frame = crypto_data_cmds._latest_profile_source(
        store,
        provider="bybit",
        family="funding",
        instrument="BTCUSDT",
        as_of=fetched_at + timedelta(days=1),
    )
    assert source_id == source.normalized_manifest["manifest_id"]
    assert dataset.family == "funding"
    assert frame.height == 1
    with pytest.raises(DataError, match="no qualified"):
        crypto_data_cmds._latest_profile_source(
            store,
            provider="bybit",
            family="funding",
            instrument="ETHUSDT",
            as_of=fetched_at + timedelta(days=1),
        )

    membership = pl.DataFrame(
        {
            "session": [fetched_at],
            "rank": [1],
            "category": ["spot"],
            "symbol": ["BTCUSDT"],
            "base_asset": ["BTC"],
            "quote_asset": ["USDT"],
            "liquidity_score": [1.0],
            "liquidity_units": ["quote_volume"],
        }
    )
    output = io.BytesIO()
    membership.write_parquet(output)
    derived = store.publish_derived(
        output.getvalue(),
        derived_kind="binance-liquidity-membership",
        input_manifest_ids=(source_id,),
        metadata={
            "schema_version": 1,
            "method_version": "binance-prior-day-liquidity-v1",
            "session": "2026-08-14",
            "category": "spot",
            "quote_asset": "USDT",
            "execution_authority": False,
        },
    )
    selected = crypto_data_cmds._latest_binance_liquidity_sources(
        store, as_of=fetched_at + timedelta(days=1)
    )
    assert selected[0][0] == derived["manifest_id"]
    assert selected[0][1] == ("spot", "USDT")
    assert selected[0][2].height == 1


def test_crypto_cli_surfaces_storage_and_artifact_failures_without_tracebacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def blocked(*_args: object, **_kwargs: object) -> object:
        raise DataError("fixture storage is unavailable")

    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", blocked)
    commands = (
        ["crypto-data", "capabilities", "--json"],
        ["crypto-data", "storage-inventory", "--json"],
        ["crypto-data", "storage-verify", "--json"],
        ["crypto-data", "cache-clean", "--confirm", "--json"],
        ["crypto-data", "coverage", "--json"],
        ["crypto-data", "quality", "a" * 64, "--json"],
        ["crypto-data", "features", "--json"],
        ["crypto-data", "feature-show", "a" * 64, "--json"],
        [
            "crypto-data",
            "compare",
            "--primary-manifest-id",
            "a" * 64,
            "--comparison-manifest-id",
            "b" * 64,
            "--json",
        ],
        [
            "crypto-data",
            "snapshot-create",
            "--manifest-id",
            "a" * 64,
            "--json",
        ],
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
    for command in commands:
        result = runner.invoke(app, command)
        assert result.exit_code != 0
        assert "fixture storage is unavailable" in result.output
        assert "Traceback" not in result.output


def test_crypto_cli_translates_immutable_control_artifact_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def blocked(*_args: object, **_kwargs: object) -> object:
        raise DataError("fixture control artifact is invalid")

    monkeypatch.setattr(crypto_data_cmds, "_read_asset_master", blocked)
    monkeypatch.setattr(crypto_data_cmds, "_read_snapshot", blocked)
    monkeypatch.setattr(crypto_data_cmds, "_read_coverage_profile", blocked)
    commands = (
        [
            "crypto-data",
            "asset-contract",
            "ethereum",
            "0xabc",
            "--asset-master-version",
            "a" * 64,
            "--as-of",
            "2026-08-15T00:00:00Z",
            "--json",
        ],
        ["crypto-data", "asset-master-verify", "a" * 64, "--json"],
        ["crypto-data", "snapshot-verify", "a" * 64, "--json"],
        ["crypto-data", "profile-show", "a" * 64, "--json"],
        [
            "crypto-data",
            "liquidity-freeze",
            "a" * 64,
            "--category",
            "spot",
            "--quote-asset",
            "USDT",
            "--session",
            "2026-08-14",
            "--json",
        ],
    )
    for command in commands:
        result = runner.invoke(app, command)
        assert result.exit_code != 0
        assert "fixture control artifact is invalid" in result.output
        assert "Traceback" not in result.output


def test_non_bybit_acquisition_contract_rejects_ambiguous_or_unbounded_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ALPHA_COINGECKO_API_KEY", raising=False)
    now = datetime.fromisoformat("2026-08-15T00:00:00+00:00")
    base = {
        "provider": "binance",
        "family": "market_bars",
        "instrument": "BTCUSDT",
        "base": "BTC",
        "quote": "USDT",
        "category": "spot",
        "frequency": "1d",
        "period": "2026-07",
        "network": None,
        "pool_address": None,
        "metrics": None,
        "start": None,
        "end": None,
    }
    cases: tuple[tuple[dict[str, object], str], ...] = (
        ({"base": "../BTC"}, "identity"),
        ({"provider": "ccxt:coinbase", "family": "funding"}, "diagnostic authority"),
        (
            {"provider": "ccxt:coinbase", "family": "comparison_bars", "category": "linear"},
            "comparison supports",
        ),
        (
            {
                "provider": "ccxt:coinbase",
                "family": "comparison_bars",
                "instrument": "BTC/USDT",
                "period": None,
            },
            "requires --start",
        ),
        (
            {
                "provider": "ccxt:coinbase",
                "family": "comparison_bars",
                "instrument": "ETH/USDT",
                "period": None,
                "start": "2026-08-01",
                "end": "2026-08-02",
            },
            "BASE/QUOTE",
        ),
        ({"category": "option"}, "Binance category"),
        ({"family": "market_membership", "start": "2026-01-01"}, "does not accept"),
        ({"family": "book_snapshots", "period": "2026-07"}, "do not accept"),
        ({"family": "funding"}, "accepts market_bars"),
        (
            {
                "family": "trades",
                "start": "2026-01-01T00:00:00Z",
                "end": "2026-01-02T00:00:00Z",
            },
            "trade archives",
        ),
        ({"period": "2026-13"}, "YYYY-MM"),
        ({"period": None}, "require --period"),
        (
            {
                "frequency": "2h",
                "period": None,
                "start": "2026-01-01T00:00:00Z",
                "end": "2026-01-02T00:00:00Z",
            },
            "kline frequency",
        ),
        ({"provider": "coingecko", "family": "market_reference"}, "scoped process injection"),
        ({"provider": "geckoterminal", "family": "dex_pools", "period": None}, "--network"),
        (
            {
                "provider": "geckoterminal",
                "family": "dex_ohlcv",
                "period": None,
                "network": "eth",
            },
            "--pool-address",
        ),
        (
            {
                "provider": "geckoterminal",
                "family": "dex_ohlcv",
                "period": None,
                "network": "eth",
                "pool_address": "0xabc",
                "frequency": "2h",
            },
            "OHLCV frequency",
        ),
        (
            {
                "provider": "geckoterminal",
                "family": "funding",
                "period": None,
                "network": "eth",
            },
            "not authoritative",
        ),
        ({"provider": "coinmetrics", "family": "funding", "period": None}, "not authoritative"),
        (
            {"provider": "coinmetrics", "family": "onchain_metrics", "period": None},
            "reviewed --metrics",
        ),
        (
            {
                "provider": "coinmetrics",
                "family": "onchain_metrics",
                "period": None,
                "metrics": "AdrActCnt",
            },
            "requires --start",
        ),
        ({"provider": "unknown", "period": None}, "unsupported crypto acquisition provider"),
    )
    for change, message in cases:
        values = base | change
        with pytest.raises(DataError, match=message):
            crypto_data_cmds._fetch_non_bybit(
                cast(str, values["provider"]),
                cast(CryptoFamily, values["family"]),
                cast(str, values["instrument"]),
                tmp_path,
                base=cast(str, values["base"]),
                quote=cast(str, values["quote"]),
                category=cast(str, values["category"]),
                frequency=cast(str, values["frequency"]),
                period=cast(str | None, values["period"]),
                network=cast(str | None, values["network"]),
                pool_address=cast(str | None, values["pool_address"]),
                metrics=cast(str | None, values["metrics"]),
                start=cast(str | None, values["start"]),
                end=cast(str | None, values["end"]),
                fetched_at=now,
            )

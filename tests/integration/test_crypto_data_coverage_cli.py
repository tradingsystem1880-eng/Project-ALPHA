from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.control_store import research_case_revision
from alpha_cli.main import app
from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoFamily
from alpha_data.crypto.ingestion import ingest_provider_payload
from alpha_data.crypto.profiles import CryptoCoverageProfileV1, CryptoCoverageTaskV1
from alpha_data.crypto.providers.binance import parse_binance_exchange_info, parse_binance_klines
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

runner = CliRunner()


def _manifest(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_coverage_profile_create_pages_and_rejects_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    as_of = datetime.fromisoformat("2026-08-15T00:00:00+00:00")
    empty_catalog = pl.DataFrame(
        schema={
            "fetched_at": pl.Datetime(time_zone="UTC"),
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
            "fetched_at": [as_of - timedelta(minutes=1)],
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
            "fetched_at": [as_of - timedelta(minutes=1)],
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

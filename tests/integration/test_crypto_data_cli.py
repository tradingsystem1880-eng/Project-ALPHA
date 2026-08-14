from __future__ import annotations

import json
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

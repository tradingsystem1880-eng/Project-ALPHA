"""Freeze recorded crypto downloads through the installed programs and detect tampering."""

from __future__ import annotations

import json
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.smoke._harness import alpha, post_json, web_server
from tests.smoke._recorded_provider import (
    RecordedProvider,
    binance_monthly_klines,
    binance_rest_klines,
)

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]


def _bars(symbol: str) -> tuple[str, ...]:
    return (
        "crypto-data", "acquire", "binance", "market_bars", symbol,
        "--base", symbol.removesuffix("USDT"), "--quote", "USDT",
        "--category", "spot", "--frequency", "1d",
    )  # fmt: skip


def _record_month(provider: RecordedProvider, symbol: str, month: int) -> None:
    archive, body, checksum, checksum_body = binance_monthly_klines(symbol, 2024, month)
    provider.record(archive, body, "application/zip")
    provider.record(checksum, checksum_body, "text/plain")


def _acquire_month(home: Path, provider: RecordedProvider, symbol: str, month: int) -> str:
    acquired = alpha(
        home, *_bars(symbol), "--period", f"2024-{month:02d}", "--json", env=provider.env()
    ).json()
    assert acquired["state"] == "qualified"
    return str(acquired["normalized_manifest_id"])


def test_snapshot_freezes_months_verifies_and_refuses_a_changed_file(crypto_home: Path) -> None:
    with RecordedProvider(crypto_home / "provider") as provider:
        for symbol, month in [("BTCUSDT", 1), ("BTCUSDT", 2), ("ETHUSDT", 1)]:
            _record_month(provider, symbol, month)
        start = int(datetime(2024, 2, 10, tzinfo=UTC).timestamp() * 1000)
        end = int(datetime(2024, 2, 12, tzinfo=UTC).timestamp() * 1000)
        tail, tail_body = binance_rest_klines("BTCUSDT", start, end)
        provider.record(tail, tail_body, "application/json")
        manifest_ids = [
            _acquire_month(crypto_home, provider, symbol, month)
            for symbol, month in [("BTCUSDT", 1), ("BTCUSDT", 2), ("ETHUSDT", 1)]
        ]
        acquired_tail = alpha(
            crypto_home,
            *_bars("BTCUSDT"),
            "--start", "2024-02-10T00:00:00Z",
            "--end", "2024-02-12T00:00:00Z",
            "--json",
            env=provider.env(),
        ).json()  # fmt: skip
        assert acquired_tail["state"] == "qualified"
        master = alpha(
            crypto_home, "crypto-data", "asset-master-verify", "reviewed-native-v1", "--json",
            env=provider.env(),
        ).json()  # fmt: skip
        assert master["state"] == "verified"
        assert master["source_manifest_ids"] == []

        snapshots = []
        for ids in (manifest_ids, list(reversed(manifest_ids))):
            options = [arg for manifest_id in ids for arg in ("--manifest-id", manifest_id)]
            frozen = alpha(
                crypto_home, "crypto-data", "snapshot-create", *options, "--json",
                env=provider.env(),
            ).json()  # fmt: skip
            assert frozen["state"] == "frozen"
            assert frozen["member_count"] == 3
            snapshots.append(frozen["snapshot_id"])
        assert snapshots[0] == snapshots[1]
        snapshot_id = snapshots[0]
        verify = (
            "crypto-data", "snapshot-verify", snapshot_id,
            "--required-family", "market_bars", "--json",
        )  # fmt: skip
        checked = alpha(crypto_home, *verify, env=provider.env()).json()
        assert checked["eligible"] is True
        assert checked["blockers"] == []

        snapshot_root = crypto_home / "data" / "crypto" / "snapshots"
        before = set(snapshot_root.glob("*.json"))
        assert before == {snapshot_root / f"{snapshot_id}.json"}
        overlap = alpha(
            crypto_home, "crypto-data", "snapshot-create",
            "--manifest-id", manifest_ids[1],
            "--manifest-id", acquired_tail["normalized_manifest_id"], "--json",
            env=provider.env(), expect=2,
        )  # fmt: skip
        assert "disjoint observed ranges" in overlap.stdout + overlap.stderr, overlap.report()
        assert set(snapshot_root.glob("*.json")) == before

        recaptured = _acquire_month(crypto_home, provider, "BTCUSDT", 1)
        assert recaptured != manifest_ids[0]
        checked = alpha(crypto_home, *verify, env=provider.env()).json()
        assert checked["eligible"] is True
        assert checked["blockers"] == []
        storage = alpha(
            crypto_home, "crypto-data", "storage-verify", "--json", env=provider.env()
        ).json()
        assert storage["state"] == "verified"
        assert storage["snapshot_count"] == 1

        manifest_path = crypto_home / "data" / "crypto" / "manifests" / f"{manifest_ids[2]}.json"
        manifest = json.loads(manifest_path.read_text())
        bulk_root = (crypto_home / "data" / "bulk").resolve()
        artifact = (bulk_root / manifest["artifact_key"]).resolve()
        assert artifact.is_relative_to(bulk_root)
        artifact.chmod(artifact.stat().st_mode | stat.S_IWUSR)
        with artifact.open("r+b") as stream:
            first = stream.read(1)
            assert first
            stream.seek(0)
            stream.write(bytes([first[0] ^ 1]))
        # A changed artifact raises a CLI usage error (exit 2), before eligibility is emitted.
        tampered = alpha(crypto_home, *verify, env=provider.env(), expect=2)
        assert "eligible" not in tampered.stdout, tampered.report()
        storage_tampered = alpha(
            crypto_home, "crypto-data", "storage-verify", "--json", env=provider.env(), expect=2
        )
        assert '"state": "verified"' not in storage_tampered.stdout, storage_tampered.report()
        assert provider.refused == []


def test_workstation_verifies_the_snapshot(crypto_home: Path) -> None:
    with RecordedProvider(crypto_home / "provider") as provider:
        for symbol in ("BTCUSDT", "ETHUSDT"):
            _record_month(provider, symbol, 1)
        manifest_ids = [
            _acquire_month(crypto_home, provider, symbol, 1) for symbol in ("BTCUSDT", "ETHUSDT")
        ]
        options = [arg for manifest_id in manifest_ids for arg in ("--manifest-id", manifest_id)]
        frozen = alpha(
            crypto_home, "crypto-data", "snapshot-create", *options, "--json", env=provider.env()
        ).json()
        assert frozen["state"] == "frozen"
        assert frozen["member_count"] == 2
        assert provider.refused == []

    with web_server(crypto_home) as base:
        checked = post_json(
            f"{base}/api/crypto-data/snapshots/{frozen['snapshot_id']}/verify",
            {"required_families": ["market_bars"], "purpose": "research"},
        )
        assert checked["snapshot_id"] == frozen["snapshot_id"]
        assert checked["eligible"] is True
        assert checked["blockers"] == []

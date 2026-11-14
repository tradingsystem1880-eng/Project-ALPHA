"""Download synthetic Binance answers through the installed programs and read them back."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alpha_data.crypto.providers.binance import archive_url, binance_public_api_url
from tests.smoke._harness import alpha, get_json, web_server
from tests.smoke._recorded_provider import (
    RecordedProvider,
    binance_monthly_klines,
    binance_rest_klines,
    binance_spot_exchange_info,
)

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]

_BARS = (
    "crypto-data", "acquire", "binance", "market_bars", "BTCUSDT",
    "--base", "BTC", "--quote", "USDT", "--category", "spot", "--frequency", "1d",
)  # fmt: skip
_MEMBERSHIP = (
    "crypto-data", "acquire", "binance", "market_membership", "spot",
    "--base", "NONE", "--quote", "NONE", "--category", "spot", "--json",
)  # fmt: skip


def test_binance_listing_archive_and_tail_download_through_recorded_provider(
    crypto_home: Path,
) -> None:
    archive, body, checksum, checksum_body = binance_monthly_klines("BTCUSDT", 2024, 1)
    listing = binance_public_api_url("spot", "exchangeInfo", {})
    start = int(datetime(2024, 3, 1, tzinfo=UTC).timestamp() * 1000)
    end = int(datetime(2024, 3, 4, tzinfo=UTC).timestamp() * 1000)
    tail, tail_body = binance_rest_klines("BTCUSDT", start, end)
    with RecordedProvider(crypto_home / "provider") as provider:
        provider.record(
            listing, binance_spot_exchange_info(["BTCUSDT", "ETHUSDT"]), "application/json"
        )
        provider.record(archive, body, "application/zip")
        provider.record(checksum, checksum_body, "text/plain")
        provider.record(tail, tail_body, "application/json")
        env = provider.env()

        catalog = alpha(crypto_home, "crypto-data", "catalog", "--json", env=env).json()
        assert {
            "family": "market_bars",
            "provider": "binance",
            "role": "primary_acquisition",
        } in catalog["families"]
        assert alpha(crypto_home, *_MEMBERSHIP, env=env).json()["state"] == "qualified"
        markets = alpha(
            crypto_home, "crypto-data", "market-catalog", "--query", "BTC", "--json", env=env
        ).json()
        assert len(markets["markets"]) == 1
        assert markets["markets"][0]["provider_symbol"] == "BTCUSDT"

        acquired = alpha(crypto_home, *_BARS, "--period", "2024-01", "--json", env=env).json()
        assert acquired["state"] == "qualified"
        archive_id = acquired["normalized_manifest_id"]
        acquired_tail = alpha(
            crypto_home,
            *_BARS,
            "--start",
            "2024-03-01T00:00:00Z",
            "--end",
            "2024-03-04T00:00:00Z",
            "--json",
            env=env,
        ).json()
        assert acquired_tail["state"] == "qualified"
        tail_id = acquired_tail["normalized_manifest_id"]
        coverage = alpha(crypto_home, "crypto-data", "coverage", "--json", env=env).json()
        bars = {
            row["manifest_id"]: row for row in coverage["items"] if row["family"] == "market_bars"
        }
        assert set(bars) == {archive_id, tail_id}
        assert bars[archive_id]["row_count"] == 31
        assert (
            datetime.fromisoformat(bars[archive_id]["observed_start"]).date().isoformat()
            == "2024-01-01"
        )
        assert (
            datetime.fromisoformat(bars[archive_id]["observed_end"]).date().isoformat()
            == "2024-01-31"
        )
        assert bars[tail_id]["row_count"] == 4
        quality = alpha(
            crypto_home, "crypto-data", "quality", archive_id, "--json", env=env
        ).json()["quality"]
        assert quality["state"] == "qualified"
        assert quality["failures"] == []

        candles = alpha(
            crypto_home,
            "data",
            "candles",
            "BTCUSDT",
            "--manifest-id",
            archive_id,
            "--start",
            "2024-01-10",
            "--end",
            "2024-01-12",
            "--json",
            env=env,
        ).json()
        with zipfile.ZipFile(io.BytesIO(body)) as recorded:
            rows = list(csv.reader(io.StringIO(recorded.read(recorded.namelist()[0]).decode())))
        assert [
            datetime.fromtimestamp(bar["t"], UTC).date().isoformat() for bar in candles["bars"]
        ] == [
            "2024-01-10",
            "2024-01-11",
        ]
        assert [(bar["o"], bar["c"]) for bar in candles["bars"]] == [
            (float(rows[day - 1][1]), float(rows[day - 1][4])) for day in (10, 11)
        ]
        assert candles["provenance"]["quality_status"] == "qualified"

        missing = alpha(crypto_home, *_BARS, "--period", "2024-02", "--json", env=env, expect=2)
        assert "HTTP 404" in missing.stdout + missing.stderr, missing.report()
        after = alpha(crypto_home, "crypto-data", "coverage", "--json", env=env).json()
        assert {row["manifest_id"] for row in after["items"] if row["family"] == "market_bars"} == {
            archive_id,
            tail_id,
        }
        missing_archive = archive_url("spot", "klines", "BTCUSDT", "1d", "2024-02")
        assert provider.requests == [
            listing,
            checksum,
            archive,
            tail,
            f"{missing_archive}.CHECKSUM",
        ]
        assert provider.refused == []


def test_workstation_serves_the_downloaded_coverage(crypto_home: Path) -> None:
    archive, body, checksum, checksum_body = binance_monthly_klines("BTCUSDT", 2024, 1)
    listing = binance_public_api_url("spot", "exchangeInfo", {})
    with RecordedProvider(crypto_home / "provider") as provider:
        provider.record(
            listing, binance_spot_exchange_info(["BTCUSDT", "ETHUSDT"]), "application/json"
        )
        provider.record(archive, body, "application/zip")
        provider.record(checksum, checksum_body, "text/plain")
        assert alpha(crypto_home, *_MEMBERSHIP, env=provider.env()).json()["state"] == "qualified"
        acquired = alpha(
            crypto_home, *_BARS, "--period", "2024-01", "--json", env=provider.env()
        ).json()
        assert acquired["state"] == "qualified"
        manifest_id = acquired["normalized_manifest_id"]
        assert provider.requests == [listing, checksum, archive]
        assert provider.refused == []

    with web_server(crypto_home) as base:
        coverage = get_json(f"{base}/api/crypto-data/coverage")
        [bars] = [row for row in coverage["items"] if row["manifest_id"] == manifest_id]
        assert bars["row_count"] == 31
        assert bars["state"] == "qualified"
        markets = get_json(f"{base}/api/crypto-data/market-catalog?query=BTC")
        assert len(markets["markets"]) == 1
        assert markets["markets"][0]["provider_symbol"] == "BTCUSDT"

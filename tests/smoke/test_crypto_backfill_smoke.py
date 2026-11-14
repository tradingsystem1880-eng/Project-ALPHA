"""Prove resumable Binance history acquisition through the installed command."""

from __future__ import annotations

import fcntl
from pathlib import Path

import pytest

from alpha_data.crypto.providers.binance import archive_url
from tests.smoke._harness import alpha
from tests.smoke._recorded_provider import RecordedProvider, binance_monthly_klines

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]

_SCOPE = (
    "binance", "market_bars", "--symbols", "BTCUSDT,ETHUSDT", "--quote", "USDT",
    "--category", "spot", "--frequency", "1d", "--start", "2024-01-01",
    "--end", "2024-03-01", "--ledger", "smoke", "--json",
)  # fmt: skip
_BACKFILL = ("crypto-data", "backfill", *_SCOPE)
_STATUS = (
    "crypto-data", "backfill-status", *_SCOPE,
    "--max-ledger-bytes", "1000000", "--max-windows", "100",
    "--max-verify-artifact-bytes", "100000000",
)  # fmt: skip


def test_binance_backfill_resumes_only_unfinished_months_and_refuses_a_second_writer(
    crypto_home: Path,
) -> None:
    with RecordedProvider(crypto_home / "provider") as provider:
        for symbol, month in (("BTCUSDT", 1), ("BTCUSDT", 2), ("ETHUSDT", 1)):
            archive, body, checksum, checksum_body = binance_monthly_klines(symbol, 2024, month)
            provider.record(archive, body, "application/zip")
            provider.record(checksum, checksum_body, "text/plain")
        env = provider.env()

        preview = alpha(crypto_home, *_BACKFILL, "--dry-run", env=env).json()
        assert preview["windows_total"] == 4
        assert provider.requests == []

        first = alpha(crypto_home, *_BACKFILL, env=env, expect=1).json()
        assert first["done"] == 3 and first["failed"] == 1
        assert len(first["failures"]) == 1
        assert first["failures"][0]["key"] == "ETHUSDT|None|None|2024-02"
        assert "HTTP 404" in first["failures"][0]["error"]
        assert first["not_published_yet"] == []
        assert first["awaiting_publication"] == []
        assert not any("2024-03" in url for url in provider.requests)
        requests = provider.requests
        ledger = crypto_home / "data" / "crypto" / "backfill" / "smoke.json"
        before = ledger.read_bytes()

        # The inspection itself completes (exit 0); the recorded failure is in its counts.
        status = alpha(crypto_home, *_STATUS, env=env).json()
        assert status["inspection_state"] == "complete"
        assert status["next_action"] == "review_failures_unrecorded_work_and_existing_admission"
        assert status["counts"]["completed_verified"] == 3
        assert status["counts"]["recorded_failure"] == 1
        assert provider.requests == requests
        assert ledger.read_bytes() == before

        with ledger.with_name(ledger.name + ".lock").open("r+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                refused = alpha(crypto_home, *_BACKFILL, env=env, expect=2)
                assert "already owned" in refused.stdout + refused.stderr, refused.report()
                assert provider.requests == requests
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

        refused = alpha(
            crypto_home, *_BACKFILL, "--max-verify-artifact-bytes", "1", env=env, expect=2
        )
        assert refused.code != 0
        assert provider.requests == requests
        assert ledger.read_bytes() == before

        archive, body, checksum, checksum_body = binance_monthly_klines("ETHUSDT", 2024, 2)
        provider.record(archive, body, "application/zip")
        provider.record(checksum, checksum_body, "text/plain")
        resumed = alpha(crypto_home, *_BACKFILL, env=env).json()
        assert resumed["done"] == 1 and resumed["skipped"] == 3
        assert resumed["verified_completed"] == 3
        assert resumed["resume_verification"] == "verified"
        assert provider.requests == [*requests, checksum, archive]
        assert not any(
            archive_url("spot", "klines", symbol, "1d", "2024-03") in url
            for symbol in ("BTCUSDT", "ETHUSDT")
            for url in provider.requests
        )

        completed_requests = provider.requests
        completed_ledger = ledger.read_bytes()
        status = alpha(crypto_home, *_STATUS, env=env).json()
        assert status["inspection_state"] == "complete"
        assert status["counts"]["completed_verified"] == 4
        assert provider.requests == completed_requests
        assert ledger.read_bytes() == completed_ledger

        # A metadata byte bound too small for the retained manifests stops the inspection loudly.
        bounded = alpha(
            crypto_home, *_STATUS, "--max-verify-metadata-bytes", "1", env=env, expect=1
        ).json()
        assert bounded["inspection_state"] != "complete"
        assert bounded["metadata_verification_aborted"] is True
        assert provider.requests == completed_requests
        assert ledger.read_bytes() == completed_ledger
        assert provider.refused == []

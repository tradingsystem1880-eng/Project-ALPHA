"""Audit downloaded daily bars through the installed CLI and Workstation API."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from collections.abc import Collection
from pathlib import Path
from typing import Any

import pytest

from tests.smoke._harness import alpha, web_server
from tests.smoke._recorded_provider import RecordedProvider, binance_monthly_klines

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]

_GRID = {
    "coverage_start": "2024-01-01T00:00:00Z",
    "coverage_end": "2024-02-01T00:00:00Z",
    "as_of": "2024-03-01T00:00:00Z",
    "expected_cadence_seconds": 86400,
    "max_verify_artifact_bytes": 100_000_000,
}
_MISSING_DAY = [
    {"start": "2024-01-15T00:00:00+00:00", "end": "2024-01-16T00:00:00+00:00", "slots": 1}
]


def _download(
    home: Path, provider: RecordedProvider, symbol: str, *, missing_days: Collection[int] = ()
) -> dict[str, Any]:
    archive, body, checksum, checksum_body = binance_monthly_klines(
        symbol, 2024, 1, missing_days=missing_days
    )
    provider.record(archive, body, "application/zip")
    provider.record(checksum, checksum_body, "text/plain")
    acquired: dict[str, Any] = alpha(
        home,
        "crypto-data", "acquire", "binance", "market_bars", symbol,
        "--base", symbol.removesuffix("USDT"), "--quote", "USDT",
        "--category", "spot", "--frequency", "1d", "--period", "2024-01", "--json",
        env=provider.env(),
    ).json()  # fmt: skip
    assert acquired.get("normalized_manifest_id"), f"download state={acquired['state']}: {acquired}"
    return acquired


def _fingerprint(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def _audit(
    home: Path,
    provider: RecordedProvider,
    acquired: dict[str, Any],
    *,
    expect: int,
    **changes: str,
) -> dict[str, Any]:
    grid = _GRID | changes
    args = [
        part for key, value in grid.items() for part in ("--" + key.replace("_", "-"), str(value))
    ]
    result = alpha(
        home,
        "crypto-data", "quality", acquired["normalized_manifest_id"], *args, "--json",
        env=provider.env(), expect=expect,
    )  # fmt: skip
    report: dict[str, Any] = result.json()
    assert report["audit_state"] == "inspected", f"download state={acquired['state']}: {report}"
    return report


def test_completeness_check_finds_the_missing_day_without_provider_calls(crypto_home: Path) -> None:
    with RecordedProvider(crypto_home / "provider") as provider:
        btc = _download(crypto_home, provider, "BTCUSDT")
        eth = _download(crypto_home, provider, "ETHUSDT", missing_days={15})
        states = f"download states: BTC={btc['state']}, ETH={eth['state']}"
        # The download's own quality check already flags the gap; it is never "qualified".
        assert btc["state"] == "qualified", states
        assert eth["state"] == "warning" and eth["warnings"] == ["cadence_gap"], states
        requests = provider.requests
        before = _fingerprint(crypto_home / "data")

        full = _audit(crypto_home, provider, btc, expect=0)["row_audit"]
        assert full["expected_slots"] == 31, states
        assert full["covered_slots"] == 31, states
        assert full["missing_slots"] == 0, states
        assert full["declared_grid_satisfied"] is True, states

        gap = _audit(crypto_home, provider, eth, expect=1)["row_audit"]
        assert gap["missing_slots"] == 1, states
        assert gap["missing_ranges"] == _MISSING_DAY, states

        wider = _audit(
            crypto_home, provider, btc, expect=1,
            coverage_start="2023-12-30T00:00:00Z", coverage_end="2024-02-02T00:00:00Z",
        )["row_audit"]  # fmt: skip
        assert wider["missing_slots"] == 3, states
        assert wider["missing_ranges"] == [
            {"start": "2023-12-30T00:00:00+00:00", "end": "2024-01-01T00:00:00+00:00", "slots": 2},
            {"start": "2024-02-01T00:00:00+00:00", "end": "2024-02-02T00:00:00+00:00", "slots": 1},
        ], states

        # A grid that has not closed at the cutoff is refused outright (exit 1, no row audit):
        # the 31 January bar, still open at noon, can never be counted as a complete day.
        grid = _GRID | {"as_of": "2024-01-31T12:00:00Z"}
        args = [
            part
            for key, value in grid.items()
            for part in ("--" + key.replace("_", "-"), str(value))
        ]
        early = alpha(
            crypto_home,
            "crypto-data", "quality", btc["normalized_manifest_id"], *args, "--json",
            env=provider.env(), expect=1,
        ).json()  # fmt: skip
        assert early["audit_state"] == "unavailable", states
        assert early["reason"] == "RETAINED_BAR_AUDIT_UNAVAILABLE", states
        assert early["row_audit"] is None, states
        assert provider.requests == requests, states
        assert provider.refused == [], states
        assert _fingerprint(crypto_home / "data") == before, states


def _post_json(url: str, payload: dict[str, Any]) -> Any:
    # Use the Workstation's canonical host: urllib cannot redirect a POST on 307.
    url = url.replace("http://127.0.0.1:", "http://localhost:", 1)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        assert response.status == 200
        return json.loads(response.read())


def test_workstation_reports_the_same_missing_day(crypto_home: Path) -> None:
    with RecordedProvider(crypto_home / "provider") as provider:
        eth = _download(crypto_home, provider, "ETHUSDT", missing_days={15})
    with web_server(crypto_home) as base:
        report = _post_json(
            f"{base}/api/crypto-data/quality/{eth['normalized_manifest_id']}/retained-coverage",
            _GRID,
        )
        state = f"download state={eth['state']}: {report}"
        assert report["audit_state"] == "inspected", state
        assert report["row_audit"]["missing_slots"] == 1, state
        assert report["row_audit"]["missing_ranges"] == _MISSING_DAY, state
        assert report["row_audit"]["declared_grid_satisfied"] is False, state

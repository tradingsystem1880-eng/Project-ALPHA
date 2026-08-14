"""Typed Crypto Data Center REST routes over the authoritative CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web import _catalog, _invoke
from alpha_web.app import create_app


def test_crypto_catalog_route_uses_authoritative_cli_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    calls: list[list[str]] = []

    def project(args: list[str], **_: object) -> dict[str, object]:
        calls.append(args)
        return {
            "families": [{"family": "funding", "provider": "bybit", "role": "primary_acquisition"}],
            "automatic_fallback": False,
            "execution_authority": False,
            "next_action": "Check storage before estimating or acquiring data.",
        }

    monkeypatch.setattr(_catalog, "_run_json", project)

    response = TestClient(create_app()).get("/api/crypto-data/catalog")

    assert response.status_code == 200
    assert response.json()["families"][0]["provider"] == "bybit"
    assert calls == [["crypto-data", "catalog", "--json"]]


def test_crypto_acquisition_route_builds_closed_argv_and_rejects_injection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    calls: list[list[str]] = []

    class Accepted:
        job_id = "job-1"
        status = "running"
        session_id = None

    def launch(args: list[str], **_: object) -> Accepted:
        calls.append(args)
        return Accepted()

    monkeypatch.setattr(_invoke, "launch", launch)
    client = TestClient(create_app())
    response = client.post(
        "/api/crypto-data/acquisitions",
        json={
            "provider": "bybit",
            "family": "funding",
            "instrument": "BTCUSDT",
            "base": "BTC",
            "quote": "USDT",
            "category": "linear",
            "frequency": "1h",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"job_id": "job-1", "status": "running", "session_id": None}
    assert calls == [
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
            "--category",
            "linear",
            "--frequency",
            "1h",
            "--json",
        ]
    ]

    rejected = client.post(
        "/api/crypto-data/acquisitions",
        json={
            "provider": "bybit",
            "family": "funding",
            "instrument": "BTCUSDT;paper-run",
            "base": "BTC",
            "quote": "USDT",
        },
    )
    assert rejected.status_code == 422
    assert len(calls) == 1


def test_crypto_snapshot_routes_build_exact_membership_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    manifest_id = "a" * 64
    snapshot_id = "b" * 64
    calls: list[list[str]] = []

    def project(args: list[str], **_: object) -> dict[str, object]:
        calls.append(args)
        if args[1] == "snapshot-create":
            return {
                "snapshot_id": snapshot_id,
                "member_count": 1,
                "families": ["funding"],
                "providers": ["bybit"],
                "state": "frozen",
                "next_action": "Verify the snapshot for the exact research purpose.",
                "execution_authority": False,
            }
        return {
            "snapshot_id": snapshot_id,
            "eligible": True,
            "purpose": "research",
            "qualified_families": ["funding"],
            "supplemental_families": [],
            "blockers": [],
            "next_action": "Bind this snapshot to the exact research proposal.",
            "execution_authority": False,
        }

    monkeypatch.setattr(_catalog, "_run_json", project)
    client = TestClient(create_app())
    created = client.post("/api/crypto-data/snapshots", json={"manifest_ids": [manifest_id]})
    verified = client.post(
        f"/api/crypto-data/snapshots/{snapshot_id}/verify",
        json={"required_families": ["funding"], "purpose": "research"},
    )

    assert created.status_code == 200
    assert verified.status_code == 200
    assert calls == [
        ["crypto-data", "snapshot-create", "--manifest-id", manifest_id, "--json"],
        [
            "crypto-data",
            "snapshot-verify",
            snapshot_id,
            "--required-family",
            "funding",
            "--purpose",
            "research",
            "--json",
        ],
    ]


def test_crypto_routes_translate_cli_failure_to_actionable_api_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))

    def fail(*_: object, **__: object) -> object:
        raise RuntimeError("review the exact data-family requirements")

    monkeypatch.setattr(_catalog, "_run_json", fail)
    response = TestClient(create_app()).post(
        "/api/crypto-data/estimate",
        json={"family": "funding", "instruments": 1, "days": 30, "frequency": "1h"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "request_invalid"
    assert body["message"] == "review the exact data-family requirements"

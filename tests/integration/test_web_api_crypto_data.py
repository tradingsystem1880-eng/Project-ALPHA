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


def test_crypto_capabilities_route_preserves_readiness_dimensions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    calls: list[list[str]] = []

    def project(args: list[str], **_: object) -> dict[str, object]:
        calls.append(args)
        return {
            "items": [
                {
                    "schema_version": 1,
                    "provider": "bybit",
                    "family": "open_interest",
                    "authentication": "none",
                    "earliest": "2026-08-01T00:00:00+00:00",
                    "latest": "2026-08-14T00:00:00+00:00",
                    "frequencies": ["1h"],
                    "limits": ["bybit_page_200_cursor_max_100_pages"],
                    "verification_state": "receipt_verified",
                    "qualification_state": "qualified",
                }
            ],
            "count": 1,
            "receipt_verified_count": 1,
            "qualified_count": 1,
            "provider_probe_performed": False,
            "automatic_fallback": False,
            "execution_authority": False,
            "canonical_next_action": "Inspect qualified coverage.",
        }

    monkeypatch.setattr(_catalog, "_run_json", project)

    response = TestClient(create_app()).get("/api/crypto-data/capabilities")

    assert response.status_code == 200
    assert response.json()["items"][0]["verification_state"] == "receipt_verified"
    assert response.json()["items"][0]["qualification_state"] == "qualified"
    assert response.json()["provider_probe_performed"] is False
    assert calls == [["crypto-data", "capabilities", "--json"]]


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
                "asset_master_version": "reviewed-native-v1",
                "state": "frozen",
                "next_action": "Verify the snapshot for the exact research purpose.",
                "execution_authority": False,
            }
        if args[0:3] == ["research", "data", "register-crypto"]:
            return {
                "ref_id": "rd_" + "c" * 64,
                "dataset_kind": "snapshot",
                "instrument": "BTC",
                "provider": "crypto-data-house",
                "start_ts": "2026-08-04T00:00:00+00:00",
                "end_ts": "2026-08-14T00:00:00+00:00",
                "bar_duration_minutes": 60,
                "origin": {
                    "snapshot_id": snapshot_id,
                    "manifest_sha256": "d" * 64,
                    "snapshot_schema": "CryptoSnapshotV1",
                },
                "research_only": True,
                "registered_by": "owner",
                "registered_at": "2026-08-15T00:00:00Z",
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
    registered = client.post(
        f"/api/crypto-data/snapshots/{snapshot_id}/register", json={"symbol": "btc"}
    )

    assert created.status_code == 200
    assert verified.status_code == 200
    assert registered.status_code == 200
    assert registered.json()["ref_id"] == "rd_" + "c" * 64
    assert calls == [
        [
            "crypto-data",
            "snapshot-create",
            "--manifest-id",
            manifest_id,
            "--asset-master-version",
            "reviewed-native-v1",
            "--json",
        ],
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
        [
            "research",
            "data",
            "register-crypto",
            snapshot_id,
            "--symbol",
            "BTC",
            "--json",
        ],
    ]


def test_crypto_asset_master_routes_build_closed_exact_identity_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    cg_manifest, gt_manifest, version = "a" * 64, "b" * 64, "c" * 64
    calls: list[list[str]] = []

    def project(args: list[str], **_: object) -> dict[str, object]:
        calls.append(args)
        if args[1] == "asset-masters":
            return {
                "items": [
                    {
                        "asset_master_version": version,
                        "identity_count": 3,
                        "contract_identity_count": 1,
                        "builtin": False,
                        "state": "verified",
                    }
                ],
                "count": 1,
                "ticker_join_allowed": False,
                "next_action": "Select this master.",
            }
        if args[1] == "asset-contract":
            return {
                "schema_version": 1,
                "coingecko_id": "usd-coin",
                "network": "ethereum",
                "contract_address": "0xusdc",
                "native_asset": False,
                "provider_symbols": [
                    ["coingecko", "usd-coin"],
                    ["geckoterminal", "0xusdc"],
                ],
                "valid_from": "2026-08-15T00:00:00Z",
                "valid_to": None,
                "migration_lineage": [],
            }
        return {
            "asset_master_version": version,
            "identity_count": 3,
            "contract_identity_count": 1,
            "source_manifest_ids": [cg_manifest, gt_manifest]
            if args[1] == "asset-master-create"
            else None,
            "ticker_join_allowed": False,
            "state": "frozen" if args[1] == "asset-master-create" else "verified",
            "next_action": "Continue.",
        }

    monkeypatch.setattr(_catalog, "_run_json", project)
    client = TestClient(create_app())
    created = client.post(
        "/api/crypto-data/asset-masters",
        json={
            "coingecko_manifest_id": cg_manifest,
            "geckoterminal_manifest_ids": [gt_manifest],
        },
    )
    listed = client.get("/api/crypto-data/asset-masters")
    verified = client.post(f"/api/crypto-data/asset-masters/{version}/verify", json={})
    contract = client.get(
        "/api/crypto-data/assets/contracts/ethereum/0xusdc",
        params={
            "asset_master_version": version,
            "as_of": "2026-08-15T00:00:00Z",
        },
    )

    assert created.status_code == 200
    assert listed.status_code == 200
    assert verified.status_code == 200
    assert contract.status_code == 200
    assert contract.json()["coingecko_id"] == "usd-coin"
    assert calls == [
        [
            "crypto-data",
            "asset-master-create",
            "--coingecko-manifest-id",
            cg_manifest,
            "--geckoterminal-manifest-id",
            gt_manifest,
            "--json",
        ],
        ["crypto-data", "asset-masters", "--json"],
        ["crypto-data", "asset-master-verify", version, "--json"],
        [
            "crypto-data",
            "asset-contract",
            "ethereum",
            "0xusdc",
            "--asset-master-version",
            version,
            "--as-of",
            "2026-08-15T00:00:00Z",
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


def test_crypto_storage_actions_use_closed_commands_and_confirm_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    calls: list[list[str]] = []

    def project(args: list[str], **_: object) -> dict[str, object]:
        calls.append(args)
        if args[1] == "storage-inventory":
            return {
                "manifest_count": 2,
                "snapshot_count": 1,
                "counts_by_kind": {"raw": 1, "normalized": 1},
                "bytes_by_kind": {"raw": 10, "normalized": 20},
                "cache_bytes": 5,
                "staging_count": 0,
                "private_paths_exposed": False,
                "next_action": "Verify storage.",
            }
        if args[1] == "storage-verify":
            return {
                "state": "verified",
                "manifest_count": 2,
                "snapshot_count": 1,
                "research_eligible_snapshot_count": 1,
                "asset_master_count": 0,
                "cache_bytes": 5,
                "private_paths_exposed": False,
                "next_action": "Continue.",
            }
        return {
            "state": "cleaned",
            "removed_bytes": 5,
            "immutable_artifacts_removed": 0,
            "private_paths_exposed": False,
            "next_action": "Run inventory.",
        }

    monkeypatch.setattr(_catalog, "_run_json", project)
    client = TestClient(create_app())

    assert client.get("/api/crypto-data/storage/inventory").status_code == 200
    assert client.post("/api/crypto-data/storage/verify", json={}).status_code == 200
    assert (
        client.post("/api/crypto-data/storage/cache/clean", json={"confirm": True}).status_code
        == 200
    )
    assert (
        client.post("/api/crypto-data/storage/cache/clean", json={"confirm": False}).status_code
        == 422
    )
    assert calls == [
        ["crypto-data", "storage-inventory", "--json"],
        ["crypto-data", "storage-verify", "--json"],
        ["crypto-data", "cache-clean", "--confirm", "--json"],
    ]

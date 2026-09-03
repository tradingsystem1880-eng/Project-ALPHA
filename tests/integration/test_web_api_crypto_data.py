"""Typed Crypto Data Center REST routes over the authoritative CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from alpha_web import _catalog, _invoke, _research
from alpha_web.api import crypto_data as crypto_api
from alpha_web.api.models import (
    CryptoAcquisitionRequest,
    CryptoAssetMasterCreateRequest,
    CryptoCoverageBatchRequest,
    CryptoCoverageBatchResumeRequest,
    CryptoCoverageProfileCreateRequest,
    CryptoSnapshotCreateRequest,
    CryptoSnapshotRegisterRequest,
    CryptoSnapshotVerifyRequest,
)
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


def test_crypto_route_functions_cover_closed_validation_and_recovery_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def project(args: list[str]) -> list[str]:
        calls.append(args)
        return args

    monkeypatch.setattr(crypto_api, "_project", project)
    assert crypto_api.storage()[1] == "storage"
    assert crypto_api.coverage()[1] == "coverage"
    crypto_api.profile_create(CryptoCoverageProfileCreateRequest(as_of="2026-08-15T00:00:00Z"))
    crypto_api.asset("btc", "2026-08-15T00:00:00Z")
    for symbol, as_of, message in (
        ("../btc", "2026-08-15", "symbol"),
        ("BTC", "", "as-of"),
    ):
        with pytest.raises(HTTPException, match=message):
            crypto_api.asset(symbol, as_of)
    with pytest.raises(HTTPException, match="contract identity"):
        crypto_api.asset_contract("../eth", "0xabc", "a" * 64, "2026-08-15")
    with pytest.raises(HTTPException, match="asset-master"):
        crypto_api.asset_contract("ethereum", "0xabc", "bad", "2026-08-15")
    with pytest.raises(HTTPException, match="as-of"):
        crypto_api.asset_contract("ethereum", "0xabc", "a" * 64, "")
    with pytest.raises(HTTPException, match="asset-master"):
        crypto_api.asset_master_verify("bad")
    with pytest.raises(HTTPException, match="manifest id"):
        crypto_api.quality("bad")
    with pytest.raises(HTTPException, match="feature manifest"):
        crypto_api.feature_show("bad")
    with pytest.raises(HTTPException, match="snapshot id"):
        crypto_api.snapshot_verify(
            "bad", CryptoSnapshotVerifyRequest(required_families=[], purpose="research")
        )
    with pytest.raises(HTTPException, match="snapshot id"):
        crypto_api.snapshot_register("bad", CryptoSnapshotRegisterRequest(symbol="BTC"))

    with pytest.raises(HTTPException, match="unique"):
        crypto_api.snapshot_create(CryptoSnapshotCreateRequest(manifest_ids=["a" * 64, "a" * 64]))
    with pytest.raises(HTTPException, match="manifest id"):
        crypto_api.snapshot_create(CryptoSnapshotCreateRequest(manifest_ids=["bad"]))
    with pytest.raises(HTTPException, match="unique"):
        crypto_api.asset_master_create(
            CryptoAssetMasterCreateRequest(
                coingecko_manifest_id="a" * 64,
                geckoterminal_manifest_ids=["b" * 64, "b" * 64],
            )
        )

    request = CryptoAcquisitionRequest(
        provider="bybit",
        family="funding",
        instrument="BTCUSDT",
        base="BTC",
        quote="USDT",
        case_id="f03802b8-df35-4f19-a90c-0b3437aa587d",
        expected_case_revision="a" * 64,
        reason="Not valid for this family.",
    )
    with pytest.raises(HTTPException, match="only valid"):
        crypto_api.acquire(request)

    class FailedLaunch:
        def __call__(self, *_args: object, **_kwargs: object) -> object:
            raise RuntimeError("fixture launch conflict")

    monkeypatch.setattr(_invoke, "launch", FailedLaunch())
    with pytest.raises(HTTPException, match="fixture launch conflict"):
        crypto_api.profile_run(
            "a" * 64,
            CryptoCoverageBatchRequest(cadence="daily", offset=0, limit=1, confirm=True),
        )
    with pytest.raises(HTTPException, match="fixture launch conflict"):
        crypto_api.profile_resume("b" * 64, CryptoCoverageBatchResumeRequest(confirm=True))


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
    monkeypatch.setattr(
        _research,
        "proposal_options",
        lambda *_args, **_kwargs: {"case_revision": "a" * 64},
    )
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

    missing_scope = client.post(
        "/api/crypto-data/acquisitions",
        json={
            "provider": "bybit",
            "family": "derivative_book_snapshots",
            "instrument": "BTCUSDT",
            "base": "BTC",
            "quote": "USDT",
            "category": "linear",
        },
    )
    assert missing_scope.status_code == 422
    assert len(calls) == 1

    revision = "a" * 64
    accepted_scope = client.post(
        "/api/crypto-data/acquisitions",
        json={
            "provider": "bybit",
            "family": "derivative_book_snapshots",
            "instrument": "BTCUSDT",
            "base": "BTC",
            "quote": "USDT",
            "category": "linear",
            "case_id": "f03802b8-df35-4f19-a90c-0b3437aa587d",
            "expected_case_revision": revision,
            "reason": "Capture the bounded BTC event book.",
        },
    )
    assert accepted_scope.status_code == 200
    assert calls[-1][-7:] == [
        "--case-id",
        "f03802b8-df35-4f19-a90c-0b3437aa587d",
        "--expected-case-revision",
        revision,
        "--reason",
        "Capture the bounded BTC event book.",
        "--json",
    ]

    stale_scope = client.post(
        "/api/crypto-data/acquisitions",
        json={
            "provider": "bybit",
            "family": "derivative_trades",
            "instrument": "BTCUSDT",
            "base": "BTC",
            "quote": "USDT",
            "category": "linear",
            "case_id": "f03802b8-df35-4f19-a90c-0b3437aa587d",
            "expected_case_revision": "b" * 64,
            "reason": "Capture the bounded BTC event trades.",
        },
    )
    assert stale_scope.status_code == 409
    assert len(calls) == 2


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


def test_crypto_feature_routes_build_named_lineage_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    source_id, feature_manifest = "a" * 64, "b" * 64
    calls: list[list[str]] = []

    def feature() -> dict[str, object]:
        return {
            "manifest_id": feature_manifest,
            "feature_id": "c" * 64,
            "feature_name": "funding",
            "method_version": "crypto-features-v1",
            "available_at": "2026-08-15T00:00:00+00:00",
            "row_count": 2,
            "artifact_sha256": "d" * 64,
            "input_count": 1,
            "state": "verified",
            "research_authority": False,
            "execution_authority": False,
        }

    def project(args: list[str], **_: object) -> dict[str, object]:
        calls.append(args)
        if args[1] == "features":
            return {
                "items": [feature()],
                "count": 1,
                "research_authority": False,
                "execution_authority": False,
                "next_action": "Create only a supported feature.",
            }
        return feature() | ({"state": "frozen"} if args[1] == "feature-create" else {})

    monkeypatch.setattr(_catalog, "_run_json", project)
    client = TestClient(create_app())
    created = client.post(
        "/api/crypto-data/features",
        json={"feature_name": "funding", "inputs": {"funding": source_id}},
    )
    listed = client.get("/api/crypto-data/features")
    shown = client.get(f"/api/crypto-data/features/{feature_manifest}")
    invalid = client.post(
        "/api/crypto-data/features",
        json={"feature_name": "basis", "inputs": {"mark": source_id}},
    )

    assert created.status_code == 200, created.text
    assert listed.status_code == 200, listed.text
    assert shown.status_code == 200, shown.text
    assert invalid.status_code == 422
    assert calls == [
        [
            "crypto-data",
            "feature-create",
            "funding",
            "--input",
            f"funding={source_id}",
            "--json",
        ],
        ["crypto-data", "features", "--json"],
        ["crypto-data", "feature-show", feature_manifest, "--json"],
    ]


def test_crypto_profile_routes_keep_batches_bounded_and_selections_case_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    profile_id, batch_id = "1" * 64, "2" * 64
    project_calls: list[list[str]] = []
    launch_calls: list[list[str]] = []

    class Accepted:
        job_id = "profile-job"
        status = "running"
        session_id = None

    def launch(args: list[str], **_: object) -> Accepted:
        launch_calls.append(args)
        return Accepted()

    summary = {
        "profile_id": profile_id,
        "as_of": "2026-08-15T00:00:00+00:00",
        "source_manifest_ids": ["a" * 64],
        "task_count": 1,
        "counts_by_provider": {"binance": 1},
        "counts_by_cadence": {"daily": 1},
        "counts_by_family": {"market_bars": 1},
        "execution_authority": False,
    }

    def project(args: list[str], **_: object) -> dict[str, object]:
        project_calls.append(args)
        command = args[1]
        if command == "profiles":
            return {
                "items": [summary],
                "count": 1,
                "execution_authority": False,
                "next_action": "Create a fresh profile after catalog changes.",
            }
        if command == "profile-create":
            return summary | {
                "state": "frozen",
                "binance_hourly_scopes": [],
                "binance_hourly_missing_scopes": [["spot", "USDT"]],
                "next_action": "Acquire the daily scope.",
            }
        if command == "profile-show":
            return summary | {
                "offset": 0,
                "limit": 100,
                "filtered_count": 1,
                "filters": {
                    "provider": "binance",
                    "family": "market_bars",
                    "category": None,
                    "frequency": "1d",
                    "cadence": None,
                },
                "items": [
                    {
                        "schema_version": 1,
                        "task_id": "b" * 64,
                        "provider": "binance",
                        "family": "market_bars",
                        "instrument": "BTCUSDT",
                        "base_asset": "BTC",
                        "quote_asset": "USDT",
                        "category": "spot",
                        "frequency": "1d",
                        "cadence": "daily",
                        "network": None,
                        "metrics": [],
                        "lookback_days": None,
                        "execution_authority": False,
                    }
                ],
                "has_more": False,
                "next_offset": None,
                "next_action": "Run only the intended bounded cadence batch.",
            }
        if command == "profile-batches":
            return {
                "items": [
                    {
                        "batch_id": batch_id,
                        "profile_id": profile_id,
                        "cadence": "daily",
                        "profile_offset": 0,
                        "task_count": 1,
                        "completed_count": 0,
                        "state": "failed",
                        "error": "fixture provider outage",
                        "recovery_action": "Resolve the provider or data blocker, then resume.",
                        "updated_at": "2026-08-15T00:01:00Z",
                        "execution_authority": False,
                    }
                ],
                "count": 1,
                "execution_authority": False,
                "next_action": "Resume only a failed batch.",
            }
        if command == "liquidity-freeze":
            return {
                "manifest_id": "c" * 64,
                "profile_id": profile_id,
                "session": "2026-08-14",
                "category": "spot",
                "quote_asset": "USDT",
                "universe_count": 1,
                "selected_count": 1,
                "state": "frozen",
                "execution_authority": False,
                "next_action": "Create a fresh profile.",
            }
        return {
            "profile_id": "d" * 64,
            "base_profile_id": profile_id,
            "selection_manifest_id": "e" * 64,
            "project_id": "f03802b8-df35-4f19-a90c-0b3437aa587d",
            "case_revision": "f" * 64,
            "selected_count": 1,
            "frequency": "1m",
            "acquisition_window": "previous_complete_hour",
            "state": "frozen",
            "execution_authority": False,
            "next_action": "Run the hourly page.",
        }

    monkeypatch.setattr(_catalog, "_run_json", project)
    monkeypatch.setattr(_invoke, "launch", launch)
    client = TestClient(create_app())

    assert client.get("/api/crypto-data/profiles").status_code == 200
    assert client.post("/api/crypto-data/profiles", json={"as_of": None}).status_code == 200
    page = client.get(
        f"/api/crypto-data/profiles/{profile_id}",
        params={"provider": "binance", "family": "market_bars", "frequency": "1d", "limit": 100},
    )
    assert page.status_code == 200, page.text
    assert page.json()["items"][0]["instrument"] == "BTCUSDT"
    run = client.post(
        f"/api/crypto-data/profiles/{profile_id}/batches",
        json={"cadence": "daily", "offset": 0, "limit": 25, "confirm": True},
    )
    assert run.status_code == 200
    assert client.get("/api/crypto-data/batches").status_code == 200
    assert (
        client.post(
            f"/api/crypto-data/batches/{batch_id}/resume", json={"confirm": True}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/crypto-data/profiles/{profile_id}/liquidity-membership",
            json={"category": "spot", "quote_asset": "USDT", "session": "2026-08-14", "limit": 250},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/crypto-data/profiles/{profile_id}/liquidity-membership",
            json={
                "category": "inverse",
                "quote_asset": "USDT",
                "session": "2026-08-14",
                "limit": 250,
            },
        ).status_code
        == 422
    )
    selected = client.post(
        f"/api/crypto-data/profiles/{profile_id}/one-minute-selection",
        json={
            "case_id": "f03802b8-df35-4f19-a90c-0b3437aa587d",
            "expected_case_revision": "f" * 64,
            "markets": ["spot:BTCUSDT"],
            "reason": "Inspect this bounded one-minute research window.",
        },
    )
    assert selected.status_code == 200, selected.text
    assert launch_calls == [
        [
            "crypto-data",
            "profile-run",
            profile_id,
            "--cadence",
            "daily",
            "--offset",
            "0",
            "--limit",
            "25",
            "--confirm",
            "--json",
        ],
        ["crypto-data", "profile-resume", batch_id, "--confirm", "--json"],
    ]
    assert project_calls[-2][1] == "liquidity-freeze"
    assert project_calls[-1][-5:] == [
        "--market",
        "spot:BTCUSDT",
        "--reason",
        "Inspect this bounded one-minute research window.",
        "--json",
    ]

    assert (
        client.post(
            f"/api/crypto-data/profiles/{profile_id}/batches",
            json={"cadence": "daily", "offset": 0, "limit": 26, "confirm": True},
        ).status_code
        == 422
    )
    assert client.get(f"/api/crypto-data/profiles/{'x' * 64}").status_code == 422


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


def test_crypto_asset_route_resolves_reviewed_xrp_and_rejects_unreviewed_doge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Real alpha subprocess: the reviewed native mapping is the CLI's, never the browser's.
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    client = TestClient(create_app())
    xrp = client.get("/api/crypto-data/assets/XRP", params={"as_of": "2024-01-01T00:00:00Z"})
    assert xrp.status_code == 200, xrp.text
    assert xrp.json()["coingecko_id"] == "ripple"

    doge = client.get("/api/crypto-data/assets/DOGE", params={"as_of": "2024-01-01T00:00:00Z"})
    assert doge.status_code == 422
    assert doge.json()["code"] == "request_invalid"
    assert "reviewed native mapping" in doge.json()["message"]

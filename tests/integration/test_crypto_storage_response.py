"""Strict storage response compatibility and the real read-only public CLI route."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from alpha_web.api.models import CryptoStorageResponse
from alpha_web.app import create_app


def _blocked() -> dict[str, Any]:
    return {
        "state": "blocked",
        "blocker": "bulk_storage_configuration_invalid",
        "bulk_root_label": "bulk",
        "manifest_count": 0,
        "cache_bytes": 0,
        "next_action": "Resolve the configured storage identity or capacity, then recheck.",
    }


@pytest.mark.parametrize("backend", ["macos_volume_uuid", "cloud_root_identity"])
@pytest.mark.parametrize("state", ["blocked", "metadata_ready", "artifact_ready"])
def test_strict_response_accepts_actual_cli_storage_shapes(backend: str, state: str) -> None:
    payload = {**_blocked(), "identity_backend": backend}
    if state != "blocked":
        payload.update(
            state="ready",
            blocker=None,
            verification="metadata_only" if state == "metadata_ready" else "artifact_verified",
            free_bytes=800,
            total_bytes=1000,
            reserve_fraction=0.15,
            minimum_free_bytes=100,
            manifest_count=1,
        )
    response = CryptoStorageResponse.model_validate(payload)
    assert response.identity_backend == backend
    assert response.state == ("blocked" if state == "blocked" else "ready")
    assert response.verification == (
        "not_checked" if state == "blocked" else payload["verification"]
    )


def test_older_storage_payload_has_unknown_backend_instead_of_invented_mac_identity() -> None:
    assert CryptoStorageResponse.model_validate(_blocked()).identity_backend is None


@pytest.mark.parametrize("mutation", ["unknown_backend", "private_path", "unknown_field"])
def test_response_remains_strict_for_unsupported_backends_or_extra_fields(mutation: str) -> None:
    payload = {**_blocked(), "identity_backend": "cloud_root_identity"}
    if mutation == "unknown_backend":
        payload["identity_backend"] = "s3"
    elif mutation == "private_path":
        payload["bulk_root"] = "/private/root"
    else:
        payload["unknown_storage_option"] = True
    with pytest.raises(ValidationError):
        CryptoStorageResponse.model_validate(payload)


def test_public_storage_route_accepts_real_cli_backend_field_without_server_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path / "private-control"))
    monkeypatch.setenv("ALPHA_BULK_DATA_DIR", str(tmp_path / "private-volume" / "bulk"))
    monkeypatch.setenv("ALPHA_BULK_STORAGE_BACKEND", "macos_volume_uuid")
    monkeypatch.setenv("ALPHA_BULK_VOLUME_UUID", "")
    for suffix in (
        "MOUNT_POINT",
        "DEVICE_ID",
        "OWNER_UID",
        "FILESYSTEM_TYPE",
        "MOUNT_SOURCE",
        "DURABILITY_REFERENCE",
    ):
        monkeypatch.delenv("ALPHA_BULK_CLOUD_" + suffix, raising=False)
    with TestClient(create_app()) as client:
        result = client.get("/api/crypto-data/storage")
    assert result.status_code == 200, result.text
    response = CryptoStorageResponse.model_validate(result.json())
    assert response.state == "blocked"
    assert response.identity_backend == "macos_volume_uuid"
    assert response.blocker == "bulk_volume_uuid_not_configured"
    assert str(tmp_path) not in result.text

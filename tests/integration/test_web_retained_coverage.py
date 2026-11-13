"""Production REST→CLI→retained evaluator with synthetic store, no provider calls."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from alpha_web import _catalog
from alpha_web.app import create_app
from tests.fixtures.retained_coverage_web_fixture import fingerprint, seed

REQUEST = {
    "coverage_start": "2024-01-01T00:00:00Z",
    "coverage_end": "2024-01-05T00:00:00Z",
    "as_of": "2024-01-05T00:00:00Z",
    "expected_cadence_seconds": 86400,
    "max_verify_artifact_bytes": 1_000_000,
}


@pytest.fixture
def retained_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    ids = seed(tmp_path)
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "retained_coverage_web_fixture.py"
    monkeypatch.setattr(
        _catalog,
        "_command",
        lambda args: [sys.executable, str(fixture), "cli", str(tmp_path), *args],
    )
    return TestClient(create_app()), ids, tmp_path


@pytest.mark.parametrize(
    "name,missing,conflicts,ok",
    [("gaps", 2, 0, False), ("full", 0, 0, True), ("conflict", 0, 1, False)],
)
def test_real_api_preserves_inspected_exit_one_and_native_findings(
    retained_api: Any, name: str, missing: int, conflicts: int, ok: bool
) -> None:
    client, ids, root = retained_api
    before = fingerprint(root)
    legacy = client.get("/api/crypto-data/quality/" + ids[name])
    assert legacy.status_code == 200
    response = client.post(
        "/api/crypto-data/quality/" + ids[name] + "/retained-coverage", json=REQUEST
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["row_audit"]["missing_slots"] == missing
    assert body["row_audit"]["conflicting_duplicate_groups"] == conflicts
    assert body["row_audit"]["declared_grid_satisfied"] is ok
    assert body["stored_quality"]["state"] == legacy.json()["quality"]["state"]
    assert body["source_retrieved_after_as_of"] is True
    assert (
        body["provider_history_complete"]
        is body["point_in_time_eligibility"]
        is body["execution_authority"]
        is False
    )
    assert fingerprint(root) == before


def test_resource_exhaustion_is_typed_unavailable_not_http_failure(retained_api: Any) -> None:
    client, ids, root = retained_api
    before = fingerprint(root)
    result = client.post(
        "/api/crypto-data/quality/" + ids["full"] + "/retained-coverage",
        json=REQUEST | {"max_verify_artifact_bytes": 1},
    )
    assert result.status_code == 200, result.text
    assert result.json()["audit_state"] == "unavailable" and result.json()["row_audit"] is None
    assert fingerprint(root) == before


@pytest.mark.parametrize(
    "changed",
    [
        {"as_of": "2024-01-01T00:00:00Z"},
        {"coverage_start": "2024-01-01"},
        {"expected_cadence_seconds": 3600},
        {"max_rows": 50001},
        {"max_verify_artifact_bytes": True},
        {"extra": "untrusted"},
    ],
)
def test_invalid_explicit_contract_does_not_launch(
    monkeypatch: pytest.MonkeyPatch, changed: dict[str, object]
) -> None:
    monkeypatch.setattr(
        _catalog, "_command", lambda _: pytest.fail("invalid request must not spawn")
    )
    result = TestClient(create_app()).post(
        "/api/crypto-data/quality/" + "a" * 64 + "/retained-coverage", json=REQUEST | changed
    )
    assert result.status_code == 422


@pytest.mark.parametrize(
    "failure", ["timeout", "invalid_json", "stderr", "wrong_identity", "exit_mismatch"]
)
def test_transport_errors_are_sanitized_not_success(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:

    secret = "PRIVATE_CANARY_MUST_NOT_REACH_BROWSER"

    def run(*args: Any, **kwargs: Any) -> Any:
        assert kwargs["timeout"] == 60.0
        assert "ALPHA_TIINGO_API_KEY" not in kwargs["env"]
        if failure == "timeout":
            raise subprocess.TimeoutExpired(secret, 60, output=secret, stderr=secret)
        payload = '{"manifest_id":"wrong"}' if failure == "wrong_identity" else secret
        if failure == "exit_mismatch":
            import json

            payload = json.dumps(
                {
                    "manifest_id": "a" * 64,
                    "audit_state": "unavailable",
                    "reason": "RETAINED_BAR_AUDIT_UNAVAILABLE",
                    "row_audit": None,
                    "stored_quality": None,
                    "limits": None,
                    "execution_authority": False,
                    "point_in_time_eligibility": False,
                    "provider_history_complete": False,
                    "inspection_provider_calls": 0,
                }
            )
        return subprocess.CompletedProcess(
            [], 2 if failure == "stderr" else 0, stdout=payload, stderr=secret
        )

    monkeypatch.setattr(subprocess, "run", run)
    response = TestClient(create_app()).post(
        "/api/crypto-data/quality/" + "a" * 64 + "/retained-coverage", json=REQUEST
    )
    assert response.status_code == 503
    assert secret not in response.text


@pytest.mark.parametrize("change", ["missing_identity", "wrong_grid"])
def test_relay_requires_explicit_identity_and_exact_requested_grid(
    retained_api: Any, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    import json

    client, ids, _ = retained_api
    url = "/api/crypto-data/quality/" + ids["full"] + "/retained-coverage"
    original = client.post(url, json=REQUEST)
    assert original.status_code == 200
    report = original.json()
    if change == "missing_identity":
        del report["manifest_id"]
    else:
        report["row_audit"]["start"] = "2023-01-01T00:00:00Z"
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 0, stdout=json.dumps(report), stderr=""
        ),
    )
    response = client.post(url, json=REQUEST)
    assert response.status_code == 503

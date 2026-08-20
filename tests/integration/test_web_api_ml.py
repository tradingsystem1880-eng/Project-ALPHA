"""Strict HTTP contracts for the Workstation ML control surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web import _ml
from alpha_web.app import create_app


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_readiness_and_strict_action_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _ml,
        "readiness",
        lambda **_: {
            "schema_version": 1,
            "worker_project_present": True,
            "worker_lock_present": True,
            "worker_environment_present": True,
            "worker_lock_hash": "a" * 64,
            "root_qlib_importable": False,
            "root_lightgbm_importable": False,
            "isolation_ready": True,
            "heavy_job_limit": 1,
            "heavy_job_busy": False,
            "supported_modes": ["fake", "real"],
        },
    )
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/ml/readiness")
    assert response.status_code == 200
    assert response.json()["isolation_ready"] is True

    rejected = client.post(
        "/api/ml/prepare",
        json={"input_bundle_id": "../secret", "unexpected": "field"},
    )
    assert rejected.status_code == 422


def test_frontend_status_and_experiment_aliases_are_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _ml,
        "service_status",
        lambda **_: {
            "available": True,
            "worker_ready": False,
            "isolation": "separate worker project and lock",
            "concurrency_limit": 1,
            "active_job_id": None,
            "min_symbols": 20,
            "min_aligned_sessions": 756,
            "message": "Project-to-panel producer is unavailable.",
        },
    )
    monkeypatch.setattr(
        _ml,
        "list_experiments",
        lambda **_: {"items": [], "limit": 50, "offset": 0, "has_more": False},
    )
    client = _client(tmp_path, monkeypatch)

    assert client.get("/api/ml/status").json()["worker_ready"] is False
    assert client.get("/api/ml/experiments?project_id=project-1").json()["items"] == []


def test_safe_ml_actions_return_only_durable_job_identifiers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    accepted = {
        "job_id": "00000000-0000-4000-8000-000000000001",
        "status": "queued",
        "action": "train",
        "exchange_id": "a" * 32,
    }
    monkeypatch.setattr(_ml, "launch_action", lambda *args, **kwargs: accepted)
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        f"/api/ml/exchanges/{'a' * 32}/train",
        json={"mode": "fake", "no_sync": True, "timeout_seconds": 600},
    )

    assert response.status_code == 202, response.text
    assert response.json() == accepted
    assert "/" not in response.text


def test_project_generation_post_returns_opaque_pipeline_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    accepted = {
        "job_id": "00000000-0000-4000-8000-000000000003",
        "status": "queued",
        "action": "generate-experiment",
        "project_id": "project-1",
        "experiment_id": "ex_" + "a" * 64,
        "input_bundle_id": "b" * 32,
        "exchange_id": "c" * 32,
    }
    monkeypatch.setattr(_ml, "experiment_preflight", lambda **kwargs: {"ready": True})
    monkeypatch.setattr(_ml, "launch_experiment_generation", lambda **kwargs: accepted)
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/ml/experiments", json={"project_id": "project-1"})

    assert response.status_code == 202, response.text
    assert response.json() == accepted
    assert "/" not in response.text


def test_project_generation_preflight_route_is_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projection = {
        "schema_version": 1,
        "project_id": "project-1",
        "experiment_id": None,
        "snapshot_id": None,
        "universe_count": 0,
        "aligned_sessions": 0,
        "active_job_id": None,
        "ready": False,
        "checks": [
            {
                "check_id": "experiment",
                "state": "blocked",
                "message": "No current immutable experiment is selected.",
                "recovery_action": "Create or select an experiment in Development Center.",
            }
        ],
    }
    monkeypatch.setattr(_ml, "experiment_preflight", lambda **_: projection)
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/ml/experiments/preflight?project_id=project-1")

    assert response.status_code == 200, response.text
    assert response.json() == projection


def test_project_generation_revalidates_preflight_before_creating_a_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _ml,
        "experiment_preflight",
        lambda **_: {
            "ready": False,
            "checks": [
                {
                    "state": "blocked",
                    "message": "The project research gate is still open.",
                }
            ],
        },
    )
    launched = False

    def launch(**kwargs: object) -> dict[str, object]:
        nonlocal launched
        launched = True
        return kwargs

    monkeypatch.setattr(_ml, "launch_experiment_generation", launch)
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/ml/experiments", json={"project_id": "project-1"})

    assert response.status_code == 422
    assert response.json()["code"] == "request_invalid"
    assert launched is False


def test_snapshot_input_generation_post_uses_opaque_bundle_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    accepted = {
        "job_id": "00000000-0000-4000-8000-000000000002",
        "status": "queued",
        "action": "export-input",
        "project_id": "project-1",
        "experiment_id": "ex_" + "a" * 64,
        "input_bundle_id": "b" * 32,
    }
    monkeypatch.setattr(_ml, "launch_input_generation", lambda **kwargs: accepted)
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/ml/inputs/generate",
        json={
            "project_id": "project-1",
            "experiment_id": "ex_" + "a" * 64,
            "input_bundle_id": "b" * 32,
        },
    )

    assert response.status_code == 202, response.text
    assert response.json() == accepted
    assert "/" not in response.text


def test_ml_page_limits_are_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/ml/exchanges?limit=101").status_code == 422
    response = client.get(f"/api/ml/exchanges/{'a' * 32}/tear-sheet?timeline_limit=2001")
    assert response.status_code == 422


def test_worker_result_route_never_exposes_a_model_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _ml,
        "exchange_result",
        lambda *args, **kwargs: {
            "status": "succeeded",
            "worker_kind": "qlib",
            "worker_implementation_version": "1.0.0",
            "prediction_rows": 2500,
            "prediction_sha256": "a" * 64,
            "diagnostic_only": True,
            "counterfactual_refit": False,
        },
    )

    response = _client(tmp_path, monkeypatch).get(f"/api/ml/exchanges/{'a' * 32}/result")

    assert response.status_code == 200
    assert set(response.json()) == {
        "status",
        "worker_kind",
        "worker_implementation_version",
        "prediction_rows",
        "prediction_sha256",
        "diagnostic_only",
        "counterfactual_refit",
    }

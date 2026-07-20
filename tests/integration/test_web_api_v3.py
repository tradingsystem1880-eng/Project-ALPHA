"""Versioned Workstation-v3 REST aliases and bounded run comparison."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web import _development, _ml
from alpha_web.app import create_app


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def _write_manifest(data_dir: Path, run_id: str, manifest: dict[str, object]) -> None:
    run_dir = data_dir / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_openapi_publishes_every_v3_alias_without_removing_legacy_routes() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]

    legacy_paths = [
        path
        for path in paths
        if path.startswith(("/api/projects", "/api/development", "/api/evidence"))
        or path.startswith("/api/stage-links")
        or path.startswith("/api/ml")
    ]
    assert legacy_paths
    for legacy_path in legacy_paths:
        alias = f"/api/v3{legacy_path.removeprefix('/api')}"
        assert legacy_path in paths
        assert alias in paths
        assert set(paths[alias]) == set(paths[legacy_path])

    for suffix in (
        "/runs/{run_id}/chart-bundle",
        "/runs/{run_id}/native-tearsheet",
        "/runs/{run_id}/portfolio-analytics",
        "/runs/{run_id}/forecast/paths",
    ):
        assert f"/api{suffix}" in paths
        assert f"/api/v3{suffix}" in paths

    assert "/api/v3/runs/compare" in paths
    comparison = paths["/api/v3/runs/compare"]["post"]
    assert comparison["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/RunComparisonRequest"
    )
    assert comparison["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/RunComparisonResponse"
    )


def test_project_and_ml_aliases_use_the_same_typed_handlers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_page = {"items": [], "limit": 7, "offset": 0, "has_more": False}
    monkeypatch.setattr(_development, "list_projects", lambda **_: project_page)
    readiness = {
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
        "supported_modes": ["fake"],
    }
    monkeypatch.setattr(_ml, "readiness", lambda **_: readiness)
    client = _client(tmp_path, monkeypatch)

    legacy_projects = client.get("/api/projects?limit=7")
    versioned_projects = client.get("/api/v3/projects?limit=7")
    assert versioned_projects.status_code == legacy_projects.status_code == 200
    assert versioned_projects.json() == legacy_projects.json() == project_page

    legacy_ml = client.get("/api/ml/readiness")
    versioned_ml = client.get("/api/v3/ml/readiness")
    assert versioned_ml.status_code == legacy_ml.status_code == 200
    assert versioned_ml.json() == legacy_ml.json() == readiness


def test_versioned_native_tearsheet_alias_matches_legacy_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "1111111111111111"
    _write_manifest(tmp_path, run_id, {"command": "backtest_run", "symbol": "SPY"})
    client = _client(tmp_path, monkeypatch)

    legacy = client.get(f"/api/runs/{run_id}/native-tearsheet?point_limit=17")
    versioned = client.get(f"/api/v3/runs/{run_id}/native-tearsheet?point_limit=17")

    assert versioned.status_code == legacy.status_code == 200
    assert versioned.json() == legacy.json()
    assert client.get(f"/api/v3/runs/{run_id}/native-tearsheet?point_limit=1").status_code == 422


def test_versioned_run_comparison_is_strict_bounded_and_cited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = "1111111111111111"
    second = "2222222222222222"
    snapshot_hash = "a" * 64
    _write_manifest(
        tmp_path,
        first,
        {
            "command": "backtest_run",
            "symbol": "SPY",
            "snapshot_id": "snap-1",
            "snapshot_hash": snapshot_hash,
            "passed": True,
            "metrics": {"sharpe": 1.25},
        },
    )
    _write_manifest(
        tmp_path,
        second,
        {
            "command": "backtest_run",
            "symbol": "QQQ",
            "snapshot_id": "snap-1",
            "snapshot_hash": snapshot_hash,
            "passed": False,
            "oos_metrics": {"sharpe": 0.75},
        },
    )
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/v3/runs/compare", json={"run_ids": [first, second]})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run_ids"] == [first, second]
    assert body["same_snapshot_hash"] is True
    assert [row["run_id"] for row in body["rows"]] == [first, second]
    assert body["rows"][0]["metrics"] == [
        {
            "name": "sharpe",
            "value": 1.25,
            "unit": "ratio",
            "source_artifact": "manifest.json",
            "source_field": "metrics.sharpe",
        }
    ]

    rejected_payloads = (
        {"run_ids": [first]},
        {"run_ids": [first, first]},
        {"run_ids": [first, second], "raw_sql": "select *"},
        {"run_ids": [first, "NOT-A-RUN-ID"]},
        {"run_ids": [f"{index:016x}" for index in range(9)]},
    )
    for payload in rejected_payloads:
        assert client.post("/api/v3/runs/compare", json=payload).status_code == 422

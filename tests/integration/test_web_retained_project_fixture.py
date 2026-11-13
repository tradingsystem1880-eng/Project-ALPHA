"""Real project and quality read composition over disposable synthetic records only."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from alpha_web import _catalog
from alpha_web.app import create_app
from tests.fixtures.retained_coverage_web_fixture import cli, fingerprint, seed, seed_projects
from tests.integration.test_web_retained_coverage import REQUEST


@pytest.fixture
def project_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    ids = seed(tmp_path)
    projects = seed_projects(tmp_path)
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    script = Path(__file__).resolve().parents[1] / "fixtures/retained_coverage_web_fixture.py"
    calls: list[list[str]] = []

    def command(args: list[str]) -> list[str]:
        calls.append(args)
        return [sys.executable, str(script), "cli", str(tmp_path), *args]

    monkeypatch.setattr(_catalog, "_command", command)
    return TestClient(create_app()), ids, projects, tmp_path, calls


def test_supported_synthetic_project_inventory_selection_and_retained_result(
    project_api: Any,
) -> None:
    client, ids, projects, root, calls = project_api
    listed = client.get("/api/projects?limit=50&offset=0")
    cases = client.get("/api/research/cases?limit=50&offset=0")
    assert listed.status_code == cases.status_code == 200
    assert {r["project_id"] for r in listed.json()["items"]} == set(projects.values())
    assert {r["case_id"] for r in cases.json()["items"]} == set(projects.values())
    for identity in projects.values():
        case = client.get("/api/research/cases/" + identity)
        assert case.status_code == 200
        assert case.json()["attempt_count"] == 0 and case.json()["active_job_id"] is None
        options = client.get("/api/research/cases/" + identity + "/proposal-options")
        assert options.status_code == 200
    before = {k: v for k, v in fingerprint(root).items() if k.startswith(("crypto/", "bulk/"))}
    response = client.post(
        "/api/crypto-data/quality/" + ids["gaps"] + "/retained-coverage", json=REQUEST
    )
    assert response.status_code == 200
    assert response.json()["row_audit"]["missing_slots"] == 2
    assert response.json()["execution_authority"] is False
    after = {k: v for k, v in fingerprint(root).items() if k.startswith(("crypto/", "bulk/"))}
    assert after == before
    assert client.get("/api/projects?limit=50&offset=0").json() == listed.json()
    assert not any("acquire" in args or "capture" in args for args in calls)


@pytest.mark.parametrize(
    "args", [["project", "create"], ["research", "capture"], ["research", "data", "register"]]
)
def test_fixture_runtime_cannot_create_projects_cases_or_admit_data(
    tmp_path: Path, args: list[str]
) -> None:
    before = Path.cwd()
    with pytest.raises(ValueError, match="closed read-only"):
        cli(tmp_path, args)
    assert Path.cwd() == before and list(tmp_path.iterdir()) == []

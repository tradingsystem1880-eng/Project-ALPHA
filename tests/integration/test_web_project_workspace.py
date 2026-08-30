"""REST parity for non-authoritative strategy-project workspaces."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alpha_cli.main import app as alpha_app
from alpha_web.app import create_app


def test_project_workspace_get_and_refresh_have_exact_cli_parity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    client = TestClient(create_app())
    created = client.post(
        "/api/projects",
        json={
            "name": "BTC workspace parity",
            "hypothesis": "A bounded event effect may exist.",
            "falsification_criterion": "Reject on an inconclusive locked result.",
        },
    )
    assert created.status_code == 200, created.text
    project_id = str(created.json()["project_id"])

    direct = CliRunner().invoke(alpha_app, ["project", "workspace", "show", project_id, "--json"])
    assert direct.exit_code == 0, direct.output
    response = client.get(f"/api/projects/{project_id}/workspace")
    assert response.status_code == 200, response.text
    assert response.json() == json.loads(direct.output)

    refreshed = client.post(f"/api/projects/{project_id}/workspace/refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["changed"] is False
    assert refreshed.json()["workspace"]["authority"] == "none"
    assert refreshed.json()["workspace"]["execution_authority"] is False


def test_project_workspace_unknown_project_is_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    response = TestClient(create_app()).get(
        "/api/projects/00000000-0000-4000-8000-000000000999/workspace"
    )
    assert response.status_code == 404

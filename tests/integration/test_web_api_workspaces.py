"""``/api/workspaces`` — save / list / load / delete named Dockview layouts."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_save_list_get_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/workspaces").json() == []
    saved = client.post(
        "/api/workspaces",
        json={
            "name": "Research Desk",
            "linked_context": {"symbol": "SPY"},
            "dockview": {"grid": {"root": 1}},
        },
    ).json()
    assert saved["slug"] == "research-desk"

    listed = client.get("/api/workspaces").json()
    assert len(listed) == 1 and listed[0]["name"] == "Research Desk"

    doc = client.get("/api/workspaces/research-desk").json()
    assert doc["dockview"] == {"grid": {"root": 1}}
    assert doc["linked_context"]["symbol"] == "SPY"

    assert client.delete("/api/workspaces/research-desk").status_code == 200
    assert client.get("/api/workspaces").json() == []


def test_get_unknown_is_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _client(tmp_path, monkeypatch).get("/api/workspaces/nope").status_code == 404


def test_unusable_name_is_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _client(tmp_path, monkeypatch).post(
        "/api/workspaces", json={"name": "!!!", "dockview": {}}
    )
    assert resp.status_code == 422


def test_invalid_path_slug_is_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/workspaces/Not_Valid").status_code == 422
    assert client.delete("/api/workspaces/Not_Valid").status_code == 422

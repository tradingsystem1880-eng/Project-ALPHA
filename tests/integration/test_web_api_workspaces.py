"""``/api/workspaces`` — save / list / load / delete named Dockview layouts."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web import _workspaces
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


def test_save_and_restore_v3_linked_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    linked = {
        "schemaVersion": 3,
        "linkGroup": "C",
        "projectId": "project-context",
        "versionId": "version-context",
        "symbol": "AAPL",
        "universe": "US-LIQUID-50",
        "timeframe": "1D",
        "start": "2024-01-01",
        "end": "2026-06-30",
        "snapshotId": "snapshot-context",
        "runId": "0123456789abcdef",
    }
    saved = client.post(
        "/api/workspaces",
        json={"name": "V3 Desk", "linked_context": linked, "dockview": {"grid": {}}},
    )
    assert saved.status_code == 200, saved.text
    restored = client.get("/api/workspaces/v3-desk")
    assert restored.status_code == 200, restored.text
    assert restored.json()["linked_context"] == linked

    legacy = client.post(
        "/api/workspaces",
        json={
            "name": "Legacy Desk",
            "linked_context": {"symbol": "SPY", "runId": None},
            "dockview": {},
        },
    )
    assert legacy.status_code == 200, legacy.text
    migrated = client.get("/api/workspaces/legacy-desk").json()["linked_context"]
    assert migrated["symbol"] == "SPY"
    assert migrated["schemaVersion"] == 3
    assert migrated["linkGroup"] == "A"
    assert migrated["timeframe"] == "1D"


def test_save_and_restore_grouped_v3_linked_context_and_panel_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    linked = {
        "schemaVersion": 3,
        "linkGroup": "B",
        "projectId": None,
        "versionId": None,
        "symbol": "MSFT",
        "universe": None,
        "timeframe": "1D",
        "start": None,
        "end": None,
        "snapshotId": "snapshot-b",
        "runId": "run-b",
        "groups": {
            "A": {"symbol": "AAPL", "runId": "run-a"},
            "B": {"symbol": "MSFT", "snapshotId": "snapshot-b", "runId": "run-b"},
            "C": {"symbol": "BTC-USD"},
            "D": {},
        },
    }
    dockview = {
        "panels": {
            "price": {
                "params": {
                    "linkBinding": {
                        "mode": "pinned-to-group",
                        "group": "A",
                        "local": {"symbol": "SPY", "timeframe": "1D"},
                    }
                }
            }
        }
    }

    saved = client.post(
        "/api/workspaces",
        json={"name": "Grouped Desk", "linked_context": linked, "dockview": dockview},
    )
    assert saved.status_code == 200, saved.text
    restored = client.get("/api/workspaces/grouped-desk")
    assert restored.status_code == 200, restored.text
    body = restored.json()
    restored_linked = body["linked_context"]
    assert {key: value for key, value in restored_linked.items() if key != "groups"} == {
        key: value for key, value in linked.items() if key != "groups"
    }
    assert restored_linked["groups"]["A"]["symbol"] == "AAPL"
    assert restored_linked["groups"]["A"]["runId"] == "run-a"
    assert restored_linked["groups"]["B"]["snapshotId"] == "snapshot-b"
    assert restored_linked["groups"]["C"]["symbol"] == "BTC-USD"
    assert restored_linked["groups"]["D"]["timeframe"] == "1D"
    assert body["dockview"] == dockview


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


def test_failed_workspace_replace_preserves_prior_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = {"name": "Desk", "linked_context": {}, "dockview": {"version": 1}}
    _workspaces.save_workspace("desk", original, data_dir=tmp_path)
    original_write = Path.write_text

    def fail_write(path: Path, content: str, **kwargs: object) -> int:
        original_write(path, "partial", encoding="utf-8")
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", fail_write)
    with pytest.raises(OSError, match="disk full"):
        _workspaces.save_workspace(
            "desk",
            {"name": "Desk", "linked_context": {}, "dockview": {"version": 2}},
            data_dir=tmp_path,
        )
    monkeypatch.undo()

    assert _workspaces.get_workspace("desk", data_dir=tmp_path) == original
    assert list((tmp_path / "web" / "workspaces").glob(".*.tmp")) == []


def test_concurrent_workspace_writers_leave_one_complete_document(tmp_path: Path) -> None:
    docs = [
        {"name": "Desk", "linked_context": {}, "dockview": {"version": version}}
        for version in range(8)
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda doc: _workspaces.save_workspace("desk", doc, data_dir=tmp_path), docs))

    final = _workspaces.get_workspace("desk", data_dir=tmp_path)
    assert final in docs
    path = tmp_path / "web" / "workspaces" / "desk.json"
    assert json.loads(path.read_text(encoding="utf-8")) == final
    assert list(path.parent.glob(".*.tmp")) == []

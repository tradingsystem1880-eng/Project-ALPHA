"""``/api/rules`` — the Strategy Builder's saved rule sets, relayed from ``alpha rules``."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app

TREND = {
    "name": "trend",
    "history": 40,
    "long_when": [
        {
            "left": {"indicator": "sma", "params": [5]},
            "op": ">",
            "right": {"indicator": "sma", "params": [20]},
        }
    ],
    "short_when": [],
}


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_rules_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/rules").json() == {"rules": [], "authority": "none"}
    check = client.post("/api/rules/validate", json={"spec": TREND})
    assert check.status_code == 200 and check.json()["valid"] is True
    bad = client.post("/api/rules/validate", json={"spec": {"name": "x"}})
    assert bad.status_code == 200
    assert bad.json()["valid"] is False and "at least one condition" in bad.json()["error"]
    saved = client.post("/api/rules", json={"name": "trend", "spec": TREND})
    assert saved.status_code == 200, saved.text
    assert saved.json()["long_conditions"] == ["sma:5 > sma:20"]
    assert (tmp_path / "rules" / "trend.json").is_file()
    listed = client.get("/api/rules").json()["rules"]
    assert [row["name"] for row in listed] == ["trend"]
    assert client.get("/api/rules/trend").json()["spec"]["name"] == "trend"
    assert client.get("/api/rules/nope").status_code == 404
    assert client.post("/api/rules", json={"name": "Bad Name", "spec": TREND}).status_code == 400
    assert client.post("/api/rules", json={"name": "x", "spec": {"name": "x"}}).status_code == 400
    assert client.delete("/api/rules/trend").json() == {"name": "trend", "deleted": True}
    assert client.delete("/api/rules/trend").status_code == 404

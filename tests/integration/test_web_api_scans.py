"""``/api/scans`` + ``/api/alerts`` — rule scans relayed from ``alpha scan`` (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alpha_cli.main import app as cli
from alpha_web.app import create_app
from tests.fixtures.cli_fixtures import seed_store

TREND = json.dumps(
    {
        "name": "trend",
        "history": 40,
        "long_when": [
            {
                "left": {"indicator": "sma", "params": [5]},
                "op": ">",
                "right": {"indicator": "sma", "params": [20]},
            }
        ],
    }
)


def test_scans_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="UP", n=80, drift=0.01, sigma=0.001)
    assert CliRunner().invoke(cli, ["rules", "save", "trend", "--spec", TREND]).exit_code == 0
    client = TestClient(create_app())
    assert client.get("/api/scans").json() == {"scans": [], "authority": "none"}
    assert client.post("/api/scans", json={"name": "s", "rules": "nope"}).status_code == 400
    saved = client.post(
        "/api/scans", json={"name": "s", "rules": "trend", "symbols": ["UP", "NOPE"]}
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["universe"] == {"kind": "list", "symbols": ["NOPE", "UP"]}
    ran = client.post("/api/scans/s/run", json={})
    assert ran.status_code == 200, ran.text
    body = ran.json()
    assert [row["symbol"] for row in body["rows"]] == ["UP"] and body["rows"][0]["signal"] == 1
    assert body["skipped"][0]["symbol"] == "NOPE"
    assert client.post("/api/scans/s/run", json={"as_of": "bad"}).status_code == 400
    checked = client.post("/api/scans/check")
    assert checked.status_code == 200 and len(checked.json()["alerts"]) == 1
    assert client.post("/api/scans/s/check").json()["alerts"] == []
    alerts = client.get("/api/alerts", params={"limit": 5}).json()["alerts"]
    assert [a["symbol"] for a in alerts] == ["UP"]
    assert client.get("/api/alerts", params={"limit": 0}).status_code == 422
    assert client.get("/api/scans/s").json()["checked_at"] is None  # show reads the file only
    assert client.get("/api/scans").json()["scans"][0]["checked_at"]
    assert client.delete("/api/scans/s").json() == {"name": "s", "deleted": True}
    assert client.get("/api/scans/s").status_code == 404

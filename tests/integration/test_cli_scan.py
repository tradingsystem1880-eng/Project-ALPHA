"""``alpha scan`` lifecycle through the CLI (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()
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


def test_scan_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="UP", n=80, drift=0.01, sigma=0.001)
    assert json.loads(runner.invoke(app, ["scan", "list", "--json"]).stdout) == {
        "scans": [],
        "authority": "none",
    }
    missing_rules = runner.invoke(app, ["scan", "save", "s", "--rules", "trend"])
    assert missing_rules.exit_code == 2 and "no saved rule" in missing_rules.output
    assert runner.invoke(app, ["rules", "save", "trend", "--spec", TREND]).exit_code == 0
    saved = runner.invoke(app, ["scan", "save", "s", "--rules", "trend", "--json"])
    assert saved.exit_code == 0, saved.output
    assert json.loads(saved.stdout) == {
        "name": "s",
        "rules": "trend",
        "universe": {"kind": "stored"},
        "checked_at": None,
    }
    listed = json.loads(runner.invoke(app, ["scan", "list", "--json"]).stdout)["scans"]
    assert listed[0]["name"] == "s" and listed[0]["checked_at"] is None
    shown = json.loads(runner.invoke(app, ["scan", "show", "s", "--json"]).stdout)
    assert shown["universe"] == {"kind": "stored"}
    ran = runner.invoke(app, ["scan", "run", "s", "--json"])
    assert ran.exit_code == 0, ran.output
    assert [row["symbol"] for row in json.loads(ran.stdout)["rows"]] == ["UP"]
    assert runner.invoke(app, ["scan", "run", "s", "--as-of", "nope"]).exit_code == 2
    text = runner.invoke(app, ["scan", "run", "s"])
    assert "UP: +1 on" in text.output
    checked = runner.invoke(app, ["scan", "check", "--json"])
    assert checked.exit_code == 0, checked.output
    payload = json.loads(checked.stdout)
    assert len(payload["alerts"]) == 1 and payload["checks"][0]["scan"] == "s"
    assert json.loads(runner.invoke(app, ["scan", "list", "--json"]).stdout)["scans"][0][
        "checked_at"
    ]
    again = json.loads(runner.invoke(app, ["scan", "check", "s", "--json"]).stdout)
    assert again["alerts"] == []
    alerts = json.loads(runner.invoke(app, ["scan", "alerts", "--json"]).stdout)["alerts"]
    assert [(a["scan"], a["symbol"], a["signal"]) for a in alerts] == [("s", "UP", 1)]
    assert runner.invoke(app, ["scan", "delete", "s", "--json"]).exit_code == 0
    assert runner.invoke(app, ["scan", "show", "s"]).exit_code == 2
    assert json.loads(runner.invoke(app, ["scan", "alerts", "--json"]).stdout)[
        "alerts"
    ]  # log survives

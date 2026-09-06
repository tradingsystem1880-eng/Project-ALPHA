"""``alpha_cli.scan_cmds`` engine: strict scan shape, PIT rows, deduplicated alerts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli import scan_cmds
from alpha_cli.main import app
from alpha_core import DataError
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
        "short_when": [
            {
                "left": {"indicator": "sma", "params": [5]},
                "op": "<",
                "right": {"indicator": "sma", "params": [20]},
            }
        ],
    }
)


def _seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="UP", n=80, drift=0.01, sigma=0.001)
    seed_store(tmp_path, symbol="DOWN", n=80, drift=-0.01, sigma=0.001)
    seed_store(tmp_path, symbol="SHORT", n=10)
    assert runner.invoke(app, ["rules", "save", "trend", "--spec", TREND]).exit_code == 0


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("x", "must be an object"),
        ({"name": "s", "rules": "r", "universe": {"kind": "stored"}, "x": 1}, "unknown keys"),
        ({"name": "Bad", "rules": "r", "universe": {"kind": "stored"}}, "lowercase slug"),
        ({"name": "s", "rules": "R!", "universe": {"kind": "stored"}}, "saved rule set"),
        ({"name": "s", "rules": "r", "universe": {"kind": "all"}}, "universe must be"),
        (
            {"name": "s", "rules": "r", "universe": {"kind": "list", "symbols": []}},
            "non-empty list",
        ),
        (
            {"name": "s", "rules": "r", "universe": {"kind": "list", "symbols": ["A"], "x": 1}},
            "allows only kind and symbols",
        ),
        (
            {"name": "s", "rules": "r", "universe": {"kind": "stored", "symbols": ["A"]}},
            "allows only kind",
        ),
    ],
)
def test_validate_scan_rejects_defects(payload: object, message: str) -> None:
    with pytest.raises(DataError, match=message):
        scan_cmds.validate_scan(payload)


def test_validate_scan_normalises_the_symbol_list() -> None:
    scan = scan_cmds.validate_scan(
        {"name": "s", "rules": "r", "universe": {"kind": "list", "symbols": [" B ", "A", "B"]}}
    )
    assert scan["universe"] == {"kind": "list", "symbols": ["A", "B"]}


def test_run_scan_reports_signals_and_skips_short_histories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(tmp_path, monkeypatch)
    scan = scan_cmds.validate_scan(
        {"name": "all", "rules": "trend", "universe": {"kind": "stored"}}
    )
    result = scan_cmds.run_scan(scan, data_dir=tmp_path, as_of=None)
    by_symbol = {row["symbol"]: row for row in result["rows"]}
    assert by_symbol["UP"]["signal"] == 1 and by_symbol["DOWN"]["signal"] == -1
    assert set(by_symbol["UP"]["values"]) == {"sma:5", "sma:20"}
    assert by_symbol["UP"]["bar_date"] == "2020-03-20"
    assert result["skipped"] == [
        {"symbol": "SHORT", "reason": "10 bars stored, the rule set needs 40"}
    ]
    assert result["authority"] == "none" and result["as_of"] is None
    again = scan_cmds.run_scan(scan, data_dir=tmp_path, as_of=None)
    assert again["rows"] == result["rows"]  # deterministic given the data


def test_diff_alerts_only_reports_changes() -> None:
    rows = [
        {"symbol": "A", "signal": 1, "bar_date": "d", "close": 1.0},
        {"symbol": "B", "signal": 0, "bar_date": "d", "close": 1.0},
        {"symbol": "C", "signal": -1, "bar_date": "d", "close": 1.0},
        {"symbol": "D", "signal": 1, "bar_date": "d", "close": 1.0},
    ]
    previous = {"A": {"signal": 1}, "C": {"signal": 1}, "D": {"signal": 0}}
    alerts = scan_cmds.diff_alerts(previous, rows, scan="s", checked_at="t")
    assert [(a["symbol"], a["previous"], a["signal"]) for a in alerts] == [
        ("C", 1, -1),
        ("D", 0, 1),
    ]
    # first sighting: a non-zero signal alerts, a flat one does not
    first = scan_cmds.diff_alerts({}, rows, scan="s", checked_at="t")
    assert [a["symbol"] for a in first] == ["A", "C", "D"]


def test_check_scan_appends_alerts_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path, monkeypatch)
    scan = scan_cmds.validate_scan(
        {"name": "all", "rules": "trend", "universe": {"kind": "list", "symbols": ["UP", "DOWN"]}}
    )
    first = scan_cmds.check_scan(scan, data_dir=tmp_path)
    assert [(a["symbol"], a["signal"]) for a in first["alerts"]] == [("DOWN", -1), ("UP", 1)]
    second = scan_cmds.check_scan(scan, data_dir=tmp_path)
    assert second["alerts"] == [] and second["rows"] == 2
    log = scan_cmds.read_alerts(tmp_path, limit=10)
    assert len(log) == 2 and log[0]["scan"] == "all"
    assert scan_cmds.read_alerts(tmp_path, limit=1) == log[-1:]

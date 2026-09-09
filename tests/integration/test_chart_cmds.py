"""``alpha chart overlays --json`` — the terminal's indicator/pattern projection (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.info_cmds import _command_catalog
from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()


def test_overlays_json_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=90)
    result = runner.invoke(
        app,
        ["chart", "overlays", "SPY", "-i", "sma:20", "-i", "rsi:14", "-p", "swings", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["symbol"] == "SPY" and payload["authority"] == "none"
    assert payload["provenance"]["timeframe"] == "1D"
    assert len(payload["t"]) == 90
    assert [s["id"] for s in payload["indicators"]] == ["sma:20", "rsi:14"]
    assert all(len(s["values"]) == 90 for s in payload["indicators"])
    assert all(a["label"].startswith("Swing") for a in payload["annotations"])


def test_overlays_end_is_an_as_of_cutoff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=90)  # daily bars from 2020-01-01
    result = runner.invoke(
        app, ["chart", "overlays", "SPY", "--end", "2020-02-29", "-i", "sma:5", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert len(payload["t"]) == 60
    assert payload["provenance"]["knowledge_cutoff"] == "2020-02-29T23:59:59.999999+00:00"


def test_overlays_text_summary_and_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=30)
    ok = runner.invoke(app, ["chart", "overlays", "SPY", "-i", "sma:5"])
    assert ok.exit_code == 0 and "SPY: 30 bars, 1 series, 0 annotations" in ok.output
    assert runner.invoke(app, ["chart", "overlays", "NOPE", "--json"]).exit_code != 0
    bad = runner.invoke(app, ["chart", "overlays", "SPY", "-i", "sma:50", "--json"])
    assert bad.exit_code == 2 and "needs more than 50 bars" in bad.output
    assert runner.invoke(app, ["chart", "overlays", "SPY", "-p", "cups", "--json"]).exit_code == 2
    assert runner.invoke(app, ["chart", "overlays", "SPY", "--end", "nope"]).exit_code == 2


def test_chart_is_not_offered_as_a_run_command() -> None:
    assert not any(entry["id"].startswith("chart") for entry in _command_catalog())

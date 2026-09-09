"""``alpha rules`` and ``alpha backtest run --strategy rules --rules NAME`` (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_cli.rules_cmds import resolve_rules_spec
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


def test_rules_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    empty = runner.invoke(app, ["rules", "list", "--json"])
    assert json.loads(empty.stdout) == {"rules": [], "authority": "none"}
    valid = runner.invoke(app, ["rules", "validate", "--spec", TREND, "--json"])
    assert valid.exit_code == 0, valid.output
    assert json.loads(valid.stdout)["valid"] is True
    invalid = runner.invoke(app, ["rules", "validate", "--spec", '{"name": "x"}'])
    assert invalid.exit_code == 2 and "at least one condition" in invalid.output
    saved = runner.invoke(app, ["rules", "save", "trend", "--spec", TREND, "--json"])
    assert saved.exit_code == 0, saved.output
    record = json.loads(saved.stdout)
    assert record["name"] == "trend" and record["long_conditions"] == ["sma:5 > sma:20"]
    assert (tmp_path / "rules" / "trend.json").read_text().endswith("\n")
    listed = json.loads(runner.invoke(app, ["rules", "list", "--json"]).stdout)["rules"]
    assert [row["name"] for row in listed] == ["trend"] and listed[0]["sha256"] == record["sha256"]
    shown = json.loads(runner.invoke(app, ["rules", "show", "trend", "--json"]).stdout)
    assert shown["spec"] == record["spec"]
    assert runner.invoke(app, ["rules", "show", "nope"]).exit_code == 2
    assert runner.invoke(app, ["rules", "save", "Bad Name", "--spec", TREND]).exit_code == 2
    assert (
        runner.invoke(app, ["rules", "save", "x", "--spec", TREND, "--file", "a.json"]).exit_code
        == 2
    )
    (tmp_path / "rules" / "broken.json").write_text("{}", encoding="utf-8")
    rows = json.loads(runner.invoke(app, ["rules", "list", "--json"]).stdout)["rules"]
    assert [row["name"] for row in rows] == ["broken", "trend"] and "error" in rows[0]
    assert runner.invoke(app, ["rules", "delete", "trend", "--json"]).exit_code == 0
    assert not (tmp_path / "rules" / "trend.json").exists()
    assert runner.invoke(app, ["rules", "delete", "trend"]).exit_code == 2


def test_resolve_rules_spec_pairs_strategy_and_flag(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="needs --rules"):
        resolve_rules_spec("rules", None, tmp_path)
    with pytest.raises(DataError, match="only applies to --strategy rules"):
        resolve_rules_spec("ts_momentum", "trend", tmp_path)
    with pytest.raises(DataError, match="no saved rule"):
        resolve_rules_spec("rules", "trend", tmp_path)
    assert resolve_rules_spec("breakout", None, tmp_path) is None


def test_validate_runs_the_gauntlet_on_a_saved_rule_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=220)
    assert runner.invoke(app, ["rules", "save", "trend", "--spec", TREND]).exit_code == 0
    result = runner.invoke(
        app,
        [
            "validate",
            "SPY",
            "--strategy",
            "rules",
            "--rules",
            "trend",
            "--vol-window",
            "10",
            "--rebalance-every",
            "1",
            "--account-type",
            "MARGIN",
            "--train-size",
            "60",
            "--test-size",
            "20",
            "--embargo",
            "2",
            "--tier1-paths",
            "20",
            "--tier2-paths",
            "2",
            "--n-resamples",
            "50",
        ],
    )
    assert result.exit_code == 0, result.output
    run_id = result.output.split("run ")[1].split(":")[0].strip()
    manifest = json.loads((tmp_path / "runs" / run_id / "manifest.json").read_text())
    assert manifest["metadata"]["strategy_name"] == "rules"
    assert json.loads(manifest["rules_spec"])["name"] == "trend"
    assert manifest["verdict"] and "nulls" in manifest


def test_backtest_run_with_saved_rules_records_the_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=120)
    assert runner.invoke(app, ["rules", "save", "trend", "--spec", TREND]).exit_code == 0
    result = runner.invoke(
        app,
        [
            "backtest",
            "run",
            "SPY",
            "--strategy",
            "rules",
            "--rules",
            "trend",
            "--vol-window",
            "10",
            "--rebalance-every",
            "1",
            "--account-type",
            "MARGIN",
        ],
    )
    assert result.exit_code == 0, result.output
    run_id = result.output.split("run ")[1].split(":")[0]
    manifest = json.loads((tmp_path / "runs" / run_id / "manifest.json").read_text())
    saved = json.loads((tmp_path / "rules" / "trend.json").read_text())
    assert manifest["params"]["strategy_name"] == "rules"
    assert json.loads(manifest["params"]["rules_spec"]) == saved
    assert manifest["fills"] > 0
    missing = runner.invoke(app, ["backtest", "run", "SPY", "--strategy", "rules"])
    assert missing.exit_code == 2 and "needs --rules" in missing.output
    wrong = runner.invoke(app, ["backtest", "run", "SPY", "--rules", "trend"])
    assert wrong.exit_code == 2 and "only applies" in wrong.output

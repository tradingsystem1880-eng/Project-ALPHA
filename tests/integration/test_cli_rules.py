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


@pytest.mark.parametrize("frozen", [False, True])
def test_validate_runs_the_gauntlet_on_a_saved_rule_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, frozen: bool
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=220)
    assert runner.invoke(app, ["rules", "save", "trend", "--spec", TREND]).exit_code == 0
    rule_args = ["--rules", "trend"]
    if frozen:
        import hashlib

        text = resolve_rules_spec("rules", "trend", tmp_path)
        assert text is not None
        path = tmp_path / "frozen.json"
        path.write_text(text)
        rule_args = [
            "--rules-file",
            str(path),
            "--rules-sha256",
            hashlib.sha256(text.encode()).hexdigest(),
        ]
        # Changing the saved name after freezing cannot affect either execution.
        (tmp_path / "rules" / "trend.json").write_text("{}")
    result = runner.invoke(
        app,
        [
            "validate",
            "SPY",
            "--strategy",
            "rules",
            *rule_args,
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
            "--tier3-paths",
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


@pytest.mark.parametrize("frozen", [False, True])
def test_backtest_run_with_saved_rules_records_the_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, frozen: bool
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=120)
    assert runner.invoke(app, ["rules", "save", "trend", "--spec", TREND]).exit_code == 0
    rule_args = ["--rules", "trend"]
    if frozen:
        import hashlib

        text = resolve_rules_spec("rules", "trend", tmp_path)
        assert text is not None
        path = tmp_path / "frozen.json"
        path.write_text(text)
        rule_args = [
            "--rules-file",
            str(path),
            "--rules-sha256",
            hashlib.sha256(text.encode()).hexdigest(),
        ]
        # Changing the saved name after freezing cannot affect either execution.
        (tmp_path / "rules" / "trend.json").write_text("{}")
    result = runner.invoke(
        app,
        [
            "backtest",
            "run",
            "SPY",
            "--strategy",
            "rules",
            *rule_args,
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
    if frozen:
        assert text is not None
    saved = json.loads(
        text if frozen and text is not None else (tmp_path / "rules" / "trend.json").read_text()
    )
    assert manifest["params"]["strategy_name"] == "rules"
    assert json.loads(manifest["params"]["rules_spec"]) == saved
    assert manifest["fills"] > 0
    missing = runner.invoke(app, ["backtest", "run", "SPY", "--strategy", "rules"])
    assert missing.exit_code == 2 and "needs --rules" in missing.output
    wrong = runner.invoke(app, ["backtest", "run", "SPY", "--rules", "trend"])
    assert wrong.exit_code == 2 and "only applies" in wrong.output


def test_frozen_rule_file_binds_exact_bytes(tmp_path: Path) -> None:
    import hashlib

    from alpha_strategies.rules import canonical_json, rule_spec_from_json

    text = canonical_json(rule_spec_from_json(TREND))
    path = tmp_path / "frozen.json"
    path.write_text(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    assert resolve_rules_spec("rules", None, tmp_path, rules_file=path, rules_sha256=digest) == text
    path.write_text(text + "\n")
    with pytest.raises(DataError, match="hash mismatch"):
        resolve_rules_spec("rules", None, tmp_path, rules_file=path, rules_sha256=digest)


@pytest.mark.parametrize(
    "strategy,name,file,sha",
    [
        ("rules", "trend", True, "a" * 64),
        ("rules", None, True, None),
        ("rules", None, False, "a" * 64),
        ("rules", None, True, "bad"),
        ("ts_momentum", None, True, "a" * 64),
    ],
)
def test_frozen_rule_inputs_fail_closed(
    tmp_path: Path, strategy: str, name: str | None, file: bool, sha: str | None
) -> None:
    with pytest.raises(DataError):
        resolve_rules_spec(
            strategy,
            name,
            tmp_path,
            rules_file=tmp_path / "missing" if file else None,
            rules_sha256=sha,
        )


@pytest.mark.parametrize("prefix", [["backtest", "run"], ["validate"]])
def test_frozen_rule_hash_fails_before_data_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prefix: list[str]
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    path = tmp_path / "frozen.json"
    path.write_text(TREND)
    result = runner.invoke(
        app,
        [
            *prefix,
            "MISSING",
            "--strategy",
            "rules",
            "--rules-file",
            str(path),
            "--rules-sha256",
            "a" * 64,
        ],
    )
    assert result.exit_code == 2 and "hash mismatch" in result.output
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize(
    "raw", [b"{}", b"\xff", TREND.encode(), b'{"name":"a","name":"b","long_when":[]}']
)
def test_frozen_rule_rejects_invalid_or_noncanonical_bytes(tmp_path: Path, raw: bytes) -> None:
    import hashlib

    path = tmp_path / "frozen.json"
    path.write_bytes(raw)
    with pytest.raises(DataError):
        resolve_rules_spec(
            "rules", None, tmp_path, rules_file=path, rules_sha256=hashlib.sha256(raw).hexdigest()
        )


def test_frozen_rule_rejects_missing_and_oversized_files(tmp_path: Path) -> None:
    path = tmp_path / "missing"
    for raw in [None, b" " * 1_000_001]:
        if raw is not None:
            path.write_bytes(raw)
        with pytest.raises(DataError, match="regular file"):
            resolve_rules_spec("rules", None, tmp_path, rules_file=path, rules_sha256="a" * 64)


def test_frozen_rules_excluded_from_default_launch_catalog() -> None:
    from alpha_cli.info_cmds import _command_catalog

    for include_all in [False, True]:
        rows = {r["id"]: r for r in _command_catalog(include_all=include_all)}
        for command in ["backtest run", "validate"]:
            names = {o["name"] for o in rows[command]["options"]}
            assert "rules_file" not in names
            assert "rules_sha256" not in names

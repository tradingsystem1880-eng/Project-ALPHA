"""`alpha propfirm run` scores a strategy against a prop firm and writes a byte-stable manifest.

Two input modes: a fresh inline backtest on a symbol, and `--from-run RUN_ID` reusing a prior
run's stored equity curve. Runs offline against the deterministic fixture store (no network).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

# small-parameter backtest so the fixture's 60 bars warm up, trade, and yield dispersed returns
_BT_ARGS = [
    "--lookback", "5", "--skip", "1", "--vol-window", "3", "--rebalance-every", "2",
    "--fee-bps", "0", "--slippage-bps", "0", "--starting-cash", "100000",
]  # fmt: skip
_MC_ARGS = ["--n-paths", "200", "--mean-block", "5", "--seed", "7"]


def test_propfirm_fresh_backtest_writes_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    result = runner.invoke(
        app, ["propfirm", "run", "SPY", "--firm", "topstep", *_BT_ARGS, *_MC_ARGS]
    )
    assert result.exit_code == 0, result.output
    assert "propfirm SPY" in result.output

    (rdir,) = list((tmp_path / "propfirm").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["command"] == "propfirm"
    assert manifest["firm"] == "topstep"
    assert set(manifest["metrics"]) == {
        "pass_probability",
        "bust_probability",
        "payout_probability",
        "median_days_to_pass",
        "expected_payout",
    }
    assert manifest["rules"]["account_size"] == 50_000.0  # the topstep preset
    assert manifest["n_paths"] == 200

    # per-path Monte-Carlo outcomes ride alongside the manifest (propfirm_paths.parquet)
    paths = pl.read_parquet(rdir / "propfirm_paths.parquet")
    assert paths.columns == ["path_index", "passed", "busted", "days_to_pass", "payout"]
    assert paths.schema["path_index"] == pl.Int64
    assert paths.schema["passed"] == pl.Boolean
    assert paths.schema["busted"] == pl.Boolean
    assert paths.schema["days_to_pass"] == pl.Float64
    assert paths.schema["payout"] == pl.Float64
    assert paths.height == manifest["n_paths"]
    assert paths["path_index"].to_list() == list(range(manifest["n_paths"]))  # sorted, gap-free
    # the manifest aggregates are exactly the per-path means
    assert paths["passed"].mean() == pytest.approx(manifest["metrics"]["pass_probability"])
    assert paths["busted"].mean() == pytest.approx(manifest["metrics"]["bust_probability"])
    assert paths["payout"].mean() == pytest.approx(manifest["metrics"]["expected_payout"])


def test_propfirm_manifest_is_byte_stable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    args = ["propfirm", "run", "SPY", "--firm", "topstep", *_BT_ARGS, *_MC_ARGS]

    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    (rdir,) = list((tmp_path / "propfirm").iterdir())
    text_a = (rdir / "manifest.json").read_text()
    paths_a = (rdir / "propfirm_paths.parquet").read_bytes()

    second = runner.invoke(app, args)  # same run_id -> same dir, overwritten identically
    assert second.exit_code == 0, second.output
    text_b = (rdir / "manifest.json").read_text()
    assert text_a == text_b  # byte-identical (spec §11.4)
    assert paths_a == (rdir / "propfirm_paths.parquet").read_bytes()  # per-path outcomes too


def test_propfirm_horizon_flag_caps_the_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(
        app,
        ["propfirm", "run", "SPY", "--firm", "topstep", "--horizon", "20", *_BT_ARGS, *_MC_ARGS],
    )
    assert result.exit_code == 0, result.output
    (rdir,) = list((tmp_path / "propfirm").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["horizon_days"] == 20  # the simulation window, not the full return series


def test_propfirm_from_run_reuses_stored_equity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    bt = runner.invoke(app, ["backtest", "run", "SPY", *_BT_ARGS])
    assert bt.exit_code == 0, bt.output
    (run_rdir,) = list((tmp_path / "runs").iterdir())
    run_id = run_rdir.name

    result = runner.invoke(
        app, ["propfirm", "run", "--from-run", run_id, "--firm", "apex", *_MC_ARGS]
    )
    assert result.exit_code == 0, result.output
    (rdir,) = list((tmp_path / "propfirm").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["firm"] == "apex"
    assert run_id in manifest["source"]
    assert "metrics" in manifest


def test_propfirm_custom_flag_overrides_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(
        app,
        [
            "propfirm",
            "run",
            "SPY",
            "--firm",
            "topstep",
            "--profit-target",
            "1500",
            *_BT_ARGS,
            *_MC_ARGS,
        ],
    )
    assert result.exit_code == 0, result.output
    (rdir,) = list((tmp_path / "propfirm").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["rules"]["profit_target"] == 1500.0  # flag overrode the preset's 3000


def test_propfirm_requires_exactly_one_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    neither = runner.invoke(app, ["propfirm", "run", "--firm", "topstep", *_MC_ARGS])
    assert neither.exit_code != 0  # no symbol and no --from-run
    both = runner.invoke(app, ["propfirm", "run", "SPY", "--from-run", "abc", "--firm", "topstep"])
    assert both.exit_code != 0  # ambiguous: both a symbol and --from-run


def test_report_renders_a_propfirm_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    run = runner.invoke(app, ["propfirm", "run", "SPY", "--firm", "topstep", *_BT_ARGS, *_MC_ARGS])
    assert run.exit_code == 0, run.output
    (rdir,) = list((tmp_path / "propfirm").iterdir())
    run_id = rdir.name

    shutil.rmtree(tmp_path / "store")  # report must rely only on the manifest
    out = runner.invoke(app, ["report", run_id])
    assert out.exit_code == 0, out.output
    assert run_id in out.output
    assert "topstep" in out.output  # firm headline
    assert "pass_probability" in out.output  # the simulation metrics

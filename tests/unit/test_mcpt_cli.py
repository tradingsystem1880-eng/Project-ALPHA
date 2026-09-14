"""``alpha optim mcpt``: the in-sample permutation test of a parameter sweep (alpha_cli._mcpt)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

_ARGS = [
    "--grid", "lookback=3,5",
    "--skip", "1", "--vol-window", "3", "--rebalance-every", "2",
    "--train-size", "15", "--test-size", "5", "--embargo", "1",
    "--fee-bps", "0", "--slippage-bps", "0", "--starting-cash", "100000",
    "--perms", "4", "--seed", "7",
]  # fmt: skip


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=90)
    result = runner.invoke(app, ["optim", "mcpt", "SPY", *_ARGS])
    assert result.exit_code == 0, result.output
    assert "optim SPY -> run " in result.output
    assert "in-sample MCPT p" in result.output and "not OOS evidence" in result.output
    (rdir,) = list((tmp_path / "optim").iterdir())
    return rdir


def test_mcpt_writes_the_null_artifact_and_a_manifest_that_never_claims_oos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rdir = _run(tmp_path, monkeypatch)
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["command"] == "optim_mcpt"
    assert manifest["n_configs"] == 2 and manifest["n_perms"] == 4
    assert manifest["statistic"] == "in_sample_sharpe"
    assert manifest["observed"]["config"] in ({"lookback": 3.0}, {"lookback": 5.0})
    assert "never out-of-sample evidence" in manifest["caveat"]
    assert isinstance(manifest["passed"], bool)
    assert "mcpt_null.parquet" in manifest["artifacts"]

    null = pl.read_parquet(rdir / "mcpt_null.parquet")
    assert null.columns == ["path_index", "statistic", "best_config"]
    assert null.schema["path_index"] == pl.Int64
    assert null.schema["statistic"] == pl.Float64
    assert null.height == 4 and null["statistic"].is_finite().all()
    assert null["path_index"].to_list() == [0, 1, 2, 3]
    assert all(json.loads(c) in ({"lookback": 3.0}, {"lookback": 5.0}) for c in null["best_config"])
    # Davison & Hinkley ranking recomputed from the persisted null
    observed = manifest["observed"]["statistic"]
    stats = null["statistic"].to_numpy()
    assert manifest["p_value"] == pytest.approx((1 + int(np.sum(stats >= observed))) / 5)
    assert manifest["percentile"] == pytest.approx(float(np.mean(stats < observed)))


def test_mcpt_is_byte_identical_across_data_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _run(tmp_path / "a", monkeypatch)
    second = _run(tmp_path / "b", monkeypatch)
    assert first.name == second.name  # same run identity
    assert (first / "mcpt_null.parquet").read_bytes() == (second / "mcpt_null.parquet").read_bytes()
    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()


def test_mcpt_rejects_a_missing_grid_and_zero_permutations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=90)
    assert runner.invoke(app, ["optim", "mcpt", "SPY", "--perms", "4"]).exit_code != 0
    bad = runner.invoke(app, ["optim", "mcpt", "SPY", "--grid", "lookback=3,5", "--perms", "0"])
    assert bad.exit_code != 0 and "--perms must be >= 1" in bad.output


def test_info_commands_lists_optim_mcpt() -> None:
    result = runner.invoke(app, ["info", "commands", "--json"])
    assert result.exit_code == 0
    catalog = {c["id"]: c for c in json.loads(result.stdout)}
    assert "optim mcpt" in catalog
    assert any(o["name"] == "perms" for o in catalog["optim mcpt"]["options"])

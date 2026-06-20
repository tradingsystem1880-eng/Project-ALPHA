"""`alpha validate` runs the gauntlet on an offline fixture; writes manifest + tear sheet."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

_ARGS = [
    "--lookback", "5", "--skip", "1", "--vol-window", "3", "--rebalance-every", "2",
    "--train-size", "15", "--test-size", "5", "--embargo", "1",
    "--fee-bps", "0", "--slippage-bps", "0", "--starting-cash", "100000",
    "--tier1-paths", "50", "--tier2-paths", "8", "--n-resamples", "200",
]  # fmt: skip


def test_validate_writes_manifest_and_tearsheet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    result = runner.invoke(app, ["validate", "SPY", *_ARGS])
    assert result.exit_code == 0, result.output
    assert "validate SPY" in result.output
    assert "PASS" in result.output or "FAIL" in result.output

    (rdir,) = list((tmp_path / "runs").iterdir())
    assert (rdir / "tearsheet.html").exists()
    assert (rdir / "equity_curve.parquet").exists()
    assert (rdir / "trades.parquet").exists()

    manifest = json.loads((rdir / "manifest.json").read_text())
    assert set(manifest) >= {"cis", "folds", "nulls", "oos_metrics", "outcomes", "passed", "run_id"}
    assert {n["tier"] for n in manifest["nulls"]} == {"returns_level", "full_engine"}
    assert {c["metric"] for c in manifest["cis"]} == {"sharpe", "cagr"}
    assert {o["name"] for o in manifest["outcomes"]} == {
        "walk_forward_oos",
        "randomized_price_null",
        "bootstrap_ci",
        "deflated_sharpe",
        "cpcv_oos",
    }
    assert manifest["dsr"]["n_trials"] == 1  # single-config DSR reduces to PSR
    assert manifest["cpcv"]["n_folds"] >= 1
    assert isinstance(manifest["passed"], bool)
    assert manifest["metadata"]["quantstats_version"]  # provenance recorded

    # `report` on a gauntlet run renders the DSR block, not a spurious/contradictory `dsr: n/a`.
    report_out = runner.invoke(app, ["report", manifest["run_id"]])
    assert report_out.exit_code == 0, report_out.output
    assert "dsr: n/a" not in report_out.output
    assert "dsr: dsr=" in report_out.output


def test_validate_rejects_unknown_null_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(app, ["validate", "SPY", "--null-model", "bogus", *_ARGS])
    assert result.exit_code == 2  # clean BadParameter, not a traceback
    # The accepted set must include the default `bootstrap`, not only the parametric models.
    assert "bootstrap" in result.output
    assert "student_t" in result.output and "garch" in result.output
    assert "Traceback" not in result.output

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
    }
    assert isinstance(manifest["passed"], bool)
    assert manifest["metadata"]["quantstats_version"]  # provenance recorded

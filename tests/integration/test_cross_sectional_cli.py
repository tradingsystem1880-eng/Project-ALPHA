"""`alpha backtest cross-sectional` runs on the offline fixture and writes a manifest."""

from __future__ import annotations

import json
import math
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

_ARGS = [
    "--lookback", "5", "--skip", "1", "--vol-window", "3", "--rebalance-every", "2",
    "--top-quantile", "0.25",
]  # fmt: skip


def test_cross_sectional_writes_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    # Realistic signal-to-noise: sigma comparable to the drifts keeps the book non-deterministic, so
    # the Sharpe is sane and the tear-sheet renderer doesn't trip a degenerate sqrt warning.
    for i, (sym, drift) in enumerate(
        {"AAA": 0.012, "BBB": -0.004, "CCC": -0.012, "DDD": 0.004}.items()
    ):
        seed_store(tmp_path, symbol=sym, n=120, seed=i, drift=drift, sigma=0.012)

    result = runner.invoke(app, ["backtest", "cross-sectional", "AAA", "BBB", "CCC", "DDD", *_ARGS])
    assert result.exit_code == 0, result.output
    assert "cross-sectional" in result.output

    (rdir,) = list((tmp_path / "cross_sectional").iterdir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["symbols"] == ["AAA", "BBB", "CCC", "DDD"]
    assert manifest["long_short"] is True
    assert manifest["n_periods"] > 0
    # Don't just check membership: pin that the BCa interval is finite and brackets a finite point
    # Sharpe, so a future degenerate-stats regression (None / absurd CI) is caught, not serialized.
    sharpe = manifest["metrics"]["sharpe"]
    ci = manifest["sharpe_ci"]
    assert isinstance(sharpe, float) and math.isfinite(sharpe)
    assert math.isfinite(ci["lower"]) and math.isfinite(ci["upper"])
    assert ci["lower"] <= sharpe <= ci["upper"]
    assert (rdir / "tearsheet.html").exists()  # reporting parity with `alpha validate`

    # the OOS stream is persisted as an equity curve (validate-run schema: base 1.0)
    eq = pl.read_parquet(rdir / "equity_curve.parquet")
    assert eq.columns == ["ts", "equity"]
    assert eq.schema["ts"] == pl.Datetime(time_unit="us", time_zone="UTC")
    assert eq.schema["equity"] == pl.Float64
    assert eq.height == manifest["n_periods"] + 1  # baseline row + one point per OOS return
    assert eq["equity"][0] == 1.0
    assert eq["ts"].is_sorted() and eq["ts"].n_unique() == eq.height  # strictly increasing
    assert eq["equity"][-1] / eq["equity"][0] - 1.0 == pytest.approx(
        manifest["metrics"]["total_return"]
    )

    report_out = runner.invoke(app, ["report", manifest["run_id"]])
    assert report_out.exit_code == 0, report_out.output
    assert "metrics:" in report_out.output


def test_cross_sectional_rejects_single_symbol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="AAA", n=120)
    result = runner.invoke(app, ["backtest", "cross-sectional", "AAA", *_ARGS])
    assert result.exit_code != 0  # needs >= 2 symbols

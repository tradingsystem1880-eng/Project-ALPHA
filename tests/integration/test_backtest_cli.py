"""`alpha backtest run` drives the engine on a committed offline fixture and writes artifacts."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

_SMALL = [
    "--lookback", "5", "--skip", "1", "--vol-window", "3", "--rebalance-every", "2",
    "--fee-bps", "0", "--slippage-bps", "0", "--starting-cash", "100000",
]  # fmt: skip


def test_backtest_run_writes_trade_log_and_equity_curve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    result = runner.invoke(app, ["backtest", "run", "SPY", *_SMALL])
    assert result.exit_code == 0, result.output
    assert "run" in result.output and "final equity" in result.output

    runs = list((tmp_path / "runs").iterdir())
    assert len(runs) == 1
    rdir = runs[0]
    assert (rdir / "manifest.json").exists()
    equity = pl.read_parquet(rdir / "equity_curve.parquet")
    assert equity.columns == ["ts", "equity"] and equity.height == 60  # one mark per session
    assert (rdir / "trades.parquet").exists()


def test_unknown_symbol_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(app, ["backtest", "run", "NOPE", *_SMALL])
    # Clean, actionable error — a typed DataError surfaces as a tidy BadParameter (exit 2), NOT a
    # raw Python traceback. No run directory is written.
    assert result.exit_code == 2
    assert "Traceback" not in result.output
    assert not (tmp_path / "runs").exists()


def test_bad_account_type_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Fail-loud golden rule: a typo'd --account-type must error, not silently run as CASH.
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(app, ["backtest", "run", "SPY", "--account-type", "BOGUS", *_SMALL])
    assert result.exit_code == 2
    assert "CASH" in result.output and "MARGIN" in result.output
    assert "Traceback" not in result.output


def test_account_type_is_case_insensitive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # "margin" (lowercase) is accepted as MARGIN, not silently coerced to an unlevered CASH account.
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    result = runner.invoke(
        app,
        ["backtest", "run", "SPY", "--account-type", "margin", "--max-leverage", "2.0", *_SMALL],
    )
    assert result.exit_code == 0, result.output

"""`alpha paper` drives the sandbox over a committed offline fixture, writing session artifacts."""

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
    "--feed-interval", "0.005",  # artifact tests don't assert fill-timing parity -> fast replay
]  # fmt: skip


def _session_id(output: str) -> str:
    # "paper SPY -> session <id>: N orders, ..."
    return output.split("session ", 1)[1].split(":", 1)[0].strip()


def test_paper_run_writes_session_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=20)

    result = runner.invoke(app, ["paper", "run", "SPY", *_SMALL])
    assert result.exit_code == 0, result.output
    assert "session" in result.output and "final equity" in result.output

    sessions = list((tmp_path / "paper").iterdir())
    assert len(sessions) == 1
    sdir = sessions[0]
    assert (sdir / "session.json").exists()
    assert (sdir / "audit.log.jsonl").exists()
    equity = pl.read_parquet(sdir / "equity_curve.parquet")
    assert equity.columns == ["ts", "equity"] and equity.height == 20  # one mark per session


def test_paper_status_and_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=20)

    run_result = runner.invoke(app, ["paper", "run", "SPY", *_SMALL])
    assert run_result.exit_code == 0, run_result.output
    session_id = _session_id(run_result.output)

    status_result = runner.invoke(app, ["paper", "status"])
    assert status_result.exit_code == 0, status_result.output
    assert session_id in status_result.output and "SPY" in status_result.output

    report_result = runner.invoke(app, ["paper", "report", session_id])
    assert report_result.exit_code == 0, report_result.output
    assert "metrics:" in report_result.output and "max_drawdown" in report_result.output


def test_paper_report_unknown_session_fails_loud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["paper", "report", "nope"])
    assert result.exit_code != 0

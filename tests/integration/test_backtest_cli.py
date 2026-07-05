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


def test_stored_dividends_flow_into_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # End-to-end: a DIVIDEND action in the store must raise the run's final equity by the credit.
    import json
    from datetime import date

    from alpha_core import ActionType, CorporateAction
    from alpha_data.store import ParquetStore

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60, seed=0, drift=0.002)
    runner = CliRunner()
    args = [
        "backtest",
        "run",
        "SPY",
        "--lookback",
        "5",
        "--skip",
        "1",
        "--vol-window",
        "5",
        "--rebalance-every",
        "5",
        "--fee-bps",
        "0",
        "--slippage-bps",
        "0",
    ]

    plain = runner.invoke(app, args)
    assert plain.exit_code == 0, plain.output

    # add a mid-series dividend (ex + pay well inside the window) and re-run
    ParquetStore(tmp_path / "store").write_actions(
        "SPY",
        [
            CorporateAction(
                symbol="SPY",
                action_type=ActionType.DIVIDEND,
                ex_date=date(2020, 2, 15),
                pay_date=date(2020, 2, 20),
                amount=1.0,
            )
        ],
    )
    paid = runner.invoke(app, args)
    assert paid.exit_code == 0, paid.output

    def final_equity(output: str) -> float:
        return float(output.split("final equity ")[1].split(" ")[0].rstrip("\n"))

    # both runs share a run_id (same params; the store is the mutable input), so compare the
    # reported equities, and confirm the manifest holds the latest (dividend-credited) value
    assert final_equity(paid.output) > final_equity(plain.output)
    run_id = paid.output.split("-> run ")[1].split(":")[0]
    manifest = json.loads((tmp_path / "runs" / run_id / "manifest.json").read_text())
    assert float(manifest["final_equity"]) == pytest.approx(final_equity(paid.output), abs=0.01)

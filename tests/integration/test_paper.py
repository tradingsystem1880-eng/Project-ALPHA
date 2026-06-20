"""Paper-trading scaffold: offline-verifiable config assembly + strategy parity + fail-loud run.

The live run (a market-data adapter + credentials + network) is the spec's deferred Phase-4 piece
and is not exercised here; everything below is constructible offline.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from alpha_cli import _paper
from alpha_cli._runner import RunSpec
from alpha_cli.main import app
from alpha_core import AlphaError

runner = CliRunner()


def _spec(account_type: str = "CASH") -> RunSpec:
    return RunSpec(
        lookback=252,
        skip=21,
        vol_window=63,
        target_vol=0.15,
        rebalance_every=21,
        max_leverage=1.0,
        allow_short=account_type == "MARGIN",
        periods_per_year=252,
        fee_bps=1.0,
        slippage_bps=2.0,
        starting_cash=100_000.0,
        account_type=account_type,
        train_size=504,
        test_size=63,
        embargo=5,
        anchored=False,
    )


def test_sandbox_exec_config_constructs() -> None:
    cfg = _paper.build_sandbox_exec_config(
        venue="SANDBOX", account_type="CASH", starting_cash=100_000.0, currency="USD"
    )
    assert str(cfg.venue) == "SANDBOX"
    assert cfg.bar_execution is False  # backtest parity: quotes fill, bars decide


def test_node_config_carries_the_sandbox_exec_client() -> None:
    cfg = _paper.build_sandbox_exec_config(
        venue="SANDBOX", account_type="MARGIN", starting_cash=50_000.0, currency="USD"
    )
    node = _paper.build_paper_node_config(trader_id="PAPER-001", exec_config=cfg)
    assert "SANDBOX" in node.exec_clients


def test_run_paper_without_data_client_fails_loud() -> None:
    with pytest.raises(AlphaError, match="market-data client"):
        _paper.run_paper(_spec(), venue="SANDBOX", data_clients=None)


def test_cli_preflight_reports_readiness_and_parity() -> None:
    result = runner.invoke(app, ["paper", "preflight", "AAPL", "--strategy", "ma_crossover"])
    assert result.exit_code == 0, result.output
    assert "paper preflight OK" in result.output
    assert "MovingAverageCrossover constructed" in result.output  # same class as the backtest
    assert "bar_execution=False" in result.output


def test_cli_preflight_rejects_unknown_strategy() -> None:
    result = runner.invoke(app, ["paper", "preflight", "AAPL", "--strategy", "nope"])
    assert result.exit_code != 0

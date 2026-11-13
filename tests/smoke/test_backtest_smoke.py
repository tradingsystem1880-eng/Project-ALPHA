"""Workflow 2, backtest: run on the snapshot -> artefacts on disk -> a second process reports it."""

from __future__ import annotations

import json

import pytest

from tests.smoke._harness import alpha
from tests.smoke.conftest import SNAPSHOT, BacktestHome

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]


def test_backtest_run_is_stored_and_reported(backtest_home: BacktestHome) -> None:
    run_dir = backtest_home.home / "data" / "runs" / backtest_home.run_id
    for artefact in ("manifest.json", "equity_curve.parquet", "trades.parquet", "fills.parquet"):
        assert (run_dir / artefact).is_file(), artefact
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["command"] == "backtest_run"
    assert manifest["snapshot_id"] == SNAPSHOT
    assert manifest["final_equity"] == backtest_home.final_equity

    report = alpha(backtest_home.home, "report", backtest_home.run_id).stdout
    assert f"run {backtest_home.run_id}  backtest_run  [SPY]" in report
    assert f"final_equity={backtest_home.final_equity:.4f}" in report


def test_backtest_report_json_describes_the_run(backtest_home: BacktestHome) -> None:
    run_dir = backtest_home.home / "data" / "runs" / backtest_home.run_id
    payload = alpha(backtest_home.home, "report", backtest_home.run_id, "--json").json()
    assert payload == json.loads((run_dir / "manifest.json").read_text())
    assert payload["run_id"] == backtest_home.run_id
    assert payload["command"] == "backtest_run"
    assert payload["snapshot_id"] == SNAPSHOT
    assert payload["final_equity"] == backtest_home.final_equity

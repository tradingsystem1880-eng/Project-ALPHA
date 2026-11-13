"""Workflow 5, web app: the installed ``alpha-web`` lists the backtest run and serves its detail."""

from __future__ import annotations

import urllib.error
from pathlib import Path

import pytest

from tests.smoke._harness import get_json, web_server
from tests.smoke.conftest import SNAPSHOT, BacktestHome, copy_home

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]


def test_web_app_lists_the_run_and_serves_its_detail(
    backtest_home: BacktestHome, tmp_path: Path
) -> None:
    home = copy_home(backtest_home.home, tmp_path)
    run_id = backtest_home.run_id
    with web_server(home) as base:
        listed = get_json(f"{base}/api/runs")
        (row,) = [item for item in listed["items"] if item["run_id"] == run_id]
        assert row["command"] == "backtest_run"
        assert row["symbol"] == "SPY"
        assert row["snapshot_id"] == SNAPSHOT

        detail = get_json(f"{base}/api/runs/{run_id}")
        assert detail["run_id"] == run_id
        assert detail["manifest"]["final_equity"] == backtest_home.final_equity
        assert detail["manifest"]["n_trades"] > 0

    with pytest.raises(urllib.error.URLError):  # the server is gone once the block ends
        get_json(f"{base}/healthz", timeout=2)

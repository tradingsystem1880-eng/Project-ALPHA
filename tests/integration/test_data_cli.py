from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_data.adapters.base import FetchResult
from alpha_data.adapters.yfinance_adapter import parse_yfinance_history
from tests.fixtures.yf_fixtures import aapl_like

runner = CliRunner()


class _FakeAdapter:
    name = "fake"
    version = "1"

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        return parse_yfinance_history(aapl_like(), symbol)


def test_pull_then_snapshot_then_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    # inject the fake adapter so the CLI does no network
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"fake": _FakeAdapter})
    r1 = runner.invoke(app, ["data", "pull", "AAPL", "--source", "fake",
                             "--start", "2020-08-28", "--end", "2020-09-02"])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(app, ["data", "snapshot", "snap1", "AAPL", "--source", "fake"])
    assert r2.exit_code == 0, r2.output
    r3 = runner.invoke(app, ["data", "verify", "snap1"])
    assert r3.exit_code == 0, r3.output
    assert "ok" in r3.output.lower()

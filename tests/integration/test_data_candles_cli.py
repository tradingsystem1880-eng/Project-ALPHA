"""``alpha data candles`` — PIT-adjusted OHLCV for the workstation price chart."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()


def test_candles_json_returns_ohlcv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=30)
    result = runner.invoke(app, ["data", "candles", "SPY", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["symbol"] == "SPY" and len(payload["bars"]) == 30
    assert set(payload["bars"][0]) == {"t", "o", "h", "l", "c", "v"}


def test_candles_window_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=30)  # daily bars from 2020-01-01
    result = runner.invoke(
        app, ["data", "candles", "SPY", "--start", "2020-01-10", "--end", "2020-01-20", "--json"]
    )
    assert result.exit_code == 0
    bars = json.loads(result.stdout)["bars"]
    lo = dt.datetime(2020, 1, 10, tzinfo=dt.UTC).timestamp()
    hi = dt.datetime(2020, 1, 20, 23, 59, 59, tzinfo=dt.UTC).timestamp()
    assert bars and all(lo <= b["t"] <= hi for b in bars) and len(bars) < 30


def test_candles_unknown_symbol_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["data", "candles", "NOPE", "--json"])
    assert result.exit_code != 0

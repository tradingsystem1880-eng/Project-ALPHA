"""`alpha data candles` must be point-in-time: ``--end`` excludes future bars and applies only
corporate actions known by then — a chart can never show a bar past its window nor a split not yet
announced. (The candles endpoint is the workstation's price feed, so it needs the same firewall a
backtest gets.)"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_core import ActionType, CorporateAction
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import linear_bars

pytestmark = pytest.mark.bias_guard

runner = CliRunner()


def _seed(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path / "store")
    store.write_bars("ZZ", linear_bars("ZZ", date(2020, 1, 2), 10, first_close=100.0))  # Jan 2..11
    store.write_actions(
        "ZZ",
        [
            CorporateAction(
                symbol="ZZ",
                action_type=ActionType.SPLIT,
                ex_date=date(2020, 6, 1),
                announce_date=date(2020, 5, 1),  # far future relative to the --end below
                ratio=4.0,
            )
        ],
    )


def _closes(result_stdout: str) -> list[float]:
    return [round(b["c"], 6) for b in json.loads(result_stdout)["bars"]]


def test_end_excludes_future_bars_and_unknown_split(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _seed(tmp_path)
    result = runner.invoke(app, ["data", "candles", "ZZ", "--end", "2020-01-06", "--json"])
    assert result.exit_code == 0
    bars = json.loads(result.stdout)["bars"]
    cutoff = datetime(2020, 1, 6, 23, 59, 59, tzinfo=UTC).timestamp()
    assert bars and all(b["t"] <= cutoff for b in bars)  # no bar past the as-of cutoff
    assert len(bars) == 5  # Jan 2-6 only; Jan 7-11 are the future, excluded
    assert _closes(result.stdout) == [100.0, 101.0, 102.0, 103.0, 104.0]  # split not yet known


def test_split_is_applied_once_known(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # counter-test so the "unadjusted" result above can't be a split that is simply never applied
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _seed(tmp_path)
    result = runner.invoke(app, ["data", "candles", "ZZ", "--end", "2020-12-31", "--json"])
    assert result.exit_code == 0
    # every Jan bar is pre-ex (ex 2020-06-01) and the split is now known -> quartered
    assert _closes(result.stdout)[:5] == [25.0, 25.25, 25.5, 25.75, 26.0]

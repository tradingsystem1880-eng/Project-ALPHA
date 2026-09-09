"""``alpha scan run --as-of`` is point-in-time: bars after the cutoff cannot change a row, and
the reported bar is never past the cutoff."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_data.store import ParquetStore
from tests.fixtures.cli_fixtures import seed_store

pytestmark = pytest.mark.bias_guard

runner = CliRunner()
TREND = json.dumps(
    {
        "name": "trend",
        "history": 30,
        "long_when": [
            {
                "left": {"indicator": "sma", "params": [5]},
                "op": ">",
                "right": {"indicator": "sma", "params": [20]},
            }
        ],
        "short_when": [
            {
                "left": {"indicator": "sma", "params": [5]},
                "op": "<",
                "right": {"indicator": "sma", "params": [20]},
            }
        ],
    }
)


def test_future_bars_cannot_change_a_scan_as_of(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="ZZ", n=60, drift=0.01, sigma=0.001)  # 2020-01-01 .. 2020-02-29
    assert runner.invoke(app, ["rules", "save", "trend", "--spec", TREND]).exit_code == 0
    assert (
        runner.invoke(app, ["scan", "save", "s", "--rules", "trend", "--symbols", "ZZ"]).exit_code
        == 0
    )
    before = runner.invoke(app, ["scan", "run", "s", "--as-of", "2020-02-29", "--json"])
    assert before.exit_code == 0, before.output
    rows = json.loads(before.stdout)["rows"]
    assert rows[0]["signal"] == 1 and rows[0]["bar_date"] == "2020-02-29"
    # Poison the future: a crash of 60 bars after the cutoff.
    import datetime as dt

    import polars as pl

    store = ParquetStore(tmp_path / "store")
    past = store.read_bars("ZZ")
    start = dt.datetime(2020, 3, 1, tzinfo=dt.UTC)
    closes = [float(past["close"][-1]) * (0.98**i) for i in range(1, 61)]  # a 60-bar crash
    crash = pl.DataFrame(
        {
            "ts": [start + dt.timedelta(days=i) for i in range(60)],
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [1000.0] * 60,
        }
    ).cast(past.schema)
    store.write_bars("ZZ", pl.concat([past, crash]))
    after = runner.invoke(app, ["scan", "run", "s", "--as-of", "2020-02-29", "--json"])
    assert after.exit_code == 0, after.output
    assert json.loads(after.stdout)["rows"] == rows
    live_result = runner.invoke(app, ["scan", "run", "s", "--json"])
    assert live_result.exit_code == 0, live_result.output
    live = json.loads(live_result.stdout)["rows"]
    assert live[0]["signal"] == -1 and live[0]["bar_date"] > "2020-02-29"  # the crash is real today

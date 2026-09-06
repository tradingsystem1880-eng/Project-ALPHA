"""Chart overlays are point-in-time: bars after ``--end`` cannot change a single value or
annotation, and a swing that is not confirmed by the last bar is never drawn (a "leaky twin" that
skipped ``swings_known_by`` would draw it)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.chart_cmds import SWING_LOOKBACK, compute_overlays, to_ohlcv
from alpha_cli.main import app
from alpha_data.store import ParquetStore
from alpha_patterns import find_swings
from tests.fixtures.pit_fixtures import linear_bars

pytestmark = pytest.mark.bias_guard

runner = CliRunner()
ARGS = ["-i", "sma:5", "-i", "rsi:5", "-i", "macd:3:6:3", "-p", "swings", "-p", "levels"]


def _wavy(symbol: str, start: date, n: int, first_close: float = 100.0):  # type: ignore[no-untyped-def]
    frame = linear_bars(symbol, start, n, first_close=first_close)
    wave = 5.0 * np.sin(np.arange(n) / 2.0)
    return frame.with_columns(
        [
            (frame["close"] + wave).alias("close"),
            (frame["open"] + wave).alias("open"),
            (frame["high"] + wave).alias("high"),
            (frame["low"] + wave).alias("low"),
        ]
    )


def test_future_bars_cannot_change_the_overlays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    store = ParquetStore(tmp_path / "store")
    store.write_bars("ZZ", _wavy("ZZ", date(2020, 1, 1), 40))
    before = runner.invoke(app, ["chart", "overlays", "ZZ", "--end", "2020-02-09", "--json", *ARGS])
    assert before.exit_code == 0, before.output
    # Poison the future: forty more bars after the --end cutoff, each at 10x the price.
    future = _wavy("ZZ", date(2020, 2, 10), 40, first_close=1000.0)
    store.write_bars("ZZ", pl.concat([_wavy("ZZ", date(2020, 1, 1), 40), future]))
    after = runner.invoke(app, ["chart", "overlays", "ZZ", "--end", "2020-02-09", "--json", *ARGS])
    assert after.exit_code == 0, after.output
    first, second = json.loads(before.stdout), json.loads(after.stdout)
    assert second["t"] == first["t"] and len(first["t"]) == 40
    assert second["indicators"] == first["indicators"]
    assert second["annotations"] == first["annotations"]


def test_unconfirmed_tail_swing_is_never_drawn() -> None:
    from alpha_core import Bar

    frame = _wavy("ZZ", date(2020, 1, 1), 60)
    full = [Bar(symbol="ZZ", **row) for row in frame.to_dicts()]
    window = full[:55]  # the trader stands on bar 54
    last = len(window) - 1
    # The leaky twin: swings found with the benefit of bars 55..59, which confirm extremes that
    # sit inside the window's last ``lookback`` bars. The overlays must not know about them.
    hindsight = to_ohlcv(full)
    leaky = find_swings(hindsight, lookback=SWING_LOOKBACK, kind="high") + find_swings(
        hindsight, lookback=SWING_LOOKBACK, kind="low"
    )
    unconfirmed = [s for s in leaky if s.index <= last < s.confirmed_index]
    assert unconfirmed, "fixture must place a swing inside the window's last lookback bars"
    drawn = {
        (r["anchors"][0]["anchor_index"], r["label"])
        for r in compute_overlays(window, [], ["swings"])["annotations"]
    }
    for swing in unconfirmed:
        assert (swing.index, f"Swing {swing.kind}") not in drawn
    confirmed = [s for s in leaky if s.confirmed_index <= last]
    assert {(s.index, f"Swing {s.kind}") for s in confirmed} == drawn

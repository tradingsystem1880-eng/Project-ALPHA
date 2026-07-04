"""Kronos signal-cache look-ahead guards.

1) Cache rows whose model windows end at/before a poison point are identical whether or not
   later bars were poisoned (per-bar child seeds are index-keyed; the fake model is
   window-pure) — and at least one later row differs (discriminating power).
2) The replaying strategy's equity through bar t+1 cannot change when cached signals AFTER
   t are mutated (decide close-t, fill open-t+1).
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from alpha_cli import _forecast_cache, _runner
from alpha_core import Bar
from tests.fixtures.forecast_fixtures import daily_bars
from tests.unit.test_forecast_cache import _kronos_spec

pytestmark = pytest.mark.bias_guard


def _spike(bar: Bar) -> Bar:
    spiked = bar.close * 9.9
    return Bar(
        symbol=bar.symbol,
        ts=bar.ts,
        open=bar.open,
        high=max(bar.high, spiked),
        low=bar.low,
        close=spiked,
        volume=bar.volume,
    )


def test_cache_rows_before_poison_are_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_FORECAST_MODEL", "fake")
    clean = daily_bars(30, start=date(2026, 1, 5))
    poison_at = 20
    poisoned = clean[:poison_at] + [_spike(b) for b in clean[poison_at:]]
    spec = _kronos_spec()

    key_a, _ = _forecast_cache.ensure_forecast_cache(clean, spec, data_dir=tmp_path, seed=7)
    key_b, _ = _forecast_cache.ensure_forecast_cache(poisoned, spec, data_dir=tmp_path, seed=7)
    assert key_a != key_b  # content-addressed: poisoned bars can never reuse the clean cache

    a = pl.read_parquet(tmp_path / "forecasts" / key_a / "signals.parquet")
    b = pl.read_parquet(tmp_path / "forecasts" / key_b / "signals.parquet")
    context = 6
    safe = [i for i in a["bar_index"].to_list() if i < poison_at]
    later = [i for i in a["bar_index"].to_list() if i >= poison_at + context]
    assert safe and later
    for col in ("signal", "q50_end"):
        assert (
            a.filter(pl.col("bar_index").is_in(safe))[col].to_list()
            == b.filter(pl.col("bar_index").is_in(safe))[col].to_list()
        )
    # discriminating power: fully-poisoned windows must actually change the forecasts
    assert (
        a.filter(pl.col("bar_index").is_in(later))["q50_end"].to_list()
        != b.filter(pl.col("bar_index").is_in(later))["q50_end"].to_list()
    )


def test_replay_strategy_ignores_future_cache_mutations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_FORECAST_MODEL", "fake")
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    bars = daily_bars(40, start=date(2026, 1, 5))
    spec = _kronos_spec()
    key, _ = _forecast_cache.ensure_forecast_cache(bars, spec, data_dir=tmp_path, seed=7)

    # a doctored cache that flips every signal AFTER the cut index
    cut = 20
    doctored_key = "f" * 16
    src, dst = tmp_path / "forecasts" / key, tmp_path / "forecasts" / doctored_key
    shutil.copytree(src, dst)
    frame = pl.read_parquet(src / "signals.parquet")
    flipped = frame.with_columns(
        pl.when(pl.col("bar_index") > cut)
        .then(-pl.col("signal"))
        .otherwise(pl.col("signal"))
        .alias("signal")
    )
    flipped.write_parquet(dst / "signals.parquet")
    meta = json.loads((src / "meta.json").read_text())
    assert frame.filter(pl.col("bar_index") > cut)["signal"].abs().sum() > 0  # something flipped

    from dataclasses import replace

    result_a = _runner.run_full_backtest(bars, replace(spec, forecast_cache=key))
    result_b = _runner.run_full_backtest(bars, replace(spec, forecast_cache=doctored_key))

    n_prefix = cut + 2  # decisions at bar <= cut affect fills through bar cut+1
    prefix_a = result_a.equity_curve[:n_prefix]
    prefix_b = result_b.equity_curve[:n_prefix]
    assert prefix_a == prefix_b  # future signals can never bend the past
    assert result_a.equity_curve != result_b.equity_curve  # but they do change the future
    assert meta["n_bars"] == 40

"""``alpha_cli._forecast_cache``: schedule, content-addressed keys, idempotent precompute."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from alpha_cli import _forecast, _forecast_cache, _runner
from alpha_core import DataError
from alpha_forecast import Forecaster
from tests.fixtures.forecast_fixtures import daily_bars


def _kronos_spec(**params: float) -> _runner.RunSpec:
    strategy_params = tuple(
        sorted({"context": 6.0, "horizon": 3.0, "samples": 8.0, **params}.items())
    )
    return _runner.RunSpec(
        lookback=252,
        skip=21,
        vol_window=3,
        target_vol=0.15,
        rebalance_every=2,
        max_leverage=1.0,
        allow_short=True,
        periods_per_year=252,
        fee_bps=0.0,
        slippage_bps=0.0,
        starting_cash=100_000.0,
        account_type="CASH",
        train_size=12,
        test_size=6,
        embargo=1,
        anchored=False,
        strategy_name="kronos",
        strategy_params=strategy_params,
    )


def test_signal_indices_mirror_engine_cadence() -> None:
    # min_history clamps to max(arg, vol_window+1) exactly like VolTargetStrategy.__init__
    assert _forecast_cache.signal_indices(20, min_history=6, vol_window=3, rebalance_every=2) == [
        5,
        7,
        9,
        11,
        13,
        15,
        17,
        19,
    ]
    assert _forecast_cache.signal_indices(20, min_history=2, vol_window=9, rebalance_every=21) == [
        9
    ]
    with pytest.raises(DataError, match="bars"):
        _forecast_cache.signal_indices(4, min_history=6, vol_window=3, rebalance_every=2)


def test_cache_key_sensitivity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_FORECAST_MODEL", "fake")
    bars = daily_bars(20)
    spec = _kronos_spec()
    key = _forecast_cache.cache_key(bars, spec, seed=7)

    assert key == _forecast_cache.cache_key(bars, spec, seed=7)  # stable
    assert key != _forecast_cache.cache_key(bars[:-1], spec, seed=7)  # bars content
    assert key != _forecast_cache.cache_key(bars, _kronos_spec(min_edge=0.01), seed=7)  # params
    assert key != _forecast_cache.cache_key(bars, spec, seed=8)  # seed
    assert key != _forecast_cache.cache_key(  # cadence is part of the schedule
        bars, replace(spec, rebalance_every=3), seed=7
    )
    monkeypatch.setenv("ALPHA_FORECAST_MODEL", "NeoQuasar/Kronos-base")
    assert key != _forecast_cache.cache_key(bars, spec, seed=7)  # model identity


def test_ensure_cache_idempotent_and_dense_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_FORECAST_MODEL", "fake")
    calls = {"n": 0}
    real_factory = _forecast._forecaster_factory

    def counting_factory(**kwargs: str) -> Forecaster:
        calls["n"] += 1
        return real_factory(**kwargs)

    monkeypatch.setattr(_forecast, "_forecaster_factory", counting_factory)

    bars = daily_bars(20)
    spec = _kronos_spec()
    key, meta = _forecast_cache.ensure_forecast_cache(bars, spec, data_dir=tmp_path, seed=7)
    assert calls["n"] == 1
    parquet = (tmp_path / "forecasts" / key / "signals.parquet").read_bytes()
    assert meta["pretrain"]["overlap"] is False  # 2026 fixture, default 2025-08-02 cutoff

    key2, _ = _forecast_cache.ensure_forecast_cache(bars, spec, data_dir=tmp_path, seed=7)
    assert key2 == key
    assert calls["n"] == 1  # cache hit: no new forecaster
    assert (tmp_path / "forecasts" / key / "signals.parquet").read_bytes() == parquet

    signals = _forecast_cache.read_signals(tmp_path, key)
    assert len(signals) == 20
    indices = _forecast_cache.signal_indices(20, min_history=6, vol_window=3, rebalance_every=2)
    for i, s in enumerate(signals):
        if i in indices:
            assert s in (-1, 0, 1)
        else:
            assert s is None


def test_prepare_spec_noop_for_non_kronos(tmp_path: Path) -> None:
    spec = replace(_kronos_spec(), strategy_name="ts_momentum")
    prepared, meta = _forecast_cache.prepare_spec_for_engine(
        daily_bars(20), spec, data_dir=tmp_path, seed=7
    )
    assert prepared is spec and meta is None


def test_prepare_spec_sets_cache_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_FORECAST_MODEL", "fake")
    prepared, meta = _forecast_cache.prepare_spec_for_engine(
        daily_bars(20), _kronos_spec(), data_dir=tmp_path, seed=7
    )
    assert prepared.forecast_cache is not None
    assert meta is not None and meta["cache_key"] == prepared.forecast_cache
    # the run id must move with the cache key (bias guard: different forecasts != same run)
    a = _runner.run_id_for(vars(prepared))
    b = _runner.run_id_for(vars(replace(prepared, forecast_cache="0" * 16)))
    assert a != b

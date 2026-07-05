"""Parameter optimization glue (``alpha_cli._optim``) — grid expansion + overfitting-aware sweep."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from alpha_cli._optim import OptimResult, expand_grid, run_optimization
from alpha_cli._runner import RunSpec
from alpha_core import Bar, DataError


def _bars(n: int = 90, seed: int = 0) -> list[Bar]:
    closes = 100.0 * np.cumprod(1.0 + 0.0008 + np.random.default_rng(seed).normal(0.0, 0.01, n))
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Bar(symbol="SPY", ts=start + timedelta(days=i), open=c, high=c, low=c, close=c, volume=1e3)
        for i, c in enumerate(closes.tolist())
    ]


def _base() -> RunSpec:
    return RunSpec(
        lookback=5,
        skip=1,
        vol_window=3,
        target_vol=0.15,
        rebalance_every=2,
        max_leverage=1.0,
        allow_short=True,
        periods_per_year=252,
        fee_bps=0.0,
        slippage_bps=0.0,
        starting_cash=100_000.0,
        account_type="MARGIN",
        train_size=15,
        test_size=5,
        embargo=1,
        anchored=False,
    )


def test_expand_grid_is_cartesian_and_sorted() -> None:
    configs = expand_grid({"lookback": [5, 8], "vol_window": [3, 4]})
    assert len(configs) == 4
    assert configs[0] == (("lookback", 5.0), ("vol_window", 3.0))  # axis names sorted
    assert all(tuple(name for name, _ in c) == ("lookback", "vol_window") for c in configs)


def test_expand_grid_fails_loud_when_empty() -> None:
    with pytest.raises(DataError):
        expand_grid({})


def test_run_optimization_produces_aligned_verdict() -> None:
    res = run_optimization(
        _bars(),
        _base(),
        {"lookback": [3, 5], "vol_window": [3, 4]},
        pbo_blocks=6,
        n_resamples=120,
        seed=7,
    )
    assert isinstance(res, OptimResult)
    assert res.n_configs == 4
    assert res.sharpes.size == 4
    assert dict(res.best_config).keys() == {"lookback", "vol_window"}
    assert 0.0 <= res.pbo.pbo <= 1.0
    assert 0.0 < res.spa.p_value <= 1.0
    assert isinstance(res.passed, bool)


def test_run_optimization_is_deterministic() -> None:
    args = (_bars(), _base(), {"lookback": [3, 5], "vol_window": [3, 4]})
    a = run_optimization(*args, pbo_blocks=6, n_resamples=120, seed=7)
    b = run_optimization(*args, pbo_blocks=6, n_resamples=120, seed=7)
    assert a.best_config == b.best_config
    assert a.pbo.pbo == b.pbo.pbo
    assert a.spa.p_value == b.spa.p_value
    assert np.array_equal(a.sharpes, b.sharpes)


def test_single_config_fails_loud() -> None:
    with pytest.raises(DataError):
        run_optimization(_bars(), _base(), {"lookback": [5]}, pbo_blocks=6, n_resamples=50)


def test_warmup_floor_misalignment_fails_loud() -> None:
    # a vol_window of 40 needs train_size >= 41, but base train_size is 15 → the OOS would misalign
    with pytest.raises(DataError):
        run_optimization(_bars(), _base(), {"vol_window": [3, 40]}, pbo_blocks=6, n_resamples=50)

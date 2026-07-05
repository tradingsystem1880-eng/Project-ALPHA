"""Tier-2 full-engine randomized-price null (``alpha_cli._synth.full_engine_null``).

Runs the real engine on block-bootstrapped synthetic paths (no network). Pins the null mechanics,
seed-determinism, and that a (spawn) process pool yields a result identical to the serial path —
the parallel-determinism guarantee.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from alpha_cli._runner import RunSpec, run_full_backtest, walk_forward_oos_for_spec
from alpha_cli._synth import full_engine_null
from alpha_core import Bar, DataError
from alpha_validation import sharpe_ratio

_SPEC = RunSpec(
    lookback=5,
    skip=1,
    vol_window=3,
    target_vol=0.15,
    rebalance_every=2,
    max_leverage=1.0,
    allow_short=True,  # long-short: earns BOTH legs of the periodic run structure below
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


def _trending_bars(seed: int = 0) -> list[Bar]:
    # Persistent 25-bar runs, alternating direction, ~zero net drift: the momentum edge here is
    # SERIAL structure, which block-resampling destroys — so the observed run must outrank its
    # nulls. (A pure-drift fixture cannot test this: resampling preserves the marginal drift, so
    # drift-heavy nulls score as well as the observed. The old raw-row-splice null hid that by
    # polluting every null path with fictitious seam jumps.)
    rng = np.random.default_rng(seed)
    rets: list[float] = []
    for k in range(4):
        sign = 1.0 if k % 2 == 0 else -1.0
        rets.extend(float(sign * 0.01 + rng.normal(0.0, 0.002)) for _ in range(25))
    closes = 100.0 * np.cumprod(1.0 + np.array(rets, dtype=np.float64))
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Bar(symbol="AAPL", ts=start + timedelta(days=i), open=c, high=c, low=c, close=c, volume=1e3)
        for i, c in enumerate(closes.tolist())
    ]


def _observed_oos_sharpe(bars: list[Bar]) -> float:
    oos = walk_forward_oos_for_spec(run_full_backtest(bars, _SPEC).equity_curve, _SPEC)
    return sharpe_ratio(oos.oos_returns, periods_per_year=_SPEC.periods_per_year)


def test_null_mechanics_and_determinism() -> None:
    bars = _trending_bars()
    observed = _observed_oos_sharpe(bars)
    nr = full_engine_null(bars, observed=observed, spec=_SPEC, n_paths=16, mean_block=5.0, seed=7)
    assert nr.n_paths == 16 and nr.null.size == 16
    assert bool(np.all(np.isfinite(nr.null)))
    assert 0.0 <= nr.percentile <= 1.0
    assert 0.0 < nr.p_value <= 1.0  # valid MC p-value, never exactly 0
    assert isinstance(nr.passed, bool)
    # the run-structured observed genuinely beats its scrambled (structure-free) nulls
    assert nr.observed == observed and nr.percentile >= 0.75

    again = full_engine_null(
        bars, observed=observed, spec=_SPEC, n_paths=16, mean_block=5.0, seed=7
    )
    assert np.array_equal(nr.null, again.null)  # seeded -> reproducible


def test_process_pool_matches_serial() -> None:
    bars = _trending_bars()
    observed = _observed_oos_sharpe(bars)
    serial = full_engine_null(
        bars, observed=observed, spec=_SPEC, n_paths=10, mean_block=5.0, seed=11, max_workers=1
    )
    pooled = full_engine_null(
        bars, observed=observed, spec=_SPEC, n_paths=10, mean_block=5.0, seed=11, max_workers=2
    )  # spawn pool
    assert np.array_equal(serial.null, pooled.null)  # execution mode must not change the result


def test_bad_threshold_fails_loud() -> None:
    bars = _trending_bars()
    with pytest.raises(DataError):
        full_engine_null(bars, observed=1.0, spec=_SPEC, n_paths=4, mean_block=5.0, threshold=1.5)


def test_non_finite_observed_fails_loud() -> None:
    # a flat real OOS (undefined Sharpe) must fail loud, not silently rank NaN at percentile 0
    bars = _trending_bars()
    with pytest.raises(DataError):
        full_engine_null(bars, observed=float("nan"), spec=_SPEC, n_paths=4, mean_block=5.0)

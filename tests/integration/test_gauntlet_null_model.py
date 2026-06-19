"""The Tier-1 null model is selectable: bootstrap (default) vs fat-tailed parametric (t / GARCH)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from alpha_cli._gauntlet import GauntletParams, run_gauntlet
from alpha_cli._runner import RunSpec
from alpha_core import Bar, DataError


def _bars(n: int = 80, seed: int = 0) -> list[Bar]:
    closes = 100.0 * np.cumprod(1.0 + 0.001 + np.random.default_rng(seed).normal(0.0, 0.01, n))
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Bar(symbol="SPY", ts=start + timedelta(days=i), open=c, high=c, low=c, close=c, volume=1e3)
        for i, c in enumerate(closes.tolist())
    ]


def _spec() -> RunSpec:
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
        account_type="CASH",
        train_size=15,
        test_size=5,
        embargo=1,
        anchored=False,
    )


@pytest.mark.parametrize("model", ["student_t", "garch"])
def test_parametric_null_models_run_and_report_returns_level_tier(model: str) -> None:
    params = GauntletParams(
        seed=7, tier1_paths=40, tier2_paths=8, n_resamples=150, mean_block=5.0, null_model=model
    )
    out = run_gauntlet(_bars(), _spec(), params, run_id="x", snapshot_id=None)
    tiers = {n.tier for n in out.report.nulls}
    assert tiers == {"returns_level", "full_engine"}
    assert isinstance(out.report.passed, bool)


def test_unknown_null_model_fails_loud() -> None:
    params = GauntletParams(seed=7, tier1_paths=40, tier2_paths=8, null_model="nope")
    with pytest.raises(DataError):
        run_gauntlet(_bars(), _spec(), params, run_id="x", snapshot_id=None)

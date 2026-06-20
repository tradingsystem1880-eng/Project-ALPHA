"""The gauntlet fails gracefully (not crashes) when a strategy produces a flat out-of-sample stream.

A long-flat strategy whose only signals are disallowed shorts never trades, so its OOS is a flat,
zero-variance equity curve and the headline Sharpe is undefined. The gauntlet must return a FAIL
report — not raise an undefined-Sharpe error mid-run. Here a long-flat (``allow_short=False``)
mean-reversion strategy on a monotonically rising series only ever signals "overbought → short",
which becomes no position.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from alpha_cli._gauntlet import GauntletParams, run_gauntlet
from alpha_cli._runner import RunSpec
from alpha_core import Bar


def _rising_bars(n: int = 40) -> list[Bar]:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Bar(
            symbol="SPY",
            ts=start + timedelta(days=i),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1e3,
        )
        for i, c in enumerate(100.0 + i for i in range(n))
    ]


def test_flat_oos_yields_a_clean_fail_report() -> None:
    spec = RunSpec(
        lookback=5,
        skip=1,
        vol_window=3,
        target_vol=0.15,
        rebalance_every=1,
        max_leverage=1.0,
        allow_short=False,  # long-flat: every "overbought → short" signal becomes no position
        periods_per_year=252,
        fee_bps=1.0,
        slippage_bps=2.0,
        starting_cash=100_000.0,
        account_type="CASH",
        train_size=8,
        test_size=4,
        embargo=1,
        anchored=False,
        strategy_name="mean_reversion",
        strategy_params=(("entry_z", 1.0), ("window", 4.0)),
    )
    out = run_gauntlet(
        _rising_bars(),
        spec,
        GauntletParams(seed=7, tier1_paths=20, tier2_paths=4, n_resamples=80, mean_block=5.0),
        run_id="degenerate",
        snapshot_id=None,
    )
    assert out.report.passed is False  # no measurable edge -> overall FAIL
    assert math.isnan(out.report.oos_metrics["sharpe"])  # Sharpe undefined on a flat OOS
    by_name = {o.name: o for o in out.report.outcomes}
    assert by_name["walk_forward_oos"].passed is False
    assert by_name["randomized_price_null"].passed is False
    assert by_name["bootstrap_ci"].passed is False
    # a no-edge run still produces a Verdict, and it is nowhere near a passing grade
    assert out.report.verdict is not None
    assert out.report.verdict.overall not in ("A", "B")
    assert math.isnan(out.report.oos_metrics["risk_of_ruin"])  # ruin undefined on a flat OOS

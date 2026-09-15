"""Tier-3 bar-permutation null inside the gauntlet (alpha_cli._synth / alpha_cli._gauntlet)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from alpha_cli._gauntlet import GauntletParams, run_gauntlet
from alpha_cli._runner import RunSpec, walk_forward_oos_for_spec
from alpha_cli._seeds import semantic_seed
from alpha_cli._synth import bar_permutation_null, permuted_bar_paths
from alpha_core import Bar, DataError
from alpha_validation.tearsheet import report_to_manifest


def _bars(n: int = 80, seed: int = 0) -> list[Bar]:
    rng = np.random.default_rng(seed)
    closes = 100.0 * np.cumprod(1.0 + 0.001 + rng.normal(0.0, 0.01, n))
    opens = np.concatenate([[100.0], closes[:-1] * (1.0 + rng.normal(0.0, 0.002, n - 1))])
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Bar(
            symbol="SPY",
            ts=start + timedelta(days=i),
            open=float(o),
            high=float(max(o, c) * 1.004),
            low=float(min(o, c) * 0.996),
            close=float(c),
            volume=1e3 + i,
        )
        for i, (o, c) in enumerate(zip(opens.tolist(), closes.tolist(), strict=True))
    ]


def _spec() -> RunSpec:
    return RunSpec(
        lookback=5,
        skip=1,
        vol_window=3,
        target_vol=0.15,
        rebalance_every=2,
        max_leverage=1.0,
        allow_short=False,
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


def test_permuted_paths_keep_the_prefix_axis_and_volume_and_shuffle_only_the_rest() -> None:
    bars = _bars()
    start = 30
    paths = permuted_bar_paths(bars, start_index=start, n_paths=3, seed=11)
    assert len(paths) == 3 and all(len(p) == len(bars) for p in paths)
    for path in paths:
        for i, (orig, perm) in enumerate(zip(bars, path, strict=True)):
            assert (perm.ts, perm.symbol, perm.volume) == (orig.ts, orig.symbol, orig.volume)
            if i <= start:
                assert (perm.open, perm.high, perm.low, perm.close) == (
                    orig.open,
                    orig.high,
                    orig.low,
                    orig.close,
                )
        closes = np.array([b.close for b in path])
        assert not np.array_equal(closes[start + 1 :], [b.close for b in bars[start + 1 :]])
        assert closes[-1] == pytest.approx(bars[-1].close, rel=1e-9)
    # three draws from one generator are three different permutations
    assert len({tuple(round(b.close, 9) for b in p) for p in paths}) == 3


def test_permuted_paths_are_seed_deterministic_and_fail_loud() -> None:
    bars = _bars(40)
    a = permuted_bar_paths(bars, start_index=5, n_paths=2, seed=3)
    b = permuted_bar_paths(bars, start_index=5, n_paths=2, seed=3)
    c = permuted_bar_paths(bars, start_index=5, n_paths=2, seed=4)
    assert [x.close for p in a for x in p] == [x.close for p in b for x in p]
    assert [x.close for p in a for x in p] != [x.close for p in c for x in p]
    with pytest.raises(DataError, match=r"^n_paths must be >= 1, got 0$"):
        permuted_bar_paths(bars, start_index=5, n_paths=0, seed=3)
    with pytest.raises(DataError, match=r"^start_index must be in \[0, 38\], got 39$"):
        permuted_bar_paths(bars, start_index=39, n_paths=1, seed=3)


def test_gauntlet_permutes_only_from_the_first_scored_oos_bar() -> None:
    bars, spec = _bars(), _spec()
    layout = walk_forward_oos_for_spec([(b.ts, 1.0) for b in bars], spec)
    first_scored = layout.folds[0].test_start
    (path,) = permuted_bar_paths(bars, start_index=first_scored - 1, n_paths=1, seed=1)
    for orig, perm in zip(bars[:first_scored], path[:first_scored], strict=True):
        assert (perm.open, perm.high, perm.low, perm.close) == (
            orig.open,
            orig.high,
            orig.low,
            orig.close,
        )
    assert path[first_scored].close != bars[first_scored].close


def test_bar_permutation_null_ranks_with_the_davison_hinkley_formula() -> None:
    bars, spec = _bars(), _spec()
    layout = walk_forward_oos_for_spec([(b.ts, 1.0) for b in bars], spec)
    result = bar_permutation_null(
        bars,
        observed=0.3,
        spec=spec,
        n_paths=5,
        start_index=layout.folds[0].test_start - 1,
        threshold=0.95,
        seed=9,
    )
    assert result.null.shape == (5,) and np.all(np.isfinite(result.null))
    assert result.n_paths == 5 and result.observed == 0.3
    at_least = int(np.sum(result.null >= 0.3))
    assert result.p_value == pytest.approx((1 + at_least) / 6)
    assert result.percentile == pytest.approx(float(np.mean(result.null < 0.3)))
    assert result.passed == (result.percentile >= 0.95)
    again = bar_permutation_null(
        bars, observed=0.3, spec=spec, n_paths=5, start_index=layout.folds[0].test_start - 1, seed=9
    )
    assert np.array_equal(again.null, result.null)
    with pytest.raises(DataError, match=r"^threshold must be in \(0, 1\), got 1.0$"):
        bar_permutation_null(
            bars, observed=0.3, spec=spec, n_paths=1, start_index=20, threshold=1.0
        )
    with pytest.raises(DataError, match=r"^bar-permutation null needs a finite observed statistic"):
        bar_permutation_null(bars, observed=float("nan"), spec=spec, n_paths=1, start_index=20)


def test_run_gauntlet_reports_the_third_tier_with_its_own_seed_and_knob() -> None:
    params = GauntletParams(seed=7, tier1_paths=30, tier2_paths=4, tier3_paths=6, n_resamples=100)
    out = run_gauntlet(_bars(), _spec(), params, run_id="t3", snapshot_id=None)
    assert [n.tier for n in out.report.nulls] == ["returns_level", "full_engine", "bar_permutation"]
    tier3 = out.report.nulls[2]
    assert tier3.n_paths == 6 and out.tier3_null.shape == (6,)
    assert tier3.observed == out.report.oos_metrics["sharpe"] == out.report.nulls[1].observed
    assert tier3.convention_divergence is None and tier3.flagged_low_fidelity is False
    assert out.report.metadata.tier3_paths == 6
    manifest = report_to_manifest(out.report)
    assert [n["tier"] for n in manifest["nulls"]][2] == "bar_permutation"
    assert manifest["metadata"]["tier3_paths"] == 6
    gate = {o.name: o for o in out.report.outcomes}["randomized_price_null"]
    assert gate.detail["bar_permutation_percentile"] == pytest.approx(tier3.percentile)
    # the knob is a run-identity input (validate_cmds hashes every GauntletParams field but
    # max_workers) and the tier draws from its own semantic namespace
    assert "tier3_paths" in vars(params)
    assert semantic_seed(7, "validation.bar_permutation_wf") != semantic_seed(
        7, "validation.tier2_null"
    )

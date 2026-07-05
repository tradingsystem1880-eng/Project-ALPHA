"""Tier-1 fidelity plumbing: OOS-window statistic + convention-divergence guard (spec §8 gate 3).

Root-cause context: docs/investigations/2026-06-23-tier1-surrogate-crediting-bias.md — the
close-fill Tier-1 surrogate structurally diverges from the engine's t+1-open fills for
high-turnover strategies; a Tier-1 FAIL in that regime is an artifact, not evidence.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_cli._gauntlet import (
    _convention_divergence,
    _oos_return_indices,
    _tier1_summary,
    _windowed,
)
from alpha_cli._runner import RunSpec
from alpha_cli._strategies import surrogate_for
from alpha_core import Bar
from alpha_validation import NullResult, walk_forward_splits


def _spec(**over: object) -> RunSpec:
    base = dict(
        lookback=5,
        skip=1,
        vol_window=5,
        target_vol=0.15,
        rebalance_every=1,
        max_leverage=1.0,
        allow_short=True,
        periods_per_year=252,
        fee_bps=0.0,
        slippage_bps=0.0,
        starting_cash=100_000.0,
        account_type="MARGIN",
        train_size=20,
        test_size=10,
        embargo=0,
        anchored=False,
        strategy_name="mean_reversion",
        strategy_params=(("entry_z", 0.5), ("window", 5.0)),
    )
    base.update(over)
    return RunSpec(**base)  # type: ignore[arg-type]


def _gapped_bars(n: int = 80, gap_scale: float = 0.02, seed: int = 3) -> list[Bar]:
    """Synthetic daily OHLCV with material overnight gaps (close != next open)."""
    from datetime import UTC, datetime, timedelta

    rng = np.random.default_rng(seed)
    closes = 100.0 * np.cumprod(1.0 + rng.normal(0.0005, 0.01, n))
    start = datetime(2020, 1, 1, tzinfo=UTC)
    bars: list[Bar] = []
    prev_close = closes[0]
    for i, c in enumerate(closes.tolist()):
        gap = float(rng.normal(0.0, gap_scale))
        o = prev_close * (1.0 + gap) if i > 0 else c
        hi, lo = max(o, c) * 1.001, min(o, c) * 0.999
        bars.append(
            Bar(
                symbol="X",
                ts=start + timedelta(days=i),
                open=o,
                high=hi,
                low=lo,
                close=c,
                volume=1e3,
            )
        )
        prev_close = c
    return bars


def test_oos_return_indices_match_walk_forward_test_windows() -> None:
    spec = _spec()
    idx = _oos_return_indices(59, spec)
    splits = walk_forward_splits(59, train_size=20, test_size=10, embargo=0, anchored=False)
    expected = np.concatenate([np.arange(sp.test.start, sp.test.stop) for sp in splits])
    assert np.array_equal(idx, expected)
    assert idx.min() >= 20  # nothing from the train region leaks into the scored window


def test_windowed_statistic_scores_only_the_oos_slice() -> None:
    idx = np.arange(50, 100)
    stat = _windowed(lambda r: float(np.mean(r)), idx)
    full = np.concatenate([np.full(50, -1.0), np.full(50, +1.0)])
    assert stat(full) == pytest.approx(1.0)  # the in-sample -1s never enter


def test_convention_divergence_zero_when_opens_equal_prior_close() -> None:
    # No overnight gap -> close-fill and open-fill credit identical moves -> divergence ~ 0.
    spec = _spec()
    bars = _gapped_bars(gap_scale=0.0)
    pr = np.array([bars[i + 1].close / bars[i].close - 1.0 for i in range(len(bars) - 1)])
    idx = _oos_return_indices(pr.size, spec)
    stat = lambda r: float(np.mean(r)) * 252  # noqa: E731 — simple linear score
    div = _convention_divergence(bars, pr, surrogate_for(spec), idx, stat)
    assert div == pytest.approx(0.0, abs=1e-9)


def test_convention_divergence_positive_for_gapped_high_turnover() -> None:
    # Real overnight gaps + a rebalance-every-bar mean-reversion book -> the two fill
    # conventions credit different gaps to different weights -> measurable divergence.
    spec = _spec()
    bars = _gapped_bars(gap_scale=0.02)
    pr = np.array([bars[i + 1].close / bars[i].close - 1.0 for i in range(len(bars) - 1)])
    idx = _oos_return_indices(pr.size, spec)
    stat = lambda r: float(np.mean(r)) * 252  # noqa: E731
    div = _convention_divergence(bars, pr, surrogate_for(spec), idx, stat)
    assert div > 0.0


def _null(passed: bool) -> NullResult:
    return NullResult(
        observed=0.1,
        null=np.zeros(4),
        percentile=0.9 if passed else 0.1,
        p_value=0.2,
        threshold=0.95,
        passed=passed,
        n_paths=4,
    )


def test_tier1_fail_is_flagged_only_when_artifact() -> None:
    # flagged: tier1 FAIL + tier2 PASS + divergence over tolerance
    s = _tier1_summary(_null(False), tier2_passed=True, divergence=0.6, tolerance=0.25)
    assert s.flagged_low_fidelity and not s.passed and s.convention_divergence == 0.6
    # NOT flagged: divergence within tolerance (a genuine fail)
    s = _tier1_summary(_null(False), tier2_passed=True, divergence=0.1, tolerance=0.25)
    assert not s.flagged_low_fidelity
    # NOT flagged: the faithful tier failed too — the AND-gate stands
    s = _tier1_summary(_null(False), tier2_passed=False, divergence=0.6, tolerance=0.25)
    assert not s.flagged_low_fidelity
    # NOT flagged: tier1 passed — nothing to demote
    s = _tier1_summary(_null(True), tier2_passed=True, divergence=0.6, tolerance=0.25)
    assert not s.flagged_low_fidelity and s.passed


def test_flagged_tier_reports_but_does_not_veto_the_gate() -> None:
    from alpha_validation import build_outcomes

    flagged = _tier1_summary(_null(False), tier2_passed=True, divergence=0.6, tolerance=0.25)
    from alpha_validation import NullSummary

    tier2 = NullSummary(
        tier="full_engine",
        observed=1.0,
        percentile=0.99,
        p_value=0.01,
        threshold=0.95,
        passed=True,
        n_paths=64,
    )
    outcomes = build_outcomes(
        oos_metrics={"sharpe": 1.0},
        nulls=(flagged, tier2),
        cis=(),
        dsr=None,
        cpcv=None,
    )
    null_gate = next(o for o in outcomes if o.name == "randomized_price_null")
    assert null_gate.passed  # advisory fail does not veto
    assert null_gate.detail["returns_level_flagged_low_fidelity"] == 1.0
    assert null_gate.detail["returns_level_convention_divergence"] == 0.6

    # an UNflagged tier-1 fail still vetoes
    genuine = _tier1_summary(_null(False), tier2_passed=True, divergence=0.1, tolerance=0.25)
    outcomes = build_outcomes(
        oos_metrics={"sharpe": 1.0}, nulls=(genuine, tier2), cis=(), dsr=None, cpcv=None
    )
    assert not next(o for o in outcomes if o.name == "randomized_price_null").passed

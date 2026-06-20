"""The quantstats HTML tear sheet renders and carries our custom gauntlet section.

Drives matplotlib/quantstats (a couple of seconds), so it lives in integration rather than the
fast unit suite. It is not a network test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from alpha_core import ValidationOutcome
from alpha_validation import (
    CISummary,
    FoldSummary,
    GauntletReport,
    NullSummary,
    RunMetadata,
    VerdictSummary,
    render_tearsheet_html,
)


def _report() -> GauntletReport:
    meta = RunMetadata(
        run_id="deadbeef",
        symbol="SPY",
        snapshot_id=None,
        seed=7,
        periods_per_year=252,
        fee_bps=1.0,
        slippage_bps=2.0,
        starting_cash=1_000_000.0,
        lookback=20,
        skip=2,
        vol_window=10,
        target_vol=0.15,
        rebalance_every=5,
        max_leverage=1.0,
        allow_short=True,
        train_size=60,
        test_size=20,
        embargo=2,
        anchored=False,
        n_bars=200,
        first_ts="2020-01-01T00:00:00+00:00",
        last_ts="2020-10-01T00:00:00+00:00",
        quantstats_version="1.1.5",
    )
    return GauntletReport(
        metadata=meta,
        oos_metrics={
            "sharpe": 0.9,
            "cagr": 0.11,
            "max_drawdown": -0.08,
            "value_at_risk": 0.018,
            "expected_shortfall": 0.026,
            "risk_of_ruin": 0.03,
        },
        folds=(
            FoldSummary(0, 0, 60, 60, 80, 20, 0.03, 0.7, 0.10),
            FoldSummary(1, 0, 80, 80, 100, 20, 0.01, 0.4, 0.05),
        ),
        nulls=(
            NullSummary("returns_level", 0.9, 0.97, 0.03, 0.95, True, 1000),
            NullSummary("full_engine", 0.9, 0.96, 0.04, 0.95, True, 64),
        ),
        cis=(
            CISummary("sharpe", 0.9, 0.2, 1.5, 0.95),
            CISummary("cagr", 0.11, 0.02, 0.20, 0.95),
        ),
        outcomes=(ValidationOutcome(name="walk_forward_oos", passed=True, detail={"sharpe": 0.9}),),
        passed=True,
        verdict=VerdictSummary(
            edge="B",
            robustness="A",
            risk="C",
            sample="A",
            overall="B",
            detail={"overall_gpa": 2.75},
        ),
    )


def test_renders_html_with_quantstats_body_and_gauntlet_section(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    n = 120
    returns = rng.normal(0.0008, 0.01, n)
    start = datetime(2020, 1, 1, tzinfo=UTC)
    stamps = [start + timedelta(days=i) for i in range(n)]
    out = tmp_path / "tearsheet.html"

    render_tearsheet_html(
        _report(), oos_returns=returns, oos_timestamps=stamps, output_path=out, periods_per_year=252
    )

    assert out.exists() and out.stat().st_size > 0
    body = out.read_text(encoding="utf-8")
    assert "<html" in body.lower()  # quantstats produced its report
    # the custom validation section and its sub-sections are present
    for marker in (
        "Validation Gauntlet",
        "Walk-Forward",
        "Randomized-Price Null",
        "BCa",
        "PASS",
        "full_engine",
        "Verdict",  # the A-F grade table
        "Risk Metrics",  # VaR / expected-shortfall / risk-of-ruin table
        "Risk of Ruin",
    ):
        assert marker in body, marker

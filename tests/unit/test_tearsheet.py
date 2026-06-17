"""Tear-sheet report schema (``alpha_validation.tearsheet``).

Grows across the Phase-5 steps; this first slice pins the report dataclasses and their public
export. Manifest serialization and HTML rendering are exercised once those helpers land.
"""

from __future__ import annotations

import dataclasses

import pytest

from alpha_core import ValidationOutcome
from alpha_validation import (
    CISummary,
    FoldSummary,
    GauntletReport,
    NullSummary,
    RunMetadata,
)


def _report() -> GauntletReport:
    meta = RunMetadata(
        run_id="abc123",
        symbol="SPY",
        snapshot_id=None,
        seed=7,
        periods_per_year=252,
        fee_bps=1.0,
        slippage_bps=2.0,
        starting_cash=1_000_000.0,
        lookback=252,
        skip=21,
        vol_window=63,
        target_vol=0.15,
        rebalance_every=21,
        max_leverage=1.0,
        allow_short=True,
        train_size=300,
        test_size=60,
        embargo=5,
        anchored=False,
        n_bars=800,
        first_ts="2018-01-02T00:00:00+00:00",
        last_ts="2021-03-01T00:00:00+00:00",
        quantstats_version="1.1.5",
    )
    return GauntletReport(
        metadata=meta,
        oos_metrics={"sharpe": 0.8, "cagr": 0.12},
        folds=(FoldSummary(0, 0, 300, 300, 360, 60, 0.02, 0.5, 0.09),),
        nulls=(NullSummary("returns_level", 0.8, 0.97, 0.03, 0.95, True, 1000),),
        cis=(CISummary("sharpe", 0.8, 0.1, 1.4, 0.95),),
        outcomes=(ValidationOutcome(name="walk_forward_oos", passed=True, detail={"sharpe": 0.8}),),
        passed=True,
    )


def test_report_assembles_and_holds_core_outcomes() -> None:
    report = _report()
    assert report.passed is True
    assert report.outcomes[0].name == "walk_forward_oos"
    assert isinstance(report.outcomes[0], ValidationOutcome)
    assert report.nulls[0].tier == "returns_level"


def test_report_pieces_are_frozen() -> None:
    report = _report()
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.metadata.seed = 9  # type: ignore[misc]

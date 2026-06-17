"""Tear-sheet report schema (``alpha_validation.tearsheet``).

Grows across the Phase-5 steps; this first slice pins the report dataclasses and their public
export. Manifest serialization and HTML rendering are exercised once those helpers land.
"""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

from alpha_core import ValidationOutcome
from alpha_validation import (
    CISummary,
    FoldSummary,
    GauntletReport,
    NullSummary,
    RunMetadata,
    build_outcomes,
    report_to_manifest,
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


def test_manifest_is_strict_json_with_nan_as_null() -> None:
    # a flat fold has an undefined (NaN) Sharpe; the manifest must still be valid JSON
    report = dataclasses.replace(
        _report(),
        folds=(FoldSummary(0, 0, 300, 300, 360, 60, 0.0, math.nan, math.nan),),
    )
    manifest = report_to_manifest(report)
    assert set(manifest) >= {
        "schema_version",
        "run_id",
        "metadata",
        "oos_metrics",
        "folds",
        "passed",
    }
    assert manifest["folds"][0]["oos_sharpe"] is None  # NaN -> null, not the JSON token NaN
    text = json.dumps(manifest, allow_nan=False, sort_keys=True)  # raises if any NaN survived
    assert json.loads(text)["run_id"] == "abc123"


def test_manifest_is_deterministic() -> None:
    a = json.dumps(report_to_manifest(_report()), sort_keys=True)
    b = json.dumps(report_to_manifest(_report()), sort_keys=True)
    assert a == b  # byte-identical for identical runs (spec §11.4)


def test_build_outcomes_gate_pass_logic() -> None:
    metrics = {"sharpe": 0.8, "cagr": 0.1}
    both_pass = [
        NullSummary("returns_level", 0.8, 0.97, 0.03, 0.95, True, 1000),
        NullSummary("full_engine", 0.8, 0.98, 0.02, 0.95, True, 64),
    ]
    edge_ci = [CISummary("sharpe", 0.8, 0.2, 1.4, 0.95)]  # lower clears zero
    outcomes = build_outcomes(oos_metrics=metrics, nulls=both_pass, cis=edge_ci)
    by_name = {o.name: o for o in outcomes}
    assert {"walk_forward_oos", "randomized_price_null", "bootstrap_ci"} == set(by_name)
    assert all(o.passed for o in outcomes)

    # any failing tier fails the null gate (conservative)
    one_fails = [both_pass[0], dataclasses.replace(both_pass[1], passed=False)]
    assert not _named(
        build_outcomes(oos_metrics=metrics, nulls=one_fails, cis=edge_ci), "randomized_price_null"
    ).passed

    # a Sharpe CI straddling zero fails the bootstrap gate
    zero_ci = [CISummary("sharpe", 0.4, -0.1, 1.0, 0.95)]
    assert not _named(
        build_outcomes(oos_metrics=metrics, nulls=both_pass, cis=zero_ci), "bootstrap_ci"
    ).passed


def _named(outcomes: tuple[ValidationOutcome, ...], name: str) -> ValidationOutcome:
    return next(o for o in outcomes if o.name == name)

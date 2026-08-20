"""Hidden holdout: the gauntlet gate semantics of spec §8 as behaviour, not implementation.

Every assertion here is a documented contract from CLAUDE.md "Validation gauntlet gates". A
change that silently relaxes a threshold, flips a comparison, or lets an advisory tier veto is
caught by tests the authoring agent never read.
"""

from __future__ import annotations

import math

import pytest

from alpha_core import ValidationOutcome
from alpha_validation.tearsheet import (
    CISummary,
    CPCVSummary,
    DSRSummary,
    NullSummary,
    build_outcomes,
)
from alpha_validation.verdict import VerdictSummary, grade_verdict

pytestmark = pytest.mark.holdout


def _null(tier: str, *, passed: bool, flagged: bool = False) -> NullSummary:
    return NullSummary(
        tier=tier,
        observed=1.0,
        percentile=0.99 if passed else 0.10,
        p_value=0.01 if passed else 0.90,
        threshold=0.95,
        passed=passed,
        n_paths=100,
        convention_divergence=0.5 if flagged else None,
        flagged_low_fidelity=flagged,
    )


def _ci(lower: float) -> CISummary:
    return CISummary(
        metric="sharpe", point=lower + 0.5, lower=lower, upper=lower + 1.0, confidence=0.95
    )


def _gates(
    *,
    sharpe: float = 1.0,
    nulls: list[NullSummary] | None = None,
    cis: list[CISummary] | None = None,
) -> dict[str, ValidationOutcome]:
    outcomes = build_outcomes(oos_metrics={"sharpe": sharpe}, nulls=nulls or [], cis=cis or [])
    return {o.name: o for o in outcomes}


def _verdict(
    *,
    oos_sharpe: float = 2.0,
    null_tiers_passed: bool = True,
    dsr_passed: bool = True,
    cpcv_passed: bool = True,
    ci_lower_positive: bool = True,
    max_drawdown: float = -0.05,
    risk_of_ruin: float = 0.0,
    n_oos: int = 1000,
) -> VerdictSummary:
    return grade_verdict(
        oos_sharpe=oos_sharpe,
        null_tiers_passed=null_tiers_passed,
        dsr_passed=dsr_passed,
        cpcv_passed=cpcv_passed,
        ci_lower_positive=ci_lower_positive,
        max_drawdown=max_drawdown,
        risk_of_ruin=risk_of_ruin,
        n_oos=n_oos,
    )


def test_walk_forward_gate_needs_a_finite_sharpe() -> None:
    assert _gates(sharpe=-0.3)["walk_forward_oos"].passed is True
    assert _gates(sharpe=math.nan)["walk_forward_oos"].passed is False


def test_null_gate_is_conservative_across_tiers() -> None:
    both = [_null("returns_level", passed=True), _null("full_engine", passed=True)]
    tier1_fail = [_null("returns_level", passed=False), _null("full_engine", passed=True)]
    tier2_fail = [_null("returns_level", passed=True), _null("full_engine", passed=False)]
    for nulls, expected in ((both, True), (tier1_fail, False), (tier2_fail, False)):
        assert _gates(nulls=nulls)["randomized_price_null"].passed is expected


def test_null_gate_with_no_tiers_cannot_pass() -> None:
    assert _gates(nulls=[])["randomized_price_null"].passed is False


def test_flagged_low_fidelity_tier1_is_advisory_not_a_veto() -> None:
    rescued = [
        _null("returns_level", passed=False, flagged=True),
        _null("full_engine", passed=True),
    ]
    gate = _gates(nulls=rescued)["randomized_price_null"]
    assert gate.passed is True
    assert gate.detail["returns_level_flagged_low_fidelity"] == 1.0
    assert gate.detail["returns_level_convention_divergence"] == 0.5


def test_bootstrap_ci_gate_requires_strictly_positive_lower_bound() -> None:
    for lower, expected in ((0.01, True), (0.0, False), (-0.01, False)):
        assert _gates(cis=[_ci(lower)])["bootstrap_ci"].passed is expected, lower
    assert _gates(cis=[])["bootstrap_ci"].passed is False


def test_optional_gates_are_appended_only_when_supplied() -> None:
    core = build_outcomes(oos_metrics={"sharpe": 1.0}, nulls=[], cis=[])
    assert [o.name for o in core] == ["walk_forward_oos", "randomized_price_null", "bootstrap_ci"]
    dsr = DSRSummary(
        sharpe=0.1,
        psr=0.97,
        dsr=0.96,
        expected_max_sharpe=0.0,
        n_trials=1,
        threshold=0.95,
        passed=True,
    )
    cpcv = CPCVSummary(n_folds=6, mean_sharpe=0.2, std_sharpe=0.1, frac_positive=0.8, passed=True)
    full = build_outcomes(oos_metrics={"sharpe": 1.0}, nulls=[], cis=[], dsr=dsr, cpcv=cpcv)
    assert [o.name for o in full][3:] == ["deflated_sharpe", "cpcv_oos"]
    assert full[3].detail["n_trials"] == 1.0
    assert full[4].detail["mean_sharpe"] == 0.2


def test_verdict_edge_bands_and_robustness_count() -> None:
    for sharpe, grade in ((1.5, "A"), (1.49, "B"), (1.0, "B"), (0.5, "C"), (0.0, "D"), (-0.1, "F")):
        assert _verdict(oos_sharpe=sharpe).edge == grade, sharpe
    # robustness = number of passed checks; zero passed is an F, all four is an A
    none = _verdict(
        null_tiers_passed=False, dsr_passed=False, cpcv_passed=False, ci_lower_positive=False
    )
    assert none.robustness == "F"
    assert _verdict().robustness == "A"
    assert _verdict(dsr_passed=False, cpcv_passed=False).robustness == "C"


def test_verdict_sample_size_bands_and_nan_drawdown() -> None:
    for n, grade in ((1000, "A"), (999, "B"), (500, "B"), (250, "C"), (100, "D"), (99, "F")):
        assert _verdict(n_oos=n).sample == grade, n
    assert _verdict(max_drawdown=math.nan).risk == "F"  # unknown drawdown is never graded safe

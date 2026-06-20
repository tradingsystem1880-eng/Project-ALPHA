"""A-F Verdict grading across edge / robustness / risk / sample-size (QuantPad-style headline).

``grade_verdict`` is a pure function over already-computed gauntlet quantities; it must degrade
gracefully (overall well below passing) when a degenerate OOS leaves inputs as ``NaN``.
"""

from __future__ import annotations

import dataclasses
import math

import pytest

from alpha_validation import VerdictSummary, grade_verdict


def _grade(**overrides: object) -> VerdictSummary:
    base: dict[str, object] = dict(
        oos_sharpe=2.0,
        null_tiers_passed=True,
        dsr_passed=True,
        cpcv_passed=True,
        ci_lower_positive=True,
        max_drawdown=-0.05,
        risk_of_ruin=0.0,
        n_oos=1500,
    )
    base.update(overrides)
    return grade_verdict(**base)  # type: ignore[arg-type]


def test_a_grade_strategy_scores_all_A() -> None:
    v = _grade()
    assert (v.edge, v.robustness, v.risk, v.sample, v.overall) == ("A", "A", "A", "A", "A")


def test_edge_grade_tracks_sharpe_bands() -> None:
    assert _grade(oos_sharpe=1.5).edge == "A"
    assert _grade(oos_sharpe=1.0).edge == "B"
    assert _grade(oos_sharpe=0.5).edge == "C"
    assert _grade(oos_sharpe=0.0).edge == "D"
    assert _grade(oos_sharpe=-0.01).edge == "F"


def test_robustness_counts_the_four_gate_checks() -> None:
    assert _grade(dsr_passed=False).robustness == "B"  # 3 of 4
    assert _grade(dsr_passed=False, cpcv_passed=False).robustness == "C"  # 2 of 4
    assert (
        _grade(
            null_tiers_passed=False, dsr_passed=False, cpcv_passed=False, ci_lower_positive=False
        ).robustness
        == "F"
    )  # 0 of 4


def test_risk_grade_is_the_worse_of_drawdown_and_ruin() -> None:
    # Shallow drawdown (A band) but a 25% ruin probability (D band) -> the worse one wins.
    assert _grade(max_drawdown=-0.05, risk_of_ruin=0.25).risk == "D"
    # Deep 40% drawdown (D band) with negligible ruin (A band) -> D.
    assert _grade(max_drawdown=-0.40, risk_of_ruin=0.0).risk == "D"


def test_sample_grade_tracks_oos_length() -> None:
    assert _grade(n_oos=1000).sample == "A"
    assert _grade(n_oos=500).sample == "B"
    assert _grade(n_oos=250).sample == "C"
    assert _grade(n_oos=100).sample == "D"
    assert _grade(n_oos=99).sample == "F"


def test_degenerate_inputs_degrade_to_a_failing_overall() -> None:
    # Flat OOS: undefined Sharpe + ruin, all robustness gates failed; only sample survives.
    v = _grade(
        oos_sharpe=math.nan,
        null_tiers_passed=False,
        dsr_passed=False,
        cpcv_passed=False,
        ci_lower_positive=False,
        max_drawdown=0.0,
        risk_of_ruin=math.nan,
        n_oos=1500,
    )
    assert v.edge == "F" and v.robustness == "F" and v.risk == "F"
    assert v.overall not in ("A", "B")  # nowhere near a passing grade


def test_detail_carries_the_component_scores() -> None:
    v = _grade(oos_sharpe=1.2, max_drawdown=-0.08, risk_of_ruin=0.02, n_oos=600)
    assert v.detail["edge_sharpe"] == pytest.approx(1.2)
    assert v.detail["risk_max_drawdown"] == pytest.approx(-0.08)
    assert v.detail["risk_of_ruin"] == pytest.approx(0.02)
    assert v.detail["sample_n_oos"] == pytest.approx(600.0)
    assert v.detail["robustness_checks_passed"] == pytest.approx(4.0)


def test_verdict_summary_is_frozen() -> None:
    v = _grade()
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.overall = "F"  # type: ignore[misc]

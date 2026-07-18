"""A-F "Verdict" grade for one validation run (the QuantPad-style headline).

Pure grading over already-computed gauntlet quantities — no numpy, no engine, no I/O — so the rules
are auditable in one place and trivially unit-testable. Four dimensions are graded independently and
then averaged on a 4.0 scale:

- **edge** — the annualized OOS Sharpe (is there a risk-adjusted return at all?).
- **robustness** — how many of the four robustness gates held (both null tiers, DSR, CPCV,
  Sharpe-CI lower bound > 0).
- **risk** — the *worse* of the max-drawdown band and the risk-of-ruin band (a strategy is only as
  safe as its ugliest tail).
- **sample** — how many out-of-sample observations backed the verdict.

Every threshold is a module-level constant so the grade is reproducible and easy to retune. NaN
inputs (a degenerate, flat OOS) score ``F`` on the affected dimension rather than raising.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

_Bands = tuple[tuple[float, str], ...]

# NOTE: the Workstation UI mirrors these bands in
# apps/alpha-web/frontend/src/explain/bands.ts to EXPLAIN grades (the persisted verdict stays
# authoritative). Change a band here -> update bands.ts; its vitest drift-guard re-grades real
# manifests and fails on mismatch.
# (inclusive lower bound, grade), scanned high-to-low; anything below the last bound is "F".
_EDGE_BANDS: _Bands = ((1.5, "A"), (1.0, "B"), (0.5, "C"), (0.0, "D"))
_SAMPLE_BANDS: _Bands = ((1000, "A"), (500, "B"), (250, "C"), (100, "D"))
_ROBUSTNESS_BY_COUNT: tuple[str, ...] = ("F", "D", "C", "B", "A")  # index = checks passed (0..4)
# Risk bands use the *upper* bound (smaller is better); scanned low-to-high.
_DRAWDOWN_BANDS: _Bands = ((0.10, "A"), (0.20, "B"), (0.35, "C"), (0.50, "D"))
_RUIN_BANDS: _Bands = ((0.01, "A"), (0.05, "B"), (0.15, "C"), (0.30, "D"))
_OVERALL_BANDS: _Bands = ((3.5, "A"), (2.5, "B"), (1.5, "C"), (0.5, "D"))

_GPA: Mapping[str, float] = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}


@dataclass(frozen=True)
class VerdictSummary:
    """The A-F grade for one run: four dimensions, an overall, plus the scores behind them."""

    edge: str
    robustness: str
    risk: str
    sample: str
    overall: str
    detail: Mapping[str, float]


def _grade_at_least(value: float, bands: _Bands) -> str:
    """Highest band whose lower bound ``value`` clears; ``F`` if it clears none (or is NaN)."""
    if not math.isfinite(value):
        return "F"
    for bound, grade in bands:
        if value >= bound:
            return grade
    return "F"


def _grade_at_most(value: float, bands: _Bands) -> str:
    """Best band whose upper bound ``value`` stays within; ``F`` if it exceeds all (or is NaN)."""
    if not math.isfinite(value):
        return "F"
    for bound, grade in bands:
        if value <= bound:
            return grade
    return "F"


def _worse(a: str, b: str) -> str:
    return a if _GPA[a] <= _GPA[b] else b


def grade_verdict(
    *,
    oos_sharpe: float,
    null_tiers_passed: bool,
    dsr_passed: bool,
    cpcv_passed: bool,
    ci_lower_positive: bool,
    max_drawdown: float,
    risk_of_ruin: float,
    n_oos: int,
) -> VerdictSummary:
    """Grade one validation run A-F across edge / robustness / risk / sample-size.

    See the module docstring for the dimensions. ``max_drawdown`` is the non-positive fraction from
    :func:`alpha_validation.metrics.max_drawdown`; ``risk_of_ruin`` is a probability in ``[0, 1]``.
    The overall grade is the equal-weighted 4.0-scale average of the four dimensions.
    """
    edge = _grade_at_least(oos_sharpe, _EDGE_BANDS)
    checks = sum((null_tiers_passed, dsr_passed, cpcv_passed, ci_lower_positive))
    robustness = _ROBUSTNESS_BY_COUNT[checks]
    drawdown_depth = abs(max_drawdown) if math.isfinite(max_drawdown) else math.nan
    risk = _worse(
        _grade_at_most(drawdown_depth, _DRAWDOWN_BANDS),
        _grade_at_most(risk_of_ruin, _RUIN_BANDS),
    )
    sample = _grade_at_least(float(n_oos), _SAMPLE_BANDS)

    gpa = sum(_GPA[g] for g in (edge, robustness, risk, sample)) / 4.0
    overall = _grade_at_least(gpa, _OVERALL_BANDS)

    detail: dict[str, float] = {
        "edge_sharpe": oos_sharpe,
        "robustness_checks_passed": float(checks),
        "risk_max_drawdown": max_drawdown,
        "risk_of_ruin": risk_of_ruin,
        "sample_n_oos": float(n_oos),
        "overall_gpa": gpa,
    }
    return VerdictSummary(
        edge=edge, robustness=robustness, risk=risk, sample=sample, overall=overall, detail=detail
    )

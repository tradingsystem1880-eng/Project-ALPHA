"""Conditional probability with an honest comparison arm — "does X actually raise the odds?".

Every claim a discretionary trader makes has the same shape: *when X happens, Y tends to follow*.
Measured naively, that claim is almost always "true" and almost always worthless, because the
quantity people report is ``P(Y | X)`` and the quantity that matters is how that compares with
``P(Y | not X)``. An asset rising 20% in the next 30 days may happen roughly a fifth of the time
unconditionally; a signal that "predicts" it 22% of the time has told you nothing.

So the unit of analysis here is a **difference of two proportions**, with the sample split into two
disjoint arms:

- **arm A** — bars where the condition holds
- **arm B** — bars where it does not

Disjointness is not a detail. Comparing arm A against the *unconditional* rate compares overlapping
samples, and the resulting interval is too narrow by exactly the amount that would make a null
result look real. :func:`~alpha_validation.proportion.newcombe_diff_interval` then supplies the
interval on the difference, which is the number the whole study is built to read.

Three further corrections are wired in because omitting any one of them reliably manufactures
findings:

1. **``valid``** masks bars whose outcome is not yet knowable — the tail of the series where the
   forward window runs off the end, and the warm-up head where the predictor has no history. Left
   unmasked, unresolved bars silently count as failures and every rate is biased downward.
2. **``overlap``** deflates both arms by the factor from
   :func:`~alpha_validation.proportion.overlap_factor`. A 30-day forward window measured on daily
   bars gives ~30 overlapping observations of the same episode; treating them as 30 independent
   trials shrinks every interval by ``sqrt(30)``.
3. **``apply_fdr``** carries a family of results through Benjamini-Hochberg. Screening ten
   predictors against four outcomes is forty hypotheses, and two of them clear ``p < 0.05`` by
   construction.

Pure ``numpy``/``scipy``, engine-agnostic, fails loud on degenerate input.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats

from alpha_core import DataError
from alpha_validation.proportion import (
    ProportionInterval,
    benjamini_hochberg,
    newcombe_diff_interval,
    wilson_interval,
)

BoolSeq = Sequence[bool] | np.ndarray


@dataclass(frozen=True)
class LiftResult:
    """One condition tested against one outcome, with everything needed to read it honestly."""

    condition: str
    outcome: str
    family: str

    n_condition: int  # nominal bars where the condition held and the outcome was knowable
    n_complement: int
    hits_condition: int
    hits_complement: int

    n_condition_eff: int  # after deflating by the overlap factor — the basis of every interval
    n_complement_eff: int
    overlap: float

    rate_condition: float
    rate_complement: float
    rate_overall: float  # unconditional, reported for context only — never the comparison arm
    lift: float  # rate_condition / rate_complement; inf when the complement never fires

    interval_condition: ProportionInterval
    interval_complement: ProportionInterval
    interval_difference: ProportionInterval  # the headline: contains 0 => nothing shown
    pvalue: float

    qvalue: float = float("nan")  # filled by apply_fdr
    rejected: bool = False

    @property
    def difference(self) -> float:
        return self.rate_condition - self.rate_complement

    @property
    def separated(self) -> bool:
        """Whether the difference interval excludes zero — the only honest 'this works' claim."""
        return not self.interval_difference.contains(0.0)

    def line(self) -> str:
        """One fixed-width row, for a terminal table."""
        d = self.interval_difference
        star = "*" if self.rejected else (" " if math.isnan(self.qvalue) else ".")
        return (
            f"{self.condition:<34} {self.outcome:<16} "
            f"n={self.n_condition:>7,}/{self.n_condition_eff:>5,} "
            f"{self.rate_condition:>6.1%} vs {self.rate_complement:>6.1%} "
            f"diff {self.difference:>+6.1%} [{d.lower:>+6.1%},{d.upper:>+6.1%}] "
            f"p={self.pvalue:.3g} {star}"
        )


def _as_bool(values: BoolSeq, name: str, size: int | None = None) -> np.ndarray:
    arr = np.asarray(values)
    if arr.ndim != 1:
        raise DataError(f"{name} must be 1-D, got shape {arr.shape}")
    if arr.dtype != np.bool_:
        if not bool(np.all(np.isin(arr, (0, 1)))):
            raise DataError(f"{name} must be boolean or 0/1, got dtype {arr.dtype}")
        arr = arr.astype(bool)
    if size is not None and arr.size != size:
        raise DataError(f"{name} has {arr.size} entries, expected {size}")
    return arr


def conditional_lift(
    condition: BoolSeq,
    outcome: BoolSeq,
    *,
    label: str = "condition",
    outcome_label: str = "outcome",
    family: str = "",
    valid: BoolSeq | None = None,
    overlap: float = 1.0,
    confidence: float = 0.95,
) -> LiftResult:
    """``P(outcome | condition)`` against ``P(outcome | not condition)``, with intervals.

    ``overlap`` is the factor by which observations double-count each other (1.0 = independent).
    Both arms are deflated by it before any interval or p-value is computed, so the reported
    precision reflects how many independent episodes the sample really contains rather than how many
    rows the dataframe happens to have. Nominal counts are retained alongside, because hiding them
    would make the deflation unauditable.

    Raises rather than returning a degenerate result when either arm is empty: a condition that
    never fires, or that fires on every bar, has no comparison to make and silently returning
    ``nan`` would let it flow into a table looking like a measurement.
    """
    cond = _as_bool(condition, "condition")
    out = _as_bool(outcome, "outcome", cond.size)
    ok = np.ones(cond.size, dtype=bool) if valid is None else _as_bool(valid, "valid", cond.size)
    if overlap < 1.0:
        raise DataError(f"overlap must be >= 1 (1 = independent), got {overlap}")

    a_mask = cond & ok
    b_mask = (~cond) & ok
    n_a, n_b = int(np.count_nonzero(a_mask)), int(np.count_nonzero(b_mask))
    if n_a == 0 or n_b == 0:
        raise DataError(
            f"conditional_lift({label!r} x {outcome_label!r}): arm sizes {n_a}/{n_b} — a condition "
            "that always or never fires has no comparison arm"
        )

    k_a = int(np.count_nonzero(out & a_mask))
    k_b = int(np.count_nonzero(out & b_mask))

    n_a_eff, k_a_eff = _deflate(n_a, k_a, overlap)
    n_b_eff, k_b_eff = _deflate(n_b, k_b, overlap)

    p_a, p_b = k_a / n_a, k_b / n_b
    return LiftResult(
        condition=label,
        outcome=outcome_label,
        family=family,
        n_condition=n_a,
        n_complement=n_b,
        hits_condition=k_a,
        hits_complement=k_b,
        n_condition_eff=n_a_eff,
        n_complement_eff=n_b_eff,
        overlap=float(overlap),
        rate_condition=p_a,
        rate_complement=p_b,
        rate_overall=(k_a + k_b) / (n_a + n_b),
        lift=(p_a / p_b) if p_b > 0.0 else float("inf"),
        interval_condition=wilson_interval(k_a_eff, n_a_eff, confidence=confidence),
        interval_complement=wilson_interval(k_b_eff, n_b_eff, confidence=confidence),
        interval_difference=newcombe_diff_interval(
            k_a_eff, n_a_eff, k_b_eff, n_b_eff, confidence=confidence
        ),
        pvalue=two_proportion_pvalue(k_a_eff, n_a_eff, k_b_eff, n_b_eff),
    )


def _deflate(n: int, k: int, overlap: float) -> tuple[int, int]:
    """Shrink a count to its effective size, keeping the proportion and staying >= 1 trial."""
    if overlap <= 1.0:
        return n, k
    n_eff = max(1, int(round(n / overlap)))
    k_eff = int(round(k * n_eff / n)) if n > 0 else 0
    return n_eff, min(k_eff, n_eff)


def two_proportion_pvalue(k_a: int, n_a: int, k_b: int, n_b: int) -> float:
    """Two-sided score (pooled-variance z) test for equality of two proportions.

    Chosen over Fisher's exact test purely for speed — this runs over hundreds of cells against
    hundreds of thousands of bars, and at these sample sizes the two agree to more decimal places
    than the study can justify reporting. A pooled proportion of exactly 0 or 1 means neither arm
    ever fired, which is no evidence of a difference, so the p-value is 1.
    """
    if n_a <= 0 or n_b <= 0:
        raise DataError("two_proportion_pvalue needs positive trial counts")
    pooled = (k_a + k_b) / (n_a + n_b)
    if pooled <= 0.0 or pooled >= 1.0:
        return 1.0
    se = math.sqrt(pooled * (1.0 - pooled) * (1.0 / n_a + 1.0 / n_b))
    if se <= 0.0:
        return 1.0
    z = (k_a / n_a - k_b / n_b) / se
    return float(2.0 * stats.norm.sf(abs(z)))


def lift_table(
    conditions: Mapping[str, BoolSeq],
    outcomes: Mapping[str, BoolSeq],
    *,
    family: str = "",
    valid: Mapping[str, BoolSeq] | None = None,
    overlap: Mapping[str, float] | None = None,
    confidence: float = 0.95,
    skip_degenerate: bool = True,
) -> list[LiftResult]:
    """Every ``condition x outcome`` cell, as a flat list ready for :func:`apply_fdr`.

    ``valid`` and ``overlap`` are keyed by *outcome* name, because both properties belong to the
    forward window rather than the predictor: a 90-day pump label is unknowable for the last 90 days
    and overlaps ~90x, whichever condition is being tested against it.

    ``skip_degenerate`` drops conditions that never fire (or always fire) against a given outcome's
    valid mask rather than aborting the whole table — with dozens of predictors screened across
    several assets, one empty arm should not cost the other ninety-nine cells.
    """
    if not conditions:
        raise DataError("lift_table needs at least one condition")
    if not outcomes:
        raise DataError("lift_table needs at least one outcome")

    results: list[LiftResult] = []
    for out_name, out_values in outcomes.items():
        ok = None if valid is None else valid.get(out_name)
        ov = 1.0 if overlap is None else overlap.get(out_name, 1.0)
        for cond_name, cond_values in conditions.items():
            try:
                results.append(
                    conditional_lift(
                        cond_values,
                        out_values,
                        label=cond_name,
                        outcome_label=out_name,
                        family=family,
                        valid=ok,
                        overlap=ov,
                        confidence=confidence,
                    )
                )
            except DataError:
                if not skip_degenerate:
                    raise
    return results


def apply_fdr(results: Sequence[LiftResult], *, alpha: float = 0.05) -> list[LiftResult]:
    """Benjamini-Hochberg across a family, returning copies with ``qvalue``/``rejected`` filled.

    Apply this **within** a family of related predictors, not across every cell in the study. With
    ``m`` in the tens, BH retains useful power; pooling six hundred cells into one correction
    destroys it, and would also be the wrong question — the families test different mechanisms and
    a discovery in one is not made less likely by a null in another.
    """
    if not results:
        return []
    adjusted = benjamini_hochberg([r.pvalue for r in results], alpha=alpha)
    return [
        dataclasses.replace(r, qvalue=float(q), rejected=bool(rej))
        for r, q, rej in zip(results, adjusted.qvalues, adjusted.rejected, strict=True)
    ]


def monotonic_trend(rates: Sequence[float], counts: Sequence[int]) -> float:
    """Cochran-Armitage trend statistic over ordered bins — "does more confluence mean more?".

    The sharpest available test of the confluence idea itself. Stacking signals is supposed to
    produce a *monotone* improvement: two conditions should beat one, three should beat two. A
    single bright bin among five is a multiplicity artefact; a rising staircase is a mechanism.

    Returns a z-score for the linear trend in proportions across equally-spaced bins. Positive means
    the rate rises with the bin index.
    """
    p = np.asarray(rates, dtype=np.float64)
    n = np.asarray(counts, dtype=np.float64)
    if p.shape != n.shape or p.size < 3:
        raise DataError(f"monotonic_trend needs >= 3 matching bins, got {p.shape} and {n.shape}")
    if bool(np.any(n <= 0)):
        raise DataError("monotonic_trend needs positive counts in every bin")

    scores = np.arange(p.size, dtype=np.float64)
    total = float(np.sum(n))
    k = float(np.sum(p * n))
    p_bar = k / total
    if p_bar <= 0.0 or p_bar >= 1.0:
        return 0.0

    mean_score = float(np.sum(n * scores) / total)
    numerator = float(np.sum(n * (p - p_bar) * (scores - mean_score)))
    variance = p_bar * (1.0 - p_bar) * float(np.sum(n * (scores - mean_score) ** 2))
    if variance <= 0.0:
        return 0.0
    return float(numerator / math.sqrt(variance))

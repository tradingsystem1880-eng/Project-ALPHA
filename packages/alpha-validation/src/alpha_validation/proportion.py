"""Interval estimation for *proportions*, and the multiplicity/overlap corrections around them.

A pattern study asks binary questions — "did the target get hit before the stop?" — so its headline
number is a proportion ``k/n``. Three things routinely make such a proportion lie, and this module
supplies the correction for each:

- **Small-sample skew.** The textbook "normal approximation" interval ``p ± z·sqrt(p(1-p)/n)`` is
  badly wrong when ``p`` is near 0 or 1, which is exactly where a high-reward/low-probability setup
  lives. It can even produce a negative lower bound. :func:`wilson_interval` inverts the *score*
  test instead, which stays inside ``[0, 1]`` and keeps its nominal coverage down to small ``n``.
- **Comparing against a control.** The edge of a pattern is a *difference* of two proportions, and
  the CI on a difference is not the difference of the two CIs. :func:`newcombe_diff_interval`
  implements Newcombe's score-based method, which keeps coverage when either arm is near 0 or 1.
- **Testing many things at once.** Sweeping parameters generates many hypotheses, and at
  ``alpha=0.05`` one in twenty looks "significant" by luck alone. :func:`benjamini_hochberg`
  controls the *false discovery rate* — the expected share of claimed discoveries that are wrong.

:func:`effective_sample_size` addresses a fourth, subtler failure that is specific to forward-return
studies: when each observation looks ``horizon`` bars into the future but events occur closer
together than that, consecutive observations share most of their price path and are **not
independent**. Treating them as independent inflates ``n`` and shrinks every interval, which is how
a backtest can count one market episode hundreds of times and report false precision.

Pure ``numpy``/``scipy``; fails loud (``DataError``) on degenerate input.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats

from alpha_core import DataError
from alpha_validation.metrics import FloatArray, FloatSeq


@dataclass(frozen=True)
class ProportionInterval:
    """A point estimate and confidence bounds for a proportion (or a difference of two)."""

    point: float
    lower: float
    upper: float
    confidence: float
    successes: int  # -1 for a difference interval, where a single success count is meaningless
    trials: int  # -1 for a difference interval

    def contains(self, value: float) -> bool:
        """Whether ``value`` (e.g. a breakeven win rate) lies inside the interval.

        The decision rule for a trading edge: if the interval *contains* breakeven, the data cannot
        distinguish the setup from a coin flip at that payoff, whatever the point estimate says.
        """
        return self.lower <= value <= self.upper

    def beats(self, value: float) -> bool:
        """Whether the interval sits strictly above ``value`` — the only honest edge claim."""
        return self.lower > value


@dataclass(frozen=True)
class MultipleTestResult:
    """Benjamini-Hochberg outcome over a family of hypotheses, in the input order."""

    pvalues: FloatArray
    qvalues: FloatArray  # BH-adjusted p-values (monotone), comparable against alpha
    rejected: np.ndarray  # bool mask: survived FDR control
    alpha: float
    n_tests: int
    n_rejected: int


def _z(confidence: float) -> float:
    if not 0.0 < confidence < 1.0:
        raise DataError(f"confidence must be in (0, 1), got {confidence}")
    return float(stats.norm.ppf(0.5 + confidence / 2.0))


def _check_counts(successes: int, trials: int, name: str) -> None:
    if trials <= 0:
        raise DataError(f"{name} needs trials > 0, got {trials}")
    if successes < 0 or successes > trials:
        raise DataError(f"{name} needs 0 <= successes <= trials, got {successes}/{trials}")


def wilson_interval(successes: int, trials: int, *, confidence: float = 0.95) -> ProportionInterval:
    """Wilson score interval for a binomial proportion.

    Prefer this to the normal approximation whenever ``p`` is small or ``n`` is modest — the regime
    of every high-R:R setup study. The interval is obtained by inverting the score test, i.e. by
    solving for the values of ``p`` that the observed data would not reject, which is why it never
    escapes ``[0, 1]``.

    The centre is pulled toward ``1/2`` by ``z^2/2n``: with little data the estimate is shrunk
    toward "no information", which is the behaviour that keeps coverage honest at the extremes.
    """
    _check_counts(successes, trials, "wilson_interval")
    z = _z(confidence)
    n = float(trials)
    p = successes / n

    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    # Half-width of the score interval; the z^2/4n^2 term is the finite-sample correction.
    margin = (z / denom) * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))

    return ProportionInterval(
        point=p,
        lower=max(0.0, centre - margin),
        upper=min(1.0, centre + margin),
        confidence=confidence,
        successes=successes,
        trials=trials,
    )


def newcombe_diff_interval(
    successes_a: int,
    trials_a: int,
    successes_b: int,
    trials_b: int,
    *,
    confidence: float = 0.95,
) -> ProportionInterval:
    """Confidence interval for ``p_a - p_b`` (Newcombe's score method, "method 10").

    This is the statistic that answers "does the pattern beat its control?". Naively subtracting two
    point estimates gives a number with no interval; naively combining two Wilson intervals is
    anti-conservative. Newcombe's construction propagates each arm's *score* interval into the
    difference, which retains coverage even when one arm is near 0 — the usual case here, since a
    166%-target barrier test wins only a few percent of the time.

    A difference interval that straddles zero means the pattern has not been shown to beat control.
    """
    _check_counts(successes_a, trials_a, "newcombe_diff_interval (arm A)")
    _check_counts(successes_b, trials_b, "newcombe_diff_interval (arm B)")

    a = wilson_interval(successes_a, trials_a, confidence=confidence)
    b = wilson_interval(successes_b, trials_b, confidence=confidence)
    diff = a.point - b.point

    # Combine the *near* bound of one arm with the *far* bound of the other, in quadrature.
    lower = diff - math.sqrt((a.point - a.lower) ** 2 + (b.upper - b.point) ** 2)
    upper = diff + math.sqrt((a.upper - a.point) ** 2 + (b.point - b.lower) ** 2)

    return ProportionInterval(
        point=diff,
        lower=max(-1.0, lower),
        upper=min(1.0, upper),
        confidence=confidence,
        successes=-1,
        trials=-1,
    )


def benjamini_hochberg(pvalues: FloatSeq, *, alpha: float = 0.05) -> MultipleTestResult:
    """Benjamini-Hochberg false-discovery-rate control over a family of p-values.

    Bonferroni controls the probability of *any* false positive and is crushingly conservative for
    large families. BH instead controls the expected *fraction* of claimed discoveries that are
    false, which is the right target when screening many configurations.

    Mechanically: sort ascending, compare ``p_(i)`` against ``alpha * i / m``, and reject everything
    up to the largest ``i`` that passes. The q-values returned here are the BH-adjusted p-values,
    made monotone by a running minimum from the largest downward so that a more extreme p-value can
    never receive a worse q-value.

    Note the direction of the correction: BH can only ever make a result *less* significant. If a
    family produced no raw significance, no correction will rescue it.
    """
    arr = np.asarray(pvalues, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 1:
        raise DataError(f"benjamini_hochberg needs a non-empty 1-D array, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError("benjamini_hochberg requires finite p-values")
    if bool(np.any((arr < 0.0) | (arr > 1.0))):
        raise DataError("benjamini_hochberg requires p-values in [0, 1]")
    if not 0.0 < alpha < 1.0:
        raise DataError(f"alpha must be in (0, 1), got {alpha}")

    m = arr.size
    order = np.argsort(arr, kind="stable")
    ranks = np.arange(1, m + 1, dtype=np.float64)

    scaled = arr[order] * m / ranks
    # Enforce monotonicity walking down from the largest, then clip back into [0, 1].
    monotone = np.minimum.accumulate(scaled[::-1])[::-1]
    qsorted = np.clip(monotone, 0.0, 1.0)

    qvalues = np.empty(m, dtype=np.float64)
    qvalues[order] = qsorted
    rejected = qvalues <= alpha

    return MultipleTestResult(
        pvalues=arr,
        qvalues=qvalues,
        rejected=rejected,
        alpha=alpha,
        n_tests=m,
        n_rejected=int(np.count_nonzero(rejected)),
    )


def effective_sample_size(n_events: int, *, span_bars: int, horizon_bars: int) -> float:
    """Independent-observation count when forward windows of ``horizon_bars`` overlap.

    Each event is scored over the following ``horizon_bars``. If events recur faster than that,
    neighbouring observations read largely the *same* price path, so they carry far less than one
    independent observation each.

    With events spread across ``span_bars``, mean spacing is ``span/n`` and the overlap factor is
    ``horizon / spacing``. Dividing the event count by that factor gives ``span / horizon`` — which
    is exactly the number of non-overlapping windows the sample can hold. The two derivations
    coincide algebraically, which is a useful sanity check: no sampling scheme extracts more
    independent 90-day observations than the record contains 90-day blocks.

    Returns a float (an effective count need not be an integer), never above ``n_events``.
    """
    if n_events < 0:
        raise DataError(f"effective_sample_size needs n_events >= 0, got {n_events}")
    if span_bars <= 0:
        raise DataError(f"effective_sample_size needs span_bars > 0, got {span_bars}")
    if horizon_bars <= 0:
        raise DataError(f"effective_sample_size needs horizon_bars > 0, got {horizon_bars}")
    if n_events == 0:
        return 0.0
    return float(min(float(n_events), span_bars / horizon_bars))


def overlap_factor(n_events: int, *, span_bars: int, horizon_bars: int) -> float:
    """How many times the average observation is double-counted (``>= 1``; 1 means no overlap).

    Reported alongside every sample size so an inflated ``n`` is visible rather than implicit.
    """
    n_eff = effective_sample_size(n_events, span_bars=span_bars, horizon_bars=horizon_bars)
    if n_eff <= 0.0:
        return 1.0
    return max(1.0, n_events / n_eff)


def autocorrelation_effective_size(series: FloatSeq, *, max_lag: int | None = None) -> float:
    """Effective sample size of a serially-correlated series, ``n / (1 + 2*sum rho_k)``.

    The companion to :func:`effective_sample_size` for the case where dependence is not induced by a
    known window width but is estimated from the data itself. Summation stops at the first negative
    autocorrelation (the standard initial-positive-sequence truncation), which keeps the estimate
    stable when higher lags are pure noise.
    """
    arr = np.asarray(series, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 2:
        raise DataError(f"autocorrelation_effective_size needs >= 2 points, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError("autocorrelation_effective_size requires finite values")

    n = arr.size
    centred = arr - float(np.mean(arr))
    denom = float(np.dot(centred, centred))
    if denom <= 0.0:
        raise DataError("autocorrelation_effective_size undefined for a zero-variance series")

    lag_cap = n - 1 if max_lag is None else min(max_lag, n - 1)
    total = 0.0
    for lag in range(1, lag_cap + 1):
        rho = float(np.dot(centred[:-lag], centred[lag:]) / denom)
        if rho <= 0.0:
            break
        total += rho

    return float(min(float(n), n / (1.0 + 2.0 * total)))

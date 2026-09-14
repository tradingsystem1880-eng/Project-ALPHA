"""Wald–Wolfowitz runs test of dependence between consecutive trade outcomes.

A run is a maximal streak of equal signs. Wald & Wolfowitz (1940) show that, when the ``n``
signs are exchangeable, the number of runs ``R`` over ``n_pos`` positives and ``n_neg``
negatives has mean ``2 n_pos n_neg / n + 1`` and variance ``(mean - 1)(mean - 2) / (n - 1)``,
and that ``(R - mean) / sd`` is asymptotically standard normal. A negative z means outcomes
cluster (wins follow wins), a positive z means they alternate; the two-sided p-value is the
normal tail. Zeros count in ``n`` and break a run without being positive or negative, exactly
as ``alpha_patterns.runs.runs_z`` (parity-tested; this package cannot import that layer).

Provenance: github.com/neurotrader888/TradeDependenceRunsTest/runs_test.py @5f63804 (MIT).
Adapted: typed result with the run count, expectation and p-value; ``DataError`` on malformed
input and on a zero variance (upstream divides by zero when fewer than two distinct signs
occur); ``trade_runs_test`` returns ``None`` for the undefined cases so a report can say why.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from alpha_core import DataError
from alpha_validation.metrics import FloatSeq


@dataclass(frozen=True, slots=True)
class RunsTestResult:
    z: float
    p_value: float
    n_runs: int
    expected_runs: float
    n_signs: int


def runs_test(signs: FloatSeq) -> RunsTestResult:
    """Runs-test z-score and two-sided normal p-value of a sign sequence.

    Every value is reduced to its sign first, so magnitudes never change the statistic. Fails
    loud on a non-1-D or non-finite input, fewer than two signs, or a zero variance (fewer than
    two distinct signs, or one positive and one negative sign only).
    """
    s = _signs(signs, "runs test signs")
    n = int(s.size)
    if n < 2:
        raise DataError(f"runs test needs at least two signs, got {n}")
    mean, var = _run_moments(s)
    if var <= 0.0:
        n_pos, n_neg = int(np.sum(s > 0.0)), int(np.sum(s < 0.0))
        raise DataError(
            f"runs test variance is zero for {n_pos} positive and {n_neg} negative signs"
        )
    runs = 1 + int(np.sum(s[1:] != s[:-1]))
    z = float((runs - mean) / math.sqrt(var))
    return RunsTestResult(
        z=z,
        p_value=float(2.0 * norm.sf(abs(z))),
        n_runs=runs,
        expected_runs=mean,
        n_signs=n,
    )


def trade_runs_test(pnl: FloatSeq) -> RunsTestResult | None:
    """``runs_test`` over the signs of realized trade PnLs in entry order.

    ``None`` when the test is undefined: fewer than two trades, or a zero variance because the
    outcomes carry fewer than two distinct signs (or exactly one win and one loss). A non-finite
    PnL still fails loud.
    """
    s = _signs(pnl, "trade PnLs")
    if s.size < 2 or _run_moments(s)[1] <= 0.0:
        return None
    return runs_test(s)


def _signs(values: FloatSeq, label: str) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        raise DataError(f"{label} must be a 1-D array")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError(f"{label} contain non-finite values")
    return np.sign(arr)


def _run_moments(s: np.ndarray) -> tuple[float, float]:
    """Wald–Wolfowitz mean and variance of the run count for a sign array of size >= 2."""
    n = int(s.size)
    n_pos = int(np.sum(s > 0.0))
    n_neg = int(np.sum(s < 0.0))
    mean = 2.0 * n_pos * n_neg / n + 1.0
    return mean, (mean - 1.0) * (mean - 2.0) / (n - 1)


__all__ = ["RunsTestResult", "runs_test", "trade_runs_test"]

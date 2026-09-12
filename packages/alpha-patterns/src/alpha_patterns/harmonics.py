"""Harmonic XABCD patterns over directional-change extremes.

The last four confirmed extremes are X, A, B and C; the current bar is the candidate D whenever
it is the most extreme bar since C was confirmed. Each named pattern is a set of Fibonacci ratio
targets for the four legs; the fit error is the sum of log-distances outside each target (a range
target costs nothing inside it and twice the distance outside), and the best pattern is reported
when its error is within the threshold. A pattern is knowable on bar D itself
(``confirmed_index == d``), and the upstream position rule holds it until the next extreme is
confirmed.

Provenance: github.com/neurotrader888/TechnicalAnalysisAutomation/harmonic_patterns.py
@da99c20bf3d977b639451258cd6cfca9baa1dcc3 (MIT); adapted: typed ratio specs and results, ``OHLCV`` +
``DCExtreme`` inputs instead of DataFrames, one combined position series, and a documented
deviation: a bar whose leg ratios are not finite and positive (a zero-height leg) is skipped rather
than raising from ``log``. The ratio tables, error and scan logic are unchanged (parity fixture
``tests/fixtures/neurotrader/harmonics.json``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_patterns.directional_change import DCExtreme
from alpha_patterns.series import OHLCV, IntArray

RatioSpec = float | tuple[float, float] | None


@dataclass(frozen=True)
class HarmonicRatios:
    """Target ratios of one named pattern: a point value, an inclusive range, or ``None``."""

    name: str
    xa_ab: RatioSpec
    ab_bc: RatioSpec
    bc_cd: RatioSpec
    xa_ad: RatioSpec


HARMONIC_RATIOS: tuple[HarmonicRatios, ...] = (
    HarmonicRatios("Gartley", 0.618, (0.382, 0.886), (1.13, 1.618), 0.786),
    HarmonicRatios("Bat", (0.382, 0.50), (0.382, 0.886), (1.618, 2.618), 0.886),
    HarmonicRatios("Butterfly", 0.786, (0.382, 0.886), (1.618, 2.24), (1.27, 1.41)),
    HarmonicRatios("Crab", (0.382, 0.618), (0.382, 0.886), (2.618, 3.618), 1.618),
    HarmonicRatios("Deep Crab", 0.886, (0.382, 0.886), (2.0, 3.618), 1.618),
    HarmonicRatios("Cypher", (0.382, 0.618), (1.13, 1.41), (1.27, 2.00), 0.786),
    HarmonicRatios("Shark", None, (1.13, 1.618), (1.618, 2.24), (0.886, 1.13)),
)

_RANGE_PENALTY = 2.0  # a range is already lenient, so misses are punished harder


def ratio_error(actual: float, spec: RatioSpec) -> float:
    """Log-distance of ``actual`` from the target; 0 inside a range or with no requirement."""
    if spec is None:
        return 0.0
    if not (math.isfinite(actual) and actual > 0.0):
        raise DataError(f"harmonic ratio must be finite and positive, got {actual}")
    log_actual = math.log(actual)
    if isinstance(spec, tuple):
        lo, hi = math.log(spec[0]), math.log(spec[1])
        if hi <= lo:
            raise DataError(f"ratio range must be increasing, got {spec}")
        if lo <= log_actual <= hi:
            return 0.0
        return _RANGE_PENALTY * min(abs(log_actual - lo), abs(log_actual - hi))
    return abs(log_actual - math.log(spec))


@dataclass(frozen=True)
class HarmonicPattern:
    """One detected XABCD; ``x .. d`` are bar indices and the entry is the close of ``d``."""

    name: str
    bullish: bool
    x: int
    a: int
    b: int
    c: int
    d: int
    confirmed_index: int  # == d: the pattern completes on the bar that prints D
    error: float


@dataclass(frozen=True)
class HarmonicScan:
    patterns: list[HarmonicPattern]
    signal: IntArray  # +1 / -1 from D until the next extreme is confirmed, else 0


def _pattern_error(pat: HarmonicRatios, ratios: tuple[float, float, float, float]) -> float:
    xa_ab, ab_bc, bc_cd, xa_ad = ratios
    return (
        ratio_error(ab_bc, pat.ab_bc)
        + ratio_error(xa_ab, pat.xa_ab)
        + ratio_error(bc_cd, pat.bc_cd)
        + ratio_error(xa_ad, pat.xa_ad)
    )


def detect_harmonics(
    bars: OHLCV, extremes: Sequence[DCExtreme], *, error_threshold: float = 0.2
) -> HarmonicScan:
    """Scan ``bars`` for XABCD completions over ``extremes`` (in confirmation order).

    ``extremes`` is the output of ``directional_change``; the scan starts at the first
    confirmation bar and, mirroring upstream, stops on the bar that confirms the last extreme.
    """
    if error_threshold <= 0.0:
        raise DataError(f"error_threshold must be > 0, got {error_threshold}")
    n = len(bars)
    signal = np.zeros(n, dtype=np.intp)
    patterns: list[HarmonicPattern] = []
    if len(extremes) < 2:
        return HarmonicScan(patterns, signal)
    for prev, cur in zip(extremes, extremes[1:], strict=False):
        if cur.confirmed_index < prev.confirmed_index:
            raise DataError("harmonic extremes must be in confirmation order")
    prices = [e.price for e in extremes]
    seg = [math.nan] + [abs(prices[k] - prices[k - 1]) for k in range(1, len(prices))]
    retrace = [math.nan, math.nan] + [seg[k] / seg[k - 1] for k in range(2, len(seg))]

    ext_i = 0
    position = 0
    for i in range(extremes[0].confirmed_index, n):
        if extremes[ext_i + 1].confirmed_index == i:
            position = 0
            ext_i += 1
        if position != 0:
            signal[i] = position
            continue
        if ext_i + 1 >= len(extremes):
            break
        if ext_i < 3:
            continue
        last = extremes[ext_i]
        if last.kind == "high":  # leg down: bullish candidate, D is the current low
            d_price = float(bars.low[i])
            if (
                i > last.confirmed_index
                and float(np.min(bars.low[last.confirmed_index : i])) < d_price
            ):
                continue
        else:  # leg up: bearish candidate, D is the current high
            d_price = float(bars.high[i])
            if (
                i > last.confirmed_index
                and float(np.max(bars.high[last.confirmed_index : i])) > d_price
            ):
                continue
        a_price = prices[ext_i - 2]
        ratios = (
            retrace[ext_i - 1],
            retrace[ext_i],
            abs(d_price - last.price) / seg[ext_i],
            abs(d_price - a_price) / seg[ext_i - 2],
        )
        if not all(math.isfinite(r) and r > 0.0 for r in ratios):
            continue  # a zero-height leg cannot be scored (deviation: skip, do not raise)
        best_err, best_name = math.inf, ""
        for pat in HARMONIC_RATIOS:
            err = _pattern_error(pat, ratios)
            if err < best_err:
                best_err, best_name = err, pat.name
        if best_err <= error_threshold:
            bullish = last.kind == "high"
            position = 1 if bullish else -1
            signal[i] = position
            patterns.append(
                HarmonicPattern(
                    name=best_name,
                    bullish=bullish,
                    x=extremes[ext_i - 3].index,
                    a=extremes[ext_i - 2].index,
                    b=extremes[ext_i - 1].index,
                    c=last.index,
                    d=i,
                    confirmed_index=i,
                    error=best_err,
                )
            )
    return HarmonicScan(patterns, signal)


def harmonics_known_by(patterns: Sequence[HarmonicPattern], bar: int) -> list[HarmonicPattern]:
    """Patterns whose D bar had printed by ``bar``."""
    return [p for p in patterns if p.confirmed_index <= bar]

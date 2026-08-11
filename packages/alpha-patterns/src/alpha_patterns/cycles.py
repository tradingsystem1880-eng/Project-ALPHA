"""Cycle, memory and mean-reversion statistics — the "is there structure in time?" layer.

The indicators elsewhere in this package ask what state the market is in. These ask a harder and
more interesting question: **does this series have memory at all, and on what horizon?** A trader
who believes in cycles, waves, or "it always bottoms in the same month" is making a claim that
these statistics can test directly, which is rarer than it sounds.

Four tools, in increasing order of how easy they are to misread:

* :func:`autocorrelation` — the plainest possible memory test.
* :func:`variance_ratio` — Lo–MacKinlay. Ratio > 1 means returns trend over that horizon, < 1 means
  they mean-revert, = 1 means a random walk. Comes with a heteroskedasticity-robust z-statistic,
  because a raw ratio of 1.2 means nothing without knowing the noise floor.
* :func:`hurst_exponent` — rescaled range. Widely quoted, widely abused, and it has two failure
  modes worth knowing before reading any number it returns. It is biased at short window lengths,
  so a reading must be quoted against :func:`hurst_random_walk_reference` rather than against the
  textbook 0.5. And it measures *long*-range dependence only: an AR(1) with strong lag-1
  autocorrelation barely moves it, so a null Hurst result does not mean returns are unpredictable.
  It also needs **returns**, not prices — fed an integrated series it returns ≈1 for anything.
* :func:`dominant_cycle` — the periodogram peak of a detrended window. This is the one most likely
  to produce a beautiful, entirely spurious answer: **every** finite noisy series has a spectral
  peak somewhere, so the returned power share is the number that matters, not the period.

Everything is computed on a **trailing window** ending at bar ``i``. The full-sample versions of
these statistics are standard in the literature and useless here — a Hurst exponent computed over
the whole series and then used to condition a trade at bar 300 is reading its own future.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import FloatArray

#: Minimum bars before a memory statistic is meaningful rather than merely computable.
MIN_MEMORY_WINDOW = 32


def _check_series(values: FloatArray, name: str, window: int) -> None:
    if values.size < 1:
        raise DataError(f"{name} needs a non-empty series")
    if window < MIN_MEMORY_WINDOW:
        raise DataError(f"{name} window must be >= {MIN_MEMORY_WINDOW}, got {window}")


def autocorrelation(values: FloatArray, lag: int) -> float:
    """Pearson autocorrelation of a series against itself at ``lag``. NaN when undefined."""
    if lag < 1:
        raise DataError(f"autocorrelation lag must be >= 1, got {lag}")
    if values.size <= lag + 1:
        return float("nan")
    a, b = values[:-lag], values[lag:]
    a_c, b_c = a - a.mean(), b - b.mean()
    denom = float(np.sqrt(np.sum(a_c**2) * np.sum(b_c**2)))
    return float("nan") if denom <= 0.0 else float(np.sum(a_c * b_c) / denom)


def rolling_autocorrelation(values: FloatArray, *, window: int, lag: int = 1) -> FloatArray:
    """Trailing-window autocorrelation at ``lag``, stamped at the end of each window."""
    _check_series(values, "rolling_autocorrelation", window)
    out = np.full(values.size, np.nan, dtype=np.float64)
    for i in range(values.size):
        if i + 1 < window:
            continue
        out[i] = autocorrelation(values[i - window + 1 : i + 1], lag)
    return out


@dataclass(frozen=True)
class VarianceRatio:
    """Lo–MacKinlay variance ratio and its robust z-statistic.

    ``ratio > 1`` with ``|z| > 2`` is evidence of trending; ``ratio < 1`` with ``|z| > 2`` is
    evidence of mean reversion; anything with ``|z| < 2`` is a random walk as far as this test can
    tell, whatever the ratio happens to read.
    """

    ratio: float
    z_score: float
    n_observations: int

    @property
    def verdict(self) -> str:
        if not np.isfinite(self.z_score) or abs(self.z_score) < 2.0:
            return "random walk"
        return "trending" if self.ratio > 1.0 else "mean reverting"


def variance_ratio(log_prices: FloatArray, *, q: int) -> VarianceRatio:
    """Lo–MacKinlay variance-ratio test at horizon ``q``, heteroskedasticity-robust.

    Takes **log prices**, not returns — the test is defined on the variance of overlapping
    ``q``-period differences against ``q`` times the one-period variance, and doing that from
    returns invites an off-by-one that quietly biases the ratio.
    """
    if q < 2:
        raise DataError(f"variance_ratio needs q >= 2, got {q}")
    n = log_prices.size - 1
    if n < 2 * q:
        return VarianceRatio(float("nan"), float("nan"), max(0, n))

    r = np.diff(log_prices)
    mu = float(np.mean(r))
    var_1 = float(np.sum((r - mu) ** 2)) / (n - 1)
    if var_1 <= 0.0:
        return VarianceRatio(float("nan"), float("nan"), n)

    # Overlapping q-period differences, with the Lo-MacKinlay unbiased denominator.
    diffs = log_prices[q:] - log_prices[:-q]
    m = q * (n - q + 1) * (1.0 - q / n)
    if m <= 0.0:
        return VarianceRatio(float("nan"), float("nan"), n)
    var_q = float(np.sum((diffs - q * mu) ** 2)) / m
    ratio = var_q / var_1

    # Robust variance of the ratio: a sum of weighted autocovariance terms, so heteroskedastic
    # returns (which crypto certainly has) do not masquerade as mean reversion.
    dev_sq = (r - mu) ** 2
    theta = 0.0
    for j in range(1, q):
        num = float(np.sum(dev_sq[j:] * dev_sq[:-j]))
        delta = num / (float(np.sum(dev_sq)) ** 2)
        theta += (2.0 * (q - j) / q) ** 2 * delta
    if theta <= 0.0:
        return VarianceRatio(ratio, float("nan"), n)
    return VarianceRatio(ratio, (ratio - 1.0) / float(np.sqrt(theta)), n)


def hurst_exponent(values: FloatArray, *, min_chunk: int = 8) -> float:
    """Rescaled-range (R/S) Hurst exponent of a series. NaN when the series is too short or flat.

    **Pass returns, not prices.** R/S measures how a series' range grows with the length of window
    it is measured over. Applied to log *prices* — an integrated series — it returns ≈1 for
    anything, including pure noise, because it is detecting the integration rather than any memory.
    Applied to log *returns* it answers the question actually being asked: H > 0.5 is persistence
    (a move tends to be followed by another in the same direction), H < 0.5 is anti-persistence.

    Read this next to :func:`hurst_random_walk_reference`, never alone. The R/S estimator is
    biased on short windows, so "H = 0.47, therefore mean-reverting" is one of the most common
    false findings in technical research — 0.47 may well be the centre of the null at that length.
    """
    n = values.size
    if n < 4 * min_chunk:
        return float("nan")
    sizes: list[int] = []
    size = min_chunk
    while size <= n // 2:
        sizes.append(size)
        size *= 2
    if len(sizes) < 2:
        return float("nan")

    logs_n: list[float] = []
    logs_rs: list[float] = []
    for size in sizes:
        rescaled: list[float] = []
        for start in range(0, n - size + 1, size):
            chunk = values[start : start + size]
            sd = float(np.std(chunk))
            if sd <= 0.0:
                continue
            dev = np.cumsum(chunk - float(np.mean(chunk)))
            rng = float(np.max(dev) - np.min(dev))
            if rng > 0.0:
                rescaled.append(rng / sd)
        if rescaled:
            logs_n.append(float(np.log(size)))
            logs_rs.append(float(np.log(np.mean(rescaled))))
    if len(logs_n) < 2:
        return float("nan")
    slope, _ = np.polyfit(np.asarray(logs_n), np.asarray(logs_rs), 1)
    return float(slope)


def hurst_random_walk_reference(
    length: int, *, trials: int = 200, seed: int = 7, min_chunk: int = 8
) -> tuple[float, float]:
    """Mean and standard deviation of :func:`hurst_exponent` under the no-memory null.

    The null is **white noise**, not a random walk in levels. R/S applied to an integrated series
    returns ≈1 by construction, so seeding this reference with ``cumsum(noise)`` would calibrate
    the null at 1.0 and make genuinely persistent returns look anti-persistent — the estimator
    would be measuring integration, which is not in question, instead of memory, which is.

    This is the distribution the estimator actually has at this sample size, rather than the 0.5
    the theory promises asymptotically. Quote any Hurst reading as a z-score against it.
    """
    rng = np.random.default_rng(seed)
    values = [
        hurst_exponent(rng.standard_normal(length), min_chunk=min_chunk) for _ in range(trials)
    ]
    finite = np.asarray([v for v in values if np.isfinite(v)])
    if finite.size < 2:
        return float("nan"), float("nan")
    return float(np.mean(finite)), float(np.std(finite, ddof=1))


@dataclass(frozen=True)
class Cycle:
    """The strongest periodic component of a window, and how much it actually explains."""

    period_bars: float
    #: Share of total detrended power sitting in that single frequency bin. **This is the number
    #: that decides whether the period means anything.** Every noisy finite series has a peak.
    power_share: float
    n_observations: int


def dominant_cycle(values: FloatArray, *, min_period: int = 4, max_period: int = 0) -> Cycle:
    """Periodogram peak of a linearly detrended window.

    Linear detrending first is essential: on a trending series the spectrum is dominated by the
    trend's own leakage into the lowest frequency bin, and the "dominant cycle" comes back as
    roughly the window length every single time.
    """
    n = values.size
    if n < 4 * min_period:
        return Cycle(float("nan"), float("nan"), n)
    if float(np.ptp(values)) == 0.0:
        return Cycle(float("nan"), float("nan"), n)
    idx = np.arange(n, dtype=np.float64)
    slope, intercept = np.polyfit(idx, values, 1)
    detrended = values - (slope * idx + intercept)
    if float(np.std(detrended)) <= 0.0:
        return Cycle(float("nan"), float("nan"), n)

    spectrum = np.abs(np.fft.rfft(detrended * np.hanning(n))) ** 2
    freqs = np.fft.rfftfreq(n, d=1.0)
    ceiling = max_period if max_period > 0 else n // 2
    with np.errstate(divide="ignore"):
        periods = np.where(freqs > 0, 1.0 / np.where(freqs > 0, freqs, 1.0), np.inf)
    usable = (periods >= min_period) & (periods <= ceiling)
    if not np.any(usable):
        return Cycle(float("nan"), float("nan"), n)

    total = float(np.sum(spectrum[1:]))
    band = np.flatnonzero(usable)
    peak = int(band[int(np.argmax(spectrum[band]))])
    share = float(spectrum[peak] / total) if total > 0 else float("nan")
    return Cycle(float(periods[peak]), share, n)


def rolling_variance_ratio(log_prices: FloatArray, *, window: int, q: int) -> FloatArray:
    """Trailing-window variance ratio, stamped at the end of each window."""
    _check_series(log_prices, "rolling_variance_ratio", window)
    out = np.full(log_prices.size, np.nan, dtype=np.float64)
    for i in range(log_prices.size):
        if i + 1 < window:
            continue
        out[i] = variance_ratio(log_prices[i - window + 1 : i + 1], q=q).ratio
    return out


def rolling_hurst(values: FloatArray, *, window: int, min_chunk: int = 8) -> FloatArray:
    """Trailing-window Hurst exponent, stamped at the end of each window."""
    _check_series(values, "rolling_hurst", window)
    out = np.full(values.size, np.nan, dtype=np.float64)
    for i in range(values.size):
        if i + 1 < window:
            continue
        out[i] = hurst_exponent(values[i - window + 1 : i + 1], min_chunk=min_chunk)
    return out

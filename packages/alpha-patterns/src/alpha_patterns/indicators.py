"""Trailing-window indicators — the conditioning variables a regime study needs.

The pattern detectors answer "is this shape present?". This module answers the other half of the
question a discretionary trader is actually asking: **what state is the market in right now?**
Compression, momentum, correlation with the market leader, position within a trailing range.

Two design rules run through everything here, and both exist to stop the study lying to itself:

1. **Strictly causal.** Every value at bar ``i`` is computed from bars ``i-window+1 .. i`` inclusive
   and nothing later. Where a warm-up window is incomplete the value is computed from what exists
   rather than being back-filled, which keeps arrays the same length as the series without inventing
   data. The ``bias_guard`` tests poison the future and assert nothing moves.
2. **Percentile-rank over absolute thresholds.** "Bollinger bandwidth below 0.04" means something
   different across assets and market regimes. :func:`percentile_rank` converts any series into its
   own trailing-window rank, so "compressed" means *compressed relative to this asset's own recent
   history* — the only definition that transfers across assets and epochs.

:func:`calendar_features` is the one place datetime semantics touch this package. It decodes the
epoch-millisecond ``ts`` array into integer day/hour/month fields and returns plain integer arrays,
so the detection layer keeps its numpy purity while a seasonality study still gets what it needs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import OHLCV, FloatArray, IntArray

#: Bars used by the classic Bollinger construction, and the classic Wilder RSI period.
BOLLINGER_WINDOW = 20
BOLLINGER_SIGMA = 2.0
RSI_WINDOW = 14

_MS_PER_DAY = 86_400_000.0
#: 1970-01-01 was a Thursday. Under Monday=0 … Sunday=6 that is 3, so ``(days + 3) % 7`` maps a
#: day count since the epoch onto the weekday.
_EPOCH_WEEKDAY_OFFSET = 3


def _check_window(window: int, name: str, size: int) -> None:
    if window < 1:
        raise DataError(f"{name} window must be >= 1, got {window}")
    if size < 1:
        raise DataError(f"{name} needs a non-empty series")


def rolling_mean(values: FloatArray, window: int) -> FloatArray:
    """Causal simple moving average over ``values[i-window+1 .. i]``.

    The workhorse the rest of the module builds on. Uses a cumulative sum rather than a Python loop,
    and divides by the *actual* number of bars available so the warm-up region is an honest average
    of a shorter window instead of a NaN or a lie.
    """
    _check_window(window, "rolling_mean", values.size)
    csum = np.concatenate(([0.0], np.cumsum(values, dtype=np.float64)))
    idx = np.arange(values.size)
    lo = np.maximum(0, idx - window + 1)
    return np.asarray((csum[idx + 1] - csum[lo]) / (idx - lo + 1).astype(np.float64))


def rolling_std(values: FloatArray, window: int) -> FloatArray:
    """Causal population standard deviation over the trailing window.

    Population (``ddof=0``) rather than sample, matching the Bollinger convention.

    **Not** computed as ``E[x^2] - E[x]^2`` over cumulative sums. That form is one subtraction of
    two nearly-equal large numbers: at BTC's price level it loses about ten significant digits, and
    a genuinely flat window comes back with a spurious non-zero standard deviation that then reads
    as a real Bollinger bandwidth. Centring the series first fixes the conditioning but reads every
    bar to compute the centre — algebraically harmless, since a constant shift cancels out of a
    variance exactly, but it makes the function's output depend on future data, and the bias guard
    is right to reject that regardless of the magnitude.

    So: an explicit per-window two-pass computation. ``numpy.std`` subtracts each window's own mean
    before squaring, which is both stable and strictly causal. The cost is one numpy call per bar,
    which is negligible next to the detection this feeds.
    """
    _check_window(window, "rolling_std", values.size)
    out = np.empty(values.size, dtype=np.float64)
    for i in range(values.size):
        out[i] = float(np.std(values[max(0, i - window + 1) : i + 1]))
    return out


def log_returns(closes: FloatArray) -> FloatArray:
    """Per-bar log returns, with the first bar set to zero so the array keeps its length.

    Log rather than simple returns because the downstream statistics (realized volatility, rolling
    correlation) assume additivity across bars, which only holds in log space.
    """
    if closes.size < 2:
        raise DataError(f"log_returns needs >= 2 closes, got {closes.size}")
    if bool(np.any(closes <= 0.0)):
        raise DataError("log_returns requires strictly-positive prices")
    out = np.zeros(closes.size, dtype=np.float64)
    out[1:] = np.log(closes[1:] / closes[:-1])
    return out


def realized_volatility(
    closes: FloatArray, window: int, *, periods_per_year: float | None = None
) -> FloatArray:
    """Trailing realized volatility: the standard deviation of log returns over ``window`` bars.

    Left unannualised by default. Annualisation multiplies by ``sqrt(periods_per_year)``, which is
    only meaningful once the caller has committed to a bar frequency — and since the whole study
    compares an asset against *itself* through :func:`percentile_rank`, the scaling usually cancels
    out anyway. It is offered because a reported number is easier to sanity-check in familiar units.
    """
    rets = log_returns(closes)
    vol = rolling_std(rets, window)
    if periods_per_year is None:
        return vol
    if periods_per_year <= 0.0:
        raise DataError(f"periods_per_year must be > 0, got {periods_per_year}")
    return np.asarray(vol * np.sqrt(periods_per_year))


def bollinger_bandwidth(
    closes: FloatArray, window: int = BOLLINGER_WINDOW, *, sigma: float = BOLLINGER_SIGMA
) -> FloatArray:
    """``(upper - lower) / middle`` — the width of a Bollinger band as a fraction of its centre.

    This is the standard quantitative rendering of "the market is coiling". Dividing by the middle
    band makes it scale-free, so a bandwidth of 0.08 means the same thing at $0.30 and $3.00.

    A zero or negative middle band would make the ratio meaningless; prices are validated positive
    upstream by :class:`~alpha_patterns.series.OHLCV`, and the guard here catches a caller passing a
    raw non-price series.
    """
    if sigma <= 0.0:
        raise DataError(f"bollinger sigma must be > 0, got {sigma}")
    if bool(np.any(closes <= 0.0)):
        raise DataError("bollinger_bandwidth requires strictly-positive prices")
    middle = rolling_mean(closes, window)
    sd = rolling_std(closes, window)
    return np.asarray(2.0 * sigma * sd / middle)


def rsi(closes: FloatArray, window: int = RSI_WINDOW) -> FloatArray:
    """Wilder's Relative Strength Index, seeded with a simple average then smoothed recursively.

    Wilder's smoothing is an EMA with ``alpha = 1/window``, which is why an RSI computed over a long
    history differs slightly from one computed over a short slice — the recursion never fully
    forgets its seed. That is a property of the indicator, not a bug, but it means an RSI value is
    only comparable against another RSI computed the same way on the same series origin.

    The first ``window`` bars are warm-up and are reported as the neutral 50 rather than NaN, so the
    array stays aligned and downstream masks do not have to special-case a ragged head.
    """
    _check_window(window, "rsi", closes.size)
    n = closes.size
    out = np.full(n, 50.0, dtype=np.float64)
    if n <= window:
        return out

    delta = np.diff(closes)
    gains = np.maximum(delta, 0.0)
    losses = np.maximum(-delta, 0.0)

    avg_gain = float(np.mean(gains[:window]))
    avg_loss = float(np.mean(losses[:window]))
    out[window] = _rsi_value(avg_gain, avg_loss)

    for i in range(window + 1, n):
        avg_gain = (avg_gain * (window - 1) + gains[i - 1]) / window
        avg_loss = (avg_loss * (window - 1) + losses[i - 1]) / window
        out[i] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    """RSI from the two smoothed averages, handling the no-loss and no-move edge cases."""
    if avg_loss <= 0.0:
        # No downside at all: RSI is 100 by definition, unless nothing moved either way.
        return 100.0 if avg_gain > 0.0 else 50.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def percentile_rank(values: FloatArray, window: int) -> FloatArray:
    """Trailing-window percentile rank in ``[0, 1]``: the share of the window at or below ``x``.

    The single most reused function in the study. "Volatility is compressed" is not a statement
    about an absolute number, it is a statement about *where the current reading sits in this
    asset's own recent distribution* — and that phrasing is what makes a threshold transferable
    across assets and market regimes.

    Includes the current bar in its own window, so a fresh all-time-low reading ranks at
    ``1/window`` rather than 0. Bars before a full window rank within whatever history exists.
    """
    _check_window(window, "percentile_rank", values.size)
    n = values.size
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        lo = max(0, i - window + 1)
        seg = values[lo : i + 1]
        out[i] = float(np.count_nonzero(seg <= values[i])) / float(seg.size)
    return out


def rolling_correlation(a: FloatArray, b: FloatArray, window: int) -> FloatArray:
    """Causal Pearson correlation of two aligned series over the trailing window.

    Zero-variance windows return 0.0 rather than NaN: a flat series is genuinely uncorrelated with
    everything, and propagating NaN through a conditioning mask silently drops bars from the sample,
    which changes the denominator of every proportion downstream.
    """
    if a.shape != b.shape:
        raise DataError(f"rolling_correlation needs equal shapes, got {a.shape} vs {b.shape}")
    _check_window(window, "rolling_correlation", a.size)
    mean_a = rolling_mean(a, window)
    mean_b = rolling_mean(b, window)
    cov = rolling_mean(a * b, window) - mean_a * mean_b
    sd_a = np.sqrt(np.maximum(rolling_mean(a * a, window) - mean_a * mean_a, 0.0))
    sd_b = np.sqrt(np.maximum(rolling_mean(b * b, window) - mean_b * mean_b, 0.0))
    denom = sd_a * sd_b
    return np.asarray(np.where(denom > 1e-15, cov / np.where(denom > 1e-15, denom, 1.0), 0.0))


@dataclass(frozen=True)
class LeadLag:
    """Cross-correlation of two return series across a symmetric band of lags.

    ``lags`` are in bars, negative meaning *``leader`` moved first*. ``best_lag`` is the lag with
    the largest absolute correlation, which is the empirical answer to "does one asset lead another,
    and by how much?" — a claim traders assert constantly and almost never measure.
    """

    lags: IntArray
    correlations: FloatArray
    best_lag: int
    best_correlation: float
    n_observations: int


def cross_correlation_lags(follower: FloatArray, leader: FloatArray, *, max_lag: int) -> LeadLag:
    """Correlate ``follower`` against ``leader`` shifted by every lag in ``[-max_lag, +max_lag]``.

    A **negative** lag correlates ``follower[t]`` with ``leader[t - k]``: the leader's past against
    the follower's present, which is the direction that would make the relationship tradeable. A
    positive lag is the reverse and is reported for symmetry — if the positive side is stronger, the
    "leader" is in fact following, and the folklore is backwards.

    This is a whole-sample diagnostic, not a per-bar feature; it summarises a relationship over a
    window the caller has already chosen. Anything used as a *conditioning variable* must go through
    :func:`rolling_correlation` instead, which is causal per bar.
    """
    if follower.shape != leader.shape:
        raise DataError(
            f"cross_correlation_lags needs equal shapes, got {follower.shape} vs {leader.shape}"
        )
    if max_lag < 1:
        raise DataError(f"max_lag must be >= 1, got {max_lag}")
    if follower.size <= 2 * max_lag + 1:
        raise DataError(f"need > {2 * max_lag + 1} points for max_lag={max_lag}")

    lags = np.arange(-max_lag, max_lag + 1, dtype=np.intp)
    corrs = np.zeros(lags.size, dtype=np.float64)
    for j, lag in enumerate(lags):
        if lag < 0:
            x, y = follower[-lag:], leader[: leader.size + lag]
        elif lag > 0:
            x, y = follower[: follower.size - lag], leader[lag:]
        else:
            x, y = follower, leader
        corrs[j] = _pearson(x, y)

    best = int(np.argmax(np.abs(corrs)))
    return LeadLag(
        lags=lags,
        correlations=corrs,
        best_lag=int(lags[best]),
        best_correlation=float(corrs[best]),
        n_observations=int(follower.size),
    )


def _pearson(x: FloatArray, y: FloatArray) -> float:
    if x.size < 3:
        return 0.0
    xc = x - float(np.mean(x))
    yc = y - float(np.mean(y))
    denom = float(np.sqrt(np.dot(xc, xc) * np.dot(yc, yc)))
    return float(np.dot(xc, yc) / denom) if denom > 1e-15 else 0.0


@dataclass(frozen=True)
class CalendarFeatures:
    """Integer calendar fields decoded from epoch milliseconds, one entry per bar.

    Kept as plain integer arrays rather than datetimes so the rest of the package never acquires
    timezone semantics. Everything is UTC, because that is what the source timestamps are.
    """

    year: IntArray
    month: IntArray  # 1-12
    day_of_month: IntArray  # 1-31
    day_of_week: IntArray  # Monday=0 ... Sunday=6
    hour: IntArray  # 0-23 UTC
    day_of_year: IntArray  # 1-366


def calendar_features(ts_millis: FloatArray) -> CalendarFeatures:
    """Decode a bar-timestamp array into UTC calendar fields.

    Seasonality is the weakest of the study's predictor families and the one most exposed to
    multiplicity — twelve months times seven weekdays times twenty-four hours is a lot of cells to
    go fishing in. It is included because it is cheap and because a trader will ask; it is read last
    and with the correction applied, not first.
    """
    if ts_millis.size < 1:
        raise DataError("calendar_features needs a non-empty timestamp array")
    if not bool(np.all(np.isfinite(ts_millis))):
        raise DataError("calendar_features requires finite timestamps")

    dt = ts_millis.astype("datetime64[ms]")
    days = dt.astype("datetime64[D]")
    years = days.astype("datetime64[Y]")
    months = days.astype("datetime64[M]")

    return CalendarFeatures(
        year=np.asarray(years.astype(int) + 1970, dtype=np.intp),
        month=np.asarray((months.astype(int) % 12) + 1, dtype=np.intp),
        day_of_month=np.asarray((days - months).astype(int) + 1, dtype=np.intp),
        day_of_week=np.asarray(
            (days.astype(int) + _EPOCH_WEEKDAY_OFFSET) % 7,
            dtype=np.intp,
        ),
        hour=np.asarray(((ts_millis % _MS_PER_DAY) // 3_600_000).astype(np.intp), dtype=np.intp),
        day_of_year=np.asarray((days - years).astype(int) + 1, dtype=np.intp),
    )


def consolidation_length(closes: FloatArray, window: int, *, threshold: float) -> IntArray:
    """How many consecutive bars the trailing range has stayed narrower than ``threshold``.

    "Coiling for weeks" is a duration claim, and duration is what separates a genuine base from a
    single quiet afternoon. Range is measured as ``(max - min) / min`` over the trailing ``window``,
    so the count answers: for how many bars in a row has this asset been range-bound?
    """
    _check_window(window, "consolidation_length", closes.size)
    if threshold <= 0.0:
        raise DataError(f"threshold must be > 0, got {threshold}")

    n = closes.size
    narrow = np.zeros(n, dtype=bool)
    for i in range(n):
        seg = closes[max(0, i - window + 1) : i + 1]
        lo = float(np.min(seg))
        narrow[i] = lo > 0.0 and (float(np.max(seg)) - lo) / lo < threshold

    out = np.zeros(n, dtype=np.intp)
    run = 0
    for i in range(n):
        run = run + 1 if narrow[i] else 0
        out[i] = run
    return out


def volume_ratio(bars: OHLCV, window: int) -> FloatArray:
    """Current bar volume over its trailing mean — the "dry-up" / "confirmation" measure.

    Above 1.5 is the conventional volume-confirmation threshold (already used by the trendline and
    head-and-shoulders detectors); well below 1.0 sustained is volume dry-up, the other half of the
    compression story. Zero-volume windows return 1.0, i.e. "no information", rather than dividing
    by zero.
    """
    mean = rolling_mean(bars.volume, window)
    return np.asarray(np.where(mean > 1e-12, bars.volume / np.where(mean > 1e-12, mean, 1.0), 1.0))

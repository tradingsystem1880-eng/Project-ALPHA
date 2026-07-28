"""Classical oscillators and channel indicators, rebuilt causally.

Everything here is standard — OBV, MACD, stochastics, ADX, Ichimoku — and that is precisely why it
needs rebuilding rather than importing. The textbook definitions are written for a chart, where the
whole series is visible at once and nobody minds that a value is centred, back-shifted or drawn
forward. Fed to a study, several of them leak the future in ways that are invisible in the output
and fatal to the conclusion.

Three traps this module handles explicitly:

* **Ichimoku's senkou spans are plotted 26 bars into the future.** The cloud a chartist sees at bar
  ``i`` was computed from data at bar ``i - 26``. That is causal and usable. What is *not* usable is
  reading the cloud off a chart at the bar it was computed on, which is what a naive implementation
  returns. :func:`ichimoku` returns the cloud **in force at** each bar.
* **Ichimoku's chikou span is the close shifted 26 bars back.** Any comparison of the form "chikou
  is above the price it sits over" is legitimate at bar ``i`` (it compares ``close[i]`` to
  ``close[i-26]``), but the *chart* shows that verdict at bar ``i-26``, where it is pure look-ahead.
  The value returned here is stamped at the bar where the information actually exists.
* **Wilder's smoothing has an initialisation choice** that changes early values. The convention here
  is to seed from the first available window and let the recursion run, and to compute the warm-up
  region from what exists rather than emitting NaN, matching :mod:`alpha_patterns.indicators`.

Every function returns an array the same length as its input, and every value at bar ``i`` depends
only on bars ``<= i``. The ``bias_guard`` suite poisons all future bars and asserts bit-identical
output.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_patterns.indicators import rolling_mean
from alpha_patterns.series import OHLCV, FloatArray

#: Classic parameterisations, named so a study cannot silently drift from the convention it claims.
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
STOCH_WINDOW, STOCH_SMOOTH = 14, 3
ADX_WINDOW = 14
MFI_WINDOW = 14
CMF_WINDOW = 20
KELTNER_WINDOW, KELTNER_MULT = 20, 2.0
ICHIMOKU_TENKAN, ICHIMOKU_KIJUN, ICHIMOKU_SPAN_B = 9, 26, 52
#: Ichimoku's forward displacement. Also the chikou lag.
ICHIMOKU_SHIFT = 26


def _check(values: FloatArray, name: str, window: int = 1) -> None:
    if values.size < 1:
        raise DataError(f"{name} needs a non-empty series")
    if window < 1:
        raise DataError(f"{name} window must be >= 1, got {window}")


def ema(values: FloatArray, window: int) -> FloatArray:
    """Exponential moving average, seeded on the first value so the recursion is fully causal.

    Seeding on ``values[0]`` rather than on a mean of the first ``window`` bars is the choice that
    keeps every output bar a function of its own past only. The alternative — priming with a simple
    average of the opening window — makes the first ``window`` outputs depend on each other's future
    and is a real, if small, leak.
    """
    _check(values, "ema", window)
    alpha = 2.0 / (window + 1.0)
    out = np.empty(values.size, dtype=np.float64)
    acc = float(values[0])
    for i in range(values.size):
        acc = alpha * float(values[i]) + (1.0 - alpha) * acc if i else float(values[0])
        out[i] = acc
    return out


def wilder_smooth(values: FloatArray, window: int) -> FloatArray:
    """Wilder's smoothing (an EMA with ``alpha = 1/window``), used by RSI, ATR and ADX."""
    _check(values, "wilder_smooth", window)
    out = np.empty(values.size, dtype=np.float64)
    acc = float(values[0])
    for i in range(values.size):
        acc = (acc * (window - 1) + float(values[i])) / window if i else float(values[0])
        out[i] = acc
    return out


def on_balance_volume(close: FloatArray, volume: FloatArray) -> FloatArray:
    """On-balance volume: cumulative signed volume, the classic accumulation proxy.

    The level of OBV is meaningless on its own — it depends entirely on where the series starts —
    so studies should read its *slope*, its divergence from price, or its percentile rank, never
    the raw number.
    """
    _check(close, "on_balance_volume")
    if volume.size != close.size:
        raise DataError(f"on_balance_volume: {close.size} closes vs {volume.size} volumes")
    direction = np.sign(np.diff(close, prepend=close[0]))
    return np.cumsum(direction * volume, dtype=np.float64)


@dataclass(frozen=True)
class MACD:
    """MACD line, its signal, and the histogram between them."""

    line: FloatArray
    signal: FloatArray
    histogram: FloatArray


def macd(
    close: FloatArray,
    *,
    fast: int = MACD_FAST,
    slow: int = MACD_SLOW,
    signal: int = MACD_SIGNAL,
) -> MACD:
    """Moving-average convergence/divergence."""
    _check(close, "macd", fast)
    if fast >= slow:
        raise DataError(f"macd needs fast < slow, got fast={fast} slow={slow}")
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return MACD(line=line, signal=sig, histogram=line - sig)


@dataclass(frozen=True)
class Stochastic:
    """Fast %K and its smoothed %D, both in [0, 100]."""

    k: FloatArray
    d: FloatArray


def stochastic(
    bars: OHLCV, *, window: int = STOCH_WINDOW, smooth: int = STOCH_SMOOTH
) -> Stochastic:
    """Stochastic oscillator over a trailing high-low range.

    A flat window (high == low) has no defined position within it; those bars are reported as 50,
    the neutral midpoint, rather than as a divide-by-zero or a NaN that would silently drop the bar
    from every downstream comparison.
    """
    _check(bars.close, "stochastic", window)
    n = bars.close.size
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        lo_i = max(0, i - window + 1)
        hi = float(np.max(bars.high[lo_i : i + 1]))
        lo = float(np.min(bars.low[lo_i : i + 1]))
        span = hi - lo
        out[i] = 50.0 if span <= 0.0 else 100.0 * (float(bars.close[i]) - lo) / span
    return Stochastic(k=out, d=rolling_mean(out, smooth))


def williams_r(bars: OHLCV, *, window: int = STOCH_WINDOW) -> FloatArray:
    """Williams %R in [-100, 0] — the stochastic %K mirrored, kept separate for readability."""
    return stochastic(bars, window=window, smooth=1).k - 100.0


def typical_price(bars: OHLCV) -> FloatArray:
    """(high + low + close) / 3, the anchor for MFI and the classic pivot family."""
    return (bars.high + bars.low + bars.close) / 3.0


def money_flow_index(bars: OHLCV, *, window: int = MFI_WINDOW) -> FloatArray:
    """Money flow index: RSI computed on volume-weighted typical price, in [0, 100].

    A window with no negative flow is reported as 100 and one with no positive flow as 0, which is
    the limit the ratio approaches rather than an arbitrary fill.
    """
    _check(bars.close, "money_flow_index", window)
    tp = typical_price(bars)
    flow = tp * bars.volume
    delta = np.diff(tp, prepend=tp[0])
    pos = np.where(delta > 0, flow, 0.0)
    neg = np.where(delta < 0, flow, 0.0)
    n = tp.size
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        lo = max(0, i - window + 1)
        p = float(np.sum(pos[lo : i + 1]))
        q = float(np.sum(neg[lo : i + 1]))
        out[i] = 50.0 if p + q <= 0.0 else 100.0 * p / (p + q)
    return out


def chaikin_money_flow(bars: OHLCV, *, window: int = CMF_WINDOW) -> FloatArray:
    """Chaikin money flow in [-1, 1]: volume weighted by where each bar closed in its own range.

    This is the closest thing to an order-flow read that plain OHLCV can support, and it is much
    weaker than real delta: a bar closing on its high is *consistent with* buying pressure, it does
    not measure it. Studies should label it as the proxy it is.
    """
    _check(bars.close, "chaikin_money_flow", window)
    span = bars.high - bars.low
    # A zero-range bar has no "position in range"; contributing 0 keeps it neutral instead of
    # letting a divide-by-zero decide the sign of the window.
    loc = np.divide(
        (bars.close - bars.low) - (bars.high - bars.close),
        span,
        out=np.zeros_like(span, dtype=np.float64),
        where=span > 0,
    )
    mfv = loc * bars.volume
    n = bars.close.size
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        lo = max(0, i - window + 1)
        vol = float(np.sum(bars.volume[lo : i + 1]))
        out[i] = 0.0 if vol <= 0.0 else float(np.sum(mfv[lo : i + 1])) / vol
    return out


@dataclass(frozen=True)
class DirectionalIndex:
    """Wilder's directional movement system."""

    plus_di: FloatArray
    minus_di: FloatArray
    adx: FloatArray


def directional_index(bars: OHLCV, *, window: int = ADX_WINDOW) -> DirectionalIndex:
    """+DI, -DI and ADX. ADX measures trend *strength* and is deliberately direction-blind."""
    _check(bars.close, "directional_index", window)
    up = np.diff(bars.high, prepend=bars.high[0])
    down = -np.diff(bars.low, prepend=bars.low[0])
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    prev_close = np.concatenate(([bars.close[0]], bars.close[:-1]))
    tr = np.maximum(
        bars.high - bars.low,
        np.maximum(np.abs(bars.high - prev_close), np.abs(bars.low - prev_close)),
    )
    atr_w = wilder_smooth(tr, window)
    safe = np.where(atr_w > 0, atr_w, np.nan)
    plus_di = 100.0 * wilder_smooth(plus_dm, window) / safe
    minus_di = 100.0 * wilder_smooth(minus_dm, window) / safe
    plus_di = np.nan_to_num(plus_di, nan=0.0)
    minus_di = np.nan_to_num(minus_di, nan=0.0)

    total = plus_di + minus_di
    dx = 100.0 * np.abs(plus_di - minus_di) / np.where(total > 0, total, np.nan)
    return DirectionalIndex(plus_di, minus_di, wilder_smooth(np.nan_to_num(dx, nan=0.0), window))


@dataclass(frozen=True)
class Channel:
    """A price channel: upper band, middle line, lower band, and position within it."""

    upper: FloatArray
    middle: FloatArray
    lower: FloatArray
    position: FloatArray  # 0 at the lower band, 1 at the upper


def _position_in(upper: FloatArray, lower: FloatArray, close: FloatArray) -> FloatArray:
    span = upper - lower
    return np.divide(
        close - lower,
        span,
        out=np.full(span.shape, 0.5, dtype=np.float64),
        where=span > 0,
    )


def keltner_channel(
    bars: OHLCV, *, window: int = KELTNER_WINDOW, mult: float = KELTNER_MULT
) -> Channel:
    """Keltner channel: an EMA centre with ATR-scaled bands.

    Paired with Bollinger bands this gives the classic "squeeze" — Bollingers inside Keltners marks
    volatility compression by a route independent of the bandwidth percentile, which is worth having
    when the whole question is whether compression predicts anything.
    """
    _check(bars.close, "keltner_channel", window)
    prev_close = np.concatenate(([bars.close[0]], bars.close[:-1]))
    tr = np.maximum(
        bars.high - bars.low,
        np.maximum(np.abs(bars.high - prev_close), np.abs(bars.low - prev_close)),
    )
    mid = ema(bars.close, window)
    band = mult * wilder_smooth(tr, window)
    upper, lower = mid + band, mid - band
    return Channel(upper, mid, lower, _position_in(upper, lower, bars.close))


def donchian_channel(bars: OHLCV, *, window: int = 20) -> Channel:
    """Donchian channel over the trailing ``window`` bars, **excluding the current bar**.

    Excluding bar ``i`` from its own channel is what makes "price broke the channel" a statement
    about a breakout rather than a tautology — a bar's own high always touches a channel that
    includes it. The first bar has no prior window and reports its own values, which the warm-up
    convention elsewhere in the package matches.
    """
    _check(bars.close, "donchian_channel", window)
    n = bars.close.size
    upper = np.empty(n, dtype=np.float64)
    lower = np.empty(n, dtype=np.float64)
    for i in range(n):
        lo = max(0, i - window)
        if i == 0:
            upper[i], lower[i] = float(bars.high[0]), float(bars.low[0])
            continue
        upper[i] = float(np.max(bars.high[lo:i]))
        lower[i] = float(np.min(bars.low[lo:i]))
    mid = (upper + lower) / 2.0
    return Channel(upper, mid, lower, _position_in(upper, lower, bars.close))


@dataclass(frozen=True)
class Ichimoku:
    """Ichimoku lines, every one stamped at the bar where its information actually exists."""

    tenkan: FloatArray
    kijun: FloatArray
    #: The cloud **in force at** each bar — computed ``ICHIMOKU_SHIFT`` bars earlier, as a chartist
    #: reading the chart at that bar would see it.
    span_a: FloatArray
    span_b: FloatArray
    #: True where close sits above both cloud edges, the classic bullish regime filter.
    above_cloud: np.ndarray
    #: ``close[i] > close[i - shift]`` — the chikou verdict, stamped where it is knowable.
    chikou_above: np.ndarray


def _midpoint(bars: OHLCV, window: int) -> FloatArray:
    n = bars.close.size
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        lo = max(0, i - window + 1)
        out[i] = (float(np.max(bars.high[lo : i + 1])) + float(np.min(bars.low[lo : i + 1]))) / 2.0
    return out


def ichimoku(
    bars: OHLCV,
    *,
    tenkan: int = ICHIMOKU_TENKAN,
    kijun: int = ICHIMOKU_KIJUN,
    span_b: int = ICHIMOKU_SPAN_B,
    shift: int = ICHIMOKU_SHIFT,
) -> Ichimoku:
    """Ichimoku Kinko Hyo with the displacement resolved in favour of causality.

    The cloud is shifted **forward** on a chart, which means the cloud drawn at bar ``i`` was
    computed at ``i - shift``. Returning it stamped at ``i`` is therefore causal and is what a
    trader actually acts on. Returning it stamped at ``i - shift`` — the naive reading — would let
    bar ``i - shift`` see ``shift`` bars of its own future.
    """
    _check(bars.close, "ichimoku", max(tenkan, kijun, span_b))
    t = _midpoint(bars, tenkan)
    k = _midpoint(bars, kijun)
    raw_a = (t + k) / 2.0
    raw_b = _midpoint(bars, span_b)

    def _shift_forward(values: FloatArray) -> FloatArray:
        out = np.empty_like(values)
        out[:shift] = values[0]
        out[shift:] = values[:-shift] if shift else values
        return out

    a, b = _shift_forward(raw_a), _shift_forward(raw_b)
    above = (bars.close > np.maximum(a, b)).astype(bool)
    lagged = np.concatenate((np.full(shift, bars.close[0]), bars.close[:-shift]))
    return Ichimoku(t, k, a, b, above, (bars.close > lagged).astype(bool))


def squeeze(bandwidth: FloatArray, keltner: Channel, close: FloatArray) -> np.ndarray:
    """True where the Bollinger bands sit inside the Keltner channel — the classic squeeze.

    ``bandwidth`` is the Bollinger width as a fraction of its centre, as
    :func:`alpha_patterns.indicators.bollinger_bandwidth` returns it, so it is converted back to a
    price width here before the comparison.
    """
    if bandwidth.size != close.size:
        raise DataError(f"squeeze: {bandwidth.size} bandwidths vs {close.size} closes")
    boll_width = bandwidth * keltner.middle
    kelt_width = keltner.upper - keltner.lower
    return (boll_width < kelt_width).astype(bool)

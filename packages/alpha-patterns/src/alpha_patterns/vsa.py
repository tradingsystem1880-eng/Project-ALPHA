"""Volume spread analysis: how far a bar's range departs from what its volume predicts.

Over a trailing window, range (in ATR units) is regressed on volume (relative to its trailing
median); the indicator is the current bar's residual from that fit. It is zero whenever the window
shows no usable relation (non-positive slope or correlation below the floor), so the reading means
"volume said this range should have been different", never "the regression was noisy". The window
ends on the current bar, so the reading is available at that bar's close.

``rolling_ols_residual`` is the generic primitive; the TVL study (plan D) reuses it with log TVL
against log close.

Provenance: github.com/neurotrader888/VSAIndicator/vsa.py@a95bf30 (MIT); adapted: numpy closed-form
OLS instead of ``scipy.stats.linregress``, ALPHA's causal simple-mean ``atr`` and ``rolling_median``
instead of ``pandas_ta``/pandas, ``DataError`` validation, and the correlation floor named for what
it is (Pearson r, not r-squared, as in the upstream code). The gate and residual rules are unchanged
(parity fixture ``tests/fixtures/neurotrader/vsa.json`` on stored normalised inputs).
"""

from __future__ import annotations

import numpy as np

from alpha_core import DataError
from alpha_patterns.indicators import rolling_median
from alpha_patterns.series import OHLCV, FloatArray, atr


def rolling_ols_residual(
    x: FloatArray,
    y: FloatArray,
    *,
    window: int,
    min_r: float = 0.2,
    require_positive_slope: bool = True,
    start: int | None = None,
) -> FloatArray:
    """``y[i] - fit(x[i])`` from the OLS of ``y`` on ``x`` over ``[i-window+1, i]``.

    NaN before ``start`` (default: the first full window) and wherever the window is not finite or
    ``x`` is constant; ``0.0`` when the gate rejects the fit.
    """
    xa = np.asarray(x, dtype=np.float64)
    ya = np.asarray(y, dtype=np.float64)
    if xa.shape != ya.shape or xa.ndim != 1:
        raise DataError(f"x and y must be 1-D and equal length, got {xa.shape}, {ya.shape}")
    if window < 3 or window > xa.size:
        raise DataError(f"window must be in [3, {xa.size}], got {window}")
    first = window - 1 if start is None else start
    if first < window - 1:
        raise DataError(f"start {first} precedes the first full window {window - 1}")
    out = np.full(xa.size, np.nan)
    for i in range(first, xa.size):
        xs, ys = xa[i - window + 1 : i + 1], ya[i - window + 1 : i + 1]
        if not (np.all(np.isfinite(xs)) and np.all(np.isfinite(ys))):
            continue
        xm, ym = xs.mean(), ys.mean()
        sxx = float(np.sum((xs - xm) ** 2))
        syy = float(np.sum((ys - ym) ** 2))
        if sxx == 0.0 or syy == 0.0:
            continue
        sxy = float(np.sum((xs - xm) * (ys - ym)))
        slope = sxy / sxx
        r = sxy / np.sqrt(sxx * syy)
        if (require_positive_slope and slope <= 0.0) or r < min_r:
            out[i] = 0.0
            continue
        intercept = ym - slope * xm
        out[i] = ya[i] - (intercept + slope * xa[i])
    return out


def vsa_indicator(bars: OHLCV, *, norm_lookback: int = 168) -> FloatArray:
    """Range-vs-volume residual per bar; NaN until ``2 * norm_lookback`` bars exist."""
    if norm_lookback < 3 or 2 * norm_lookback > len(bars):
        raise DataError(f"norm_lookback must be in [3, {len(bars) // 2}], got {norm_lookback}")
    norm_range = (bars.high - bars.low) / atr(bars, norm_lookback)
    norm_volume = bars.volume / rolling_median(bars.volume, norm_lookback)
    return rolling_ols_residual(
        norm_volume, norm_range, window=norm_lookback, start=2 * norm_lookback
    )

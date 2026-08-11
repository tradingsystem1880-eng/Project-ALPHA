"""The OHLCV container every detector consumes, plus the derived measures they share.

Keeping one validated container means each detector states its input contract once, and the
fail-loud checks (finite, ordered, OHLC-consistent) happen in a single place rather than being
re-implemented — inconsistently — in six modules.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from alpha_core import DataError

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.intp]


@dataclass(frozen=True)
class OHLCV:
    """A validated, strictly time-ordered bar series.

    ``ts`` holds epoch milliseconds rather than datetimes so the whole detection layer stays pure
    numpy — no timezone semantics leak into pattern geometry, and equality/ordering are exact.
    """

    ts: FloatArray
    open: FloatArray
    high: FloatArray
    low: FloatArray
    close: FloatArray
    volume: FloatArray
    symbol: str = "UNKNOWN"

    def __post_init__(self) -> None:
        n = self.ts.size
        for name in ("open", "high", "low", "close", "volume"):
            arr = getattr(self, name)
            if arr.shape != (n,):
                raise DataError(f"OHLCV.{name} must have shape ({n},), got {arr.shape}")
            if not bool(np.all(np.isfinite(arr))):
                raise DataError(f"OHLCV.{name} contains non-finite values")
        if n < 2:
            raise DataError(f"OHLCV needs >= 2 bars, got {n}")
        if not bool(np.all(np.diff(self.ts) > 0)):
            raise DataError("OHLCV timestamps must be strictly increasing")
        if bool(np.any(self.high < self.low)):
            raise DataError("OHLCV has a bar whose high is below its low")
        if bool(np.any((self.open > self.high) | (self.open < self.low))):
            raise DataError("OHLCV has an open outside its bar range")
        if bool(np.any((self.close > self.high) | (self.close < self.low))):
            raise DataError("OHLCV has a close outside its bar range")
        if bool(np.any(self.close <= 0.0)):
            raise DataError("OHLCV requires strictly-positive prices")

    def __len__(self) -> int:
        return int(self.ts.size)

    def slice(self, start: int, stop: int) -> OHLCV:
        """A view over ``[start, stop)`` — used to hand a detector only the past."""
        return OHLCV(
            ts=self.ts[start:stop],
            open=self.open[start:stop],
            high=self.high[start:stop],
            low=self.low[start:stop],
            close=self.close[start:stop],
            volume=self.volume[start:stop],
            symbol=self.symbol,
        )


def true_range(bars: OHLCV) -> FloatArray:
    """Wilder's true range per bar; the first bar falls back to its own high-low span."""
    prev_close = np.concatenate(([bars.close[0]], bars.close[:-1]))
    return np.maximum(
        bars.high - bars.low,
        np.maximum(np.abs(bars.high - prev_close), np.abs(bars.low - prev_close)),
    )


def atr(bars: OHLCV, window: int = 14) -> FloatArray:
    """Trailing simple-average true range.

    Deliberately **causal**: ``atr[i]`` averages true range over bars ``i-window+1 .. i`` inclusive,
    so it never reads a bar the market had not yet printed. Values before a full window are the
    average of what exists so far, which keeps the array the same length as the series without
    inventing data.
    """
    if window < 1:
        raise DataError(f"atr window must be >= 1, got {window}")
    tr = true_range(bars)
    csum = np.concatenate(([0.0], np.cumsum(tr)))
    idx = np.arange(tr.size)
    lo = np.maximum(0, idx - window + 1)
    counts = (idx - lo + 1).astype(np.float64)
    return (csum[idx + 1] - csum[lo]) / counts


def rolling_vwap(bars: OHLCV, window: int) -> FloatArray:
    """Causal rolling volume-weighted average price over ``window`` bars.

    Used as one of the higher-timeframe trend-state definitions: price above its 90-day VWAP is a
    different regime from price below it, and conditioning on that is what separates "trendline
    broken in a downtrend" from "trendline broken in a range".
    """
    if window < 1:
        raise DataError(f"rolling_vwap window must be >= 1, got {window}")
    typical = (bars.high + bars.low + bars.close) / 3.0
    pv = typical * bars.volume
    cpv = np.concatenate(([0.0], np.cumsum(pv)))
    cv = np.concatenate(([0.0], np.cumsum(bars.volume)))
    idx = np.arange(len(bars))
    lo = np.maximum(0, idx - window + 1)
    num = cpv[idx + 1] - cpv[lo]
    den = cv[idx + 1] - cv[lo]
    # Zero-volume windows fall back to typical price rather than producing NaN.
    return np.where(den > 0.0, num / np.where(den > 0.0, den, 1.0), typical)


def rolling_min(values: FloatArray, window: int) -> FloatArray:
    """Causal rolling minimum (``values[i-window+1 .. i]``)."""
    if window < 1:
        raise DataError(f"rolling_min window must be >= 1, got {window}")
    out = np.empty_like(values)
    for i in range(values.size):
        out[i] = np.min(values[max(0, i - window + 1) : i + 1])
    return out


def rolling_max(values: FloatArray, window: int) -> FloatArray:
    """Causal rolling maximum (``values[i-window+1 .. i]``)."""
    if window < 1:
        raise DataError(f"rolling_max window must be >= 1, got {window}")
    out = np.empty_like(values)
    for i in range(values.size):
        out[i] = np.max(values[max(0, i - window + 1) : i + 1])
    return out

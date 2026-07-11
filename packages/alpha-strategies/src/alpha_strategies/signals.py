"""Pure, look-ahead-safe trading signals (spec §7).

Each returns ``{-1, 0, 1}`` from a trailing window of prices and reads only the closes (or
highs/lows) it is handed — never anything "after" the decision bar. They fail loud (``DataError``)
on bad parameters or non-finite/non-positive prices, and return ``0`` on insufficient history.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from alpha_core import DataError


def _check_prices(label: str, values: Sequence[float]) -> None:
    """Fail loud if any price in ``values`` is non-finite or non-positive."""
    for value in values:
        if not math.isfinite(value) or value <= 0:
            raise DataError(f"{label} prices must be finite > 0, got {value!r}")


def ts_momentum_signal(closes: Sequence[float], lookback: int, skip: int) -> int:
    """Sign of the trailing ``lookback``-bar return, skipping the most recent ``skip`` bars.

    Classic "12-1" momentum (``lookback≈252``, ``skip≈21``): compares the close ``skip`` bars ago
    to the close ``skip + lookback`` bars ago, returning ``+1`` (up), ``-1`` (down), or ``0``
    (flat). The most recent ``skip`` bars are deliberately excluded (short-term reversal) and never
    influence the signal. Returns ``0`` when there is insufficient history; fails loud
    (``DataError``) on bad parameters or non-positive/NaN reference prices.
    """
    if lookback < 1:
        raise DataError(f"lookback must be >= 1, got {lookback}")
    if skip < 0:
        raise DataError(f"skip must be >= 0, got {skip}")
    if len(closes) < skip + lookback + 1:
        return 0
    recent = closes[-1 - skip]
    past = closes[-1 - skip - lookback]
    for label, value in (("recent", recent), ("past", past)):
        if not math.isfinite(value) or value <= 0:
            raise DataError(
                f"ts_momentum_signal {label} reference price must be finite > 0, got {value!r}"
            )
    ret = recent / past - 1.0
    if ret > 0:
        return 1
    if ret < 0:
        return -1
    return 0


def ma_crossover_signal(closes: Sequence[float], fast: int, slow: int) -> int:
    """Sign of (fast SMA − slow SMA) over the trailing closes — a classic trend filter.

    ``+1`` when the fast simple moving average is above the slow (uptrend), ``-1`` when below, ``0``
    when equal or on insufficient history (``< slow`` closes). Only the last ``slow`` closes matter.
    Fails loud (``DataError``) unless ``1 <= fast < slow`` or on non-positive/NaN prices used.
    """
    if fast < 1:
        raise DataError(f"fast must be >= 1, got {fast}")
    if slow <= fast:
        raise DataError(f"slow must be > fast, got slow={slow}, fast={fast}")
    if len(closes) < slow:
        return 0
    window = closes[-slow:]
    _check_prices("ma_crossover_signal", window)
    fast_ma = sum(window[-fast:]) / fast
    slow_ma = sum(window) / slow
    if fast_ma > slow_ma:
        return 1
    if fast_ma < slow_ma:
        return -1
    return 0


def zscore_reversion_signal(closes: Sequence[float], window: int, entry_z: float) -> int:
    """Mean-reversion: fade deviations beyond ``entry_z`` rolling standard deviations.

    Computes the z-score of the latest close against the trailing ``window`` closes (sample std,
    ddof=1). Returns ``-1`` when the close is ``>= entry_z`` std *above* the mean (overbought → fade
    short), ``+1`` when ``<= -entry_z`` std below (oversold → buy), else ``0``. Returns ``0`` on
    insufficient history (``< window`` closes) or a zero-dispersion window. Only the last ``window``
    closes matter. Fails loud (``DataError``) on ``window < 2``, ``entry_z <= 0``, or bad prices.
    """
    if window < 2:
        raise DataError(f"window must be >= 2, got {window}")
    if not math.isfinite(entry_z) or entry_z <= 0:
        raise DataError(f"entry_z must be finite > 0, got {entry_z!r}")
    if len(closes) < window:
        return 0
    sample = closes[-window:]
    _check_prices("zscore_reversion_signal", sample)
    mean = sum(sample) / window
    variance = sum((c - mean) ** 2 for c in sample) / (window - 1)
    std = math.sqrt(variance)
    if std <= 0.0:
        return 0  # flat window — no deviation to fade
    z = (sample[-1] - mean) / std
    if z >= entry_z:
        return -1  # overbought → fade (short)
    if z <= -entry_z:
        return 1  # oversold → buy
    return 0


def breakout_signal(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], window: int
) -> int:
    """Donchian channel breakout: trade in the direction of a new ``window``-bar extreme.

    ``+1`` when the latest close exceeds the highest high of the *prior* ``window`` bars (upside
    breakout), ``-1`` when it is below the lowest low of the prior ``window`` bars, else ``0``. The
    breakout channel deliberately excludes the current bar (uses bars ``[-window-1 : -1]``), so the
    most recent bar never defines its own channel. Returns ``0`` on insufficient history
    (``< window + 1`` bars). Fails loud (``DataError``) on ``window < 1``, length mismatch, or bad
    prices.
    """
    if window < 1:
        raise DataError(f"window must be >= 1, got {window}")
    if not (len(highs) == len(lows) == len(closes)):
        raise DataError(f"highs/lows/closes must align, got {len(highs)}/{len(lows)}/{len(closes)}")
    if len(closes) < window + 1:
        return 0
    prior_highs = highs[-window - 1 : -1]
    prior_lows = lows[-window - 1 : -1]
    last_close = closes[-1]
    _check_prices("breakout_signal", [*prior_highs, *prior_lows, last_close])
    if last_close > max(prior_highs):
        return 1
    if last_close < min(prior_lows):
        return -1
    return 0


def forecast_signal(
    last_close: float, forecast_closes: Sequence[float], deadband_bps: float
) -> int:
    """Sign of the horizon-end expected log-return, with a deadband.

    ``r = ln(forecast_closes[-1] / last_close)``; returns ``+1`` when ``r`` exceeds
    ``deadband_bps`` basis points, ``-1`` below ``-deadband_bps``, else ``0`` (a forecast
    inside the deadband is noise — don't trade it). The forecast values are produced by a
    ``BarForecaster`` fed trailing bars only; this mapping itself reads nothing but its
    arguments. Fails loud (``DataError``) on an empty forecast, a negative deadband, or
    non-finite/non-positive prices.
    """
    if deadband_bps < 0:
        raise DataError(f"deadband_bps must be >= 0, got {deadband_bps}")
    if len(forecast_closes) == 0:
        raise DataError("forecast_closes is empty")
    _check_prices("forecast_signal last_close", [last_close])
    _check_prices("forecast_signal forecast", forecast_closes)
    r_bps = math.log(forecast_closes[-1] / last_close) * 1e4
    if r_bps > deadband_bps:
        return 1
    if r_bps < -deadband_bps:
        return -1
    return 0

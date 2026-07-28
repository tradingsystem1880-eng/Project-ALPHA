"""Synthetic price series with *known* patterns injected — the detectors' ground truth.

A pattern study has two failure modes, and only one of them is statistical. The other is that the
detector does not find what the analyst believes it finds. No amount of confidence-interval rigour
downstream repairs a detector that silently misses half its targets or fires on noise.

So: build a series with no structure, inject triple taps (or trendlines) at *known* indices, and
require the detector to recover exactly those. :func:`geometric_brownian_series` alone also serves
as the **null calibration** — running a detector over pattern-free noise measures how often it
invents patterns, which is the base rate every real-data count must be read against.

Everything is seeded and reproducible.
"""

from __future__ import annotations

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import OHLCV, FloatArray

_BAR_MS = 4 * 60 * 60 * 1000  # 4-hour bars, in epoch milliseconds


def _bars_from_closes(
    closes: FloatArray, *, wiggle: float, rng: np.random.Generator, symbol: str
) -> OHLCV:
    """Wrap a close path in plausible OHLC and volume, preserving OHLC coherence exactly."""
    n = closes.size
    opens = np.concatenate(([closes[0]], closes[:-1]))
    spread = np.abs(closes) * wiggle
    highs = np.maximum(opens, closes) + rng.random(n) * spread
    lows = np.minimum(opens, closes) - rng.random(n) * spread
    lows = np.maximum(lows, 1e-8)
    volume = 1_000.0 + rng.random(n) * 1_000.0
    ts = np.arange(n, dtype=np.float64) * _BAR_MS
    return OHLCV(
        ts=ts, open=opens, high=highs, low=lows, close=closes, volume=volume, symbol=symbol
    )


def geometric_brownian_series(
    n_bars: int,
    *,
    start: float = 1.0,
    vol_per_bar: float = 0.01,
    drift_per_bar: float = 0.0,
    seed: int = 7,
    symbol: str = "SYNTH",
) -> OHLCV:
    """A driftless-by-default random walk: the pattern-free null.

    Any pattern a detector reports here is a false positive by construction, which makes the count
    the detector's own base rate.
    """
    if n_bars < 10:
        raise DataError(f"need >= 10 bars, got {n_bars}")
    rng = np.random.default_rng(seed)
    shocks = rng.normal(drift_per_bar - 0.5 * vol_per_bar**2, vol_per_bar, size=n_bars)
    closes = start * np.exp(np.cumsum(shocks))
    return _bars_from_closes(closes, wiggle=vol_per_bar * 0.5, rng=rng, symbol=symbol)


def inject_triple_tap(
    n_bars: int = 400,
    *,
    level: float = 1.0,
    tap_bars: tuple[int, int, int] = (60, 160, 260),
    rally_fraction: float = 0.15,
    tap_jitter: float = 0.0,
    plateau_drift: float = 0.35,
    noise: float = 0.002,
    seed: int = 7,
    symbol: str = "SYNTH_TT",
) -> tuple[OHLCV, tuple[int, int, int]]:
    """A series that dips to ``level`` at exactly ``tap_bars``, rallying in between.

    Returns the bars and the injected tap indices so a test can assert exact recovery.
    ``tap_jitter`` raises each successive tap by that fraction, producing the *ascending* variant.
    """
    if len(set(tap_bars)) != 3:
        raise DataError("tap_bars must be three distinct indices")
    if not all(0 < t < n_bars for t in tap_bars):
        raise DataError(f"tap_bars must lie inside (0, {n_bars})")
    if rally_fraction <= 0.0:
        raise DataError("rally_fraction must be > 0")

    rng = np.random.default_rng(seed)
    taps = sorted(tap_bars)
    tap_levels = [level * (1.0 + tap_jitter * k) for k in range(len(taps))]

    # The filler between taps *drifts upward* rather than sitting flat. A flat plateau is itself a
    # band of near-equal lows, so a tolerance-based detector correctly finds dozens of triples in
    # it — true to the definition, but useless as ground truth. Drifting the filler by more than the
    # tolerance guarantees the injected taps are the only three lows sharing a level.
    peak = level * (1.0 + rally_fraction)
    closes = peak * np.linspace(1.0, 1.0 + plateau_drift, n_bars)

    half = max(3, min(int(np.diff([0, *taps, n_bars - 1]).min()) // 3, 20))
    for t, lvl in zip(taps, tap_levels, strict=True):
        lo, hi = max(0, t - half), min(n_bars - 1, t + half)
        closes[lo : t + 1] = np.linspace(closes[lo], lvl, t - lo + 1)
        closes[t : hi + 1] = np.linspace(lvl, closes[hi], hi - t + 1)

    closes *= 1.0 + rng.normal(0.0, noise, size=n_bars)
    for t, lvl in zip(taps, tap_levels, strict=True):
        closes[t] = lvl  # pin exactly; noise must not blur the injected level

    bars = _bars_from_closes(closes, wiggle=noise, rng=rng, symbol=symbol)

    # Drive each tap's low strictly below every bar within the fractal window. Pinning to a fixed
    # fraction is not enough: an adjacent bar's random wiggle can dip under a shallow pin, which
    # silently shifts the detected tap by one bar.
    lows = np.minimum(bars.low, np.minimum(bars.open, bars.close))
    for t, lvl in zip(taps, tap_levels, strict=True):
        lo, hi = max(0, t - 25), min(n_bars, t + 26)
        neighbourhood = np.delete(lows[lo:hi], t - lo)
        lows[t] = min(lvl, float(np.min(neighbourhood))) * (1.0 - 2e-3)
    return (
        OHLCV(
            ts=bars.ts,
            open=bars.open,
            high=bars.high,
            low=lows,
            close=bars.close,
            volume=bars.volume,
            symbol=symbol,
        ),
        tuple(taps),  # type: ignore[return-value]
    )


def inject_descending_trendline(
    n_bars: int = 300,
    *,
    start: float = 2.0,
    slope_per_bar: float = -0.002,
    peak_bars: tuple[int, ...] = (40, 120, 200),
    break_bar: int = 250,
    break_size: float = 0.12,
    noise: float = 0.003,
    seed: int = 7,
    symbol: str = "SYNTH_TL",
) -> tuple[OHLCV, tuple[int, ...], int]:
    """A series whose swing highs sit on one descending line until a break at ``break_bar``.

    Returns the bars, the injected peak indices, and the break index.
    """
    if break_bar <= max(peak_bars):
        raise DataError("break_bar must come after every peak")
    if break_bar >= n_bars:
        raise DataError(f"break_bar must be < n_bars ({n_bars})")

    rng = np.random.default_rng(seed)
    line = start + slope_per_bar * np.arange(n_bars, dtype=np.float64)

    # Sit on a flat discount below the line, with a sharp triangular rally into each peak. As with
    # the triple-tap generator, a flat base means the injected peaks are the only swing highs.
    closes = line * 0.82
    span = 10
    for p in peak_bars:
        lo, hi = max(0, p - span), min(n_bars - 1, p + span)
        closes[lo : p + 1] = line[lo : p + 1] * np.linspace(0.82, 0.995, p - lo + 1)
        closes[p : hi + 1] = line[p : hi + 1] * np.linspace(0.995, 0.82, hi - p + 1)

    closes[break_bar:] = line[break_bar:] * (1.0 + break_size)
    closes *= 1.0 + rng.normal(0.0, noise, size=n_bars)

    bars = _bars_from_closes(closes, wiggle=noise, rng=rng, symbol=symbol)
    # Pin each peak's high just under the line: it touches without closing through.
    highs = np.maximum(bars.high, np.maximum(bars.open, bars.close))
    for p in peak_bars:
        highs[p] = float(line[p]) * 0.999
    highs = np.maximum(highs, np.maximum(bars.open, bars.close))
    return (
        OHLCV(
            ts=bars.ts,
            open=bars.open,
            high=highs,
            low=np.minimum(bars.low, np.minimum(bars.open, bars.close)),
            close=bars.close,
            volume=bars.volume,
            symbol=symbol,
        ),
        tuple(peak_bars),
        break_bar,
    )

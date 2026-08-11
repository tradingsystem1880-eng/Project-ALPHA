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

from dataclasses import dataclass

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


def inject_head_shoulders(
    n_bars: int = 500,
    *,
    direction: str = "bullish",
    anchor_bars: tuple[int, int, int] = (80, 220, 360),
    level: float = 1.0,
    head_depth: float = 0.10,
    neck_rise: float = 0.12,
    shoulder_tilt: float = 0.0,
    bos_overshoot: float = 0.0,
    breakout: float = 0.10,
    noise: float = 0.001,
    seed: int = 7,
    symbol: str = "SYNTH_HS",
) -> tuple[OHLCV, dict[str, int]]:
    """A series containing exactly one head-and-shoulders structure at known bars.

    Built as an explicit zig-zag through seven anchor points — start, left shoulder, neckline pivot,
    head, neckline pivot, right shoulder, breakout — joined by straight legs. Because every leg is
    monotonic, the only local extrema in the whole series are the anchors themselves, which is what
    lets a test assert *exact* recovery rather than "found it, plus whatever the filler created".
    This replaces the plateau-drift trick used by ``inject_triple_tap``: a zig-zag needs no drift
    because it has no flat region to generate spurious pivots.

    ``shoulder_tilt`` raises the right shoulder by that fraction (the ascending-shoulder variant the
    user's own chart shows). ``bos_overshoot`` lifts the *second* neckline pivot above the first, so
    the post-head rally makes a genuine higher high — that is the **break of structure**, and it is
    what turns an inverse head and shoulders into a Quasimodo. Leave it at 0 for a plain H&S.
    ``direction="bearish"`` mirrors everything into a topping pattern.

    Returns the bars and a dict of the injected indices keyed ``ls``/``n1``/``head``/``n2``/``rs``,
    so a test can compare against detector output directly.
    """
    if direction not in ("bullish", "bearish"):
        raise DataError(f"direction must be bullish|bearish, got {direction}")
    ls_bar, head_bar, rs_bar = anchor_bars
    if not 0 < ls_bar < head_bar < rs_bar < n_bars:
        raise DataError(f"anchor_bars must be increasing inside (0, {n_bars}), got {anchor_bars}")
    if head_depth <= 0.0 or neck_rise <= 0.0:
        raise DataError("head_depth and neck_rise must be > 0")

    rng = np.random.default_rng(seed)
    sign = 1.0 if direction == "bullish" else -1.0

    # Anchor levels. For a bottoming pattern the head is the lowest point and the neckline pivots
    # sit above the shoulders; `sign` mirrors that for a topping pattern.
    shoulder = level
    right_shoulder = level * (1.0 + sign * shoulder_tilt)
    head_lvl = level * (1.0 - sign * head_depth)
    neck_lvl = level * (1.0 + sign * neck_rise)
    neck2_lvl = neck_lvl * (1.0 + sign * bos_overshoot)
    end_lvl = (
        max(neck_lvl, neck2_lvl) * (1.0 + sign * breakout)
        if sign > 0
        else (min(neck_lvl, neck2_lvl) * (1.0 + sign * breakout))
    )

    n1_bar = (ls_bar + head_bar) // 2
    n2_bar = (head_bar + rs_bar) // 2
    knots = [
        (0, neck_lvl),
        (ls_bar, shoulder),
        (n1_bar, neck_lvl),
        (head_bar, head_lvl),
        (n2_bar, neck2_lvl),
        (rs_bar, right_shoulder),
        (n_bars - 1, end_lvl),
    ]

    closes = np.empty(n_bars, dtype=np.float64)
    for (i0, v0), (i1, v1) in zip(knots, knots[1:], strict=False):
        closes[i0 : i1 + 1] = np.linspace(v0, v1, i1 - i0 + 1)
    closes *= 1.0 + rng.normal(0.0, noise, size=n_bars)
    for idx, lvl in (
        (ls_bar, shoulder),
        (n1_bar, neck_lvl),
        (head_bar, head_lvl),
        (n2_bar, neck2_lvl),
        (rs_bar, right_shoulder),
    ):
        closes[idx] = lvl  # pin exactly; noise must not blur an injected level

    bars = _bars_from_closes(closes, wiggle=noise, rng=rng, symbol=symbol)
    lows = np.minimum(bars.low, np.minimum(bars.open, bars.close))
    highs = np.maximum(bars.high, np.maximum(bars.open, bars.close))

    # Drive each anchor strictly beyond every other bar within a wide neighbourhood. A fixed pin
    # is not enough: an adjacent bar's random wiggle can beat a shallow one and silently shift the
    # detected pivot by a bar. The window must exceed the largest fractal lookback under test.
    anchor_is_low = direction == "bullish"
    for idx in (ls_bar, head_bar, rs_bar):
        _pin(lows if anchor_is_low else highs, idx, n_bars, deeper=anchor_is_low)
    for idx in (n1_bar, n2_bar):
        _pin(highs if anchor_is_low else lows, idx, n_bars, deeper=not anchor_is_low)

    return (
        OHLCV(
            ts=bars.ts,
            open=bars.open,
            high=np.maximum(highs, np.maximum(bars.open, bars.close)),
            low=np.minimum(lows, np.minimum(bars.open, bars.close)),
            close=bars.close,
            volume=bars.volume,
            symbol=symbol,
        ),
        {"ls": ls_bar, "n1": n1_bar, "head": head_bar, "n2": n2_bar, "rs": rs_bar},
    )


@dataclass(frozen=True)
class WedgeTruth:
    """What :func:`inject_wedge` actually built — the ground truth a detector must recover.

    Typed rather than a loose dict so a test that misreads a field fails at type-check time instead
    of comparing an integer against a tuple and passing for the wrong reason.
    """

    highs: tuple[int, ...]  # bar indices of the upper-boundary pivots
    lows: tuple[int, ...]  # bar indices of the lower-boundary pivots
    apex: int  # the bar the two boundaries were generated to meet on
    break_bar: int
    kind: str


def inject_wedge(
    n_bars: int = 420,
    *,
    kind: str = "falling",
    start_upper: float = 1.30,
    start_lower: float = 1.00,
    apex_bar: int = 320,
    first_pivot: int = 30,
    pivot_gap: int = 40,
    n_pivots: int = 6,
    break_bar: int = 300,
    break_direction: int = 1,
    break_size: float = 0.10,
    inset: float = 0.006,
    noise: float = 0.0004,
    seed: int = 7,
    symbol: str = "SYNTH_WEDGE",
) -> tuple[OHLCV, WedgeTruth]:
    """A series that oscillates between two converging boundaries meeting at a known apex.

    Built in **log space**, matching :class:`~alpha_patterns.wedge.WedgeConfig`'s default scale, so
    a detector fitting a log-linear line through two exact anchors recovers the generating boundary
    exactly and the computed apex lands on ``apex_bar`` rather than near it. That exactness is the
    whole point: it lets a test assert recovery instead of resemblance.

    Pivots alternate high, low, high, low from ``first_pivot`` every ``pivot_gap`` bars. Closes are
    inset from the boundaries by ``inset`` so the "no close outside the lines" validity rule holds,
    while the pivot bars' own high/low sit exactly *on* the line — a touch, not a break.

    Returns the bars and a :class:`WedgeTruth` carrying the pivot bar indices, the generated apex
    bar and the break bar, so a test can assert exact recovery rather than resemblance.
    """
    if kind not in ("falling", "rising", "symmetrical"):
        raise DataError(f"kind must be falling|rising|symmetrical, got {kind}")
    if not 0.0 < start_lower < start_upper:
        raise DataError("need 0 < start_lower < start_upper")
    if break_direction not in (-1, 1):
        raise DataError(f"break_direction must be -1 or 1, got {break_direction}")
    if n_pivots < 4:
        raise DataError(f"need >= 4 pivots to define both lines, got {n_pivots}")

    pivots = [first_pivot + k * pivot_gap for k in range(n_pivots)]
    if not (pivots[0] > 0 and pivots[-1] < break_bar < n_bars):
        raise DataError(f"pivots {pivots} and break_bar {break_bar} must fit inside {n_bars} bars")
    if apex_bar <= pivots[-1]:
        raise DataError("apex_bar must lie beyond the last pivot")

    rng = np.random.default_rng(seed)
    # Both boundaries converge on one apex level; which side that level sits on is what makes the
    # formation falling (both lines down), rising (both up) or symmetrical (one of each).
    if kind == "falling":
        apex_level = start_lower * 0.88
    elif kind == "rising":
        apex_level = start_upper * 1.12
    else:
        apex_level = float(np.sqrt(start_upper * start_lower))

    frac = np.arange(n_bars, dtype=np.float64) / float(apex_bar)
    log_upper = np.log(start_upper) + (np.log(apex_level) - np.log(start_upper)) * frac
    log_lower = np.log(start_lower) + (np.log(apex_level) - np.log(start_lower)) * frac
    upper, lower = np.exp(log_upper), np.exp(log_lower)

    high_pivots = pivots[0::2]
    low_pivots = pivots[1::2]

    # Zig-zag the closes through the pivots, inset from each boundary so no close ever leaves the
    # formation — a close outside is exactly what the detector treats as invalidation.
    knots: list[tuple[int, float]] = [(0, float(lower[0] * (1.0 + inset)))]
    for p in pivots:
        level = upper[p] * (1.0 - inset) if p in high_pivots else lower[p] * (1.0 + inset)
        knots.append((p, float(level)))
    knots.append((break_bar, float((upper[break_bar] + lower[break_bar]) / 2.0)))

    closes = np.empty(n_bars, dtype=np.float64)
    for (i0, v0), (i1, v1) in zip(knots, knots[1:], strict=False):
        closes[i0 : i1 + 1] = np.linspace(v0, v1, i1 - i0 + 1)

    # The break leaves the formation and keeps going, so it cannot be mistaken for a wick.
    tail = np.arange(n_bars - break_bar, dtype=np.float64) / max(1, n_bars - break_bar - 1)
    edge = upper[break_bar:] if break_direction > 0 else lower[break_bar:]
    closes[break_bar:] = edge * (1.0 + break_direction * break_size * (0.2 + 0.8 * tail))
    closes *= 1.0 + rng.normal(0.0, noise, size=n_bars)

    opens = np.concatenate(([closes[0]], closes[:-1]))
    body_hi = np.maximum(opens, closes)
    body_lo = np.minimum(opens, closes)
    # Deterministic wicks rather than random ones: a random wiggle can beat a pivot's pin and
    # silently move the detected swing by a bar, which would make "exact recovery" untestable.
    highs = body_hi * (1.0 + noise)
    lows = body_lo * (1.0 - noise)
    for p in high_pivots:
        highs[p] = float(upper[p])
    for p in low_pivots:
        lows[p] = float(lower[p])
    highs = np.maximum(highs, body_hi)
    lows = np.minimum(lows, body_lo)

    bars = OHLCV(
        ts=np.arange(n_bars, dtype=np.float64) * _BAR_MS,
        open=opens,
        high=highs,
        low=lows,
        close=closes,
        volume=1_000.0 + rng.random(n_bars) * 200.0,
        symbol=symbol,
    )
    return bars, WedgeTruth(
        highs=tuple(high_pivots),
        lows=tuple(low_pivots),
        apex=apex_bar,
        break_bar=break_bar,
        kind=kind,
    )


def _pin(values: FloatArray, index: int, n_bars: int, *, deeper: bool, radius: int = 30) -> None:
    """Force ``values[index]`` strictly beyond every neighbour within ``radius`` bars, in place."""
    lo, hi = max(0, index - radius), min(n_bars, index + radius + 1)
    neighbourhood = np.delete(values[lo:hi], index - lo)
    if deeper:
        values[index] = float(np.min(neighbourhood)) * (1.0 - 3e-3)
    else:
        values[index] = float(np.max(neighbourhood)) * (1.0 + 3e-3)

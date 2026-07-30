"""One figure holding the whole structural argument: what is on the chart, and what it is worth.

The screenshot showed a triple tap, a sweep below it, and a reclaim. Every one of those readings is
accurate. The purpose of this figure is to put the accurate reading next to the measured value of
that reading, in the same frame, because the two are usually presented in different rooms.

Four panels:

* **price** — the 4h structure with every detected triple tap, the double top and double bottom,
  the order blocks, the volume-profile levels and the position's own levels. Annotated with the
  fact that matters most: five triple taps in fifty-five days, so the shape is common.
* **volume profile** — where trade actually happened, showing that the defended line at 1.0607 is a
  *low*-volume node and the real value-area low sits ~1.7% beneath it.
* **sweep test** — the reclaim thesis run over 455 events on five assets, per asset, so the
  single-asset false positive is visible rather than argued about.
* **fractal analogues** — the forty closest historical matches to the current 45-bar shape, scored
  against the true base rate and then Benjamini-Hochberg corrected across the four horizons.

Everything past 2026-07-25 is drawn as absent, not guessed. The uploaded chart showed 1.0868 and a
sweep that this environment's data does not contain, and inventing those bars to make the picture
tidy would be the one unforgivable thing to do here.

Run: ``python -m research.xrp_deep.structure_chart``
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.patches import Rectangle

from alpha_patterns import (
    OHLCV,
    detect_triple_taps,
    find_order_blocks,
    find_swings,
    rolling_mean,
)
from alpha_validation import benjamini_hochberg, newcombe_diff_interval
from research.hs_quasimodo import config as C
from research.hs_quasimodo.config import SOURCES
from research.hs_quasimodo.data import load
from research.xrp_deep.trade_chart import build_profile

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "research" / "xrp_deep" / "out"

#: The line the screenshot defended, and the price it showed. Both come from the uploaded image,
#: which is four days newer than any data available here — carried as annotation, never as data.
DEFENDED_LINE = 1.0607
SCREENSHOT_PRICE = 1.0868
SCREENSHOT_NOTE = "from the uploaded 4h chart — beyond this mirror's last bar"

WINDOW_START = "2026-06-01"
ASSETS = ("XRP", "BTC", "ETH", "SOL", "LTC")
#: Sweep definition, fixed before any outcome was measured.
SWEEP_LOOKBACK = 20
SWEEP_UP = 0.05
SWEEP_HORIZON = 20
#: Fractal-analogue settings.
TEMPLATE_BARS = 45
N_ANALOGUES = 40
ANALOGUE_HORIZONS = (5, 10, 20, 30)

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "text.color": C.FG,
        "axes.labelcolor": C.FG,
        "xtick.color": C.MUTED,
        "ytick.color": C.MUTED,
        "axes.edgecolor": C.GRID,
        "figure.dpi": 120,
    }
)
MONO: dict[str, Any] = {"family": "DejaVu Sans Mono"}


def _style(ax: Axes) -> None:
    ax.set_facecolor(C.PANEL)
    ax.grid(True, color=C.GRID, lw=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(C.GRID)


def _iso(ts: float, length: int = 10) -> str:
    return str(np.datetime64(int(ts), "ms"))[:length]


# --------------------------------------------------------------------------- evidence


@dataclass(frozen=True)
class SweepRow:
    asset: str
    n: int
    rate: float
    base: float
    lower: float
    upper: float


def sweep_evidence(horizon: int = SWEEP_HORIZON) -> tuple[list[SweepRow], SweepRow]:
    """Sweep-and-reclaim of a 20-bar low, per asset and pooled.

    A sweep is a bar whose low takes out the lowest low of the prior ``SWEEP_LOOKBACK`` bars and
    whose close is back above it. Outcome: did price reach +5% at any point inside the horizon.
    """
    rows: list[SweepRow] = []
    pool = [0, 0, 0, 0]
    for key in ASSETS:
        bars, _ = load(next(s for s in SOURCES if s.key == key), "1d")
        low, high, close = bars.low, bars.high, bars.close
        n = close.size
        hits = total = 0
        for i in range(SWEEP_LOOKBACK, n - horizon):
            prior = float(np.min(low[i - SWEEP_LOOKBACK : i]))
            if not (low[i] < prior and close[i] > prior):
                continue
            total += 1
            if float(np.max(high[i + 1 : i + horizon + 1])) / close[i] - 1.0 >= SWEEP_UP:
                hits += 1
        base_hits = base_total = 0
        for i in range(SWEEP_LOOKBACK, n - horizon):
            base_total += 1
            if float(np.max(high[i + 1 : i + horizon + 1])) / close[i] - 1.0 >= SWEEP_UP:
                base_hits += 1
        if total < 20:
            continue
        ci = newcombe_diff_interval(hits, total, base_hits, base_total)
        rows.append(SweepRow(key, total, hits / total, base_hits / base_total, ci.lower, ci.upper))
        pool[0] += hits
        pool[1] += total
        pool[2] += base_hits
        pool[3] += base_total
    ci = newcombe_diff_interval(*pool)
    pooled = SweepRow("POOLED", pool[1], pool[0] / pool[1], pool[2] / pool[3], ci.lower, ci.upper)
    return rows, pooled


@dataclass(frozen=True)
class AnalogueRow:
    horizon: int
    rate: float
    base: float
    median: float
    pvalue: float
    qvalue: float
    rejected: bool


def analogue_evidence() -> tuple[list[AnalogueRow], float, float]:
    """The K closest non-overlapping historical matches to the current shape, scored honestly.

    Matches are chosen on normalised shape alone, with no sight of their outcome. They are then
    compared against the *unconditional* base rate for the same horizon across the same assets —
    not against 50%, which would quietly credit the pattern for crypto's general upward drift.
    """
    from scipy.stats import norm as snorm

    def normalise(window: np.ndarray) -> np.ndarray:
        returns: np.ndarray = np.log(window / window[0])
        sd = float(returns.std())
        return returns / sd if sd > 0 else returns

    xrp, _ = load(next(s for s in SOURCES if s.key == "XRP"), "1d")
    template = normalise(xrp.close[-TEMPLATE_BARS:])

    series: dict[str, np.ndarray] = {}
    candidates: list[tuple[float, str, int]] = []
    for key in ASSETS:
        bars, _ = load(next(s for s in SOURCES if s.key == key), "1d")
        close = bars.close
        series[key] = close
        n = close.size
        for i in range(TEMPLATE_BARS, n - max(ANALOGUE_HORIZONS) - 1):
            if key == "XRP" and i > n - TEMPLATE_BARS - max(ANALOGUE_HORIZONS) - 5:
                continue
            shape = normalise(close[i - TEMPLATE_BARS : i])
            candidates.append((float(np.sqrt(np.mean((shape - template) ** 2))), key, i))
    candidates.sort(key=lambda t: t[0])

    kept: list[tuple[float, str, int]] = []
    used: dict[str, list[int]] = {}
    for dist, key, i in candidates:
        seen = used.setdefault(key, [])
        if any(abs(i - j) < TEMPLATE_BARS for j in seen):
            continue
        seen.append(i)
        kept.append((dist, key, i))
        if len(kept) >= N_ANALOGUES:
            break

    raw: list[tuple[int, float, float, float, float]] = []
    pvalues: list[float] = []
    for horizon in ANALOGUE_HORIZONS:
        forward = [
            series[k][i + horizon] / series[k][i] - 1.0
            for _, k, i in kept
            if i + horizon < series[k].size
        ]
        up = sum(1 for f in forward if f > 0)
        n_match = len(forward)
        base_hits = base_total = 0
        for close in series.values():
            for i in range(TEMPLATE_BARS, close.size - horizon):
                base_total += 1
                if close[i + horizon] / close[i] - 1.0 > 0:
                    base_hits += 1
        base = base_hits / base_total
        rate = up / n_match
        se = float(np.sqrt(base * (1 - base) / n_match))
        z = (rate - base) / se if se > 0 else 0.0
        pvalues.append(float(2 * (1 - snorm.cdf(abs(z)))))
        raw.append((horizon, rate, base, float(np.median(forward)), 0.0))

    fdr = benjamini_hochberg(pvalues, alpha=0.05)
    rows = [
        AnalogueRow(h, rate, base, median, p, float(q), bool(r))
        for (h, rate, base, median, _), p, q, r in zip(
            raw, pvalues, fdr.qvalues, fdr.rejected, strict=True
        )
    ]
    return rows, kept[0][0], kept[-1][0]


# --------------------------------------------------------------------------- drawing


def _candles(ax: Axes, bars: OHLCV, lo: int, hi: int) -> None:
    x = np.arange(lo, hi)
    up = bars.close[lo:hi] >= bars.open[lo:hi]
    colour = np.where(up, C.UP, C.DOWN)
    ax.vlines(x, bars.low[lo:hi], bars.high[lo:hi], color=colour, lw=0.7)
    ax.bar(
        x,
        np.abs(bars.close[lo:hi] - bars.open[lo:hi]),
        bottom=np.minimum(bars.open[lo:hi], bars.close[lo:hi]),
        width=0.66,
        color=colour,
        linewidth=0,
    )


def _price_panel(ax: Axes, bars: OHLCV, lo: int, hi: int, profile: Any) -> None:  # noqa: PLR0915
    _style(ax)
    _candles(ax, bars, lo, hi)
    ts, close = bars.ts, bars.close
    last = hi - 1
    px = float(close[last])

    # --- order blocks, drawn first so candles sit on top ---------------------------------
    for block in find_order_blocks(bars):
        if block.index < lo:
            continue
        colour = C.UP if block.direction == "bullish" else C.DOWN
        ax.add_patch(
            Rectangle(
                (block.index, block.bottom),
                hi - block.index,
                block.top - block.bottom,
                facecolor=colour,
                alpha=0.10,
                edgecolor=colour,
                lw=0.6,
                zorder=1,
            )
        )

    # --- every triple tap in the window: the point is that there are five ------------------
    taps = [t for t in detect_triple_taps(bars) if t.confirmed_index >= lo]
    for tap in taps:
        highlight = abs(tap.level - DEFENDED_LINE) / DEFENDED_LINE < 0.01
        colour = "#58a6ff" if highlight else "#6e7681"
        ax.hlines(
            tap.level,
            tap.tap_indices[0],
            hi - 1,
            color=colour,
            lw=1.8 if highlight else 0.9,
            alpha=1.0 if highlight else 0.55,
            zorder=4,
        )
        for k, idx in enumerate(tap.tap_indices, start=1):
            ax.plot(
                [idx], [tap.level], marker="v", ms=7 if highlight else 4.5, color=colour, zorder=6
            )
            if highlight:
                ax.text(
                    idx,
                    tap.level - 0.006,
                    f"{k}",
                    color=colour,
                    fontsize=9,
                    ha="center",
                    va="top",
                    fontweight="bold",
                    **MONO,
                )
        if highlight:
            ax.text(
                tap.tap_indices[0] + 2,
                tap.level * 1.008,
                f"TRIPLE TAP {tap.level:.4f}",
                color=colour,
                fontsize=9.5,
                ha="left",
                va="bottom",
                fontweight="bold",
                **MONO,
            )
    ax.text(
        0.012,
        0.965,
        f"{len(taps)} separate triple taps confirmed in this window\n"
        "— the shape is common, not special",
        transform=ax.transAxes,
        color="#8b949e",
        fontsize=9,
        va="top",
        **MONO,
    )

    # --- volume-profile levels -------------------------------------------------------------
    for value, label, colour, style in (
        (profile.poc, f"POC {profile.poc:.4f}", "#a371f7", "--"),
        (profile.vah, f"VAH {profile.vah:.4f}", "#6e7681", ":"),
        (profile.val, f"VAL {profile.val:.4f}  (the real floor)", "#d29922", "-"),
    ):
        ax.hlines(
            value,
            lo,
            hi - 1,
            color=colour,
            lw=1.4 if style == "-" else 1.0,
            linestyle=style,
            alpha=0.9,
            zorder=4,
        )
        ax.text(
            hi + 13, value, f"{label} ", color=colour, fontsize=8.5, va="center", ha="right", **MONO
        )

    # --- position levels ---------------------------------------------------------------------
    for value, colour, label in (
        (C.ENTRY, C.ACCENT, f"ENTRY {C.ENTRY:.4f}"),
        (C.STOP, C.DOWN, f"STOP {C.STOP:.4f}"),
        (C.LIQUIDATION, "#ff7b72", f"LIQ {C.LIQUIDATION:.4f}"),
    ):
        ax.hlines(value, lo, hi - 1, color=colour, lw=1.5, zorder=5)
        ax.text(
            lo + 0.5,
            value * 1.002,
            label,
            color=colour,
            fontsize=8.5,
            va="bottom",
            ha="left",
            **MONO,
        )

    # --- double top / double bottom ------------------------------------------------------------
    highs = [s for s in find_swings(bars, lookback=5, kind="high") if s.index >= lo]
    lows = [s for s in find_swings(bars, lookback=5, kind="low") if s.index >= lo]

    def _pair(swings: list[Any], tol: float = 0.006) -> tuple[Any, Any] | None:
        best = None
        for i in range(len(swings) - 1):
            for j in range(i + 1, len(swings)):
                if swings[j].index - swings[i].index < 5:
                    continue
                if abs(swings[j].price / swings[i].price - 1) <= tol and (
                    best is None or swings[j].index > best[1].index
                ):
                    best = (swings[i], swings[j])
        return best

    top = _pair(sorted(highs, key=lambda s: -s.price)[:6])
    if top:
        level = (top[0].price + top[1].price) / 2
        ax.hlines(level, top[0].index, hi - 1, color=C.DOWN, lw=1.3, linestyle="-.", zorder=5)
        ax.text(
            top[0].index,
            level * 1.004,
            f"DOUBLE TOP {level:.4f} — first real resistance",
            color=C.DOWN,
            fontsize=9,
            fontweight="bold",
            **MONO,
        )
        for s in top:
            ax.plot([s.index], [s.price], marker="^", ms=7, color=C.DOWN, zorder=6)

    bottom = _pair(sorted(lows, key=lambda s: s.price)[:6])
    if bottom:
        for s in bottom:
            ax.plot([s.index], [s.price], marker="o", ms=6, mfc="none", mec=C.UP, mew=1.4, zorder=6)

    # --- the screenshot's price, which this data does not reach ---------------------------------
    # The screenshot's price lives in a band this mirror has no data for. Draw the band, mark
    # the level, and label it once, rotated, so nothing competes with the level labels.
    ax.axvspan(hi - 1, hi + 42, color=C.BG, alpha=0.62, zorder=2)
    ax.hlines(
        SCREENSHOT_PRICE, hi - 1, hi + 14, color=C.FG, lw=1.2, linestyle=(0, (2, 2)), zorder=7
    )
    ax.plot([hi + 7], [SCREENSHOT_PRICE], marker="D", ms=6, color=C.FG, zorder=8)
    ax.text(
        hi + 20,
        float(bars.low[lo:hi].min()) * 1.03,
        f"NO DATA HERE  —  screenshot showed {SCREENSHOT_PRICE:.4f}",
        color=C.MUTED,
        fontsize=9,
        rotation=90,
        ha="center",
        va="bottom",
        fontweight="bold",
        zorder=9,
        **MONO,
    )

    # --- moving averages -------------------------------------------------------------------------
    for window, colour in ((50, "#8b949e"), (200, "#d29922")):
        ma = rolling_mean(close, window)
        ax.plot(np.arange(lo, hi), ma[lo:hi], color=colour, lw=1.1, alpha=0.85)
        ax.text(
            hi - 2,
            ma[last],
            f"{window}MA ",
            color=colour,
            fontsize=8,
            va="center",
            ha="right",
            **MONO,
        )

    ax.plot([last], [px], marker="o", ms=7, color=C.FG, zorder=9)
    ax.set_xlim(lo - 2, hi + 42)
    ax.set_ylim(
        min(C.LIQUIDATION, float(bars.low[lo:hi].min())) * 0.985,
        float(bars.high[lo:hi].max()) * 1.02,
    )
    ticks = np.arange(lo, hi, 42)
    ax.set_xticks(ticks)
    ax.set_xticklabels([_iso(ts[int(i)]) for i in ticks], fontsize=8, rotation=0)
    ax.set_ylabel("XRP / USDT   (4h)", fontsize=10)
    ax.set_title(
        f"XRP 4h structure, {_iso(ts[lo])} to {_iso(ts[last])}   ·   "
        f"last bar {px:.4f}   ·   every level the screenshot named, plus what the data says "
        "each one is worth",
        color=C.FG,
        fontsize=13,
        loc="left",
        pad=12,
    )


def _profile_panel(ax: Axes, profile: Any, ylim: tuple[float, float]) -> None:
    _style(ax)
    inside = (profile.centers >= profile.val) & (profile.centers <= profile.vah)
    height = (profile.high - profile.low) / profile.centers.size * 0.9
    ax.barh(
        profile.centers,
        profile.volume / profile.total * 100,
        height=height,
        color=np.where(inside, "#3b6ea5", "#2d3742"),
        linewidth=0,
    )
    peak = int(np.argmax(profile.volume))
    ax.barh(
        profile.centers[peak],
        profile.volume[peak] / profile.total * 100,
        height=height,
        color="#a371f7",
        linewidth=0,
    )
    for value, colour in (
        (profile.val, "#d29922"),
        (DEFENDED_LINE, "#58a6ff"),
        (C.ENTRY, C.ACCENT),
        (C.STOP, C.DOWN),
    ):
        ax.axhline(value, color=colour, lw=1.1, alpha=0.9)
    ax.annotate(
        f"defended {DEFENDED_LINE:.4f}\nonly {profile.share_at(DEFENDED_LINE):.2%} of volume",
        xy=(profile.share_at(DEFENDED_LINE) * 100, DEFENDED_LINE),
        xytext=(1.5, DEFENDED_LINE * 1.055),
        color="#58a6ff",
        fontsize=8,
        arrowprops={"arrowstyle": "->", "color": "#58a6ff", "lw": 0.9},
        **MONO,
    )
    ax.set_ylim(*ylim)
    ax.tick_params(labelleft=False, labelsize=7.5)
    ax.set_xlabel("% of volume", fontsize=8.5)
    ax.text(
        0.97,
        0.995,
        "volume at price\n5m, since 1 Jun",
        color=C.MUTED,
        fontsize=8,
        ha="right",
        va="top",
        transform=ax.transAxes,
        **MONO,
    )


def _sweep_panel(ax: Axes, rows: list[SweepRow], pooled: SweepRow) -> None:
    _style(ax)
    everything = [*rows, pooled]
    y = np.arange(len(everything))
    diffs = [r.rate - r.base for r in everything]
    colours = [C.UP if d > 0 else C.DOWN for d in diffs]
    colours[-1] = "#d29922"
    ax.barh(y, diffs, color=colours, alpha=0.85, height=0.6)
    for i, r in enumerate(everything):
        ax.plot([r.lower, r.upper], [i, i], color=C.MUTED, lw=1.3)
        ax.plot([r.lower, r.upper], [i, i], marker="|", ms=6, color=C.MUTED, lw=0)
    ax.axvline(0, color=C.FG, lw=1.1)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r.asset}  n={r.n}" for r in everything], fontsize=8.5, **MONO)
    ax.invert_yaxis()
    ax.set_xlabel("P(+5% in 20d) minus base rate", fontsize=8.5)
    ax.set_title(
        "SWEEP + RECLAIM of a 20-bar low — the thesis, tested",
        color=C.ACCENT,
        fontsize=10,
        loc="left",
        pad=8,
    )
    ax.text(
        0.5,
        -0.30,
        "XRP is the only asset that looks positive, and its interval still contains zero.\n"
        "Pooled over 455 events the effect is NEGATIVE. One asset up, the group down,\n"
        "is what a false positive looks like.",
        transform=ax.transAxes,
        color=C.MUTED,
        fontsize=8.5,
        ha="center",
        va="top",
        **MONO,
    )


def _analogue_panel(ax: Axes, rows: list[AnalogueRow], closest: float, worst: float) -> None:
    _style(ax)
    x = np.arange(len(rows))
    width = 0.38
    ax.bar(
        x - width / 2,
        [r.rate * 100 for r in rows],
        width,
        label="40 closest analogues",
        color="#3b6ea5",
    )
    ax.bar(
        x + width / 2,
        [r.base * 100 for r in rows],
        width,
        label="base rate, same horizon",
        color="#2d3742",
    )
    for i, r in enumerate(rows):
        mark = "survives BH" if r.rejected else f"q={r.qvalue:.2f}"
        colour = C.UP if r.rejected else C.MUTED
        ax.text(
            i, max(r.rate, r.base) * 100 + 2.2, mark, color=colour, fontsize=8, ha="center", **MONO
        )
        ax.text(
            i - width / 2,
            r.rate * 100 - 6,
            f"{r.rate:.0%}",
            color=C.FG,
            fontsize=8.5,
            ha="center",
            **MONO,
        )
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r.horizon}d" for r in rows], fontsize=9)
    ax.set_ylabel("P(up)", fontsize=8.5)
    ax.set_ylim(0, 88)
    ax.legend(loc="upper left", fontsize=8, facecolor=C.PANEL, edgecolor=C.GRID, labelcolor=C.FG)
    ax.set_title(
        "FRACTAL ANALOGUES — the 40 closest historical shapes",
        color=C.ACCENT,
        fontsize=10,
        loc="left",
        pad=8,
    )
    ax.text(
        0.5,
        -0.30,
        f"Matched on normalised shape alone over 5 assets (distance {closest:.2f}-{worst:.2f}).\n"
        "The 10-day cell reaches p=0.035 on its own and q=0.14 once the four horizons are\n"
        "corrected together. ZERO of four survive. It is the best signal here, and it fails.",
        transform=ax.transAxes,
        color=C.MUTED,
        fontsize=8.5,
        ha="center",
        va="top",
        **MONO,
    )


def _verdict_panel(ax: Axes, bars: OHLCV, profile: Any) -> None:
    ax.axis("off")
    close = bars.close
    px = float(close[-1])
    ma_lines = []
    for window in (20, 50, 100, 200):
        ma = float(rolling_mean(close, window)[-1])
        ma_lines.append(f"  {window:>3}MA {ma:.4f}  {px / ma - 1:+.2%}")

    blocks: list[tuple[str, str]] = [
        ("WHAT IS TRUE ON THE CHART", "head"),
        ("triple tap at 1.0620 CONFIRMED", "good"),
        ("  taps 6 Jun / 8 Jul / 17 Jul", "body"),
        ("price sits inside a bullish order", "good"),
        ("  block at 1.0848-1.0933 (2 Jul)", "body"),
        ("double bottom 1.0678 / 1.0691", "good"),
        ("", "gap"),
        ("WHAT IS NOT", "head"),
        (f"NOT holding VAL. VAL is {profile.val:.4f};", "bad"),
        (f"  {DEFENDED_LINE:.4f} sits {DEFENDED_LINE / profile.val - 1:+.1%} above it,", "body"),
        ("  inside the value area, on only", "body"),
        (f"  {profile.share_at(DEFENDED_LINE):.2%} of the window's volume", "body"),
        ("the tap is not rare: 5 triple taps,", "bad"),
        ("  17 double tops, 12 double bottoms", "body"),
        ("  in the same 55 days", "body"),
        ("", "gap"),
        ("MOVING AVERAGES (4h)", "head"),
        *[(line, "body" if "+" in line else "bad") for line in ma_lines],
        ("daily: below all four; -11.8% under", "bad"),
        ("  the 100d, -21.3% under the 200d", "bad"),
        ("", "gap"),
        ("THE PRIOR STUDY", "head"),
        ("1,324 triple taps, seven series:", "body"),
        ("  33.38% vs 33.33% breakeven", "body"),
        ("  +0.63pp  CI [-2.13, +3.46]", "bad"),
        ("third taps resolve up 42.7% at 20d;", "bad"),
        ("  FOURTH taps 52.1% — backwards", "bad"),
    ]

    colours = {"head": C.ACCENT, "body": C.FG, "good": C.UP, "bad": C.DOWN, "gap": C.FG}
    y = 1.0
    for text, kind in blocks:
        if kind == "gap":
            y -= 0.016
            continue
        ax.text(
            0.0,
            y,
            text,
            color=colours[kind],
            fontsize=8.6,
            fontweight="bold" if kind == "head" else "normal",
            va="top",
            ha="left",
            transform=ax.transAxes,
            **MONO,
        )
        if kind == "head":
            y -= 0.006
            ax.plot(
                [0.0, 0.95], [y, y], color=C.GRID, lw=0.9, transform=ax.transAxes, clip_on=False
            )
        y -= 0.0305


def structure_chart(out: Path | None = None) -> Path:
    bars, prov = load(next(s for s in SOURCES if s.key == "XRP"), "4h")
    profile = build_profile(start=WINDOW_START, bins=70)
    start = int(np.flatnonzero(bars.ts >= np.datetime64(WINDOW_START, "ms").astype(float))[0])
    lo, hi = start, bars.close.size

    sweep_rows, pooled = sweep_evidence()
    analogues, closest, worst = analogue_evidence()

    fig = plt.figure(figsize=(23.0, 14.0), facecolor=C.BG)
    grid = fig.add_gridspec(
        2,
        4,
        width_ratios=[7.4, 1.6, 0.55, 5.0],
        height_ratios=[3.05, 1.0],
        hspace=0.34,
        wspace=0.16,
    )
    ax_price = fig.add_subplot(grid[0, 0])
    ax_vp = fig.add_subplot(grid[0, 1], sharey=ax_price)
    ax_txt = fig.add_subplot(grid[0, 3])
    ax_sweep = fig.add_subplot(grid[1, 0])
    ax_ana = fig.add_subplot(grid[1, 2:])

    _price_panel(ax_price, bars, lo, hi, profile)
    _profile_panel(ax_vp, profile, ax_price.get_ylim())
    _verdict_panel(ax_txt, bars, profile)
    _sweep_panel(ax_sweep, sweep_rows, pooled)
    _analogue_panel(ax_ana, analogues, closest, worst)

    fig.text(
        0.5,
        0.975,
        "XRP — the screenshot's structure, and what nine years of data say each piece is worth",
        color=C.FG,
        fontsize=16,
        ha="center",
        fontweight="bold",
    )
    fig.text(
        0.006,
        0.008,
        f"Price: {prov.exchange} {prov.market} 4h, ends {prov.last_ts[:16]}   ·   "
        f"volume profile from 5m bars since {WINDOW_START}   ·   "
        "sweep test 455 events / 5 assets   ·   analogues matched on shape then BH-corrected\n"
        "The uploaded chart showed 1.0868 and a sweep below 1.0607. Neither exists in this "
        "mirror, which ends 2026-07-25 — that region is drawn empty rather than guessed.",
        color=C.MUTED,
        fontsize=8.5,
        va="bottom",
        **MONO,
    )

    out = out or (OUT / "xrp-structure-evidence.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=C.BG, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> int:
    print(f"wrote {structure_chart()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

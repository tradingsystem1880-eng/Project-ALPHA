"""The live XRP long, as a trade — not as a pattern.

The earlier chart put the inverse-head-and-shoulders geometry at the centre and the position in a
footnote. That is backwards for someone who is *in* the trade: the pattern is one input, and a
thoroughly discredited one (the deep study found chart patterns produced zero surviving results in
1,832 tests, and `inverse_hs_confirmed` at 30 days carries an uncorrected **bearish** tilt). What
matters day to day is where price sits relative to entry, stop, liquidation and target, and where
the volume actually is.

So this figure leads with three things the old one did not show:

1. **A volume profile** built from 5-minute bars since 1 May. It answers the question a horizontal
   support line only gestures at: how much was actually traded at each price? The single most
   important fact it surfaces is that the stop and the liquidation both sit *below the entire
   three-month profile* — no volume has changed hands there since May, so there is nothing to slow
   a move through that zone.
2. **The position's own arithmetic** — mark-to-market P&L, distance to each level, and the fact
   that the stop and the liquidation are 0.33% apart and therefore one event, not two.
3. **The stall.** Price rallied off the June low, topped on 4 July, and has spent three weeks
   grinding sideways-to-down inside the heaviest volume shelf on the chart.

Run: ``python -m research.xrp_deep.trade_chart``
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.axes import Axes

from alpha_patterns import OHLCV
from research.hs_quasimodo import config as C
from research.hs_quasimodo.config import SOURCES
from research.hs_quasimodo.data import load

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "research" / "xrp_deep" / "out"
FIVE_MIN = REPO_ROOT / "data" / "cache" / "raw_github" / "binance_linear_XRPUSDT_5m.parquet"

#: Volume profile window. May onward covers the whole move the position is trading — the top, the
#: June capitulation, the July bounce and the current stall — without reaching back into a price
#: regime that no longer informs where liquidity sits.
PROFILE_START = "2026-05-01"
PROFILE_BINS = 90
#: Daily bars shown. Chosen so the June low, the July high and the current stall all fit while
#: the target still sits on the chart — a longer window pushes the May top to 1.55 and squashes
#: every level the position actually cares about into the bottom third.
WINDOW_BARS = 62
#: Share of volume defining the value area, the standard market-profile convention.
VALUE_AREA = 0.70

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "text.color": C.FG,
        "axes.labelcolor": C.FG,
        "xtick.color": C.MUTED,
        "ytick.color": C.MUTED,
        "axes.edgecolor": C.GRID,
        "figure.dpi": 130,
    }
)
MONO: dict[str, Any] = {"family": "DejaVu Sans Mono"}


@dataclass(frozen=True)
class Profile:
    """A volume-at-price histogram plus the levels traders read off it."""

    centers: np.ndarray
    volume: np.ndarray
    poc: float
    val: float
    vah: float
    low: float
    high: float
    total: float

    def share_at(self, price: float) -> float:
        """Fraction of profile volume in the bin containing ``price``; 0.0 outside the range."""
        if not self.low <= price <= self.high:
            return 0.0
        idx = int(np.clip(np.searchsorted(self.centers, price), 0, self.centers.size - 1))
        return float(self.volume[idx] / self.total)


def build_profile(start: str = PROFILE_START, bins: int = PROFILE_BINS) -> Profile:
    """Volume at price from 5-minute bars, weighted by each bar's typical price.

    Typical price rather than close: a 5-minute bar that ranged over half a cent did not trade all
    its volume at the closing tick, and using the close alone puts spikes of volume at prices where
    comparatively little changed hands.
    """
    df = pl.read_parquet(FIVE_MIN).with_columns(
        pl.from_epoch(pl.col("timestamp"), time_unit="ms").alias("dt")
    )
    year, month, day = (int(x) for x in start.split("-"))
    window = df.filter(pl.col("dt") >= pl.datetime(year, month, day))
    typical = ((window["high"] + window["low"] + window["close"]) / 3).to_numpy()
    volume = window["volume"].to_numpy().astype(np.float64)

    low, high = float(typical.min()), float(typical.max())
    edges = np.linspace(low, high, bins + 1)
    idx = np.clip(np.digitize(typical, edges) - 1, 0, bins - 1)
    hist = np.zeros(bins, dtype=np.float64)
    np.add.at(hist, idx, volume)
    centers = (edges[:-1] + edges[1:]) / 2.0

    total = float(hist.sum())
    # Value area: take bins in descending volume order until VALUE_AREA of the total is covered,
    # then report the price span they occupy. The standard construction.
    order = np.argsort(hist)[::-1]
    cumulative, chosen = 0.0, []
    for i in order:
        chosen.append(int(i))
        cumulative += hist[i]
        if cumulative >= VALUE_AREA * total:
            break
    return Profile(
        centers=centers,
        volume=hist,
        poc=float(centers[int(np.argmax(hist))]),
        val=float(centers[min(chosen)]),
        vah=float(centers[max(chosen)]),
        low=low,
        high=high,
        total=total,
    )


def _candles(ax: Axes, bars: OHLCV, lo: int, hi: int) -> None:
    x = np.arange(lo, hi)
    up = bars.close[lo:hi] >= bars.open[lo:hi]
    colour = np.where(up, C.UP, C.DOWN)
    ax.vlines(x, bars.low[lo:hi], bars.high[lo:hi], color=colour, lw=0.8)
    ax.bar(
        x,
        np.abs(bars.close[lo:hi] - bars.open[lo:hi]),
        bottom=np.minimum(bars.open[lo:hi], bars.close[lo:hi]),
        width=0.72,
        color=colour,
        linewidth=0,
    )


def _style(ax: Axes) -> None:
    ax.set_facecolor(C.PANEL)
    ax.grid(True, color=C.GRID, lw=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(C.GRID)


def _in_value(profile: Profile, price: float) -> str:
    return "inside the value area" if profile.val <= price <= profile.vah else "outside value"


def _iso(ts: float) -> str:
    return str(np.datetime64(int(ts), "ms"))[:10]


def trade_chart(out: Path | None = None) -> Path:  # noqa: PLR0915 — one figure, drawn top to bottom
    bars, prov = load(next(s for s in SOURCES if s.key == "XRP"), "1d")
    profile = build_profile()
    n = bars.close.size
    last = n - 1
    px = float(bars.close[last])

    # Window: enough context to show the June low, the July high and the stall, without shrinking
    # the current action into the right-hand edge.
    lo = max(0, n - WINDOW_BARS)
    hi = n

    # Vertical range must cover the target and the liquidation, or the two levels the position
    # actually turns on end up off-screen. Computed here because the profile-level loop below
    # needs it to decide which labels are visible.
    y_lo = min(C.LIQUIDATION, float(bars.low[lo:hi].min())) * 0.985
    y_hi = max(C.TARGET, float(bars.high[lo:hi].max())) * 1.015

    pnl = C.QUANTITY * (px - C.ENTRY)
    risk_usdt = C.QUANTITY * (C.ENTRY - C.STOP)

    fig = plt.figure(figsize=(19.2, 9.6), facecolor=C.BG)
    grid = fig.add_gridspec(
        2, 3, width_ratios=[7.4, 1.5, 4.0], height_ratios=[4.2, 1.0], hspace=0.06, wspace=0.03
    )
    ax = fig.add_subplot(grid[0, 0])
    ax_vp = fig.add_subplot(grid[0, 1], sharey=ax)
    ax_vol = fig.add_subplot(grid[1, 0], sharex=ax)
    ax_txt = fig.add_subplot(grid[:, 2])

    # ---------------------------------------------------------------- price
    _style(ax)
    _candles(ax, bars, lo, hi)

    span = (lo, hi - 1)
    # `stop` and `liquidation` are 0.33% apart, so their labels overlap if both are left-anchored.
    # Anchoring the liquidation label on the right separates them without moving either line.
    fall_to_stop = C.STOP / px - 1.0
    levels = (
        (C.TARGET, C.WARN, "-", 1.7, "left", f"TARGET {C.TARGET:.4f}   {C.TARGET / px - 1:+.1%}"),
        (C.ENTRY, C.ACCENT, "-", 1.7, "left", f"ENTRY {C.ENTRY:.4f}"),
        (C.STOP, C.DOWN, "-", 1.7, "left", f"STOP {C.STOP:.4f}   {fall_to_stop:+.1%}"),
        (
            C.LIQUIDATION,
            "#ff7b72",
            ":",
            1.5,
            "right",
            f"LIQ {C.LIQUIDATION:.4f}   {C.LIQUIDATION / px - 1:+.1%}",
        ),
    )
    for value, colour, style, width, side, label in levels:
        ax.hlines(value, *span, color=colour, lw=width, linestyle=style, zorder=5)
        x = lo + 0.6 if side == "left" else hi - 1.2
        va = "bottom" if value is not C.LIQUIDATION else "top"
        ax.text(x, value, label, color=colour, fontsize=9, va=va, ha=side, **MONO)

    # Only levels inside the visible range: VAH sits at 1.43 on this profile, well above the
    # window, and drawing its label anyway strands text above the axes.
    for value, label, colour in (
        (profile.poc, f"POC {profile.poc:.4f}", "#a371f7"),
        (profile.vah, f"VAH {profile.vah:.4f}", "#6e7681"),
        (profile.val, f"VAL {profile.val:.4f}", "#6e7681"),
    ):
        if not y_lo <= value <= y_hi:
            continue
        ax.hlines(value, *span, color=colour, lw=1.0, linestyle="--", alpha=0.75, zorder=4)
        ax.text(hi - 1.2, value, label, color=colour, fontsize=8, va="bottom", ha="right", **MONO)

    # Entry-to-now shading: green when in profit, red when not.
    ax.fill_between(
        [lo, hi - 1],
        C.ENTRY,
        px,
        color=C.UP if px >= C.ENTRY else C.DOWN,
        alpha=0.07,
        zorder=1,
    )
    ax.plot([last], [px], marker="o", ms=7, color=C.FG, zorder=8)
    ax.text(
        last - 1.5,
        px,
        f"{px:.4f}  ",
        color=C.FG,
        fontsize=10,
        va="center",
        ha="right",
        fontweight="bold",
        **MONO,
    )

    # The two structural facts the eye should catch: the June low and the July high.
    low_i = int(np.argmin(bars.low[lo:hi])) + lo
    high_i = int(np.argmax(bars.high[lo:hi])) + lo
    ax.annotate(
        f"low {bars.low[low_i]:.4f}\n{_iso(bars.ts[low_i])}",
        xy=(low_i, bars.low[low_i]),
        xytext=(low_i - 9, bars.low[low_i] - 0.035),
        color=C.UP,
        fontsize=8,
        ha="center",
        arrowprops={"arrowstyle": "->", "color": C.UP, "lw": 0.9},
        **MONO,
    )
    ax.annotate(
        f"high {bars.high[high_i]:.4f}\n{_iso(bars.ts[high_i])}",
        xy=(high_i, bars.high[high_i]),
        xytext=(high_i + 9, bars.high[high_i] - 0.030),
        color=C.DOWN,
        fontsize=8,
        ha="center",
        arrowprops={"arrowstyle": "->", "color": C.DOWN, "lw": 0.9},
        **MONO,
    )

    ax.set_ylabel("XRP / USDT", fontsize=10)
    ax.set_xlim(lo - 1, hi + 1)
    ax.set_ylim(y_lo, y_hi)
    ax.tick_params(labelbottom=False)
    ax.set_title(
        f"XRP long — {C.QUANTITY:,.0f} XRP @ {C.ENTRY:.4f}, {C.LEVERAGE}x isolated   ·   "
        f"mark {px:.4f} ({_iso(bars.ts[last])})   ·   "
        f"unrealised {pnl:+,.0f} USDT ({pnl / C.MARGIN_USDT:+.1%} on margin)",
        color=C.FG,
        fontsize=13,
        loc="left",
        pad=14,
    )

    # ---------------------------------------------------------------- volume profile
    _style(ax_vp)
    inside = (profile.centers >= profile.val) & (profile.centers <= profile.vah)
    ax_vp.barh(
        profile.centers,
        profile.volume / profile.total * 100,
        height=(profile.high - profile.low) / PROFILE_BINS * 0.92,
        color=np.where(inside, "#3b6ea5", "#2d3742"),
        linewidth=0,
    )
    poc_index = int(np.argmax(profile.volume))
    ax_vp.barh(
        profile.centers[poc_index],
        profile.volume[poc_index] / profile.total * 100,
        height=(profile.high - profile.low) / PROFILE_BINS * 0.92,
        color="#a371f7",
        linewidth=0,
    )
    for value, colour in (
        (C.ENTRY, C.ACCENT),
        (C.TARGET, C.WARN),
        (C.STOP, C.DOWN),
        (C.LIQUIDATION, "#ff7b72"),
    ):
        ax_vp.axhline(value, color=colour, lw=1.1, alpha=0.85)
    ax_vp.axhline(px, color=C.FG, lw=1.2)

    # The point of the whole panel: nothing traded below the profile's floor, so the stop sits in
    # a vacuum. Shade it and say so.
    ax_vp.axhspan(ax.get_ylim()[0], profile.low, color=C.DOWN, alpha=0.12, zorder=0)
    ax_vp.text(
        ax_vp.get_xlim()[1] * 0.97,
        (ax.get_ylim()[0] + profile.low) / 2,
        "NO VOLUME\nSINCE MAY",
        color="#ff7b72",
        fontsize=8,
        ha="right",
        va="center",
        fontweight="bold",
        **MONO,
    )
    ax_vp.set_xlabel("% of volume", fontsize=8.5)
    ax_vp.tick_params(labelleft=False, labelsize=7.5)
    ax_vp.text(
        0.97,
        0.995,
        "volume at price\n5m, since 1 May",
        color=C.MUTED,
        fontsize=8,
        ha="right",
        va="top",
        transform=ax_vp.transAxes,
        **MONO,
    )

    # ---------------------------------------------------------------- daily volume
    _style(ax_vol)
    bar_x = np.arange(lo, hi)
    up = bars.close[lo:hi] >= bars.open[lo:hi]
    ax_vol.bar(
        bar_x,
        bars.volume[lo:hi],
        width=0.72,
        color=np.where(up, C.UP, C.DOWN),
        alpha=0.55,
        linewidth=0,
    )
    avg20 = np.convolve(bars.volume, np.ones(20) / 20, mode="same")
    ax_vol.plot(bar_x, avg20[lo:hi], color=C.MUTED, lw=1.1)
    ax_vol.set_ylabel("volume", fontsize=8.5)
    ax_vol.tick_params(labelsize=8)
    ax_vol.set_xticks(np.arange(lo, hi, 14))
    ax_vol.set_xticklabels([_iso(bars.ts[int(i)]) for i in np.arange(lo, hi, 14)], fontsize=8)
    ax_vol.text(
        lo + 0.6,
        ax_vol.get_ylim()[1] * 0.86,
        f"last bar {bars.volume[last] / bars.volume[last - 20 : last].mean():.2f}x the 20d average",
        color=C.MUTED,
        fontsize=8,
        **MONO,
    )

    # ---------------------------------------------------------------- the trade, in words
    ax_txt.axis("off")
    ax_txt.set_facecolor(C.PANEL)

    to_target = (C.TARGET / px - 1) * 100
    # How far price must FALL to reach the stop, so the base is the current mark. Dividing by the
    # stop instead reads 9.9% and overstates the cushion by nearly a point.
    to_stop = (C.STOP / px - 1) * 100
    progress = (px - C.ENTRY) / (C.TARGET - C.ENTRY)

    # The trade's actual experience. The entry date is not recorded, but the entry price is: these
    # are the bars whose range contained it, which bracket when the fill could have happened.
    touched = [i for i in range(lo, hi) if bars.low[i] <= C.ENTRY <= bars.high[i]]
    first_touch, last_touch = (touched[0], touched[-1]) if touched else (last, last)
    mfe_early = float(bars.high[first_touch:].max()) / C.ENTRY - 1.0
    mae_early = float(bars.low[first_touch:].min()) / C.ENTRY - 1.0
    mfe_late = float(bars.high[last_touch:].max()) / C.ENTRY - 1.0
    mae_late = float(bars.low[last_touch:].min()) / C.ENTRY - 1.0
    range_lo, range_hi = float(bars.low[-21:].min()), float(bars.high[-21:].max())

    lines: list[tuple[str, str]] = [
        ("THE POSITION", "head"),
        (f"size        {C.QUANTITY:>12,.1f} XRP", "body"),
        (f"entry       {C.ENTRY:>12.4f}", "body"),
        (f"mark        {px:>12.4f}   {px / C.ENTRY - 1:+.2%}", "good" if px >= C.ENTRY else "bad"),
        (f"notional    {C.QUANTITY * C.ENTRY:>12,.0f} USDT", "body"),
        (f"margin      {C.MARGIN_USDT:>12,.0f} USDT   {C.LEVERAGE}x isolated", "body"),
        (f"unrealised  {pnl:>+12,.0f} USDT", "good" if pnl >= 0 else "bad"),
        (f"on margin   {pnl / C.MARGIN_USDT:>+12.1%}", "good" if pnl >= 0 else "bad"),
        ("", "gap"),
        ("DISTANCE TO EACH LEVEL", "head"),
        (f"target      {C.TARGET:.4f}   {to_target:>+6.1f}%   {progress:.0%} of the way", "body"),
        (f"stop        {C.STOP:.4f}   {to_stop:>+6.1f}%", "body"),
        (f"liquidation {C.LIQUIDATION:.4f}   {(C.LIQUIDATION / px - 1) * 100:>+6.1f}%", "body"),
        ("stop and liquidation are 0.33% apart —", "warn"),
        ("they are one event, not two", "warn"),
        ("", "gap"),
        ("HOW IT HAS GONE", "head"),
        (f"entry traded {_iso(bars.ts[first_touch])} to {_iso(bars.ts[last_touch])}", "body"),
        ("fill date unrecorded; these bracket it", "body"),
        (f"best since first touch  {mfe_early:>+7.1%}", "body"),
        (f"worst since first touch {mae_early:>+7.1%}", "body"),
        (f"best since last touch   {mfe_late:>+7.1%}", "body"),
        (f"worst since last touch  {mae_late:>+7.1%}", "body"),
        # A single "giveback" number would hide which entry basis it assumes and would blur
        # percentage-points-of-gain against price drawdown. Stating the arc is unambiguous.
        (f"arc: peak {mfe_early:+.1%} -> now {px / C.ENTRY - 1:+.1%}", "warn"),
        (f"price is {px / (C.ENTRY * (1 + mfe_early)) - 1:.1%} below that peak", "warn"),
        ("", "gap"),
        ("THE LAST THREE WEEKS", "head"),
        (f"range {range_lo:.4f} - {range_hi:.4f}  ({range_hi / range_lo - 1:.1%} wide)", "body"),
        ("topped 4 Jul, drifting since — 20d -5.1%", "body"),
        ("ADX 11.3 (no trend), RSI 47 (neutral)", "body"),
        ("perp share 88% vs 77% median: the move", "body"),
        ("is leveraged, not spot-driven", "body"),
        ("", "gap"),
        ("WHERE THE VOLUME IS", "head"),
        (f"POC         {profile.poc:.4f}   {profile.poc / px - 1:+.1%} from mark", "body"),
        (f"value area  {profile.val:.4f} - {profile.vah:.4f}", "body"),
        (f"mark sits   {_in_value(profile, px)}, below POC", "body"),
        (f"at mark     {profile.share_at(px):.1%} of 3-month volume", "body"),
        (f"at target   {profile.share_at(C.TARGET):.1%}  — thin air above", "body"),
        (f"profile low {profile.low:.4f}", "body"),
        ("stop is BELOW the entire profile:", "warn"),
        ("no volume has traded there since May", "warn"),
        ("", "gap"),
        ("RISK", "head"),
        (f"loss if stopped {risk_usdt:>10,.0f} USDT", "bad"),
        (
            f"framework cap   {C.RISK_CAP_USDT:>10,.0f} USDT"
            f"   = {risk_usdt / C.RISK_CAP_USDT:.0f}x",
            "bad",
        ),
        (f"R:R {C.REWARD_RISK:.2f}   breakeven win rate {C.BREAKEVEN:.1%}", "body"),
        ("", "gap"),
        ("WHAT THE DATA SAYS", "head"),
        ("1,832 tests / 24 families / 9 years:", "body"),
        ("zero directional edge survived (p=1.00);", "body"),
        ("chart patterns incl. inverse H&S: nothing.", "body"),
        ("Compression at the 1.6th percentile calls", "body"),
        ("a bigger move — it does not call a side.", "body"),
    ]

    colours = {
        "head": C.ACCENT,
        "body": C.FG,
        "good": C.UP,
        "bad": C.DOWN,
        "warn": C.WARN,
        "gap": C.FG,
    }
    y = 0.998
    for text, kind in lines:
        if kind == "gap":
            y -= 0.013
            continue
        weight = "bold" if kind == "head" else "normal"
        size = 9.2 if kind == "head" else 8.6
        ax_txt.text(
            0.0,
            y,
            text,
            color=colours[kind],
            fontsize=size,
            fontweight=weight,
            va="top",
            ha="left",
            transform=ax_txt.transAxes,
            **MONO,
        )
        if kind == "head":
            y -= 0.005
            ax_txt.plot(
                [0.0, 0.92], [y, y], color=C.GRID, lw=1.0, transform=ax_txt.transAxes, clip_on=False
            )
        y -= 0.0238

    fig.text(
        0.008,
        0.028,
        f"Data: {prov.exchange} {prov.market} daily, {prov.first_ts[:10]} .. {prov.last_ts[:10]}"
        f"   ·   volume profile from 5m bars since {PROFILE_START}\n"
        "Exchange APIs are egress-blocked and the mirror returned a byte-identical file on "
        "re-fetch — no XRP data past 2026-07-25 exists in this environment.",
        color=C.MUTED,
        fontsize=8,
        va="bottom",
        **MONO,
    )

    out = out or (OUT / "xrp-trade-review.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=C.BG, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> int:
    path = trade_chart()
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

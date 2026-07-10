"""Bloomberg-terminal style ETH/USD 1H chart of @MizerXBT's short-trade thesis.

Renders July 7-10 2026 hourly candles with the trade's levels overlaid:
short entry $1,745, stop $1,840, the $1,800-$1,848 rejection zone, TP1 $1,650,
TP3/support $1,508, plus a projected-downside path and a volume subpanel.

Live exchange feeds (coinbase/yahoo) are blocked by this sandbox's egress
policy, so the candle series is deterministic synthetic data (seed 7, matching
``AlphaSettings.random_seed``) calibrated to the real market structure of that
window: repeated rejections at the $1,800 wall and a last price near $1,782.
The chart footer discloses this.

Run: ``uv run python research/charts/mizerxbt_eth_short_1h.py``
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import matplotlib.dates  # noqa: F401  (register date converters)
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.legend_handler import HandlerTuple
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch
from matplotlib.ticker import FuncFormatter, MultipleLocator

# ---------------------------------------------------------------- palette ---
BG = "#070b14"  # figure background: deep navy-black
SURFACE = "#0d1220"  # axes background
GRID = "#232c42"  # crisp but recessive grid
INK = "#e8ecf5"  # primary text
INK_MUTED = "#8b95ab"  # secondary text
UP = "#26d07c"  # candle up
DOWN = "#f6465d"  # candle down
ENTRY = "#ffa63d"  # orange dashed - short entry
STOP = "#ff4d5e"  # thick red solid - stop loss
ZONE = "#b18cff"  # purple dotted - resistance zone
TP1 = "#00e07f"  # bright green solid - TP1
TP3 = "#35d6e8"  # cyan dashed - TP3 / support
PROJ = "#4da3ff"  # blue projected path

ENTRY_PX = 1745.0
STOP_PX = 1840.0
ZONE_LO, ZONE_HI = 1800.0, 1848.0
TP1_PX = 1650.0
TP3_PX = 1508.0
LAST_PX = 1782.4  # calibration target for the final close (~$1,782)

OUT = Path(__file__).with_suffix(".png")


@dataclass(frozen=True)
class Series:
    """Hourly OHLCV arrays plus their timestamps."""

    ts: list[datetime]
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray


def synthetic_eth_1h(seed: int = 7) -> Series:
    """Deterministic 1H ETH/USD series for 2026-07-07 00:00 -> 2026-07-10 09:00 UTC.

    Shape: grind up into the $1,800-$1,815 wall on Jul 7, a second exhaustion
    push and fade on Jul 8, choppy lower-high drift on Jul 9, and a settle
    near $1,782 into Jul 10 - mirroring the repeated-rejection structure the
    July 2026 coverage describes.
    """
    start = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)
    n = 82  # hourly bars through 2026-07-10 09:00
    ts = [start + timedelta(hours=i) for i in range(n)]

    # Piecewise anchor path (hour index -> close), interpolated then perturbed.
    anchors_x = np.array([0, 6, 12, 15, 18, 24, 30, 36, 39, 44, 48, 55, 60, 66, 72, 76, 81])
    anchors_y = np.array(
        [
            1742.0,  # Jul 7 00:00 - base
            1758.0,
            1779.0,
            1798.0,  # first test of the wall
            1806.0,  # Jul 7 18:00 - rejection wick zone
            1784.0,  # fade off the zone
            1771.0,
            1792.0,  # Jul 8 12:00 - second push
            1809.0,  # exhaustion high print
            1780.0,  # passive selling fades it again
            1764.0,
            1757.0,  # Jul 9 07:00 - range low area
            1774.0,
            1768.0,
            1761.0,  # Jul 10 00:00
            1776.0,
            LAST_PX,  # settle ~$1,782
        ]
    )
    base = np.interp(np.arange(n), anchors_x, anchors_y)

    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, 3.1, n).cumsum() * 0.16
    close = base + noise - noise[-1]  # pin the final close to LAST_PX exactly
    open_ = np.empty(n)
    open_[0] = close[0] - 2.0
    open_[1:] = close[:-1]

    body_hi = np.maximum(open_, close)
    body_lo = np.minimum(open_, close)
    wick_up = np.abs(rng.normal(0.0, 2.6, n)) + 0.6
    wick_dn = np.abs(rng.normal(0.0, 2.6, n)) + 0.6
    # Exaggerate upper wicks while price is pressing the rejection zone.
    in_zone = body_hi > ZONE_LO - 12.0
    wick_up[in_zone] *= 2.4
    high = body_hi + wick_up
    low = body_lo - wick_dn

    rel_range = (high - low) / np.mean(high - low)
    volume = 8200.0 * rel_range * rng.uniform(0.65, 1.45, n)
    volume[in_zone] *= 1.5  # sell-side participation on the rejection pushes

    for arr in (open_, high, low, close, volume):
        if not np.all(np.isfinite(arr)):
            raise ValueError("synthetic series produced non-finite values")
    return Series(ts, open_, high, low, close, volume)


def _level(
    ax: plt.Axes, y: float, color: str, ls: str, lw: float, label: str, *, below: bool = False
) -> Line2D:
    line = ax.axhline(y, color=color, linestyle=ls, linewidth=lw, alpha=0.95, zorder=3)
    ax.annotate(
        f"{label}  ${y:,.0f}",
        xy=(1.0, y),
        xycoords=("axes fraction", "data"),
        xytext=(-8, -7 if below else 5),
        textcoords="offset points",
        ha="right",
        va="top" if below else "bottom",
        fontsize=8.5,
        fontweight="bold",
        color=color,
        family="DejaVu Sans Mono",
        zorder=6,
    )
    return line


def render(series: Series) -> Path:
    n = len(series.ts)
    x = np.arange(n)
    up_mask = series.close >= series.open

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "text.color": INK,
            "axes.edgecolor": GRID,
            "xtick.color": INK_MUTED,
            "ytick.color": INK_MUTED,
        }
    )
    fig, (ax, axv) = plt.subplots(
        2,
        1,
        figsize=(16, 9),
        dpi=300,
        sharex=True,
        gridspec_kw={"height_ratios": [4.0, 1.0], "hspace": 0.04},
    )
    fig.patch.set_facecolor(BG)
    proj_slots = 20  # empty slots to the right for the projected path
    for a in (ax, axv):
        a.set_facecolor(SURFACE)
        a.grid(True, color=GRID, linewidth=0.55, alpha=0.55)
        a.set_axisbelow(True)
        for spine in a.spines.values():
            spine.set_color(GRID)
        a.set_xlim(-1.5, n - 0.5 + proj_slots)

    # ------------------------------------------------------------ candles ---
    colors = np.where(up_mask, UP, DOWN)
    ax.vlines(x, series.low, series.high, color=colors, linewidth=0.9, zorder=4)
    ax.bar(
        x,
        np.abs(series.close - series.open),
        bottom=np.minimum(series.open, series.close),
        width=0.62,
        color=colors,
        edgecolor=colors,
        linewidth=0.4,
        zorder=5,
    )

    # ------------------------------------------------------------- levels ---
    zone = ax.axhspan(ZONE_LO, ZONE_HI, facecolor=ZONE, alpha=0.10, zorder=1)
    for yy in (ZONE_LO, ZONE_HI):
        ax.axhline(yy, color=ZONE, linestyle=(0, (2, 3)), linewidth=1.4, alpha=0.9, zorder=3)
    ax.annotate(
        f"MizerXBT Key Resistance / Rejection Zone  \\${ZONE_LO:,.0f} – \\${ZONE_HI:,.0f}",
        xy=(0.012, (ZONE_HI + ZONE_LO) / 2.0),
        xycoords=("axes fraction", "data"),
        ha="left",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        color=ZONE,
        zorder=6,
    )
    entry_ln = _level(ax, ENTRY_PX, ENTRY, (0, (6, 4)), 1.6, "USER SHORT ENTRY")
    stop_ln = _level(ax, STOP_PX, STOP, "-", 3.0, "USER STOP LOSS", below=True)
    tp1_ln = _level(ax, TP1_PX, TP1, "-", 1.8, "TP1")
    tp3_ln = _level(ax, TP3_PX, TP3, (0, (6, 4)), 1.8, "MAJOR TP3 / SUPPORT")

    # ----------------------------------------------------- projected path ---
    last = float(series.close[-1])
    px0, px3 = float(n - 1), float(n - 1 + proj_slots - 1.5)
    p0, p1 = np.array([px0, last]), np.array([px0 + 6.5, last + 6.0])
    p2, p3 = np.array([px3 - 7.5, TP1_PX + 8.0]), np.array([px3, TP3_PX + 14.0])
    t = np.linspace(0.0, 1.0, 90)[:, None]
    bez = ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3 * p3
    ax.plot(bez[:-4, 0], bez[:-4, 1], color=PROJ, linewidth=2.6, alpha=0.95, zorder=6)
    ax.plot(bez[:-4, 0], bez[:-4, 1], color=PROJ, linewidth=7.0, alpha=0.14, zorder=5)
    arrow = FancyArrowPatch(
        tuple(bez[-5]),
        tuple(p3),
        arrowstyle="-|>",
        mutation_scale=26,
        color=PROJ,
        linewidth=2.6,
        zorder=7,
    )
    ax.add_patch(arrow)
    ax.annotate(
        "MizerXBT Projected Downside\n(Lower $ETH)",
        xy=(px0 + proj_slots * 0.52, (last + TP1_PX) / 2.0 - 14.0),
        ha="center",
        va="top",
        fontsize=9.5,
        fontweight="bold",
        color=PROJ,
        zorder=7,
    )
    ax.plot(
        [n - 1],
        [last],
        marker="o",
        markersize=7,
        markerfacecolor=BG,
        markeredgecolor=PROJ,
        markeredgewidth=1.8,
        zorder=8,
    )
    ax.annotate(
        f"LAST ${last:,.1f}",
        xy=(n - 1, last),
        xytext=(12, -20),
        textcoords="offset points",
        fontsize=9,
        fontweight="bold",
        color=INK,
        family="DejaVu Sans Mono",
        zorder=8,
    )

    # ------------------------------------------------------------- volume ---
    axv.bar(x, series.volume, width=0.62, color=colors, alpha=0.55, zorder=3)
    axv.set_ylabel("VOLUME", fontsize=8, color=INK_MUTED, labelpad=8)
    axv.set_ylim(0, series.volume.max() * 1.25)
    axv.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:,.0f}K"))
    axv.tick_params(labelsize=8)

    # --------------------------------------------------------------- axes ---
    ax.set_ylim(1470, 1875)
    ax.yaxis.set_major_locator(MultipleLocator(50))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.tick_params(labelsize=9)
    for a in (ax, axv):
        a.tick_params(axis="y", which="both", length=0)
    tick_ix = [i for i in range(n) if series.ts[i].hour % 12 == 0]
    axv.set_xticks(tick_ix)
    axv.set_xticklabels(
        [series.ts[i].strftime("%b %d\n%H:%M") for i in tick_ix],
        fontsize=8,
        family="DejaVu Sans Mono",
    )

    # ------------------------------------------------------ title / legend ---
    fig.suptitle(
        "ETH Short Trade - MizerXBT Thesis  |  Current ~$1,782  |  Patient LTF Setup",
        x=0.065,
        y=0.975,
        ha="left",
        fontsize=16,
        fontweight="bold",
        color=INK,
    )
    fig.text(
        0.065,
        0.938,
        "Following @MizerXBT: Expecting Lower Prices on Resistance Rejection"
        "  |  Holding with Patience",
        ha="left",
        fontsize=10.5,
        color=INK_MUTED,
    )
    fig.text(
        0.935,
        0.975,
        "ETH-USD · 1H",
        ha="right",
        va="top",
        fontsize=11,
        fontweight="bold",
        color=INK_MUTED,
        family="DejaVu Sans Mono",
    )
    proj_handle = Line2D([], [], color=PROJ, linewidth=2.6)
    candle_handle = (
        Line2D([], [], color=UP, linewidth=5),
        Line2D([], [], color=DOWN, linewidth=5),
    )
    legend = ax.legend(
        handles=[candle_handle, entry_ln, stop_ln, zone, tp1_ln, tp3_ln, proj_handle],
        labels=[
            "1H candles (up / down)",
            f"Short Entry ${ENTRY_PX:,.0f}",
            f"Stop Loss ${STOP_PX:,.0f}",
            f"Resistance / Rejection Zone \\${ZONE_LO:,.0f}–\\${ZONE_HI:,.0f}",
            f"TP1 ${TP1_PX:,.0f}",
            f"TP3 / Support ${TP3_PX:,.0f}",
            "Projected Downside Path",
        ],
        handler_map={tuple: HandlerTuple(ndivide=None, pad=0.3)},
        loc="lower left",
        fontsize=8.5,
        framealpha=0.92,
        facecolor="#101728",
        edgecolor=GRID,
        labelcolor=INK,
        borderpad=0.9,
        handlelength=2.6,
    )
    legend.set_zorder(10)
    fig.text(
        0.935,
        0.012,
        "Deterministic synthetic 1H series (seed 7), calibrated to Jul 7-10 2026 market"
        " structure - live exchange feeds unavailable in sandbox. Not financial advice.",
        ha="right",
        fontsize=7,
        color=INK_MUTED,
        style="italic",
    )

    fig.subplots_adjust(left=0.065, right=0.935, top=0.90, bottom=0.075)
    fig.savefig(OUT, facecolor=BG, dpi=300)
    plt.close(fig)
    return OUT


def main() -> None:
    out = render(synthetic_eth_1h())
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

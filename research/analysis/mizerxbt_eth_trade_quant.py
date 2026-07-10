"""Quant analysis of the user's live ETH short (MizerXBT thesis) — first-passage Monte Carlo.

Position parameters come from the user's exchange screenshot (2026-07-10): ETHUSDT perp short,
isolated 16x, entry $1,745.02, mark $1,797.38, ~68.05 ETH notional, liq $1,844.86, exchange
TP/SL $1,642.55/$1,840. Live feeds are egress-blocked, so hourly volatility is a scenario grid
(daily 2.5%/3.5%/4.5%) rather than fitted; drift is a bear/neutral/bull scenario axis.

Reuses ``alpha_validation.montecarlo.student_t_paths`` (fat-tailed, df=4) for the path engine and
``garch_paths`` as a clustering robustness check. Deterministic: master seed 7, child seeds via
``np.random.SeedSequence.spawn`` (repo convention).

Outputs: a JSON summary on stdout and a 4-panel dark-terminal dashboard PNG next to this file.

Run: ``uv run python research/analysis/mizerxbt_eth_trade_quant.py``
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

from alpha_validation.montecarlo import garch_paths, student_t_paths

# ------------------------------------------------------------- position ---
ENTRY = 1745.02
MARK = 1797.38
NOTIONAL = 122_311.709  # USDT, at mark
QTY = NOTIONAL / MARK  # ~68.05 ETH
UPNL = -3_562.83
MARGIN = abs(UPNL) / 0.4756  # screenshot: uPnL = -47.56% of margin
LIQ = 1844.86
SL = 1840.0
TP_EXCH = 1642.55
TP1 = 1650.0
TP3 = 1508.0
FUNDING_8H = 0.0001  # |0.01%| per 8h scenario magnitude, on notional

MASTER_SEED = 7
N_PATHS = 10_000
T_DF = 4.0
HORIZONS = {"24h": 24, "72h": 72, "168h": 168}
DAILY_VOLS = {"low": 0.025, "mid": 0.035, "high": 0.045}
# hourly log drift: bear = thesis right (drift to ~$1,650 in a week), bull = breakout to ~$1,900
DRIFTS = {
    "bear": float(np.log(TP1 / MARK) / 168.0),
    "neutral": 0.0,
    "bull": float(np.log(1900.0 / MARK) / 168.0),
}

OUT_PNG = Path(__file__).with_suffix(".png")

BG = "#070b14"
SURFACE = "#0d1220"
GRID = "#232c42"
INK = "#e8ecf5"
INK_MUTED = "#8b95ab"
RED = "#ff4d5e"
GREEN = "#00e07f"
ORANGE = "#ffa63d"
CYAN = "#35d6e8"
BLUE = "#4da3ff"
PURPLE = "#b18cff"


def pnl_at(price: float | np.ndarray) -> float | np.ndarray:
    """Short PnL in USDT at ``price`` (0 at entry, negative above entry)."""
    return (ENTRY - price) * QTY


def _calibrated_sample(mu_h: float, sigma_h: float, rng: np.random.Generator) -> np.ndarray:
    """A synthetic hourly log-return sample with mean exactly ``mu_h`` and sd ``sigma_h``.

    ``student_t_paths``/``garch_paths`` match the *sample* mean and variance, so standardizing the
    draw pins the generators to the scenario parameters exactly.
    """
    z = rng.standard_normal(512)
    z = (z - z.mean()) / z.std(ddof=1)
    return mu_h + sigma_h * z


@dataclass(frozen=True)
class Cell:
    """First-passage results for one (drift, vol, horizon) scenario cell."""

    p_tp_first: float  # exchange TP $1,642.55 touched before SL
    p_sl_first: float  # SL $1,840 touched before TP
    p_gap_liq: float  # of ALL paths: SL crossed with the step landing >= liq $1,844.86
    p_neither: float
    p_touch_tp1: float  # $1,650 touched at any point (either-order)
    p_touch_tp3: float  # $1,508 touched at any point
    ev_usdt: float  # expected PnL vs. holding to barrier/horizon (funding excluded)


def first_passage(prices: np.ndarray) -> Cell:
    """Classify each path: exchange TP first, SL first (incl. liq gap-through), or neither.

    ``prices``: (n_paths, hours) hourly closes. Barrier checks are on hourly closes — a
    conservative under-count of intra-hour wick touches on both sides.
    """
    n, h = prices.shape
    hit_sl = prices >= SL
    hit_tp = prices <= TP_EXCH
    t_sl = np.where(hit_sl.any(axis=1), hit_sl.argmax(axis=1), h)
    t_tp = np.where(hit_tp.any(axis=1), hit_tp.argmax(axis=1), h)

    sl_first = t_sl < t_tp
    tp_first = t_tp < t_sl  # h < h is False, so "neither" stays out of both
    neither = ~sl_first & ~tp_first
    # gap-through proxy: the hourly step that crosses the stop lands at/beyond the liq price
    gap = sl_first & (prices[np.arange(n), np.minimum(t_sl, h - 1)] >= LIQ)

    pnl_sl = float(pnl_at(SL))
    pnl_liq = -MARGIN  # isolated-margin wipe
    pnl_tp = float(pnl_at(TP_EXCH))
    end_pnl = np.asarray(pnl_at(prices[:, -1]), dtype=np.float64)
    ev = (
        float(np.sum(gap)) * pnl_liq
        + float(np.sum(sl_first & ~gap)) * pnl_sl
        + float(np.sum(tp_first)) * pnl_tp
        + float(end_pnl[neither].sum())
    ) / n

    cell = Cell(
        p_tp_first=float(tp_first.mean()),
        p_sl_first=float(sl_first.mean()),
        p_gap_liq=float(gap.mean()),
        p_neither=float(neither.mean()),
        p_touch_tp1=float((prices <= TP1).any(axis=1).mean()),
        p_touch_tp3=float((prices <= TP3).any(axis=1).mean()),
        ev_usdt=ev,
    )
    total = cell.p_tp_first + cell.p_sl_first + cell.p_neither
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"first-passage probabilities must sum to 1, got {total}")
    return cell


def simulate(mu_h: float, sigma_h: float, hours: int, seed: np.random.SeedSequence) -> np.ndarray:
    """(N_PATHS, hours) price paths from MARK via fat-tailed i.i.d. hourly log returns."""
    s_sample, s_paths = seed.spawn(2)
    sample = _calibrated_sample(mu_h, sigma_h, np.random.default_rng(s_sample))
    rets = student_t_paths(sample, n_paths=N_PATHS, df=T_DF, seed=int(s_paths.generate_state(1)[0]))
    return MARK * np.exp(np.cumsum(rets[:, :hours], axis=1))


def garch_check(mu_h: float, sigma_h: float, hours: int, seed: np.random.SeedSequence) -> Cell:
    """Same cell computed with GARCH(1,1) clustering — robustness, not the headline number."""
    s_sample, s_paths = seed.spawn(2)
    sample = _calibrated_sample(mu_h, sigma_h, np.random.default_rng(s_sample))
    rets = garch_paths(sample, n_paths=N_PATHS, df=T_DF, seed=int(s_paths.generate_state(1)[0]))[
        :, :hours
    ]
    return first_passage(MARK * np.exp(np.cumsum(rets, axis=1)))


def sanity_checks() -> None:
    """Fail loud if the position math disagrees with the screenshot."""
    if abs(float(pnl_at(MARK)) - UPNL) > 5.0:
        raise ValueError(f"uPnL mismatch: {pnl_at(MARK):.2f} vs screenshot {UPNL}")
    pct = float(pnl_at(MARK)) / MARGIN
    if abs(pct - (-0.4756)) > 0.005:
        raise ValueError(f"margin-% mismatch: {pct:.4f} vs -0.4756")
    if not (SL < LIQ < ENTRY + MARGIN / QTY):
        raise ValueError("expected SL < liq < margin-exhaustion price ordering")


# ---------------------------------------------------------------- charts ---
def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.55, alpha=0.55)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=8)


def _panel_pnl(ax: plt.Axes) -> None:
    px = np.linspace(1480, 1880, 400)
    pnl = np.asarray(pnl_at(px))
    pnl_liq = np.where(px >= LIQ, -MARGIN, pnl)  # isolated margin caps the loss at liquidation
    ax.plot(px, pnl_liq / 1000.0, color=BLUE, linewidth=2.2, zorder=5)
    ax.axhline(0, color=INK_MUTED, linewidth=0.8, alpha=0.6)
    ax.axhspan(-MARGIN / 1000.0, (pnl_liq.min()) / 1000.0 - 0.4, color=RED, alpha=0.08)
    for x_, c, name in (
        (TP3, CYAN, "TP3 1,508"),
        (TP_EXCH, GREEN, "TP 1,642.5"),
        (ENTRY, ORANGE, "entry 1,745"),
        (MARK, INK, "mark 1,797"),
        (SL, RED, "SL 1,840"),
    ):
        ax.axvline(x_, color=c, linewidth=1.1, linestyle=(0, (4, 3)), alpha=0.85)
        y_frac = 0.97 if x_ != MARK else 0.80
        ax.annotate(
            f"{name}\n{float(pnl_at(x_)) / 1000.0:+.1f}k",
            xy=(x_, 1),
            xycoords=("data", "axes fraction"),
            xytext=(0, -6 - (0 if x_ != MARK else 34)),
            textcoords="offset points",
            ha="center",
            va="top",
            fontsize=7.2,
            color=c,
            fontweight="bold",
        )
        del y_frac
    ax.axvline(LIQ, color=RED, linewidth=2.6, alpha=0.95)
    ax.annotate(
        f"LIQ 1,844.9 = -100% margin (-${MARGIN / 1000.0:.1f}k)\nonly $4.86 above the SL",
        xy=(LIQ, -MARGIN / 1000.0),
        xytext=(-8, 26),
        textcoords="offset points",
        ha="right",
        fontsize=7.8,
        color=RED,
        fontweight="bold",
    )
    ax.set_title("Position PnL vs price (68.05 ETH short @ 16x isolated)", color=INK, fontsize=10)
    ax.set_xlabel("ETH price", color=INK_MUTED, fontsize=8)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}k"))


def _panel_fan(ax: plt.Axes, neutral: np.ndarray, bear: np.ndarray) -> None:
    hours = neutral.shape[1]
    t = np.arange(1, hours + 1)
    for lo, hi, a in ((10, 90, 0.13), (25, 75, 0.22)):
        band = np.percentile(neutral, [lo, hi], axis=0)
        ax.fill_between(t, band[0], band[1], color=BLUE, alpha=a, linewidth=0)
    ax.plot(t, np.median(neutral, axis=0), color=BLUE, linewidth=1.8, label="neutral median")
    ax.plot(
        t,
        np.median(bear, axis=0),
        color=GREEN,
        linewidth=1.8,
        linestyle=(0, (5, 3)),
        label="bear-thesis median",
    )
    for y_, c, lbl in ((SL, RED, "SL 1,840"), (LIQ, RED, ""), (TP_EXCH, GREEN, "TP 1,642.5")):
        ax.axhline(y_, color=c, linewidth=1.4 if y_ != LIQ else 2.2, alpha=0.9)
        if lbl:
            ax.annotate(
                lbl,
                xy=(1.0, y_),
                xycoords=("axes fraction", "data"),
                xytext=(-4, 3),
                textcoords="offset points",
                ha="right",
                fontsize=7.5,
                color=c,
                fontweight="bold",
            )
    ax.set_title(
        "7-day Monte Carlo fan from $1,797.38 (mid vol, fat-tailed t, 10k paths)",
        color=INK,
        fontsize=10,
    )
    ax.set_xlabel("hours ahead", color=INK_MUTED, fontsize=8)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.legend(loc="lower left", fontsize=7.5, facecolor="#101728", edgecolor=GRID, labelcolor=INK)


def _panel_probs(ax: plt.Axes, cells: dict[str, dict[str, Cell]]) -> None:
    drifts = list(DRIFTS)
    horizons = list(HORIZONS)
    width = 0.26
    xbase = np.arange(len(horizons))
    series = [("TP first", GREEN), ("SL first", RED), ("neither", INK_MUTED)]
    for di, drift in enumerate(drifts):
        vals = {
            "TP first": [cells[drift][h].p_tp_first for h in horizons],
            "SL first": [cells[drift][h].p_sl_first for h in horizons],
            "neither": [cells[drift][h].p_neither for h in horizons],
        }
        bottom = np.zeros(len(horizons))
        for name, color in series:
            v = np.array(vals[name])
            ax.bar(
                xbase + (di - 1) * width,
                v,
                width * 0.9,
                bottom=bottom,
                color=color,
                alpha=0.9 if name != "neither" else 0.45,
                edgecolor=SURFACE,
                linewidth=0.8,
            )
            bottom += v
        for xi in range(len(horizons)):
            ax.annotate(
                drift,
                xy=(xbase[xi] + (di - 1) * width, 1.015),
                ha="center",
                fontsize=6.4,
                color=INK_MUTED,
                rotation=0,
            )
    ax.set_xticks(xbase)
    ax.set_xticklabels(horizons, fontsize=8.5)
    ax.set_ylim(0, 1.30)
    ax.set_yticks(np.arange(0.0, 1.01, 0.25))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=c, alpha=a)
        for _, c, a in [("TP", GREEN, 0.9), ("SL", RED, 0.9), ("n", INK_MUTED, 0.45)]
    ]
    ax.legend(
        handles,
        ["TP $1,642.5 first", "SL $1,840 first", "neither (still open)"],
        loc="upper center",
        ncols=3,
        fontsize=7.5,
        facecolor="#101728",
        edgecolor=GRID,
        labelcolor=INK,
    )
    ax.set_title("First-passage odds by drift scenario × horizon (mid vol)", color=INK, fontsize=10)


def _panel_watch(ax: plt.Axes, mid: dict[str, dict[str, Cell]]) -> None:
    ax.axis("off")
    n168 = mid["neutral"]["168h"]
    b168 = mid["bear"]["168h"]
    lines = [
        ("STRUCTURAL RED FLAG", RED),
        ("  SL $1,840 is only $4.86 under liq $1,844.86 - a wick+slippage through the", INK),
        ("  $1,840 ask wall (8.3k ETH) can liquidate (-100% margin) before the stop fills.", INK),
        ("", INK),
        ("INVALIDATION (thesis dead - MizerXBT's own rule: close on invalidation)", ORANGE),
        ("  - 1H/4H acceptance ABOVE $1,800-$1,810 (26.8k-ETH ask wall at $1,810 breaking)", INK),
        ("  - 4H close above $1,848 (zone top) => stop is already too late at $1,840", INK),
        ("  - funding flips decisively positive + bid skew >60% (squeeze fuel)", INK),
        ("", INK),
        ("CONFIRMATION (thesis working)", GREEN),
        ("  - rejection wicks off $1,800-$1,810 + reclaim of $1,782 then $1,745 (entry)", INK),
        ("  - sell-side taker flow returning; BTC stalling (chop regime persists)", INK),
        ("", INK),
        ("ODDS AT 7 DAYS (mid vol)", BLUE),
        (
            f"  neutral drift: TP first {n168.p_tp_first:.0%} | SL first {n168.p_sl_first:.0%}"
            f" (liq gap-through {n168.p_gap_liq:.0%}) | EV {n168.ev_usdt / 1000.0:+.1f}k",
            INK,
        ),
        (
            f"  bear (thesis): TP first {b168.p_tp_first:.0%} | SL first {b168.p_sl_first:.0%}"
            f" (liq gap-through {b168.p_gap_liq:.0%}) | EV {b168.ev_usdt / 1000.0:+.1f}k",
            INK,
        ),
        ("", INK),
        (
            f"  funding carry magnitude ~${NOTIONAL * FUNDING_8H * 3:.0f}/day on $122k notional",
            INK_MUTED,
        ),
        ("  Not financial advice - scenario math from screenshot parameters, seed 7.", INK_MUTED),
    ]
    y = 0.98
    for text, color in lines:
        ax.text(
            0.01,
            y,
            text.replace("$", r"\$"),  # keep matplotlib from parsing $...$ as mathtext
            color=color,
            fontsize=8.2,
            family="DejaVu Sans Mono",
            va="top",
            transform=ax.transAxes,
        )
        y -= 0.052
    ax.set_title("What to watch / decision triggers", color=INK, fontsize=10)


def render(cells: dict[str, dict[str, Cell]], neutral: np.ndarray, bear: np.ndarray) -> Path:
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})
    fig, axes = plt.subplots(2, 2, figsize=(16, 9), dpi=300)
    fig.patch.set_facecolor(BG)
    for ax in axes.flat:
        _style(ax)
    _panel_pnl(axes[0][0])
    _panel_fan(axes[0][1], neutral, bear)
    _panel_probs(axes[1][0], cells)
    _panel_watch(axes[1][1], cells)
    fig.suptitle(
        "ETH Short @ 16x - Risk Dashboard  |  entry $1,745.02 · mark $1,797.38 ·"
        " liq $1,844.86  |  MizerXBT thesis",
        x=0.5,
        y=0.985,
        fontsize=14,
        fontweight="bold",
        color=INK,
    )
    fig.text(
        0.5,
        0.955,
        "First-passage Monte Carlo (student-t df=4, 10k paths/cell, seed 7) -"
        " vol scenario grid, live feeds egress-blocked",
        ha="center",
        fontsize=9,
        color=INK_MUTED,
    )
    fig.subplots_adjust(left=0.055, right=0.975, top=0.90, bottom=0.06, hspace=0.34, wspace=0.18)
    fig.savefig(OUT_PNG, facecolor=BG, dpi=300)
    plt.close(fig)
    return OUT_PNG


def main() -> None:
    sanity_checks()
    sigma_mid = DAILY_VOLS["mid"] / np.sqrt(24.0)
    root = np.random.SeedSequence(MASTER_SEED)
    seeds = iter(root.spawn(64))

    cells: dict[str, dict[str, Cell]] = {}
    vol_sensitivity: dict[str, dict[str, float]] = {}
    for drift_name, mu in DRIFTS.items():
        cells[drift_name] = {}
        paths_168 = simulate(mu, sigma_mid, 168, next(seeds))
        for hname, hours in HORIZONS.items():
            cells[drift_name][hname] = first_passage(paths_168[:, :hours])
    for vol_name, dv in DAILY_VOLS.items():
        sig = dv / np.sqrt(24.0)
        cell = first_passage(simulate(DRIFTS["neutral"], sig, 168, next(seeds)))
        vol_sensitivity[vol_name] = {"p_sl_first": cell.p_sl_first, "p_tp_first": cell.p_tp_first}
    garch_cell = garch_check(DRIFTS["neutral"], sigma_mid, 168, next(seeds))

    neutral_fan = simulate(DRIFTS["neutral"], sigma_mid, 168, next(seeds))
    bear_fan = simulate(DRIFTS["bear"], sigma_mid, 168, next(seeds))
    out = render(cells, neutral_fan, bear_fan)

    summary = {
        "position": {
            "qty_eth": round(QTY, 2),
            "margin_usdt": round(MARGIN, 2),
            "pnl_at_sl": round(float(pnl_at(SL)), 2),
            "pnl_at_sl_pct_margin": round(float(pnl_at(SL)) / MARGIN, 4),
            "pnl_at_liq": round(-MARGIN, 2),
            "pnl_at_tp": round(float(pnl_at(TP_EXCH)), 2),
            "pnl_at_tp3": round(float(pnl_at(TP3)), 2),
            "rr_from_mark_sl_vs_tp": round((MARK - TP_EXCH) / (SL - MARK), 2),
            "sl_liq_gap_usd": round(LIQ - SL, 2),
            "margin_exhaustion_price": round(ENTRY + MARGIN / QTY, 2),
        },
        "cells": {d: {h: vars(c) for h, c in per.items()} for d, per in cells.items()},
        "vol_sensitivity_neutral_168h": vol_sensitivity,
        "garch_robustness_neutral_168h": vars(garch_cell),
        "funding_carry_per_day_usdt": round(NOTIONAL * FUNDING_8H * 3, 2),
        "png": str(out),
    }
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

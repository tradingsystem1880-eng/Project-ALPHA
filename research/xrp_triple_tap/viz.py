"""Dark-theme annotated charts in the user's standard deliverable format.

Palette is the requested GitHub-dark (`#0d1117` background, `#c9d1d9` text) rather than the navy
used by the earlier `research/analysis` scripts — the brief specified it explicitly.

Three figures:
- :func:`setup_chart` — the live XRP situation: taps, trendline, order blocks, entry/stop/target,
  a volume-profile sidebar and a monospace metrics block.
- :func:`evidence_chart` — what the study found: barrier grid against breakeven, edge-vs-control
  intervals, walk-forward, and the sweep distribution.
- :func:`gallery_chart` — the 20 most recent detected instances with their forward outcome, so the
  detector can be eyeballed rather than trusted.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from alpha_patterns import OHLCV, TripleTap
from research.xrp_triple_tap import config as C

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

MONO = {"family": "DejaVu Sans Mono"}


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(C.PANEL)
    ax.grid(True, color=C.GRID, lw=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_color(C.GRID)


def _candles(ax: plt.Axes, bars: OHLCV, lo: int, hi: int, width: float = 0.7) -> None:
    x = np.arange(lo, hi)
    up = bars.close[lo:hi] >= bars.open[lo:hi]
    ax.vlines(x, bars.low[lo:hi], bars.high[lo:hi], color=np.where(up, C.UP, C.DOWN), lw=0.6)
    ax.bar(
        x,
        np.abs(bars.close[lo:hi] - bars.open[lo:hi]),
        bottom=np.minimum(bars.open[lo:hi], bars.close[lo:hi]),
        width=width,
        color=np.where(up, C.UP, C.DOWN),
        linewidth=0,
    )


def _volume_profile(ax: plt.Axes, bars: OHLCV, lo: int, hi: int, bins: int = 60) -> float:
    """Horizontal volume-by-price sidebar; returns the point of control."""
    prices = (bars.high[lo:hi] + bars.low[lo:hi] + bars.close[lo:hi]) / 3.0
    hist, edges = np.histogram(prices, bins=bins, weights=bars.volume[lo:hi])
    centres = (edges[:-1] + edges[1:]) / 2.0
    poc = float(centres[int(np.argmax(hist))])
    ax.barh(centres, hist, height=(edges[1] - edges[0]) * 0.9, color=C.ACCENT, alpha=0.35)
    ax.axhline(poc, color=C.WARN, lw=1.2, ls="--")
    _style(ax)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("vol", fontsize=7, color=C.MUTED)
    return poc


def setup_chart(
    bars: OHLCV,
    events: list[TripleTap],
    metrics: list[str],
    out: Path,
    *,
    lookback_bars: int = 720,
) -> Path:
    """The live setup with every marked structure and a metrics block."""
    n = len(bars)
    lo, hi = max(0, n - lookback_bars), n

    fig = plt.figure(figsize=(17, 9.5))
    fig.patch.set_facecolor(C.BG)
    gs = fig.add_gridspec(
        2,
        3,
        width_ratios=[6.2, 0.85, 2.6],
        height_ratios=[3.4, 1.0],
        hspace=0.10,
        wspace=0.06,
        left=0.05,
        right=0.985,
        top=0.915,
        bottom=0.075,
    )
    ax = fig.add_subplot(gs[0, 0])
    axv = fig.add_subplot(gs[0, 1], sharey=ax)
    axm = fig.add_subplot(gs[:, 2])
    axb = fig.add_subplot(gs[1, 0], sharex=ax)

    _candles(ax, bars, lo, hi)
    _style(ax)
    poc = _volume_profile(axv, bars, lo, hi)

    for lvl, col, lab in (
        (C.ENTRY, C.ACCENT, f"entry {C.ENTRY:.4f}"),
        (C.STOP, C.DOWN, f"stop {C.STOP:.4f}  (-5.79%)"),
    ):
        ax.axhline(lvl, color=col, lw=1.3, ls="--")
        ax.text(lo + 4, lvl, f" {lab}", color=col, fontsize=8.5, va="bottom", **MONO)
    ax.axhline(poc, color=C.WARN, lw=1.0, ls=":")
    ax.text(lo + 4, poc, f" 90d POC {poc:.4f}", color=C.WARN, fontsize=8, va="bottom", **MONO)

    shown = [e for e in events if e.tap_indices[2] >= lo]
    for e in shown[-4:]:
        for t in e.tap_indices:
            if t >= lo:
                ax.plot(t, bars.low[t], marker="^", color=C.UP, ms=9, zorder=5)
        ax.axhline(e.level, color=C.UP, lw=0.8, alpha=0.45)

    ax.set_title(
        f"XRP 4H — triple-tap zone, live long  |  data to {C.DATA_ENDS[:10]}  "
        f"(target {C.TARGET:.4f} = +{(C.TARGET / C.ENTRY - 1) * 100:.0f}% is off-scale)",
        color=C.FG,
        fontsize=11.5,
        loc="left",
        pad=10,
    )
    ax.set_ylabel("XRPUSDT perp", fontsize=9)
    ax.tick_params(labelbottom=False)

    up = bars.close[lo:hi] >= bars.open[lo:hi]
    axb.bar(
        np.arange(lo, hi),
        bars.volume[lo:hi],
        width=0.8,
        color=np.where(up, C.UP, C.DOWN),
        alpha=0.55,
        linewidth=0,
    )
    _style(axb)
    axb.set_ylabel("volume", fontsize=8)
    axb.set_xlabel("4H bar index", fontsize=8)

    axm.set_facecolor(C.PANEL)
    axm.set_xticks([])
    axm.set_yticks([])
    for s in axm.spines.values():
        s.set_color(C.GRID)
    axm.text(
        0.03,
        0.985,
        "\n".join(metrics),
        transform=axm.transAxes,
        va="top",
        ha="left",
        fontsize=8.1,
        color=C.FG,
        linespacing=1.55,
        **MONO,
    )

    fig.savefig(out, facecolor=C.BG, bbox_inches="tight")
    plt.close(fig)
    return out


def evidence_chart(
    cells: list[tuple[str, int, float, float, float, float]],
    edges: list[tuple[str, float, float, float]],
    walk: dict[str, tuple[int, int, float, float, float]],
    sweep_rates: np.ndarray,
    out: Path,
) -> Path:
    """Four panels: barrier grid, edge-vs-control, walk-forward, and sweep stability."""
    fig, axes = plt.subplots(2, 2, figsize=(15.5, 9))
    fig.patch.set_facecolor(C.BG)
    (a1, a2), (a3, a4) = axes
    for a in (a1, a2, a3, a4):
        _style(a)

    # --- barrier grid vs breakeven
    labs = [c[0] for c in cells]
    y = np.arange(len(labs))
    rates = np.array([c[2] for c in cells])
    be = np.array([c[3] for c in cells])
    errs = np.array([[c[2] - c[4] for c in cells], [c[5] - c[2] for c in cells]])
    a1.errorbar(
        rates * 100,
        y,
        xerr=errs * 100,
        fmt="o",
        color=C.ACCENT,
        ecolor=C.MUTED,
        capsize=3,
        ms=5,
        lw=1.2,
    )
    a1.plot(be * 100, y, "|", color=C.WARN, ms=16, mew=2.2, label="breakeven")
    a1.set_yticks(y)
    a1.set_yticklabels(labs, fontsize=7.5, **MONO)
    a1.invert_yaxis()
    a1.set_xlabel("P(target first) %, 95% CI at effective n", fontsize=8.5)
    a1.set_title("Barrier grid vs breakeven — XRP", color=C.FG, fontsize=10, loc="left")
    a1.legend(facecolor=C.PANEL, edgecolor=C.GRID, labelcolor=C.FG, fontsize=8)

    # --- edge vs matched control
    el = [e[0] for e in edges]
    ey = np.arange(len(el))
    ev = np.array([e[1] for e in edges])
    eerr = np.array([[e[1] - e[2] for e in edges], [e[3] - e[1] for e in edges]])
    cols = [C.UP if lo > 0 else C.DOWN if hi < 0 else C.MUTED for _, _, lo, hi in edges]
    a2.errorbar(
        ev * 100,
        ey,
        xerr=eerr * 100,
        fmt="o",
        ecolor=C.MUTED,
        capsize=3,
        ms=5,
        lw=1.2,
        mfc="none",
        mec=C.FG,
    )
    for i, c in enumerate(cols):
        a2.plot(ev[i] * 100, ey[i], "o", color=c, ms=6)
    a2.axvline(0, color=C.WARN, lw=1.4, ls="--")
    a2.set_yticks(ey)
    a2.set_yticklabels(el, fontsize=7.5, **MONO)
    a2.invert_yaxis()
    a2.set_xlabel("edge vs matched control, percentage points (Newcombe CI)", fontsize=8.5)
    a2.set_title(
        "Edge against matched controls — zero line is the verdict",
        color=C.FG,
        fontsize=10,
        loc="left",
    )

    # --- walk-forward
    keys = list(walk)
    x = np.arange(len(keys))
    isr = [walk[k][2] * 100 for k in keys]
    oos = [walk[k][3] * 100 for k in keys]
    a3.bar(x - 0.2, isr, 0.4, color=C.MUTED, label="in-sample (pre-2023)")
    a3.bar(x + 0.2, oos, 0.4, color=C.ACCENT, label="out-of-sample (2023-26)")
    a3.axhline(100 / 3, color=C.WARN, lw=1.4, ls="--", label="breakeven 33.3%")
    a3.set_xticks(x)
    a3.set_xticklabels(keys, fontsize=8)
    a3.set_ylabel("P(target first) %", fontsize=8.5)
    a3.set_title(
        "Walk-forward: in-sample vs confirmatory out-of-sample", color=C.FG, fontsize=10, loc="left"
    )
    a3.legend(facecolor=C.PANEL, edgecolor=C.GRID, labelcolor=C.FG, fontsize=7.5)

    # --- sweep stability
    a4.hist(sweep_rates * 100, bins=18, color=C.ACCENT, alpha=0.75, edgecolor=C.BG)
    a4.axvline(100 / 3, color=C.WARN, lw=1.6, ls="--", label="breakeven 33.3%")
    a4.axvline(
        float(np.mean(sweep_rates)) * 100,
        color=C.DOWN,
        lw=1.4,
        label=f"sweep mean {np.mean(sweep_rates) * 100:.1f}%",
    )
    a4.set_xlabel("P(target first) % across parameter configurations", fontsize=8.5)
    a4.set_ylabel("configs", fontsize=8.5)
    a4.set_title(
        f"Sensitivity sweep — {sweep_rates.size} configs, 0 survive Benjamini-Hochberg",
        color=C.FG,
        fontsize=10,
        loc="left",
    )
    a4.legend(facecolor=C.PANEL, edgecolor=C.GRID, labelcolor=C.FG, fontsize=7.5)

    fig.tight_layout()
    fig.savefig(out, facecolor=C.BG, bbox_inches="tight")
    plt.close(fig)
    return out


def gallery_chart(bars: OHLCV, events: list[TripleTap], out: Path, *, n_show: int = 20) -> Path:
    """The 20 most recent detected instances with forward outcome overlaid."""
    sel = events[-n_show:]
    ncol, nrow = 5, int(np.ceil(len(sel) / 5)) or 1
    fig, axes = plt.subplots(nrow, ncol, figsize=(16, 2.5 * nrow))
    fig.patch.set_facecolor(C.BG)
    flat = np.atleast_1d(axes).ravel()
    fwd = 20 * C.BARS_PER_DAY

    for ax, e in zip(flat, sel, strict=False):
        i0 = max(0, e.tap_indices[0] - 20)
        i1 = min(len(bars), e.entry_confirm_index + fwd)
        _style(ax)
        x = np.arange(i0, i1)
        ax.plot(x, bars.close[i0:i1], color=C.FG, lw=0.8)
        ax.axhline(e.level, color=C.UP, lw=0.8, alpha=0.6)
        for t in e.tap_indices:
            ax.plot(t, bars.low[t], "^", color=C.UP, ms=6)
        ei = e.entry_confirm_index
        ax.axvline(ei, color=C.ACCENT, lw=0.9, ls="--")
        if ei + fwd < len(bars):
            ret = bars.close[ei + fwd] / bars.close[ei] - 1.0
            col = C.UP if ret > 0 else C.DOWN
            ax.set_title(f"bar {ei}  20d {ret * 100:+.1f}%", color=col, fontsize=8)
        ax.set_xticks([])
        ax.tick_params(labelsize=6)
    for ax in flat[len(sel) :]:
        ax.axis("off")
        ax.set_facecolor(C.BG)

    fig.suptitle(
        f"{bars.symbol} — {len(sel)} most recent detected triple taps, 20-day forward outcome",
        color=C.FG,
        fontsize=12,
        x=0.02,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out, facecolor=C.BG, bbox_inches="tight")
    plt.close(fig)
    return out

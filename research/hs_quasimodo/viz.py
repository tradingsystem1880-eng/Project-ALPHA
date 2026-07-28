"""Dark-theme charts for the head-and-shoulders study.

Same palette as the triple-tap deliverables (`#0d1117` / `#c9d1d9`). Two figures:

* :func:`structure_chart` — the live XRP inverse head and shoulders with all five anchors, the
  neckline, the measured-move target, and the trader's own levels overlaid, so the gap between the
  pattern's geometry and the hand-set target is visible rather than tabulated.
* :func:`evidence_chart` — what the study found: outcomes against breakeven, the break-of-structure
  split, the walk-forward, and the bullish/bearish symmetry check.

Run: ``python -m research.hs_quasimodo.viz``
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from alpha_patterns import OHLCV, HSConfig, HSEvent, detect_head_shoulders
from research.hs_quasimodo import config as C
from research.hs_quasimodo.data import REPO_ROOT, load
from research.hs_quasimodo.study import evaluate, load_events

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
OUT_DIR = REPO_ROOT / "research/hs_quasimodo/out"


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(C.PANEL)
    ax.grid(True, color=C.GRID, lw=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_color(C.GRID)


def _candles(ax: plt.Axes, bars: OHLCV, lo: int, hi: int) -> None:
    x = np.arange(lo, hi)
    up = bars.close[lo:hi] >= bars.open[lo:hi]
    ax.vlines(x, bars.low[lo:hi], bars.high[lo:hi], color=np.where(up, C.UP, C.DOWN), lw=0.7)
    ax.bar(
        x,
        np.abs(bars.close[lo:hi] - bars.open[lo:hi]),
        bottom=np.minimum(bars.open[lo:hi], bars.close[lo:hi]),
        width=0.7,
        color=np.where(up, C.UP, C.DOWN),
        linewidth=0,
    )


def structure_chart(bars: OHLCV, ev: HSEvent, metrics: list[str], out: Path) -> Path:
    """The live structure with its anchors, neckline, measured move, and the trader's levels."""
    lo = max(0, ev.ls_index - 40)
    hi = min(len(bars), ev.rs_index + 90)

    fig = plt.figure(figsize=(16, 9))
    fig.patch.set_facecolor(C.BG)
    gs = fig.add_gridspec(1, 2, width_ratios=[6.4, 2.5], wspace=0.06, left=0.05, right=0.985)
    ax = fig.add_subplot(gs[0, 0])
    axm = fig.add_subplot(gs[0, 1])

    _candles(ax, bars, lo, hi)
    _style(ax)

    # Five anchors.
    for idx, price, lbl, col in (
        (ev.ls_index, ev.ls_price, "LS", C.ACCENT),
        (ev.head_index, ev.head_price, "HEAD", C.WARN),
        (ev.rs_index, ev.rs_price, "RS", C.ACCENT),
    ):
        ax.plot(
            idx, price, marker="v" if ev.direction == "bearish" else "^", color=col, ms=13, zorder=6
        )
        ax.annotate(
            f"{lbl}\n{price:.4f}",
            (idx, price),
            textcoords="offset points",
            xytext=(0, -34 if ev.direction == "bullish" else 18),
            ha="center",
            color=col,
            fontsize=8.5,
            **MONO,
        )

    # Neckline, extrapolated to the right edge.
    xs = np.array([ev.n1_index, hi], dtype=float)
    slope = (ev.n2_price - ev.n1_price) / max(ev.n2_index - ev.n1_index, 1)
    ax.plot(xs, ev.n1_price + slope * (xs - ev.n1_index), color=C.MUTED, lw=1.4, ls="--")
    ax.annotate(
        "neckline",
        (hi - 2, ev.n1_price + slope * (hi - 2 - ev.n1_index)),
        color=C.MUTED,
        fontsize=8.5,
        ha="right",
        va="bottom",
        **MONO,
    )

    # Stop, their stop and the liquidation all sit within ~1% of each other, so the labels are
    # staggered horizontally — the crowding is itself the point being made.
    for lvl, col, lbl, xoff in (
        (ev.target_measured, C.UP, f"measured move {ev.target_measured:.4f}", 2),
        (C.TARGET, C.WARN, f"THEIR target {C.TARGET:.4f}", 2),
        (ev.stop_head, C.DOWN, f"stop below head {ev.stop_head:.4f}", 2),
        (C.STOP, C.WARN, f"THEIR stop {C.STOP:.4f}", 44),
        (C.LIQUIDATION, C.DOWN, f"LIQUIDATION {C.LIQUIDATION:.4f}", 86),
    ):
        ax.axhline(
            lvl, color=col, lw=1.1, ls=":" if "THEIR" in lbl or "LIQ" in lbl else "-", alpha=0.85
        )
        ax.text(lo + xoff, lvl, f" {lbl}", color=col, fontsize=8, va="bottom", **MONO)

    ax.set_title(
        f"XRP daily — {ev.variant.replace('_', ' ')} confirmed "
        f"(shoulder asymmetry {ev.shoulder_asymmetry:.2f}, head depth {ev.head_depth:.1%})",
        color=C.FG,
        fontsize=11.5,
        loc="left",
        pad=10,
    )
    ax.set_ylabel("XRP", fontsize=9)
    ax.set_xlabel("bar index", fontsize=8.5)

    axm.set_facecolor(C.PANEL)
    axm.set_xticks([])
    axm.set_yticks([])
    for s in axm.spines.values():
        s.set_color(C.GRID)
    axm.text(
        0.04,
        0.985,
        "\n".join(metrics),
        transform=axm.transAxes,
        va="top",
        ha="left",
        fontsize=8.4,
        color=C.FG,
        linespacing=1.6,
        **MONO,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=C.BG, bbox_inches="tight")
    plt.close(fig)
    return out


def evidence_chart(df: pl.DataFrame, out: Path) -> Path:
    """Outcomes vs breakeven, the BOS split, and the symmetry check."""
    fig, axes = plt.subplots(1, 3, figsize=(17, 6))
    fig.patch.set_facecolor(C.BG)
    grid = [(f"b_s{int(s * 100)}_r{r:g}_{d}d", r, d) for s, r, d in C.BARRIER_GRID]

    for ax, (base, title) in zip(
        axes[:2],
        [(b, b.replace("_", " ")) for b in C.BASE_VARIANTS],
        strict=False,
    ):
        _style(ax)
        sub = df.filter(pl.col("base_variant") == base)
        tf_bars = int(np.median([C.BARS_PER_DAY[t] for t in sub["timeframe"].unique()]))
        labels, qm_r, pl_r, be = [], [], [], []
        for col, rr, days in grid[:6]:
            a = evaluate(sub.filter(pl.col("has_bos")), col, rr, days * tf_bars, col)
            b = evaluate(sub.filter(~pl.col("has_bos")), col, rr, days * tf_bars, col)
            if not a or not b:
                continue
            labels.append(col.replace("b_", ""))
            qm_r.append(a.rate * 100)
            pl_r.append(b.rate * 100)
            be.append(a.breakeven * 100)
        y = np.arange(len(labels))
        ax.barh(y - 0.2, qm_r, 0.4, color=C.ACCENT, label="with BOS (Quasimodo)")
        ax.barh(y + 0.2, pl_r, 0.4, color=C.MUTED, label="no BOS")
        ax.plot(be, y, "|", color=C.WARN, ms=22, mew=2.4, label="breakeven")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=7.5, **MONO)
        ax.invert_yaxis()
        ax.set_xlabel("P(target first) %", fontsize=8.5)
        ax.set_title(title, color=C.FG, fontsize=10, loc="left")
        ax.legend(facecolor=C.PANEL, edgecolor=C.GRID, labelcolor=C.FG, fontsize=7.5)

    ax = axes[2]
    _style(ax)
    cut = C.WALK_FORWARD_SPLIT
    labs, vals, cols = [], [], []
    for base in C.BASE_VARIANTS:
        sub = df.filter((pl.col("base_variant") == base) & pl.col("has_bos"))
        tf_bars = int(np.median([C.BARS_PER_DAY[t] for t in sub["timeframe"].unique()]))
        for tag, pop in (
            ("IS", sub.filter(pl.col("confirmed_ts") < cut)),
            ("OOS", sub.filter(pl.col("confirmed_ts") >= cut)),
        ):
            c = evaluate(pop, "b_s3_r2_10d", 2.0, 10 * tf_bars, tag)
            if c:
                labs.append(f"{base[:9]}\n{tag}")
                vals.append((c.rate - c.breakeven) * 100)
                cols.append(C.UP if c.beats else (C.DOWN if c.rate < c.breakeven else C.MUTED))
    ax.bar(np.arange(len(labs)), vals, color=cols)
    ax.axhline(0, color=C.WARN, lw=1.4, ls="--")
    ax.set_xticks(np.arange(len(labs)))
    ax.set_xticklabels(labs, fontsize=7.5)
    ax.set_ylabel("edge over breakeven, percentage points", fontsize=8.5)
    ax.set_title(
        "Quasimodo, walk-forward (green = CI clears breakeven)", color=C.FG, fontsize=10, loc="left"
    )

    fig.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=C.BG, bbox_inches="tight")
    plt.close(fig)
    return out


def main(argv: list[str] | None = None) -> int:
    src = next(s for s in C.SOURCES if s.key == C.PRIMARY_KEY)
    bars, prov = load(src, "1d")
    cfg = HSConfig(**C.PRIMARY["inverse_head_shoulders"])  # type: ignore[arg-type]
    cutoff = len(bars) - 150
    recent = [e for e in detect_head_shoulders(bars, cfg) if e.rs_index >= cutoff]
    if recent:
        ev = recent[-1]
        entry = float(bars.close[ev.confirmed_index])
        rr_live = (ev.target_measured - C.ENTRY) / (C.ENTRY - C.STOP)
        size = C.RISK_CAP_USDT / max(entry - ev.stop_head, 1e-9)
        metrics = [
            "DETECTED STRUCTURE",
            "-" * 40,
            f"variant   {ev.variant}",
            f"BOS       {'yes (Quasimodo)' if ev.has_bos else 'no (plain iH&S)'}",
            f"LS        {ev.ls_price:>10.4f}",
            f"HEAD      {ev.head_price:>10.4f}",
            f"RS        {ev.rs_price:>10.4f}",
            f"neckline  {ev.n1_price:.4f} -> {ev.n2_price:.4f}",
            f"slope     {ev.neckline_slope:>+9.2%}",
            f"head depth{ev.head_depth:>10.2%}",
            f"shoulder asym {ev.shoulder_asymmetry:>6.2f}",
            "",
            "PATTERN'S OWN TRADE",
            "-" * 40,
            f"measured target {ev.target_measured:>7.4f}",
            f"stop below head {ev.stop_head:>7.4f}",
            f"stop below RS   {ev.stop_rs:>7.4f}",
            "",
            "VS THE HELD POSITION",
            "-" * 40,
            f"their target    {C.TARGET:>7.4f}",
            f"pattern target  {ev.target_measured:>7.4f}",
            f"  target is {(C.TARGET / ev.target_measured - 1) * 100:>5.1f}% too high",
            "",
            f"their R:R       {C.REWARD_RISK:>7.2f}",
            f"pattern R:R     {rr_live:>7.2f}",
            f"their breakeven {C.BREAKEVEN * 100:>6.2f}%",
            f"pattern be      {100 / (1 + rr_live):>6.2f}%",
            "",
            "SIZE AT 44 USDT CAP",
            "-" * 40,
            f"pattern stop -> {size:>7,.0f} XRP",
            f"held is       {C.QUANTITY / size:>7,.0f}x that",
        ]
        print("wrote", structure_chart(bars, ev, metrics, OUT_DIR / "01_structure.png"))

    df = load_events()
    if df.height:
        print("wrote", evidence_chart(df, OUT_DIR / "02_evidence.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

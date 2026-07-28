"""Dark-theme charts for the pump study: lift forest, compression scatter, and the live structure.

Three figures, each answering one question a table answers badly:

1. **The forest plot.** Every predictor's difference with its interval, on one axis, sorted. A table
   of thirty-three intervals is unreadable; the same thirty-three as horizontal bars makes "almost
   everything crosses zero, and the ones that do not are all compression pointing the wrong way"
   visible in a second.
2. **Compression vs forward return.** The scatter behind the headline. If coiling preceded moves,
   the left edge would sit high. It does not.
3. **The live chart.** XRP with the detected wedges, the inverse head-and-shoulders anchors, the
   position levels, and the two dated calls marked.

Run: ``python -m research.xrp_pumps.viz``
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from alpha_patterns import HSConfig, WedgeConfig, detect_head_shoulders, detect_wedges  # noqa: E402
from research.hs_quasimodo.data import load  # noqa: E402
from research.xrp_pumps import config as C  # noqa: E402
from research.xrp_pumps import features, labels  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "research" / "xrp_pumps"


def _style(ax: Axes, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_facecolor(C.PANEL)
    ax.set_title(title, color=C.FG, fontsize=11, loc="left", pad=10)
    ax.set_xlabel(xlabel, color=C.MUTED, fontsize=9)
    ax.set_ylabel(ylabel, color=C.MUTED, fontsize=9)
    ax.tick_params(colors=C.MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(C.GRID)
    ax.grid(True, color=C.GRID, linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)


def forest(frame: pl.DataFrame, outcome: str, dest: Path) -> None:
    """Every predictor's lift with its interval, sorted, coloured by family."""
    sub = frame.filter(
        (pl.col("asset") == C.SUBJECT_KEY)
        & (pl.col("window") == "full")
        & (pl.col("outcome") == outcome)
    ).sort("difference")
    if sub.height == 0:
        print(f"  forest: no rows for {outcome}")
        return

    n = sub.height
    fig, ax = plt.subplots(figsize=(11, max(6.0, n * 0.32)), facecolor=C.BG)
    y = np.arange(n)
    diff = sub["difference"].to_numpy()
    lo = sub["diff_lower"].to_numpy()
    hi = sub["diff_upper"].to_numpy()

    for i in range(n):
        colour = C.FAMILY_COLOURS.get(sub["family"][i], C.MUTED)
        # Intervals that exclude zero are drawn solid; the rest are faded, so the eye is not
        # invited to read a point estimate whose interval spans the whole plot.
        separated = bool(sub["separated"][i])
        ax.plot(
            [lo[i], hi[i]],
            [y[i], y[i]],
            color=colour,
            lw=2.0 if separated else 1.0,
            alpha=1.0 if separated else 0.45,
            solid_capstyle="butt",
        )
        ax.plot(
            diff[i],
            y[i],
            "o",
            color=colour,
            ms=6 if separated else 4,
            alpha=1.0 if separated else 0.5,
        )

    ax.axvline(0.0, color=C.FG, lw=1.0, alpha=0.7)
    ax.set_yticks(y)
    ax.set_yticklabels(
        [f"{c}  (n={e})" for c, e in zip(sub["condition"], sub["n_condition_eff"], strict=True)],
        fontsize=8,
        fontfamily="monospace",
    )
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:+.0%}")
    _style(
        ax,
        f"Lift over the complement arm — XRP daily, outcome = {outcome}\n"
        f"solid = 95% interval excludes zero · n = effective (overlap-deflated) sample size",
        xlabel="P(pump | condition) − P(pump | not condition)",
    )
    handles = [Line2D([], [], color=col, lw=2, label=fam) for fam, col in C.FAMILY_COLOURS.items()]
    leg = ax.legend(handles=handles, loc="lower right", fontsize=8, framealpha=0.9)
    leg.get_frame().set_facecolor(C.PANEL)
    leg.get_frame().set_edgecolor(C.GRID)
    for text in leg.get_texts():
        text.set_color(C.FG)

    fig.tight_layout()
    fig.savefig(dest, dpi=140, facecolor=C.BG)
    plt.close(fig)
    print(f"  wrote {dest.name}")


def compression_scatter(dest: Path) -> None:
    """Trailing compression percentile against the forward 7-day maximum return.

    The picture behind the study's central negative result. Folklore says the left edge — the most
    compressed bars — should be where the big forward moves live. Binned medians are overlaid
    because a scatter of two thousand points shows density, not tendency.
    """
    panel = features.build(C.SUBJECT_KEY, "1d")
    closes = panel["close"].to_numpy().astype(np.float64)
    lab = labels.make_label(closes, C.POWER_PUMPS[0], "1d")
    bw = panel["bandwidth_pct"].to_numpy().astype(np.float64)
    fwd = lab.forward_return

    ok = lab.valid & np.isfinite(bw) & np.isfinite(fwd)
    x, y = bw[ok], fwd[ok]

    fig, ax = plt.subplots(figsize=(10, 6), facecolor=C.BG)
    ax.scatter(x, y, s=7, c=C.ACCENT, alpha=0.25, edgecolors="none")

    edges = np.linspace(0.0, 1.0, 11)
    mids, meds, rates = [], [], []
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        sel = (x >= a) & (x < b)
        if int(np.count_nonzero(sel)) < 20:
            continue
        mids.append((a + b) / 2.0)
        meds.append(float(np.median(y[sel])))
        rates.append(float(np.mean(y[sel] >= 0.10)))
    ax.plot(mids, meds, color=C.WARN, lw=2.0, marker="o", ms=5, label="median forward 7d max")

    ax2 = ax.twinx()
    ax2.plot(mids, rates, color=C.UP, lw=2.0, ls="--", marker="s", ms=4, label="P(+10% in 7d)")
    ax2.set_ylabel("P(+10% within 7 days)", color=C.UP, fontsize=9)
    ax2.tick_params(colors=C.UP, labelsize=8)
    ax2.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    for spine in ax2.spines.values():
        spine.set_color(C.GRID)

    ax.axhline(0.10, color=C.MUTED, lw=0.8, ls=":")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:+.0%}")
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    _style(
        ax,
        "Does coiling precede the move?  XRP daily, 2020-09 to 2026-07\n"
        "If it did, both overlaid lines would fall from left to right. They rise.",
        xlabel="Bollinger bandwidth percentile (trailing year) — LEFT = most compressed",
        ylabel="forward 7-day maximum return",
    )
    fig.tight_layout()
    fig.savefig(dest, dpi=140, facecolor=C.BG)
    plt.close(fig)
    print(f"  wrote {dest.name}")


def live_chart(dest: Path, *, lookback: int = 200) -> None:
    """XRP daily with detected structure, the position levels, and the two dated calls."""
    bars, prov = load(features.source_for(C.SUBJECT_KEY), "1d")  # type: ignore[arg-type]
    n = len(bars)
    lo = max(0, n - lookback)
    dates = bars.ts[lo:n].astype("datetime64[ms]")

    fig, (ax, axv) = plt.subplots(
        2, 1, figsize=(13, 8), facecolor=C.BG, height_ratios=[4, 1], sharex=True
    )

    up = bars.close[lo:n] >= bars.open[lo:n]
    ax.vlines(dates, bars.low[lo:n], bars.high[lo:n], color=C.MUTED, lw=0.6, alpha=0.8)
    ax.vlines(dates[up], bars.open[lo:n][up], bars.close[lo:n][up], color=C.UP, lw=2.6)
    ax.vlines(dates[~up], bars.open[lo:n][~up], bars.close[lo:n][~up], color=C.DOWN, lw=2.6)

    # Detected converging formations, drawn only over the bars they were valid for.
    from alpha_patterns import wedge_lines

    for w in detect_wedges(bars, WedgeConfig()):
        if w.end_index < lo:
            continue
        upper, lower = wedge_lines(w, n)
        stop = w.break_index if w.break_index >= 0 else min(w.confirmed_index + 60, n - 1)
        seg = np.arange(max(w.start_index, lo), min(stop, n - 1) + 1)
        if seg.size < 3:
            continue
        d = bars.ts[seg].astype("datetime64[ms]")
        ax.plot(d, upper[seg], color=C.WARN, lw=1.0, alpha=0.75)
        ax.plot(d, lower[seg], color=C.WARN, lw=1.0, alpha=0.75)

    # The inverse head and shoulders both this study's detector and the 21 July call identify.
    cfg = HSConfig(
        direction="bullish",
        lookback=5,
        head_prominence=0.03,
        shoulder_tol=0.75,
        time_symmetry_tol=0.25,
        max_neckline_slope=0.20,
        gap_min=10,
        gap_max=250,
        shoulder_rule="any",
        require_bos=False,
    )
    for e in detect_head_shoulders(bars, cfg):
        if e.rs_index < lo:
            continue
        pts = [(e.ls_index, e.ls_price), (e.head_index, e.head_price), (e.rs_index, e.rs_price)]
        ax.plot(
            [bars.ts[i].astype("datetime64[ms]") for i, _ in pts],
            [p for _, p in pts],
            color=C.ACCENT,
            lw=1.4,
            marker="o",
            ms=6,
            alpha=0.9,
        )
        for i, p in pts:
            ax.annotate(
                f"{p:.4f}",
                (bars.ts[i].astype("datetime64[ms]"), p),
                textcoords="offset points",
                xytext=(0, -14),
                color=C.ACCENT,
                fontsize=7,
                ha="center",
            )
        ax.axhline(e.target_measured, color=C.ACCENT, lw=0.9, ls="--", alpha=0.7)
        ax.text(
            dates[0],
            e.target_measured,
            f" measured target {e.target_measured:.4f}",
            color=C.ACCENT,
            fontsize=8,
            va="bottom",
        )

    for level, colour, text in (
        (C.ENTRY, C.FG, f"entry {C.ENTRY}"),
        (C.STOP, C.DOWN, f"stop {C.STOP}"),
        (C.LIQUIDATION, C.DOWN, f"liq {C.LIQUIDATION}"),
        (C.TARGET, C.UP, f"held target {C.TARGET}"),
    ):
        ax.axhline(level, color=colour, lw=1.0, ls=":", alpha=0.8)
        ax.text(dates[-1], level, f"  {text}", color=colour, fontsize=8, va="center")

    for date, text in (("2026-07-01", "wedge chart"), ("2026-07-21", "iH&S call")):
        stamp = np.datetime64(date, "ms")
        if stamp >= dates[0]:
            ax.axvline(stamp, color=C.WARN, lw=1.0, alpha=0.6)
            ax.text(
                stamp,
                float(np.max(bars.high[lo:n])),
                f" {text}",
                color=C.WARN,
                fontsize=8,
                rotation=90,
                va="top",
            )

    _style(
        ax,
        f"XRP daily — detected structure vs the position (data ends {prov.last_ts[:10]})",
        ylabel="price (USDT)",
    )
    axv.bar(dates, bars.volume[lo:n], color=C.MUTED, alpha=0.6, width=0.8)
    _style(axv, "", xlabel="", ylabel="volume")
    axv.set_title("")

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(dest, dpi=140, facecolor=C.BG)
    plt.close(fig)
    print(f"  wrote {dest.name}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Charts for the XRP pump study")
    ap.add_argument("--timeframe", default=C.PRIMARY_TIMEFRAME)
    args = ap.parse_args(argv)

    lifts = REPO_ROOT / C.OUT_DIR / f"lifts_{args.timeframe}.parquet"
    if lifts.exists():
        frame = pl.read_parquet(lifts)
        forest(frame, "up10_7d", OUT / "lift-forest-7d.png")
        forest(frame, C.PUMPS[0].label, OUT / "lift-forest-30d.png")
    else:
        print(f"  {lifts} absent — run `python -m research.xrp_pumps.study` first")
    compression_scatter(OUT / "compression-vs-forward.png")
    live_chart(OUT / "xrp-live-structure.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())

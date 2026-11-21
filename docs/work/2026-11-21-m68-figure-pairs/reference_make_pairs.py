"""Sample chart pairs: plain notebook chart + annotated teaching version.

Standalone: matplotlib, numpy, pandas, polars only. Reads one stored `alpha validate` run.
Usage:  ALPHA_DATA_DIR=<demo home> uv run python make_pairs.py <run_dir> <bars_parquet> <out_dir>
Plain charts use matplotlib defaults (no style sheet). Annotated charts add callouts,
labelled bands and a "How to read this chart" box. All annotation numbers are computed.
"""
import json
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle

RUN = Path(sys.argv[1])
BARS = Path(sys.argv[2])
OUT = Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
HELD_BACK = pd.Timestamp("2024-01-01")
HELD_END = pd.Timestamp("2025-01-01")  # width of the hatched band only
CRISES = [("2000-03-01", "2002-10-31", "2000-02 bust"), ("2007-10-01", "2009-03-31", "2008 crisis"),
          ("2020-02-01", "2020-04-30", "2020")]
BBOX = dict(boxstyle="square", fc="white", ec="0.4", lw=0.8)
ARROW = dict(arrowstyle="->", color="0.2", lw=1.0)


def read(name):
    df = pl.read_parquet(RUN / f"{name}.parquet")
    for c, t in df.schema.items():
        if isinstance(t, pl.Datetime):
            df = df.with_columns(pl.col(c).dt.replace_time_zone(None))
    return pd.DataFrame(df.to_dict(as_series=False))


def ym(ts):
    return pd.Timestamp(ts).strftime("%Y-%m")


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


# ---------------------------------------------------------------- data
manifest = json.load(open(RUN / "manifest.json"))
meta = manifest["metadata"]
bc = read("benchmark_comparison").set_index("ts")
eq = bc["strategy_equity"]
bh = bc["benchmark_equity"]
ret = eq.pct_change().dropna()
bret = bh.pct_change().dropna()
expo = read("exposure_turnover")
trades = read("trades")
bars = read_b = pd.DataFrame(pl.read_parquet(BARS).with_columns(pl.col("ts").dt.replace_time_zone(None)).to_dict(as_series=False)).set_index("ts")
nulls = read("nulls")
folds = pd.DataFrame(manifest["folds"])
for c in ["test_start_ts", "test_end_ts"]:
    folds[c] = pd.to_datetime(folds[c]).dt.tz_localize(None)
cal = read("calendar_returns")
START, END = eq.index[0], eq.index[-1]
TITLE = f"{meta['symbol']} {meta['strategy_name']}"
SPAN = f"{ym(START)} to {ym(END)}"
FOOT = "Source: stored validate run " + manifest["run_id"]


def drawdown(s):
    return s / s.cummax() - 1.0


def dd_episode(s):
    """Worst drawdown: peak date, trough date, recovery date (None if not recovered), depth."""
    dd = drawdown(s)
    trough = dd.idxmin()
    peak = s.loc[:trough].idxmax()
    after = s.loc[trough:]
    rec = after[after >= s.loc[peak]]
    return peak, trough, (rec.index[0] if len(rec) else None), dd.min()


def longest_run(mask):
    """Longest consecutive True run in a boolean Series -> (start, end, n)."""
    best = (None, None, 0)
    start = None
    prev = None
    n = 0
    for ts, v in mask.items():
        if v:
            if start is None:
                start, n = ts, 0
            n += 1
            prev = ts
            if n > best[2]:
                best = (start, prev, n)
        else:
            start = None
    return best


flat_days = pd.Series((expo["gross_exposure"].values == 0), index=expo["end_ts"])
FLAT_START, FLAT_END, FLAT_N = longest_run(flat_days)
IN_MKT = float((expo["gross_exposure"] > 0).mean())


# ---------------------------------------------------------------- helpers
def new_fig(annotated, height=8.0):
    h = height + (1.3 if annotated else 0)
    fig, ax = plt.subplots(figsize=(14, h))
    return fig, ax


def band(ax, a, b, label, hatch=None, color="0.5", alpha=0.15, ytxt=0.985, rot=0):
    ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), facecolor=color, alpha=alpha, hatch=hatch,
               edgecolor="0.4" if hatch else "none", lw=0)
    ax.text(pd.Timestamp(a), ytxt, " " + label, transform=ax.get_xaxis_transform(), ha="left", va="top",
            fontsize=8.5, color="0.25", rotation=rot)


def held_back(ax):
    ax.set_xlim(START, HELD_END)
    ax.axvspan(HELD_BACK, HELD_END, facecolor="none", hatch="///", edgecolor="0.6", lw=0)
    ax.text(HELD_BACK + (HELD_END - HELD_BACK) / 2, 0.5, "held back, not used", transform=ax.get_xaxis_transform(),
            rotation=90, ha="center", va="center", fontsize=9, color="0.25",
            bbox=dict(fc="white", ec="none", alpha=0.85))


def crises(ax, ytxt=0.985):
    for a, b, lab in CRISES:
        band(ax, a, b, lab, ytxt=ytxt)


def call(ax, text, xy, xyt, ha="left", va="center"):
    ax.annotate(text, xy=xy, xycoords="data", xytext=xyt, textcoords="axes fraction", fontsize=9,
                ha=ha, va=va, bbox=BBOX, arrowprops=ARROW, zorder=10)


def finish(fig, ax, name, annotated, subtitle="", note=""):
    suffix = "annotated" if annotated else "plain"
    if annotated:
        ax.text(0, 1.012, subtitle, transform=ax.transAxes, fontsize=10, color="0.3", va="bottom")
        t = ax.get_title()
        ax.set_title("")
        ax.set_title(t, loc="left", pad=30, fontsize=13)
        fig.subplots_adjust(left=0.07, right=0.97, top=0.89, bottom=0.21)
        body = "\n".join(textwrap.wrap(note, 175))
        fig.text(0.07, 0.02, "How to read this chart\n" + body + "\n" + FOOT + "; " + SPAN + ".",
                 fontsize=9.5, va="bottom", ha="left", linespacing=1.4,
                 bbox=dict(boxstyle="square,pad=0.6", fc="0.96", ec="0.6"))
    else:
        fig.tight_layout()
    fig.savefig(OUT / f"{name}-{suffix}.png", dpi=150)
    plt.close(fig)
    print("wrote", f"{name}-{suffix}.png")


def date_axis(ax, annotated):
    ax.margins(x=0)
    if annotated:
        held_back(ax)
    ax.grid(True, color="0.85")


# ---------------------------------------------------------------- 01 equity
def c01(annotated):
    fig, ax = new_fig(annotated)
    ax.plot(eq.index, eq, label=f"Strategy ({meta['strategy_name']})")
    ax.plot(bh.index, bh, label="Buy and hold")
    ax.set_title(f"{meta['symbol']} Strategy vs Buy and Hold: Growth of $1")
    ax.set_xlabel("Date")
    ax.set_ylabel("Growth of $1")
    ax.legend(loc="center left")
    date_axis(ax, annotated)
    if annotated:
        crises(ax, 0.985)
        ax.plot(eq.loc[FLAT_START:FLAT_END], color="C0", lw=6, alpha=0.35)
        call(ax, f"Strategy out of the market for {FLAT_N} sessions in a row\n({ym(FLAT_START)} to {ym(FLAT_END)}); equity stays at "
             f"${eq.loc[FLAT_START]:.2f}", (FLAT_START + (FLAT_END - FLAT_START) / 2, eq.loc[FLAT_START]), (0.30, 0.45), "left")
        call(ax, f"Buy and hold ends at ${bh.iloc[-1]:.2f}", (END, bh.iloc[-1]), (0.93, 0.74), "right")
        call(ax, f"Strategy ends at ${eq.iloc[-1]:.2f}", (END, eq.iloc[-1]), (0.93, 0.40), "right")
        hi = bh.idxmax()
        call(ax, f"Buy and hold high: ${bh.max():.2f} ({ym(hi)})", (hi, bh.max()), (0.80, 0.93), "right")
        finish(fig, ax, "01-equity-curve", True, f"Both lines start at $1. The strategy was in the market {pct(IN_MKT, 0)} of sessions.",
               "The x axis is time and the y axis is what $1 would have grown to. Compare how high each line ends and how far each falls "
               "from its earlier peaks. Buy and hold is price only (no dividends); fees and slippage are in the strategy line. "
               "A growth curve shows one historical path; it cannot say what the next path will look like. A log-scale view would show equal percentage moves as equal distances.")
    else:
        finish(fig, ax, "01-equity-curve", False)


# ---------------------------------------------------------------- 02 drawdown
def c02(annotated):
    fig, ax = new_fig(annotated)
    sd, bd = drawdown(eq), drawdown(bh)
    ax.plot(sd.index, sd * 100, label="Strategy")
    ax.plot(bd.index, bd * 100, label="Buy and hold")
    ax.set_title(f"{meta['symbol']} Drawdown (Underwater Curve)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown (%)")
    ax.legend(loc="lower left")
    date_axis(ax, annotated)
    if annotated:
        crises(ax, 0.985)
        sp, st, sr, sdep = dd_episode(eq)
        bp, bt, br, bdep = dd_episode(bh)
        ax.plot(sd.loc[sp:(sr or END)], color="C0", lw=6, alpha=0.35)
        call(ax, f"Strategy worst: {pct(sdep)} at {ym(st)}\npeak {ym(sp)}, "
             + (f"recovered {ym(sr)}" if sr else "not recovered by the end"), (st, sdep * 100), (0.04, 0.55), "left")
        call(ax, f"Buy and hold worst: {pct(bdep)} at {ym(bt)}\npeak {ym(bp)}, "
             + (f"recovered {ym(br)}" if br else "not recovered by the end"), (bt, bdep * 100), (0.20, 0.12), "left")
        u = longest_run(sd < 0)
        call(ax, f"Strategy longest time below its peak: {u[2]} sessions\n({ym(u[0])} to {ym(u[1])})", (u[0] + (u[1] - u[0]) / 2, sd.loc[u[0]:u[1]].min() * 100 * 0.9), (0.04, 0.35), "left")
        finish(fig, ax, "02-drawdown", True, "Each point is the percentage below the highest equity reached so far; 0% means a new high.",
               "The y axis is the loss from the previous peak; the deeper and wider the dip, the worse and longer the loss. Look at the depth of each dip "
               "and how long the line stays below zero. The wide pale-blue stretch on the strategy line marks its worst drawdown, from peak to recovery. "
               "It cannot show losses inside a day, or whether a future drawdown will be deeper.")
    else:
        finish(fig, ax, "02-drawdown", False)


# ---------------------------------------------------------------- 03 price + trades
def c03(annotated):
    px = bars["close"].loc[START:END]
    fig, ax = new_fig(annotated)
    ax.plot(px.index, px, label=f"{meta['symbol']} close")
    et = pd.to_datetime(trades["entry_ts"])
    xt = pd.to_datetime(trades["exit_ts"])
    ei = px.index.get_indexer(et, method="nearest")
    xi = px.index.get_indexer(xt, method="nearest")
    ax.scatter(px.index[ei], px.iloc[ei], marker="^", s=70, color="C2", zorder=5, label="Entry")
    ax.scatter(px.index[xi], px.iloc[xi], marker="v", s=70, color="C3", zorder=5, label="Exit")
    ax.set_title(f"{meta['symbol']} Close Price with Entries and Exits")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price ($)")
    ax.legend(loc="upper left")
    date_axis(ax, annotated)
    if annotated:
        ax.set_ylim(top=px.max() * 1.12)
        for a, b in zip(et, xt):
            ax.axvspan(a, b, color="C2", alpha=0.10, lw=0)
        crises(ax, 0.985)
        r = trades["realized_return"]
        w, l = r.idxmax(), r.idxmin()
        call(ax, f"Best trade {pct(r[w])}\n{ym(et[w])} to {ym(xt[w])}", (xt[w], px.iloc[xi[w]]), (0.84, 0.30), "right")
        call(ax, f"Worst trade {pct(r[l])}\n{ym(et[l])} to {ym(xt[l])}", (xt[l], px.iloc[xi[l]]), (0.08, 0.55), "left")
        gaps = [(xt[i], et[i + 1]) for i in range(len(trades) - 1)]
        gaps.append((START, et[0]))
        g = max(gaps, key=lambda t: t[1] - t[0])
        call(ax, f"Longest time out of the market:\n{ym(g[0])} to {ym(g[1])} ({(g[1] - g[0]).days} days)",
             (g[0] + (g[1] - g[0]) / 2, px.loc[g[0]:g[1]].mean()), (0.30, 0.45), "left")
        finish(fig, ax, "03-price-entries-exits", True, f"{len(trades)} completed trades. Green shading = holding the position; unshaded = flat.",
               "The line is the daily close. Triangles up mark the day a position was opened, triangles down the day it was closed; green shading is the time held. "
               "Look at whether exits came before or after the big moves. Markers sit on that day's close; the actual fills were at the next open and in several partial steps, "
               "so a marker shows the date, not the exact price paid.")
    else:
        finish(fig, ax, "03-price-entries-exits", False)


# ---------------------------------------------------------------- 04 return distribution
def c04(annotated):
    r = ret.values
    mu, sd = r.mean(), r.std(ddof=1)
    fig, ax = new_fig(annotated)
    n, edges, _ = ax.hist(r, bins=100, label="Daily returns", edgecolor="white", linewidth=0.3)
    x = np.linspace(edges[0], edges[-1], 500)
    pdf = np.exp(-0.5 * ((x - mu) / sd) ** 2) / (sd * np.sqrt(2 * np.pi))
    ax.plot(x, pdf * len(r) * (edges[1] - edges[0]), color="C3", lw=2, label="Normal PDF (same mean and std)")
    ax.set_yscale("log")
    ax.set_ylim(0.5, n.max() * 3)
    ax.set_title(f"{meta['symbol']} Strategy Daily Return Distribution")
    ax.set_xlabel("Daily Return")
    ax.set_ylabel("Count (log scale)")
    ax.legend(loc="upper left")
    ax.grid(True, color="0.85")
    if annotated:
        zero = int((r == 0).sum())
        q5 = np.quantile(r, 0.05)
        pos = r[r != 0]
        q5 = np.quantile(pos, 0.05)
        ax.axvline(q5, color="0.3", ls="--", lw=1)
        ax.axvspan(edges[0], q5, color="C1", alpha=0.15)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v * 100:.1f}%"))
        w, b = r.min(), r.max()
        call(ax, f"{zero} of {len(r)} days ({pct(zero / len(r), 0)}) are exactly 0.0%:\nthe strategy held cash", (0, n.max()), (0.68, 0.88), "left")
        call(ax, f"5% tail of days when invested starts at {pct(q5, 2)}", (q5, 3), (0.20, 0.35), "left")
        call(ax, f"Worst day {pct(w, 2)}", (w, 1), (0.08, 0.20), "left")
        call(ax, f"Best day {pct(b, 2)}", (b, 1), (0.88, 0.20), "right")
        finish(fig, ax, "04-return-distribution", True, "Each bar counts days with a return in that range. Red line: a bell curve with the same average and spread.",
               f"The x axis is the one-day return and the y axis is the number of days (log scale, so small counts stay visible). The tall bar at zero is the days spent in cash. "
               f"Look at the tails: bars above the red line mean more extreme days than a normal curve predicts (skew {pd.Series(r).skew():.2f}, excess kurtosis {pd.Series(r).kurt():.1f}). "
               "A histogram hides the order of days, so it cannot show clusters of bad days.")
    else:
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v * 100:.1f}%"))
        finish(fig, ax, "04-return-distribution", False)


# ---------------------------------------------------------------- 05 rolling sharpe
def c05(annotated):
    W = 252
    m, s = ret.rolling(W).mean(), ret.rolling(W).std(ddof=1)
    sh = (m / s.where(s > 0)) * np.sqrt(252)
    fig, ax = new_fig(annotated)
    ax.plot(sh.index, sh, label="Rolling 1-year Sharpe")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title(f"{meta['symbol']} Strategy Rolling 1-Year Sharpe Ratio")
    ax.set_xlabel("Date")
    ax.set_ylabel("Sharpe ratio")
    ax.set_ylim(-1.8, 4.6)
    ax.legend(loc="upper left")
    date_axis(ax, annotated)
    if annotated:
        crises(ax, 0.985)
        hi, lo = sh.idxmax(), sh.idxmin()
        call(ax, f"Highest: {ym(hi)}, {sh[hi]:.2f}", (hi, sh[hi]), (0.55, 0.90), "right")
        call(ax, f"Lowest: {ym(lo)}, {sh[lo]:.2f}", (lo, sh[lo]), (0.33, 0.06), "left")
        gap = longest_run(sh.isna() & (sh.index > sh.first_valid_index()))
        if gap[2] > 5:
            call(ax, f"Line breaks where the whole year was cash:\nSharpe undefined ({ym(gap[0])} to {ym(gap[1])})", (gap[0], 0), (0.20, 0.80), "left")
        frac = float((sh.dropna() > 0).mean())
        ax.text(0.62, 0.04, f"Above zero in {pct(frac, 0)} of defined windows", transform=ax.transAxes, ha="left", fontsize=9, bbox=BBOX)
        finish(fig, ax, "05-rolling-sharpe", True, "Each point is the Sharpe ratio (average daily return over its spread, times square root of 252) of the 252 sessions ending that day.",
               "The y axis is risk-adjusted return over the trailing year; above zero means the year gained more than its ups and downs, below zero means it lost. "
               "Look at how much the line moves, not only where it ends. Windows with no trades have no defined Sharpe, so the line stops. "
               "It cannot show the Sharpe of the next year; each point reuses 251 days of the one before.")
    else:
        finish(fig, ax, "05-rolling-sharpe", False)


# ---------------------------------------------------------------- 06 monthly heat map
def c06(annotated):
    m = cal[cal["period_type"] == "month"].pivot(index="year", columns="month", values="return_value")
    m = m.reindex(columns=range(1, 13))
    last_full = END.to_period("M") - 1  # last month is partial
    for mo in range(1, 13):
        if pd.Period(year=int(m.index[-1]), month=mo, freq="M") > END.to_period("M"):
            m.loc[m.index[-1], mo] = np.nan
    yrs = list(m.index)
    vals = m.values * 100
    fig, ax = plt.subplots(figsize=(14, 10 + (1.0 if annotated else 0)))
    vmax = np.nanmax(np.abs(vals))
    im = ax.imshow(vals, cmap="RdYlGn", norm=TwoSlopeNorm(0, -vmax, vmax), aspect="auto")
    fig.colorbar(im, ax=ax, label="Monthly return (%) - pale yellow is zero", orientation="horizontal", location="bottom", pad=0.07, fraction=0.03)
    ax.set_xticks(range(12), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set_yticks(range(len(yrs)), yrs)
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            if not np.isnan(vals[i, j]):
                ax.text(j, i, f"{vals[i, j]:.1f}", ha="center", va="center", fontsize=7.5)
    ax.set_title(f"{meta['symbol']} Strategy Monthly Returns (%)")
    ax.set_xlabel("Month")
    ax.set_ylabel("Year")
    if annotated:
        flat = int((vals == 0).sum())
        tot = int((~np.isnan(vals)).sum())
        bi = np.unravel_index(np.nanargmax(vals), vals.shape)
        wi = np.unravel_index(np.nanargmin(vals), vals.shape)
        for (i, j), c in ((bi, "darkgreen"), (wi, "darkred")):
            ax.add_patch(Rectangle((j - .5, i - .5), 1, 1, fill=False, ec=c, lw=2.5))
        ax.text(1.03, 0.985, f"Green outline: best month\n{vals[bi]:.1f}% ({yrs[bi[0]]}-{bi[1] + 1:02d})", transform=ax.transAxes, fontsize=9, bbox=BBOX, va="top")
        ax.text(1.03, 0.915, f"Red outline: worst month\n{vals[wi]:.1f}% ({yrs[wi[0]]}-{wi[1] + 1:02d})", transform=ax.transAxes, fontsize=9, bbox=BBOX, va="top")
        ax.text(1.03, 0.60, f"{flat} of {tot} months are exactly 0.0:\nthe strategy held cash all month", transform=ax.transAxes, fontsize=9, bbox=BBOX)
        for yr, lab in ((2000, "dashed: 2000-02 bust"), (2008, "dashed: 2008 crisis"), (2020, "dashed: 2020")):
            if yr in yrs:
                k = yrs.index(yr)
                ax.add_patch(Rectangle((-.5, k - .5), 12, 1, fill=False, ec="0.2", lw=1.2, ls="--"))
                ax.text(12.0, k, lab, ha="left", va="center", fontsize=8.5, color="0.2", clip_on=False)
        ax.text(12.0, len(yrs) - 1, "2023: Jan to Nov 14 only", ha="left", va="center", fontsize=8.5, color="0.2", clip_on=False)
        fig.subplots_adjust(left=0.07, right=0.80, top=0.90, bottom=0.25)
        ax.text(0, 1.012, "Each cell is one calendar month of the strategy. Green gained, red lost, pale yellow is zero.", transform=ax.transAxes, fontsize=10, color="0.3", va="bottom")
        t = ax.get_title(); ax.set_title(""); ax.set_title(t, loc="left", pad=30, fontsize=13)
        body = "\n".join(textwrap.wrap("Rows are years and columns are calendar months; the number in a cell is that month's return in percent. "
                                       "Look for runs of red, for months that repeat across years, and for rows that are all pale yellow (cash). "
                                       "The colour scale is centred at zero (pale yellow) and symmetric. A month is only a one-month sample, so a column pattern here cannot show a calendar effect that would repeat.", 175))
        fig.text(0.07, 0.02, "How to read this chart\n" + body + "\n" + FOOT + "; " + SPAN + ".", fontsize=9.5, va="bottom", linespacing=1.4,
                 bbox=dict(boxstyle="square,pad=0.6", fc="0.96", ec="0.6"))
    else:
        fig.tight_layout()
    fig.savefig(OUT / f"06-monthly-returns-{'annotated' if annotated else 'plain'}.png", dpi=150)
    plt.close(fig)
    print("wrote 06", annotated)


# ---------------------------------------------------------------- 07 Monte Carlo
def c07(annotated):
    rng = np.random.default_rng(42)
    r = ret.values
    n = len(r)
    paths = np.cumprod(1 + rng.choice(r, size=(1000, n), replace=True), axis=1) - 1
    orig = np.cumprod(1 + r) - 1
    fig, ax = new_fig(annotated)
    for p in paths[:10]:
        ax.plot(p, lw=0.8)
    ax.plot(orig, color="red", lw=3, label="Original")
    ax.axhline(0, color="black", lw=1)
    ax.set_title("SPY Strategy Returns Monte Carlo Simulations")
    ax.set_xlabel("Occurrences")
    ax.set_ylabel("Results")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
    ax.legend(loc="upper left")
    ax.grid(True, color="0.85")
    ax.margins(x=0)
    if annotated:
        fin = paths[:, -1]
        pr = float((fin < orig[-1]).mean())
        p5, p50, p95 = np.quantile(fin, [0.05, 0.5, 0.95])
        ax.plot([n - 1], [orig[-1]], "o", color="red", ms=9)
        ax.text(0.99, 0.04, f"Original ends at {pct(orig[-1], 0)}\nMedian of 1000 resampled paths ends at {pct(p50, 0)}\n"
                f"5th to 95th percentile of the 1000 end values: {pct(p5, 0)} to {pct(p95, 0)}\nOriginal ends above {pct(pr, 0)} of the 1000 resampled paths",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=9.5, bbox=BBOX, zorder=10)
        finish(fig, ax, "07-monte-carlo", True, "Thin coloured lines are ten of 1000 reshuffled versions of the strategy's own daily returns; the thick red line is what actually happened.",
               f"The x axis counts trading days (occurrences) and the y axis is cumulative return. Each thin path draws {n} daily returns at random, with replacement, from the strategy's {n} actual daily returns (seed 42). "
               "Look at how far the red line sits from the thin lines. Random draws destroy the order of days, so streaks of cash and bad runs are mixed up; this shows how much sequence matters, not how a future path will unfold.")
    else:
        finish(fig, ax, "07-monte-carlo", False)


# ---------------------------------------------------------------- 08 trade returns
def c08(annotated):
    r = trades["realized_return"].values
    fig, ax = new_fig(annotated)
    bins = np.linspace(min(r.min(), -0.01) - 0.005, r.max() + 0.005, 10)
    n, edges, _ = ax.hist(r, bins=bins, label="Trades", edgecolor="white")
    ax.set_title(f"{meta['symbol']} Strategy Trade Return Distribution")
    ax.set_xlabel("Trade Return")
    ax.set_ylabel("Count")
    ax.yaxis.get_major_locator().set_params(integer=True)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
    ax.legend(loc="upper right")
    ax.grid(True, color="0.85")
    if annotated:
        et, xt = pd.to_datetime(trades["entry_ts"]), pd.to_datetime(trades["exit_ts"])
        ax.axvline(0, color="black", lw=1)
        ax.axvline(r.mean(), color="C3", ls="--", label=f"Mean {pct(r.mean())}")
        ax.axvline(np.median(r), color="C2", ls=":", lw=2, label=f"Median {pct(np.median(r))}")
        ax.legend(loc="upper left")
        ax.plot(r, np.full_like(r, 0.08), "|", color="k", ms=14)
        w, l = int(np.argmax(r)), int(np.argmin(r))
        ymax = n.max()
        call(ax, f"Best: {pct(r[w])}\n{ym(et[w])} to {ym(xt[w])}", (r[w], 0.08), (0.80, 0.70), "right")
        call(ax, f"Worst: {pct(r[l])}\n{ym(et[l])} to {ym(xt[l])}", (r[l], 0.08), (0.14, 0.50), "left")
        hold = (xt - et).dt.days
        ax.text(0.99, 0.97, f"{len(r)} trades; {int((r > 0).sum())} gained, {int((r <= 0).sum())} did not\nHolding time {hold.min()} to {hold.max()} days (median {int(hold.median())})",
                transform=ax.transAxes, ha="right", va="top", fontsize=9, bbox=BBOX)
        finish(fig, ax, "08-trade-returns", True, "Each bar counts completed round-trip trades whose return fell in that range; the black ticks are the individual trades.",
               f"The x axis is the percent gained or lost from entry to exit and the y axis is the number of trades. Look at where the bars sit relative to the black zero line, and at how far the mean and median are apart. "
               f"With only {len(r)} trades, one trade can move the mean a lot. Returns are per trade and do not show position size, so a small win can matter more than a large one.")
    else:
        finish(fig, ax, "08-trade-returns", False)


# ---------------------------------------------------------------- 09 walk-forward
def c09(annotated):
    f = folds
    fig, ax = new_fig(annotated)
    width = (f["test_end_ts"] - f["test_start_ts"]).dt.days.values
    ax.bar(f["test_start_ts"], f["oos_sharpe"], width=width, align="edge", label="Out-of-sample Sharpe per fold")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title(f"{meta['symbol']} Walk-Forward: Out-of-Sample Sharpe per Fold")
    ax.set_xlabel("Test period start date")
    ax.set_ylabel("Sharpe ratio")
    ax.set_ylim(-4, 5.4)
    ax.legend(loc="upper right")
    ax.grid(True, color="0.85", axis="y")
    ax.margins(x=0)
    if annotated:
        ax.set_xlim(f["test_start_ts"].iloc[0], HELD_END)
        ax.axvspan(HELD_BACK, HELD_END, facecolor="none", hatch="///", edgecolor="0.6", lw=0)
        ax.text(HELD_BACK + (HELD_END - HELD_BACK) / 2, 0.5, "held back, not used", transform=ax.get_xaxis_transform(), rotation=90, ha="center", va="center", fontsize=9,
                bbox=dict(fc="white", ec="none", alpha=0.85))
        hi, lo = f["oos_sharpe"].idxmax(), f["oos_sharpe"].idxmin()
        rng = lambda i: f"{ym(f['test_start_ts'][i])} to {ym(f['test_end_ts'][i])}"
        call(ax, f"Best fold #{hi}: Sharpe {f['oos_sharpe'][hi]:.2f}\ntested {rng(hi)}", (f["test_start_ts"][hi], f["oos_sharpe"][hi]), (0.12, 0.92), "left")
        call(ax, f"Worst fold #{lo}: Sharpe {f['oos_sharpe'][lo]:.2f}\ntested {rng(lo)}", (f["test_start_ts"][lo], f["oos_sharpe"][lo]), (0.62, 0.10), "left")
        mean = f["oos_sharpe"].mean()
        ax.axhline(mean, color="C3", ls="--", lw=1)
        ax.text(0.02, 0.03, f"Mean of folds {mean:.2f}; {int((f['oos_sharpe'] > 0).sum())} of {len(f)} folds above zero.\n"
                f"First fold tested {rng(0)}; last fold tested {rng(len(f) - 1)}.", transform=ax.transAxes, va="bottom", fontsize=9, bbox=BBOX)
        finish(fig, ax, "09-walk-forward", True, f"Each bar is one {int(f['n_test'].iloc[0])}-session test window the rule was never fitted on; the bar spans that window.",
               f"The x axis places each fold by its test window and the y axis is the Sharpe ratio earned in it. Each fold's rule is trained on earlier data only, then scored on the next unseen window. "
               "Look at how many bars are above zero and how widely they vary. A 63-day Sharpe is noisy, so single bars say little; folds with no trades have a Sharpe of zero. It does not cover the held-back years.")
    else:
        finish(fig, ax, "09-walk-forward", False)


# ---------------------------------------------------------------- 10 luck test
def c10(annotated):
    nl = nulls[nulls["tier"] == "bar_permutation"]["statistic"].values
    obs = [x for x in manifest["nulls"] if x["tier"] == "bar_permutation"][0]
    o = obs["observed"]
    fig, ax = new_fig(annotated)
    n, edges, _ = ax.hist(nl, bins=16, label="Randomized-price runs", edgecolor="white")
    ax.axvline(o, color="red", lw=2.5, label=f"Strategy's own Sharpe ({o:.2f})")
    ax.set_title(f"{meta['symbol']} Luck Test: Sharpe from Randomized-Price Runs")
    ax.set_xlabel("Sharpe ratio")
    ax.set_ylabel("Count")
    ax.set_ylim(0, 12)
    ax.legend(loc="upper left")
    ax.grid(True, color="0.85")
    if annotated:
        q95 = np.quantile(nl, 0.95)
        ax.axvspan(q95, max(nl.max(), o) * 1.1, color="C1", alpha=0.15)
        ax.axvline(q95, color="0.3", ls="--", lw=1)
        beat = int((nl >= o).sum())
        top = n.max()
        call(ax, f"Strategy's Sharpe {o:.2f}\n{beat} of {len(nl)} random runs reached it or more", (o, top * 0.5), (0.97, 0.70), "right")
        call(ax, f"5% tail starts at Sharpe {q95:.2f}\n(95th percentile of the random runs)", (q95, top * 0.8), (0.50, 0.92), "right")
        call(ax, f"Random runs: median {np.median(nl):.2f}, range {nl.min():.2f} to {nl.max():.2f}", (np.median(nl), top * 0.3), (0.10, 0.30), "left")
        ax.set_xlim(min(nl.min(), 0) - 0.05, max(nl.max(), o) * 1.1)
        finish(fig, ax, "10-luck-test", True, "Blue bars show the Sharpe the same strategy rule earned on price series where the bar order was shuffled, so any real pattern is removed.",
               f"The x axis is Sharpe and the y axis counts runs. The red line is the strategy's Sharpe on the real prices. If the red line sits inside the bars, shuffled data produced similar results by chance; if it sits far to the right, few shuffles matched it. "
               f"This uses {len(nl)} runs, so the smallest possible p-value is about {1 / (len(nl) + 1):.3f}. It tests luck against shuffled history only, not whether the pattern will persist.")
    else:
        finish(fig, ax, "10-luck-test", False)


if __name__ == "__main__":
    for fn in (c01, c02, c03, c04, c05, c06, c07, c08, c09, c10):
        for a in (False, True):
            fn(a)

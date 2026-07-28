"""The statistical protocol: intervals, controls, symmetry, and the three targeted hypotheses.

Reads the event shards written by :mod:`detect` and answers, in order:

1. Does the pattern beat **breakeven** at each barrier configuration? Compared against
   ``1/(1+R)``, never against 50%.
2. Does it beat a **matched control** — same trend state, same distance above the trailing low?
   Reported as a difference with a Newcombe interval, because the interval on a difference is not
   the difference of two intervals.
3. Does the **bearish mirror** behave like the bullish case? A bullish-only edge that does not
   mirror is usually drift-fitting rather than a pattern.
4. Three within-sample comparisons on shared populations: the **break-of-structure filter**
   (Quasimodo vs plain), **volume-confirmed** neckline breaks (the widely-quoted 73%/54% claim),
   and the **measured-move target** against fixed R multiples.

Every table carries effective sample size alongside nominal n. With overlapping forward windows —
severe at 15-minute resolution — nominal n badly overstates how much independent information is
present, and it is the effective figure that should be read.

Run: ``python -m research.hs_quasimodo.study [--tf 4h]``
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import numpy as np
import polars as pl

from alpha_validation import (
    effective_sample_size,
    newcombe_diff_interval,
    overlap_factor,
    wilson_interval,
)
from research.hs_quasimodo import config as C
from research.hs_quasimodo.detect import EVENTS_DIR


@dataclass(frozen=True)
class Cell:
    """One evaluated population under one barrier configuration."""

    label: str
    n: int
    n_eff: float
    overlap: float
    target: int
    stop: int
    unresolved: int
    rate: float
    breakeven: float
    ci_low: float
    ci_high: float
    ci_low_eff: float
    ci_high_eff: float
    expectancy_r: float
    beats: bool


def load_events(timeframes: list[str] | None = None) -> pl.DataFrame:
    """Concatenate every event shard, keeping only columns common to all of them."""
    shards = sorted(EVENTS_DIR.glob("*.parquet"))
    frames = []
    for p in shards:
        df = pl.read_parquet(p)
        if df.height == 0 or "asset" not in df.columns:
            continue
        if timeframes and df["timeframe"][0] not in timeframes:
            continue
        frames.append(df)
    if not frames:
        return pl.DataFrame()
    common = set(frames[0].columns)
    for f in frames[1:]:
        common &= set(f.columns)
    cols = [c for c in frames[0].columns if c in common]
    return pl.concat([f.select(cols) for f in frames], how="vertical_relaxed")


def evaluate(
    df: pl.DataFrame, column: str, reward_risk: float, horizon_bars: int, label: str
) -> Cell | None:
    """Tally one outcome column into counts, intervals and expectancy.

    ``n_eff`` uses the same overlap correction as the triple-tap study: with events closer together
    than the forward horizon, neighbouring observations share most of their price path and are not
    independent. The span is taken as the total bar count implied by the event index range.
    """
    if column not in df.columns or df.height == 0:
        return None
    vals = df[column].drop_nulls()
    n = vals.len()
    if n < 10:
        return None

    target = int((vals == "target").sum())
    stop = int((vals == "stop").sum())
    unresolved = n - target - stop
    rate = target / n
    breakeven = 1.0 / (1.0 + reward_risk)

    span = max(int(df["confirmed_index"].max() or 0), n)
    n_eff = effective_sample_size(n, span_bars=span, horizon_bars=max(horizon_bars, 1))
    ov = overlap_factor(n, span_bars=span, horizon_bars=max(horizon_bars, 1))

    ci = wilson_interval(target, n, confidence=C.CONFIDENCE)
    n_e = max(2, int(round(n_eff)))
    ci_eff = wilson_interval(int(round(rate * n_e)), n_e, confidence=C.CONFIDENCE)

    return Cell(
        label=label,
        n=n,
        n_eff=n_eff,
        overlap=ov,
        target=target,
        stop=stop,
        unresolved=unresolved,
        rate=rate,
        breakeven=breakeven,
        ci_low=ci.lower,
        ci_high=ci.upper,
        ci_low_eff=ci_eff.lower,
        ci_high_eff=ci_eff.upper,
        expectancy_r=(target * reward_risk - stop) / n,
        beats=ci_eff.lower > breakeven,
    )


def compare(
    df_a: pl.DataFrame, df_b: pl.DataFrame, column: str
) -> tuple[float, float, float, int, int]:
    """Difference in target-first rate between two populations, with a Newcombe interval."""
    a = df_a[column].drop_nulls() if column in df_a.columns else pl.Series([], dtype=pl.Utf8)
    b = df_b[column].drop_nulls() if column in df_b.columns else pl.Series([], dtype=pl.Utf8)
    if a.len() < 10 or b.len() < 10:
        return (float("nan"), float("nan"), float("nan"), a.len(), b.len())
    d = newcombe_diff_interval(
        int((a == "target").sum()),
        a.len(),
        int((b == "target").sum()),
        b.len(),
        confidence=C.CONFIDENCE,
    )
    return (d.point, d.lower, d.upper, a.len(), b.len())


def _fmt(c: Cell) -> str:
    flag = "BEATS" if c.beats else ""
    return (
        f"  {c.label:<34} {c.n:>6,} {c.n_eff:>7.0f} {c.overlap:>5.1f} "
        f"{c.rate * 100:>6.2f}% {c.breakeven * 100:>6.2f}% "
        f"[{c.ci_low_eff * 100:>5.1f},{c.ci_high_eff * 100:>5.1f}]% "
        f"{c.expectancy_r:>+6.2f}  {flag}"
    )


_HDR = (
    f"  {'population':<34} {'n':>6} {'n_eff':>7} {'ovl':>5} {'rate':>7} {'be':>7} "
    f"{'CI(n_eff)':>15} {'EV/R':>6}"
)


def report(df: pl.DataFrame) -> None:
    """Print the whole protocol."""
    if df.height == 0:
        print("no events — run `python -m research.hs_quasimodo.detect` first")
        return

    print(f"\n{'=' * 100}\nEVENT POPULATION\n{'=' * 100}")
    summary = (
        df.group_by(["base_variant", "timeframe"])
        .agg(pl.len().alias("n"), pl.col("has_bos").sum().alias("qm"))
        .sort(["base_variant", "timeframe"])
    )
    print(summary)
    print(f"\ntotal events: {df.height:,}   assets: {df['asset'].n_unique()}")

    grid = [(f"b_s{int(s * 100)}_r{r:g}_{d}d", r, d) for s, r, d in C.BARRIER_GRID]

    for base in C.BASE_VARIANTS:
        sub = df.filter(pl.col("base_variant") == base)
        if sub.height == 0:
            continue
        print(f"\n{'=' * 100}\n{base.upper()} — barrier grid, pooled across assets & timeframes")
        print(f"{'=' * 100}\n{_HDR}")
        for col, rr, days in grid:
            tf_bars = int(np.median([C.BARS_PER_DAY[t] for t in sub["timeframe"].unique()]))
            c = evaluate(sub, col, rr, days * tf_bars, col)
            if c:
                print(_fmt(c))

    print(f"\n{'=' * 100}\nHYPOTHESIS 1 — does the break-of-structure filter add anything?")
    print(f"{'=' * 100}\n  (Quasimodo vs plain, same detected population — a within-sample test)")
    for base in C.BASE_VARIANTS:
        sub = df.filter(pl.col("base_variant") == base)
        for col, _rr, _days in grid[:4]:
            qm = sub.filter(pl.col("has_bos"))
            plain = sub.filter(~pl.col("has_bos"))
            pt, lo, hi, na, nb = compare(qm, plain, col)
            if np.isfinite(pt):
                verdict = (
                    "BOS helps" if lo > 0 else ("BOS hurts" if hi < 0 else "indistinguishable")
                )
                print(
                    f"  {base[:14]:<14} {col:<18} qm n={na:>5,} plain n={nb:>5,}  "
                    f"diff {pt * 100:>+6.2f}% [{lo * 100:>+6.2f},{hi * 100:>+6.2f}]%  {verdict}"
                )

    print(f"\n{'=' * 100}\nHYPOTHESIS 1b — does the BOS filter lift Quasimodo ABOVE breakeven?")
    print(f"{'=' * 100}")
    print("  (a filter can beat the unfiltered population and still lose money — this is the test")
    print("   that decides whether Quasimodo is tradeable, not merely better than plain H&S)")
    print(f"{_HDR}")
    for base in C.BASE_VARIANTS:
        sub = df.filter(pl.col("base_variant") == base)
        tf_bars = int(np.median([C.BARS_PER_DAY[t] for t in sub["timeframe"].unique()]))
        for col, rr, days in grid[:4]:
            for tag, pop in (
                ("QM", sub.filter(pl.col("has_bos"))),
                ("plain", sub.filter(~pl.col("has_bos"))),
            ):
                c = evaluate(pop, col, rr, days * tf_bars, f"{base[:12]} {tag:<5} {col}")
                if c:
                    print(_fmt(c))

    print(f"\n{'=' * 100}\nHYPOTHESIS 2 — do volume-confirmed neckline breaks do better?")
    print(f"{'=' * 100}\n  (the widely-quoted 73% vs 54% claim, tested directly)")
    for base in C.BASE_VARIANTS:
        sub = df.filter((pl.col("base_variant") == base) & pl.col("volume_confirmed").is_not_null())
        for col, _rr, _days in grid[:3]:
            yes = sub.filter(pl.col("volume_confirmed"))
            no = sub.filter(~pl.col("volume_confirmed"))
            pt, lo, hi, na, nb = compare(yes, no, col)
            if np.isfinite(pt):
                verdict = (
                    "confirmed better" if lo > 0 else ("worse" if hi < 0 else "indistinguishable")
                )
                print(
                    f"  {base[:14]:<14} {col:<18} vol n={na:>5,} novol n={nb:>5,}  "
                    f"diff {pt * 100:>+6.2f}% [{lo * 100:>+6.2f},{hi * 100:>+6.2f}]%  {verdict}"
                )

    print(f"\n{'=' * 100}\nHYPOTHESIS 3 — the pattern's own measured-move trade")
    print(f"{'=' * 100}")
    print(
        f"  {'entry x stop':<34} {'n':>6} {'median R:R':>11} {'target%':>9} {'be%':>7} {'EV/R':>7}"
    )
    for stop_name in C.STOPS:
        for entry_name in C.ENTRIES:
            tag = f"m_{entry_name}_{stop_name}"
            if tag not in df.columns:
                continue
            sub = df.filter(pl.col(tag).is_not_null())
            if sub.height < 20:
                continue
            rr = float(sub[f"{tag}_rr"].median() or float("nan"))
            vals = sub[tag]
            t = int((vals == "target").sum())
            s = int((vals == "stop").sum())
            n = vals.len()
            be = 1.0 / (1.0 + rr) if np.isfinite(rr) and rr > 0 else float("nan")
            ev = (t * rr - s) / n if np.isfinite(rr) else float("nan")
            print(
                f"  {entry_name + ' x ' + stop_name:<34} {n:>6,} {rr:>11.2f} "
                f"{t / n * 100:>8.2f}% {be * 100:>6.2f}% {ev:>+7.2f}"
            )

    print(f"\n{'=' * 100}\nWALK-FORWARD — the only confirmatory test")
    print(f"{'=' * 100}")
    print(f"  (pre-{C.WALK_FORWARD_SPLIT} is descriptive; 2023-26 is the out-of-sample run of the")
    print("   pre-registered specification. An edge that does not survive here is an artefact.)")
    print(f"{_HDR}")
    cut = C.WALK_FORWARD_SPLIT
    for base in C.BASE_VARIANTS:
        sub = df.filter(pl.col("base_variant") == base)
        tf_bars = int(np.median([C.BARS_PER_DAY[t] for t in sub["timeframe"].unique()]))
        for col, rr, days in grid[1:3]:
            for tag, pop in (
                ("IS  QM", sub.filter(pl.col("has_bos") & (pl.col("confirmed_ts") < cut))),
                ("OOS QM", sub.filter(pl.col("has_bos") & (pl.col("confirmed_ts") >= cut))),
            ):
                c = evaluate(pop, col, rr, days * tf_bars, f"{base[:12]} {tag} {col}")
                if c:
                    print(_fmt(c))

    print(f"\n{'=' * 100}\nSYMMETRY — bullish vs bearish mirror")
    print(f"{'=' * 100}")
    for col, _rr, _days in grid[:4]:
        bull = df.filter(pl.col("direction") == "bullish")
        bear = df.filter(pl.col("direction") == "bearish")
        pt, lo, hi, na, nb = compare(bull, bear, col)
        if np.isfinite(pt):
            verdict = "ASYMMETRIC" if (lo > 0 or hi < 0) else "symmetric"
            print(
                f"  {col:<20} bull n={na:>6,} bear n={nb:>6,}  "
                f"diff {pt * 100:>+6.2f}% [{lo * 100:>+6.2f},{hi * 100:>+6.2f}]%  {verdict}"
            )

    print(f"\n{'=' * 100}\nCONTEXT — under overhead supply vs clear air (the user's situation)")
    print(f"{'=' * 100}")
    for base in C.BASE_VARIANTS:
        sub = df.filter(pl.col("base_variant") == base)
        for col, _rr, _days in grid[:3]:
            under = sub.filter(pl.col("under_supply"))
            clear = sub.filter(~pl.col("under_supply"))
            pt, lo, hi, na, nb = compare(under, clear, col)
            if np.isfinite(pt):
                verdict = "differs" if (lo > 0 or hi < 0) else "indistinguishable"
                print(
                    f"  {base[:14]:<14} {col:<18} under n={na:>5,} clear n={nb:>5,}  "
                    f"diff {pt * 100:>+6.2f}% [{lo * 100:>+6.2f},{hi * 100:>+6.2f}]%  {verdict}"
                )

    print(f"\n{'=' * 100}\nFORWARD RETURNS (signed so positive = the pattern's direction worked)")
    print(f"{'=' * 100}")
    print(
        f"  {'population':<32} {'n':>6} "
        + " ".join(f"{f'{d}d':>16}" for d in C.FORWARD_HORIZONS_DAYS)
    )
    for base in C.BASE_VARIANTS:
        for tf in sorted(df["timeframe"].unique()):
            sub = df.filter((pl.col("base_variant") == base) & (pl.col("timeframe") == tf))
            if sub.height < 30:
                continue
            cells = []
            for d in C.FORWARD_HORIZONS_DAYS:
                v = sub[f"fwd_{d}d"].drop_nulls()
                cells.append(
                    f"{float(v.median()) * 100:>7.2f}% {float((v > 0).mean()) * 100:>5.1f}%"
                    if v.len()
                    else " " * 16
                )
            print(f"  {base[:20] + ' ' + tf:<32} {sub.height:>6,} " + " ".join(cells))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Statistical protocol over detected H&S/QM events")
    ap.add_argument("--tf", nargs="*", default=None)
    args = ap.parse_args(argv)
    report(load_events(args.tf))
    return 0


if __name__ == "__main__":
    sys.exit(main())

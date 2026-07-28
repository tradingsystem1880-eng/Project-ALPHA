"""The study: every pre-registered condition against every pump definition, read honestly.

Structure, in the order the report presents it:

1. **Base rates.** What fraction of bars are followed by a pump at all. Everything else is a
   comparison against this number, and quoting a conditional probability without it is the single
   most common way a pattern claim misleads.
2. **Lift tables per family**, Benjamini-Hochberg corrected within the family.
3. **The symmetry check.** Does the condition raise the odds of a large *fall* by the same amount?
   If so it has found volatility, not direction, and the "breakout predictor" reading is wrong.
4. **Cross-asset consistency.** The same primary predictors on BTC, ETH, SOL, LTC. A finding present
   on XRP and nowhere else is a property of one price series.
5. **Walk-forward.** In-sample (pre-2023) versus out-of-sample. Only the out-of-sample column may
   carry a claim; everything else is descriptive.
6. **Confluence.** Does stacking independent conditions produce a monotone improvement, or is the
   whole idea an artefact of picking the best cell?

Run: ``python -m research.xrp_pumps.study [--timeframe 1d] [--quick]``
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

from alpha_core import DataError
from alpha_validation import LiftResult, apply_fdr, conditional_lift, monotonic_trend
from research.xrp_pumps import config as C
from research.xrp_pumps import features, labels

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / C.OUT_DIR


@dataclass(frozen=True)
class AssetPanel:
    """A built feature panel plus its realised labels — everything one asset contributes."""

    key: str
    timeframe: str
    panel: pl.DataFrame
    labels: dict[str, labels.Label]
    conditions: dict[str, np.ndarray]
    defined: dict[str, np.ndarray]  # per-condition mask of bars where the feature exists

    @property
    def n_bars(self) -> int:
        return self.panel.height

    @property
    def first_date(self) -> str:
        return str(np.datetime64(int(self.panel["ts"][0]), "ms"))[:10]

    @property
    def last_date(self) -> str:
        return str(np.datetime64(int(self.panel["ts"][-1]), "ms"))[:10]


def _mask(panel: pl.DataFrame, pred: C.Predictor) -> tuple[np.ndarray, np.ndarray]:
    """Realise one predictor as (condition, defined) boolean arrays.

    ``defined`` matters as much as ``condition``. A bar where the feature is missing — before the
    chain record starts, inside a warm-up window, outside any wedge — belongs in *neither* arm. Left
    unhandled it silently joins the complement and contaminates the comparison, which biases the
    measured lift in whichever direction the missingness happens to correlate with.
    """
    if pred.column not in panel.columns:
        raise DataError(f"predictor {pred.name!r} needs missing column {pred.column!r}")
    values = panel[pred.column].to_numpy().astype(np.float64)
    defined = np.isfinite(values)

    if pred.rule == "below":
        cond = values < pred.threshold
    elif pred.rule == "above":
        cond = values > pred.threshold
    elif pred.rule == "equal":
        cond = values == pred.threshold
    elif pred.rule == "between":
        cond = (values >= pred.threshold) & (values <= pred.upper)
    else:
        raise DataError(f"unknown predictor rule {pred.rule!r}")

    return (cond & defined), defined


def build_asset(key: str, timeframe: str) -> AssetPanel:
    """Feature panel, labels and realised conditions for one asset."""
    panel = features.build(key, timeframe)
    closes = panel["close"].to_numpy().astype(np.float64)
    labs = labels.all_labels(closes, timeframe)

    conditions: dict[str, np.ndarray] = {}
    defined: dict[str, np.ndarray] = {}
    for pred in C.PREDICTORS:
        try:
            cond, dfn = _mask(panel, pred)
        except DataError as exc:
            print(f"    {key}: {exc}")
            continue
        conditions[pred.name] = cond
        defined[pred.name] = dfn
    return AssetPanel(key, timeframe, panel, labs, conditions, defined)


def evaluate(
    asset: AssetPanel,
    *,
    window: np.ndarray | None = None,
    label_names: tuple[str, ...] | None = None,
    predictor_names: tuple[str, ...] | None = None,
) -> list[LiftResult]:
    """Every (predictor x label) cell for one asset, optionally restricted to a date window.

    ``window`` is a boolean bar mask used for the walk-forward split. It intersects the label's own
    validity mask, so the out-of-sample run genuinely scores only bars whose forward window also
    falls out of sample rather than borrowing resolution from the in-sample period.
    """
    results: list[LiftResult] = []
    for lab_name, lab in asset.labels.items():
        if label_names is not None and lab_name not in label_names:
            continue
        overlap = labels.overlap_for(lab)
        for pred in C.PREDICTORS:
            if predictor_names is not None and pred.name not in predictor_names:
                continue
            if pred.name not in asset.conditions:
                continue
            valid = lab.valid & asset.defined[pred.name]
            if window is not None:
                valid = valid & window
            try:
                results.append(
                    conditional_lift(
                        asset.conditions[pred.name],
                        lab.hit,
                        label=pred.name,
                        outcome_label=lab_name,
                        family=pred.family,
                        valid=valid,
                        overlap=overlap,
                        confidence=C.CONFIDENCE,
                    )
                )
            except DataError:
                # A condition that never fires inside this window has no comparison to make. That is
                # information (reported in the coverage table), not a reason to abort the study.
                continue
    return results


def corrected(results: list[LiftResult]) -> list[LiftResult]:
    """Benjamini-Hochberg within each family separately, then re-flattened in the input order."""
    out: list[LiftResult] = []
    for family in C.FAMILIES:
        fam = [r for r in results if r.family == family]
        if fam:
            out.extend(apply_fdr(fam, alpha=C.FDR_ALPHA))
    return out


def to_frame(results: list[LiftResult], asset: str, window: str) -> pl.DataFrame:
    """Flatten results to a tidy frame — the artefact everything downstream reads."""
    if not results:
        return pl.DataFrame()
    return pl.DataFrame(
        {
            "asset": [asset] * len(results),
            "window": [window] * len(results),
            "family": [r.family for r in results],
            "condition": [r.condition for r in results],
            "outcome": [r.outcome for r in results],
            "n_condition": [r.n_condition for r in results],
            "n_complement": [r.n_complement for r in results],
            "n_condition_eff": [r.n_condition_eff for r in results],
            "n_complement_eff": [r.n_complement_eff for r in results],
            "overlap": [r.overlap for r in results],
            "rate_condition": [r.rate_condition for r in results],
            "rate_complement": [r.rate_complement for r in results],
            "rate_overall": [r.rate_overall for r in results],
            "difference": [r.difference for r in results],
            "diff_lower": [r.interval_difference.lower for r in results],
            "diff_upper": [r.interval_difference.upper for r in results],
            "lift": [r.lift for r in results],
            "pvalue": [r.pvalue for r in results],
            "qvalue": [r.qvalue for r in results],
            "rejected": [r.rejected for r in results],
            "separated": [r.separated for r in results],
        }
    )


# --------------------------------------------------------------------------- confluence


@dataclass(frozen=True)
class ConfluenceResult:
    """Pump rate by how many independent conditions hold simultaneously."""

    counts: list[int]
    n_bars: list[int]  # nominal
    n_bars_eff: list[int]  # after deflating for forward-window overlap
    rates: list[float]
    trend_z: float  # computed at the EFFECTIVE size — the nominal z is inflated by sqrt(overlap)
    trend_z_nominal: float
    overlap: float
    label: str

    def line(self) -> str:
        cells = " ".join(
            f"{k}:{r:.1%}(n={n:,}/{e})"
            for k, n, e, r in zip(
                self.counts, self.n_bars, self.n_bars_eff, self.rates, strict=True
            )
        )
        return (
            f"{self.label:<16} {cells}   trend z={self.trend_z:+.2f} "
            f"(nominal {self.trend_z_nominal:+.2f} / sqrt({self.overlap:.0f}))"
        )


def confluence(asset: AssetPanel, label_name: str, *, min_bars: int = 25) -> ConfluenceResult:
    """Pump rate as a function of how many pre-registered conditions hold at once.

    The sharpest available test of the confluence idea itself. Stacking is supposed to produce a
    *monotone* staircase: two conditions beat one, three beat two. One bright bin among five is what
    multiplicity produces on its own. The Cochran-Armitage z-score summarises the staircase in one
    number so the eye cannot pick the bin it likes.

    Members are drawn from different families deliberately — four rescalings of the same volatility
    reading would agree with each other and prove nothing.
    """
    lab = asset.labels[label_name]
    members = [m for m in C.CONFLUENCE_MEMBERS if m in asset.conditions]
    if len(members) < 3:
        raise DataError(f"confluence needs >= 3 available members, have {len(members)}")

    stack = np.vstack([asset.conditions[m].astype(np.int64) for m in members])
    # A bar only gets a confluence score if every member is *defined* there; otherwise a missing
    # chain reading would silently read as "condition absent" and depress the count.
    defined = np.logical_and.reduce([asset.defined[m] for m in members])
    score = stack.sum(axis=0)
    valid = lab.valid & defined

    overlap = labels.overlap_for(lab)
    counts: list[int] = []
    n_bars: list[int] = []
    n_eff: list[int] = []
    rates: list[float] = []
    for k in range(len(members) + 1):
        sel = valid & (score == k)
        n = int(np.count_nonzero(sel))
        if n < min_bars:
            continue
        counts.append(k)
        n_bars.append(n)
        n_eff.append(max(2, int(round(n / overlap))))
        rates.append(float(np.count_nonzero(lab.hit & sel)) / n)

    if len(counts) < 3:
        raise DataError(f"confluence for {label_name}: only {len(counts)} populated bins")

    # The trend statistic scales with sqrt(n), so feeding it nominal bar counts inflates it by
    # sqrt(overlap) — a factor of 5.5 at a 30-day horizon on daily bars. That is the difference
    # between "z = -5.3, overwhelming" and "z = -1.0, nothing". Only the deflated figure is quoted.
    return ConfluenceResult(
        counts=counts,
        n_bars=n_bars,
        n_bars_eff=n_eff,
        rates=rates,
        trend_z=monotonic_trend(rates, n_eff),
        trend_z_nominal=monotonic_trend(rates, n_bars),
        overlap=overlap,
        label=label_name,
    )


# --------------------------------------------------------------------------- consistency


@dataclass(frozen=True)
class SignTest:
    """Whether a family's effect points the same way across independent assets.

    Individual cells in this study have almost no power — a 30-day forward window leaves ~70
    independent observations, and no interval on a 6-point difference is going to clear zero at that
    size. But *direction* is cheap to measure and, across assets that are separate price series, is
    close to independent. Six assets all pointing the same way is a one-in-thirty-two event under
    the null, which is a real test where the individual intervals are not.

    This is the same logic the head-and-shoulders study used to promote break-of-structure from
    "one suggestive cell" to a finding: consistency across assets, not significance in one place.
    """

    family: str
    outcome: str
    per_asset: dict[str, float]  # mean difference across the family's predictors, per asset
    n_negative: int
    n_positive: int
    pvalue: float

    def line(self) -> str:
        cells = " ".join(f"{k}:{v:+.1%}" for k, v in self.per_asset.items())
        return (
            f"  {self.family:<14} {self.n_negative}-/{self.n_positive}+  "
            f"sign p={self.pvalue:.3f}   {cells}"
        )


def sign_consistency(
    panels: dict[str, AssetPanel], family: str, outcome: str, *, exclude_mirror: bool = True
) -> SignTest:
    """Mean within-family lift per asset, and a two-sided sign test over the assets.

    The statistic per asset is the *mean* difference over the family's predictors, which keeps one
    noisy predictor from flipping an asset's vote. Assets are the unit of replication because they
    are separate series; the predictors inside a family are not independent of each other
    (bandwidth, realized vol and ATR are three views of one quantity) and counting them as
    replicates would inflate the test.
    """
    names = tuple(p.name for p in C.predictors_in(family))
    per_asset: dict[str, float] = {}
    for key, ap in panels.items():
        if exclude_mirror and key.endswith("_BITSTAMP") and key.replace("_BITSTAMP", "") in panels:
            continue  # the same underlying on a second venue is not an independent replicate
        rows = evaluate(ap, label_names=(outcome,), predictor_names=names)
        if rows:
            per_asset[key] = float(np.mean([r.difference for r in rows]))

    if len(per_asset) < 3:
        raise DataError(f"sign test for {family}: only {len(per_asset)} assets")

    vals = np.array(list(per_asset.values()))
    n_neg = int(np.count_nonzero(vals < 0))
    n_pos = int(np.count_nonzero(vals > 0))
    n = n_neg + n_pos
    extreme = max(n_neg, n_pos)
    # Exact two-sided binomial tail at p=0.5.
    tail = sum(_choose(n, k) for k in range(extreme, n + 1)) / (2.0**n)
    return SignTest(family, outcome, per_asset, n_neg, n_pos, min(1.0, 2.0 * tail))


def _choose(n: int, k: int) -> float:
    from math import comb

    return float(comb(n, k))


# --------------------------------------------------------------------------- reporting


def _rule(title: str) -> None:
    print(f"\n{'=' * 108}\n{title}\n{'=' * 108}")


def _print_family(results: list[LiftResult], family: str, outcome: str) -> None:
    rows = [r for r in results if r.family == family and r.outcome == outcome]
    if not rows:
        return
    rows.sort(key=lambda r: -abs(r.difference))
    print(f"\n  [{family}] vs {outcome}")
    for r in rows:
        print("   " + r.line())


def run(timeframe: str, *, assets: tuple[str, ...], quick: bool) -> pl.DataFrame:
    """Build every asset, evaluate every cell, print the report, return the tidy frame."""
    OUT.mkdir(parents=True, exist_ok=True)
    panels: dict[str, AssetPanel] = {}
    for key in assets:
        t0 = time.time()
        try:
            panels[key] = build_asset(key, timeframe)
        except Exception as exc:  # noqa: BLE001 — one bad source must not sink the study
            print(f"  FAIL {key}: {exc}")
            continue
        a = panels[key]
        print(
            f"  {key:<14} {a.n_bars:>5,} bars  {a.first_date} -> {a.last_date}  "
            f"{len(a.conditions)} predictors  ({time.time() - t0:.1f}s)"
        )

    subject = panels.get(C.SUBJECT_KEY)
    if subject is None:
        raise DataError(f"subject {C.SUBJECT_KEY} failed to build — nothing to report")

    frames: list[pl.DataFrame] = []

    # ---- 1. base rates ----------------------------------------------------
    _rule("1. BASE RATES — every conditional number below is a comparison against these")
    print(
        f"\n  {'label':<18} {'base rate':>10} {'nominal n':>11} {'n_eff':>8} {'overlap':>9}  "
        "what it means"
    )
    for name, lab in subject.labels.items():
        n = int(np.count_nonzero(lab.valid))
        print(
            f"  {name:<18} {lab.base_rate:>9.1%} {n:>11,} {labels.effective_n(lab):>8.0f} "
            f"{labels.overlap_for(lab):>8.0f}x  threshold {lab.threshold:+.2f}"
        )
    print(
        "\n  Read the n_eff column before anything else. A 30-day forward window on daily bars\n"
        "  overlaps 30x, so ~2,100 rows carry roughly 70 independent observations. Every interval\n"
        "  in this report is computed at the effective size, not the nominal one."
    )

    # ---- 2. lift tables ---------------------------------------------------
    all_results = corrected(evaluate(subject))
    frames.append(to_frame(all_results, subject.key, "full"))
    primary_label = C.PUMPS[0].label

    _rule(f"2. LIFT TABLES — {subject.key} {timeframe}, all pre-registered predictors")
    print(
        "\n  rate(condition) vs rate(complement), difference with a Newcombe 95% interval at the\n"
        "  effective sample size. '*' = survives Benjamini-Hochberg within its family at q<0.05."
    )
    for family in C.FAMILIES:
        _print_family(all_results, family, primary_label)

    if not quick:
        _rule("2b. THE SAME PREDICTORS AGAINST THE OTHER PUMP DEFINITIONS")
        print(
            "\n  A condition that lifts every definition is describing a mechanism. One that\n"
            "  lifts a single threshold has found a number."
        )
        for lab_name in ("up50_90d", "up100_180d", "top10pct_30d"):
            rows = [r for r in all_results if r.outcome == lab_name and r.separated]
            print(f"\n  [{lab_name}] {len(rows)} of {len(C.PREDICTORS)} cells separate from zero:")
            for r in sorted(rows, key=lambda r: -abs(r.difference))[:8]:
                print("   " + r.line())

    # ---- 2c. the post-hoc, higher-powered labels --------------------------
    _rule("2c. POST-HOC SHORTER HORIZONS — declared after the fact, and the only powered cells")
    print(
        "\n  These two labels were NOT pre-registered. They were added once it was clear that a\n"
        "  30-90-180 day horizon leaves 71/23/11 independent windows in a decade of daily bars —\n"
        "  a sample in which no interval could separate from zero whatever the market did. The\n"
        "  power argument depends only on the horizon, not on any outcome, which is what makes\n"
        "  the addition defensible; it is still post-hoc, so these carry no confirmatory weight.\n"
        "  They are shown because they are the only place in this study with enough independent\n"
        "  observations to distinguish a real effect from nothing."
    )
    for lab_name in labels.POST_HOC:
        rows = [r for r in all_results if r.outcome == lab_name]
        if not rows:
            continue
        rows.sort(key=lambda r: -r.difference)
        lab = subject.labels[lab_name]
        print(
            f"\n  [{lab_name}] base rate {lab.base_rate:.1%}, "
            f"n_eff {labels.effective_n(lab):.0f} (overlap {labels.overlap_for(lab):.0f}x)"
        )
        for r in rows[:6] + rows[-6:]:
            print("   " + r.line())

    # ---- 3. symmetry ------------------------------------------------------
    _rule("3. SYMMETRY CHECK — does the condition predict direction, or just volatility?")
    print(
        f"\n  {'predictor':<34} {'up +20%/30d':>14} {'down -20%/30d':>15} {'asymmetry':>12}\n"
        "  A predictor whose two columns move together has found volatility. Only a gap between\n"
        "  them is directional information."
    )
    ups = {r.condition: r for r in all_results if r.outcome == "up20_30d"}
    downs = {r.condition: r for r in all_results if r.outcome == "downup-20_30d"}
    for name in sorted(set(ups) & set(downs), key=lambda k: -abs(ups[k].difference)):
        u, d = ups[name], downs[name]
        print(
            f"  {name:<34} {u.difference:>+13.1%} {d.difference:>+14.1%} "
            f"{u.difference - d.difference:>+11.1%}"
        )

    # ---- 4. cross-asset ---------------------------------------------------
    _rule("4. CROSS-ASSET — the primary predictor of each family on every asset")
    primaries = tuple(C.primary_of(f).name for f in C.FAMILIES)
    print(f"\n  {'asset':<14} " + " ".join(f"{p[:22]:>24}" for p in primaries))
    for key, ap in panels.items():
        res = {
            r.condition: r
            for r in evaluate(ap, label_names=(primary_label,), predictor_names=primaries)
        }
        cells = []
        for p in primaries:
            r = res.get(p)
            cells.append(
                f"{'--':>24}" if r is None else f"{r.difference:>+16.1%} n={r.n_condition_eff:<5}"
            )
        print(f"  {key:<14} " + " ".join(cells))
        if key != subject.key:
            frames.append(
                to_frame(corrected(evaluate(ap, label_names=(primary_label,))), key, "full")
            )

    # ---- 5. walk-forward --------------------------------------------------
    _rule(f"5. WALK-FORWARD — in-sample (pre-{C.WALK_FORWARD_SPLIT}) vs out-of-sample")
    cutoff = float(np.datetime64(C.WALK_FORWARD_SPLIT, "ms").astype(np.float64))
    ts = subject.panel["ts"].to_numpy().astype(np.float64)
    in_s, out_s = ts < cutoff, ts >= cutoff
    print(
        f"\n  in-sample {int(in_s.sum()):,} bars, out-of-sample {int(out_s.sum()):,} bars.\n"
        "  Only the out-of-sample column may carry a claim. The in-sample column is the one the\n"
        "  specification was allowed to see, so agreement between them is the whole test."
    )
    is_res = {r.condition: r for r in evaluate(subject, window=in_s, label_names=(primary_label,))}
    oos_res = {
        r.condition: r for r in evaluate(subject, window=out_s, label_names=(primary_label,))
    }
    frames.append(to_frame(corrected(list(is_res.values())), subject.key, "in_sample"))
    frames.append(to_frame(corrected(list(oos_res.values())), subject.key, "out_of_sample"))

    print(f"\n  {'predictor':<34} {'in-sample':>26} {'out-of-sample':>30}")
    for name in sorted(set(is_res) & set(oos_res), key=lambda k: -abs(oos_res[k].difference)):
        i, o = is_res[name], oos_res[name]
        od = o.interval_difference
        print(
            f"  {name:<34} {i.difference:>+9.1%} (n={i.n_condition_eff:>4})  "
            f"{o.difference:>+9.1%} [{od.lower:>+6.1%},{od.upper:>+6.1%}] "
            f"(n={o.n_condition_eff:>4})"
        )

    # ---- 6. confluence ----------------------------------------------------
    _rule("6. CONFLUENCE — does stacking independent conditions produce a monotone improvement?")
    print(
        f"\n  Members: {', '.join(C.CONFLUENCE_MEMBERS)}\n"
        "  A rising staircase is a mechanism. One bright bin is multiplicity."
    )
    for lab_name in (*labels.POST_HOC, primary_label, "top10pct_30d"):
        try:
            print("  " + confluence(subject, lab_name).line())
        except (DataError, KeyError) as exc:
            print(f"  {lab_name:<18} not computable: {exc}")

    # ---- 7. cross-asset sign consistency ----------------------------------
    _rule("7. DIRECTIONAL CONSISTENCY ACROSS ASSETS — where the real power in this study is")
    print(
        "\n  No single cell above has the sample size to clear zero. Direction is cheaper to\n"
        "  measure: if a family carried no information, its mean lift would point up or down at\n"
        "  random on each asset. Assets are the replicates; the predictors inside a family are\n"
        "  not independent of one another and are averaged rather than counted.\n"
        "\n  Run at three horizons, because the answer differs between them and picking one would\n"
        "  be a choice the data does not license. The 7d and 14d rows are where the sample has\n"
        "  enough independent windows to mean anything; the 30d row is shown so its instability\n"
        "  is visible rather than hidden."
    )
    for lab_name in (*labels.POST_HOC, primary_label):
        lab = subject.labels.get(lab_name)
        n_eff = labels.effective_n(lab) if lab else 0.0
        print(f"\n  [{lab_name}]  n_eff {n_eff:.0f}")
        for family in C.FAMILIES:
            try:
                print(sign_consistency(panels, family, lab_name).line())
            except DataError as exc:
                print(f"  {family:<14} not computable: {exc}")
    print(
        "\n  CAVEAT, and it is not small: crypto assets are far from independent. The sign test\n"
        "  assumes they are, so its p-values are optimistic — most so for [seasonal], where every\n"
        "  asset shares the same calendar and a Q4 rally is one market event counted five times.\n"
        "  Treat these as a consistency check, not as a test."
    )

    # ---- 8. the two named claims ------------------------------------------
    _rule("8. THE TWO CLAIMS UNDER DIRECT TEST")
    claim = next((r for r in all_results if r.condition == C.CLAIM_MARKET_BREAKOUT), None)
    print('\n  A. "The whole crypto market is on the verge of a breakout"')
    print(f"     operationalised as {C.CLAIM_MARKET_BREAKOUT} (half the majors compressed at once)")
    if claim is None:
        print("     NOT COMPUTABLE on this sample")
    else:
        d = claim.interval_difference
        print(
            f"     P(+20% in 30d | market compressed) = {claim.rate_condition:.1%}\n"
            f"     P(+20% in 30d | not)               = {claim.rate_complement:.1%}\n"
            f"     difference {claim.difference:+.1%} [{d.lower:+.1%}, {d.upper:+.1%}] "
            f"at n_eff={claim.n_condition_eff}, p={claim.pvalue:.3g}"
        )
    print('\n  B. "Multiple technical factors reinforcing the upside bias"')
    print("     operationalised as: does the pump rate rise monotonically with how many")
    print("     independent conditions hold at once?  (see section 6 above)")

    combined = pl.concat([f for f in frames if f.height], how="vertical")
    combined.write_parquet(OUT / f"lifts_{timeframe}.parquet")
    print(f"\nwrote {combined.height:,} result rows -> {OUT / f'lifts_{timeframe}.parquet'}")
    return combined


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="XRP pump-condition study")
    ap.add_argument("--timeframe", default=C.PRIMARY_TIMEFRAME, choices=list(C.BARS_PER_DAY))
    ap.add_argument("--quick", action="store_true", help="skip the secondary label tables")
    ap.add_argument("--assets", default=",".join(C.PRICE_KEYS))
    args = ap.parse_args(argv)

    t0 = time.time()
    run(args.timeframe, assets=tuple(args.assets.split(",")), quick=args.quick)
    print(f"done in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

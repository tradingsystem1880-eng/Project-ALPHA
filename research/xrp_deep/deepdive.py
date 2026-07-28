"""The named analyses the battery cannot express: cycles, lead-lag, seasonality, confluence.

The conditional-lift battery answers "does state X precede outcome Y?". Four questions do not fit
that shape and are worth asking directly:

1. **Cycles.** Is there a periodic component in XRP at all? Every finite noisy series has a
   spectral peak, so the number that decides the answer is the share of power in that peak, not its
   period. Reported against a matched-length random-walk reference, because a peak explaining 4% of
   detrended power is what noise looks like.
2. **Lead-lag with BTC.** Does BTC lead XRP by a measurable number of bars, or is the relationship
   contemporaneous? A genuine lead is tradeable; a contemporaneous correlation of 0.87 is not, and
   the two are routinely confused.
3. **Seasonality.** Month, weekday and day-of-month effects, each with the number of *independent*
   observations behind it. Nine years is nine January observations, not 279 January days, and that
   single correction is what separates a seasonality study from an astrology column.
4. **Confluence.** The direct test of "multiple technical factors reinforcing the bias": score each
   bar by how many bullish conditions hold, and ask whether the forward hit rate rises
   *monotonically* with the count. This is the sharpest available test of the confluence idea, and
   it has a specific failure mode worth naming — stacking correlated conditions produces a smooth
   rising curve for free, because the high-count bars are simply the strongest-trend bars.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from alpha_patterns import (
    cross_correlation_lags,
    dominant_cycle,
    hurst_exponent,
    hurst_random_walk_reference,
    log_returns,
    variance_ratio,
)
from alpha_validation import monotonic_trend, wilson_interval
from research.xrp_deep import config as C
from research.xrp_deep.conditions import build_conditions, screen
from research.xrp_deep.outcomes import build_outcomes
from research.xrp_deep.panel import Panel, build_panel

OUT = Path(__file__).resolve().parent / "out"

#: Bullish-side conditions for the confluence stack, chosen before the counts were computed.
#: One per family where the family has an unambiguous bullish reading — deliberately not the
#: best-performing ones, which would make the stack a restatement of the survivor list.
CONFLUENCE_BULLISH: tuple[str, ...] = (
    "ma_price_above_200",
    "macd_hist_positive",
    "rsi_above_50",
    "stoch_bull_cross",
    "adx_bull_di",
    "obv_rising",
    "cmf_positive",
    "ichi_above_cloud",
    "donch_upper_half",
    "ratio_above_ma",
)


def cycle_analysis(panel: Panel) -> dict[str, object]:
    """Spectral and memory structure, each against its own null."""
    close = panel.bars.close
    logp = np.log(close)
    rets = log_returns(close)
    finite_rets = rets[np.isfinite(rets)]

    cycle = dominant_cycle(logp, min_period=8)
    # The reference: the same estimator on random walks of the same length. Without it, "the
    # dominant cycle is 407 days" sounds like a finding rather than like the arithmetic guarantee
    # it usually is.
    rng = np.random.default_rng(C.SEED)
    null_shares = [
        dominant_cycle(np.cumsum(rng.standard_normal(logp.size)), min_period=8).power_share
        for _ in range(200)
    ]
    null_shares_arr = np.asarray([s for s in null_shares if np.isfinite(s)])

    h_mean, h_sd = hurst_random_walk_reference(min(len(finite_rets), 2048), trials=100, seed=C.SEED)
    h = hurst_exponent(finite_rets)

    vrs = {q: variance_ratio(logp, q=q) for q in (2, 5, 10, 20, 60)}
    return {
        "dominant_period_bars": cycle.period_bars,
        "power_share": cycle.power_share,
        "power_share_null_median": float(np.median(null_shares_arr)),
        "power_share_null_p95": float(np.percentile(null_shares_arr, 95)),
        "power_share_beats_null": bool(cycle.power_share > np.percentile(null_shares_arr, 95)),
        "hurst": h,
        "hurst_null_mean": h_mean,
        "hurst_null_sd": h_sd,
        "hurst_z": (h - h_mean) / h_sd if np.isfinite(h_sd) and h_sd > 0 else float("nan"),
        "variance_ratios": {
            str(q): {"ratio": v.ratio, "z": v.z_score, "verdict": v.verdict} for q, v in vrs.items()
        },
    }


def leadlag_analysis(panel: Panel) -> dict[str, object]:
    """Cross-correlation of XRP against BTC/ETH/SOL at lags, and where the peak sits.

    Sign convention follows ``cross_correlation_lags``: a **negative** lag correlates XRP's present
    against the leader's *past*, which is the only direction that could be traded. A peak at lag 0
    means the two move together and there is nothing to act on, however large the correlation.
    """
    rets = log_returns(panel.bars.close)
    out: dict[str, object] = {}
    for key in C.CONTROL_KEYS:
        other = panel.features.get(f"{key.lower()}_ret_1")
        if other is None:
            continue
        both = np.isfinite(rets) & np.isfinite(other)
        if int(both.sum()) < 500:
            continue
        result = cross_correlation_lags(rets[both], other[both], max_lag=10)
        profile = {
            int(lag): float(c) for lag, c in zip(result.lags, result.correlations, strict=True)
        }
        out[key] = {
            "peak_lag": int(result.best_lag),
            "peak_correlation": float(result.best_correlation),
            "contemporaneous": profile.get(0, float("nan")),
            "n": int(result.n_observations),
            "leader_actually_leads": bool(result.best_lag < 0),
            "profile": {str(k): v for k, v in profile.items()},
        }
    return out


def _independent_blocks(selected: np.ndarray, horizon: int) -> int:
    """Independent forward windows available inside a selection of bars.

    Two selected bars closer together than the forward horizon share almost all of the future they
    are measuring, so they are one observation rather than two. But merely *counting clusters* is
    too harsh for a selection that recurs often: every Monday is 7 days from the next, so all 462
    of them collapse into one cluster, and calling that a single observation is plainly wrong when
    the cluster spans nine years.

    So each cluster contributes the number of non-overlapping windows that fit inside **its own
    span**, and the totals are summed. A 31-day January cluster yields 2; the one enormous cluster
    of Mondays spanning 3,262 days yields ~109. The two seasonal questions get the two different
    answers they should: nine Januaries carry almost no information about January, while Mondays
    carry as much information as any other slice of the same span.
    """
    idx = np.flatnonzero(selected)
    if idx.size == 0:
        return 0
    breaks = np.flatnonzero(np.diff(idx) > horizon)
    starts = np.concatenate(([0], breaks + 1))
    ends = np.concatenate((breaks, [idx.size - 1]))
    total = 0
    for s, e in zip(starts, ends, strict=True):
        span = int(idx[e] - idx[s]) + 1
        total += max(1, -(-span // horizon))  # ceil division
    return min(total, int(idx.size))


def seasonality_analysis(panel: Panel) -> dict[str, object]:
    """Month, weekday and turn-of-month forward hit rates with honest independent counts."""
    outcomes = build_outcomes(panel)
    outcome = outcomes[f"fwd_positive_{C.PRIMARY_HORIZON}"]
    month = panel.features["month"]
    weekday = panel.features["weekday"]

    def _table(labels: np.ndarray, names: dict[int, str], overlap: int) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for value, name in sorted(names.items()):
            sel = (labels == value) & outcome.valid
            n = int(sel.sum())
            if n < 30:
                continue
            hits = int(outcome.hit[sel].sum())
            ci = wilson_interval(hits, n)
            # The number that matters: 279 January days across nine years are **nine** independent
            # Januaries, and quoting the interval on 279 is the standard seasonality error.
            #
            # The whole-panel formula (span / horizon) is wrong here and gives 108.7 for every
            # month, which is not even a seasonal quantity — it does not vary with the month. A
            # seasonal selection is not spread evenly across the span; it arrives in one clump per
            # year, and with a 30-day forward window a 31-day clump is worth about one observation.
            # Counting the clumps is the honest denominator, and it takes September from
            # "significantly above base rate" to "nine observations, interval spans everything".
            n_eff = float(_independent_blocks(sel, overlap))
            eff_hits = int(round(n_eff * hits / n)) if n else 0
            eff_ci = wilson_interval(eff_hits, max(1, int(round(n_eff))))
            rows.append(
                {
                    "name": name,
                    "n": n,
                    "n_effective": n_eff,
                    "rate": hits / n,
                    "ci": [ci.lower, ci.upper],
                    "ci_effective": [eff_ci.lower, eff_ci.upper],
                }
            )
        return rows

    months = {
        i: n
        for i, n in enumerate(
            ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        )
        if i
    }
    days = dict(enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]))
    return {
        "base_rate": outcome.base_rate,
        "months": _table(month, months, C.PRIMARY_HORIZON),
        "weekdays": _table(weekday, days, C.PRIMARY_HORIZON),
    }


@dataclass(frozen=True)
class ConfluenceRow:
    count: int
    n: int
    n_effective: float
    rate: float
    lower: float
    upper: float


def confluence_analysis(panel: Panel) -> dict[str, object]:
    """Does stacking bullish conditions raise the forward hit rate monotonically?"""
    conditions, _ = screen(build_conditions(panel))
    by_key = {c.key: c for c in conditions}
    used = [by_key[k] for k in CONFLUENCE_BULLISH if k in by_key]
    if len(used) < 5:
        return {"available": False, "reason": f"only {len(used)} of the stack conditions exist"}

    valid = np.ones(len(panel), dtype=bool)
    for c in used:
        valid &= c.valid
    score = np.zeros(len(panel), dtype=int)
    for c in used:
        score += c.mask.astype(int)

    outcomes = build_outcomes(panel)
    outcome = outcomes[f"fwd_positive_{C.PRIMARY_HORIZON}"]
    valid &= outcome.valid

    rows: list[ConfluenceRow] = []
    rates: list[float] = []
    counts: list[int] = []
    for k in range(len(used) + 1):
        sel = (score == k) & valid
        n = int(sel.sum())
        if n < 30:
            continue
        hits = int(outcome.hit[sel].sum())
        ci = wilson_interval(hits, n)
        n_eff = float(_independent_blocks(sel, C.PRIMARY_HORIZON))
        rows.append(ConfluenceRow(k, n, n_eff, hits / n, ci.lower, ci.upper))
        rates.append(hits / n)
        counts.append(n)

    trend_z = monotonic_trend(rates, counts) if len(rates) >= 3 else float("nan")
    # Deflate by re-running the trend test on the independent-block counts rather than by scaling
    # the nominal z. Dividing by sqrt(overlap) assumes every bucket is overlapped equally, and
    # these are not: the extreme buckets (all-bearish, all-bullish) arrive in short bursts and the
    # middle ones are spread across the whole span. Passing the per-bucket n_eff to the same
    # Cochran-Armitage statistic uses each bucket's own information content.
    eff_counts = [int(round(r.n_effective)) for r in rows]
    deflated = monotonic_trend(rates, eff_counts) if len(rates) >= 3 else float("nan")
    return {
        "available": True,
        "n_conditions": len(used),
        "conditions": [c.key for c in used],
        "rows": [
            {
                "count": r.count,
                "n": r.n,
                "n_effective": r.n_effective,
                "rate": r.rate,
                "ci": [r.lower, r.upper],
            }
            for r in rows
        ],
        "trend_z_nominal": trend_z,
        "trend_z_deflated": deflated,
        "significant_after_deflation": bool(abs(deflated) > 1.96)
        if np.isfinite(deflated)
        else False,
    }


def main() -> int:  # noqa: PLR0915 — a report, printed in one pass
    panel = build_panel()

    print("=" * 96)
    print("1. CYCLES AND MEMORY")
    print("=" * 96)
    cyc = cycle_analysis(panel)
    print(f"\n  dominant period       {cyc['dominant_period_bars']:.0f} days")
    print(f"  power share           {cyc['power_share']:.1%} of detrended power")
    print(
        f"  null median / p95     {cyc['power_share_null_median']:.1%} / "
        f"{cyc['power_share_null_p95']:.1%}   (random walks, same length)"
    )
    print(f"  beats the null?       {'YES' if cyc['power_share_beats_null'] else 'NO'}")
    print(f"\n  Hurst (returns)       {cyc['hurst']:.3f}")
    print(
        f"  no-memory null        {cyc['hurst_null_mean']:.3f} +/- {cyc['hurst_null_sd']:.3f}"
        f"   -> z = {cyc['hurst_z']:+.2f}"
    )
    print("\n  variance ratio (>1 trending, <1 mean-reverting, |z|>2 to matter):")
    for q, v in cyc["variance_ratios"].items():  # type: ignore[union-attr]
        print(f"    q={q:>3}  ratio {v['ratio']:.3f}  z {v['z']:+6.2f}  {v['verdict']}")

    print("\n" + "=" * 96)
    print("2. LEAD-LAG (NEGATIVE lag = the other asset leads XRP — the tradeable direction)")
    print("=" * 96 + "\n")
    for key, info in leadlag_analysis(panel).items():
        print(
            f"  {key:5} peak at lag {info['peak_lag']:+d} (r={info['peak_correlation']:+.3f}), "
            f"contemporaneous r={info['contemporaneous']:+.3f}, n={info['n']}"
        )
        profile = info["profile"]
        near = "  ".join(f"{k:>+3}:{profile[str(k)]:+.3f}" for k in (-3, -2, -1, 0, 1, 2, 3))
        print(f"        {near}")

    print("\n" + "=" * 96)
    print("3. SEASONALITY (30-day forward positive rate)")
    print("=" * 96)
    seas = seasonality_analysis(panel)
    print(f"\n  base rate {seas['base_rate']:.1%}\n")
    print(
        f"  {'':6} {'n':>5} {'n_eff':>7} {'rate':>7}  {'95% CI (nominal)':>20}  {'CI at n_eff':>20}"
    )
    for group in ("months", "weekdays"):
        for row in seas[group]:  # type: ignore[union-attr]
            print(
                f"  {row['name']:6} {row['n']:>5} {row['n_effective']:>7.1f} {row['rate']:>6.1%}"
                f"  [{row['ci'][0]:>6.1%},{row['ci'][1]:>6.1%}]"
                f"  [{row['ci_effective'][0]:>6.1%},{row['ci_effective'][1]:>6.1%}]"
            )
        print()

    print("=" * 96)
    print("4. CONFLUENCE — does stacking bullish conditions help?")
    print("=" * 96)
    conf = confluence_analysis(panel)
    if not conf.get("available"):
        print(f"\n  unavailable: {conf.get('reason')}")
    else:
        print(f"\n  stacking {conf['n_conditions']} bullish conditions, one per family\n")
        print(f"  {'count':>5} {'n':>6} {'n_eff':>7} {'rate':>7}  95% CI")
        for row in conf["rows"]:  # type: ignore[union-attr]
            print(
                f"  {row['count']:>5} {row['n']:>6} {row['n_effective']:>7.1f} "
                f"{row['rate']:>6.1%}  [{row['ci'][0]:>6.1%},{row['ci'][1]:>6.1%}]"
            )
        print(f"\n  monotonic trend z (nominal counts)  {conf['trend_z_nominal']:+.2f}")
        print(f"  same test on independent-block counts  {conf['trend_z_deflated']:+.2f}")
        print(
            f"  significant on independent counts?    "
            f"{'YES' if conf['significant_after_deflation'] else 'NO'}"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "deepdive.json").write_text(
        json.dumps(
            {
                "cycles": cyc,
                "leadlag": leadlag_analysis(panel),
                "seasonality": seas,
                "confluence": conf,
            },
            indent=2,
            default=float,
        )
    )
    print(f"\nwrote {OUT / 'deepdive.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

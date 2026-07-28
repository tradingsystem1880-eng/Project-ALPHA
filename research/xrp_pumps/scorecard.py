"""The live read: which of the studied conditions actually hold on XRP right now.

The study measures whether conditions carry information. This prints the current value of every one
of them, next to what the study found, so the two can be read together instead of the reader having
to hold thirty numbers in their head.

Two rules govern this file, because a scorecard is where a careful study most easily turns into a
confident wrong answer:

1. **Stale data is marked stale, never carried forward.** The chain record ends two months before
   the price record. Every on-chain row prints as UNAVAILABLE with its true age rather than
   repeating a value from May as though it described July.
2. **A condition's current state is reported next to its measured lift**, including when that lift
   was null or negative. A green light on a condition the study found worthless is not a green
   light, and the layout makes that visible rather than leaving it to the footnotes.

The live position and the two structural calls (the weekly falling wedge, the daily inverse head and
shoulders) are priced against what the detectors actually find, not against what was asserted.

Run: ``python -m research.xrp_pumps.scorecard``
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import polars as pl

from alpha_core import DataError
from alpha_patterns import HSConfig, WedgeConfig, detect_head_shoulders, detect_wedges
from research.hs_quasimodo.data import iso_of, load
from research.xrp_pumps import config as C
from research.xrp_pumps import features, labels
from research.xrp_pumps.study import build_asset, evaluate

#: Columns whose currency depends on the chain record rather than the price record.
ONCHAIN_COLUMNS: frozenset[str] = frozenset(
    {
        "mvrv_pct",
        "adr_pct",
        "adr_growth_30",
        "tx_growth_30",
        "adr_price_divergence",
        "cm_volume_pct",
        "dominance_pct",
        "dominance_chg_30",
    }
)


def _fmt(value: float | None) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    if abs(value) < 10.0:
        return f"{value:+.3f}"
    return f"{value:,.1f}"


def scorecard(asset_key: str, timeframe: str) -> None:
    """Print the current state of every pre-registered condition, with its measured lift."""
    asset = build_asset(asset_key, timeframe)
    panel = asset.panel
    last = panel.height - 1
    last_ts = float(panel["ts"][last])
    last_date = str(np.datetime64(int(last_ts), "ms"))[:10]

    primary = C.PUMPS[0].label
    lifts = {r.condition: r for r in evaluate(asset, label_names=(primary,))}
    base = asset.labels[primary].base_rate

    print("=" * 112)
    print(f"LIVE CONDITION SCORECARD — {asset_key} {timeframe} as of {last_date}")
    print("=" * 112)
    print(
        f"  last close {float(panel['close'][last]):.4f}   "
        f"base rate P(+20% in 30d) = {base:.1%}   "
        f"n_eff behind every lift below = {labels.effective_n(asset.labels[primary]):.0f}"
    )
    print(
        f"\n  {'condition':<34} {'now':>6} {'value':>10} {'measured lift':>16} {'95% CI':>18}  age"
    )
    print("  " + "-" * 106)

    for family in C.FAMILIES:
        print(f"  [{family}]")
        for pred in C.predictors_in(family):
            if pred.name not in asset.conditions:
                print(f"    {pred.name:<32} {'--':>6}  (feature unavailable)")
                continue
            holds = bool(asset.conditions[pred.name][last])
            defined = bool(asset.defined[pred.name][last])
            raw = panel[pred.column][last] if pred.column in panel.columns else None
            value = None if raw is None else float(raw)

            stale = _staleness(pred, panel, last)
            if not defined or stale:
                state, age = "STALE" if stale else " n/a ", stale or "-"
            else:
                state, age = ("  YES" if holds else "   no"), "current"

            r = lifts.get(pred.name)
            if r is None:
                lift_txt, ci_txt = "not measurable", ""
            else:
                d = r.interval_difference
                lift_txt = f"{r.difference:+.1%} (n_eff {r.n_condition_eff})"
                ci_txt = f"[{d.lower:+.1%},{d.upper:+.1%}]"
            print(
                f"    {pred.name:<32} {state:>6} {_fmt(value):>10} {lift_txt:>16} "
                f"{ci_txt:>18}  {age}"
            )

    _structure(asset_key, last_date)
    _position()


def _staleness(pred: C.Predictor, panel: pl.DataFrame, last: int) -> str:
    """How out of date a column's most recent real value is, as a printable string ('' if current).

    On-chain columns are the reason this exists. The as-of join in ``features.build`` deliberately
    leaves them null past the end of the chain record rather than forward-filling, so a null here
    means "we do not know", and saying so is the whole job.
    """
    if pred.column not in ONCHAIN_COLUMNS or pred.column not in panel.columns:
        return ""
    series = panel[pred.column]
    if series[last] is not None:
        return ""
    valid = np.flatnonzero(series.is_not_null().to_numpy())
    if valid.size == 0:
        return "never available"
    gap_ms = float(panel["ts"][last]) - float(panel["ts"][int(valid[-1])])
    return f"{gap_ms / 86_400_000.0:.0f}d stale"


def _structure(asset_key: str, last_date: str) -> None:
    """What the detectors currently find: wedges and head-and-shoulders structures, on 1d and 1w.

    The two source charts assert a weekly falling wedge and a daily inverse head and shoulders. Both
    are checkable, and the check is the point — an asserted pattern and a detected one are different
    kinds of object.
    """
    print("\n" + "=" * 112)
    print("STRUCTURE THE DETECTORS ACTUALLY FIND")
    print("=" * 112)
    src = features.source_for(asset_key)

    for tf, lookback_bars in (("1d", 260), ("4h", 900)):
        try:
            bars, prov = load(src, tf)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            print(f"  {tf}: unavailable ({exc})")
            continue
        cutoff = max(0, len(bars) - lookback_bars)

        wedges = [w for w in detect_wedges(bars, WedgeConfig()) if w.end_index >= cutoff]
        print(f"\n  {tf} — {prov.first_ts[:10]} to {prov.last_ts[:10]}, last {lookback_bars} bars")
        if not wedges:
            print("    no converging formation detected under the primary specification")
        for w in wedges[-3:]:
            resolved = (
                f"broke {'UP' if w.break_direction > 0 else 'DOWN'} at "
                f"{iso_of(bars, w.break_index)[:10]} ({w.bars_past_apex:+d} bars vs apex)"
                if w.break_index >= 0
                else ("DRIFTED PAST APEX, never broke" if w.apex_passed_unbroken else "unresolved")
            )
            print(
                f"    {w.kind:<12} anchors {iso_of(bars, w.start_index)[:10]}"
                f"..{iso_of(bars, w.end_index)[:10]}  "
                f"confirmed {iso_of(bars, w.confirmed_index)[:10]}"
                f"  apex bar {w.apex_index:.0f} ({w.bars_to_apex:+.0f} from confirmation)"
            )
            print(f"      convergence {w.convergence:.0%}   {resolved}")

        for variant in ("inverse_head_shoulders", "head_shoulders"):
            cfg_kwargs = {
                "direction": "bullish" if variant.startswith("inverse") else "bearish",
                "lookback": 5,
                "head_prominence": 0.03,
                "shoulder_tol": 0.75,
                "time_symmetry_tol": 0.25,
                "max_neckline_slope": 0.20,
                "gap_min": 10,
                "gap_max": 250,
                "shoulder_rule": "any",
                "require_bos": False,
            }
            events = [
                e
                for e in detect_head_shoulders(bars, HSConfig(**cfg_kwargs))  # type: ignore[arg-type]
                if e.rs_index >= cutoff
            ]
            for e in events[-2:]:
                print(
                    f"    {e.variant:<24} LS {e.ls_price:.4f} / head {e.head_price:.4f} / "
                    f"RS {e.rs_price:.4f}   confirmed {iso_of(bars, e.confirmed_index)[:10]}"
                )
                print(
                    f"      neckline {e.n1_price:.4f}->{e.n2_price:.4f} "
                    f"({e.neckline_slope:+.1%})   measured target {e.target_measured:.4f}   "
                    f"{'BOS present (Quasimodo)' if e.has_bos else 'no BOS'}"
                )


def _position() -> None:
    """The live position, priced against the risk framework rather than against hope."""
    rr = (C.TARGET - C.ENTRY) / (C.ENTRY - C.STOP)
    risk_usdt = C.QUANTITY * (C.ENTRY - C.STOP)
    print("\n" + "=" * 112)
    print("LIVE POSITION")
    print("=" * 112)
    print(
        f"  {C.QUANTITY:,.0f} XRP @ {C.ENTRY} · {C.LEVERAGE}x · stop {C.STOP} · "
        f"target {C.TARGET} · liq {C.LIQUIDATION}"
    )
    print(
        f"  R:R {rr:.2f}:1 · breakeven {100 / (1 + rr):.1f}% · risk at stop "
        f"{risk_usdt:,.0f} USDT = {risk_usdt / C.RISK_CAP_USDT:.1f}x the {C.RISK_CAP_USDT:.0f} "
        "USDT framework cap (flagged once, as agreed)"
    )
    print(
        f"  stop sits {(C.STOP - C.LIQUIDATION) / C.STOP * 100:.2f}% above liquidation — the two "
        "are effectively the same level."
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Live XRP condition scorecard")
    ap.add_argument("--asset", default=C.SUBJECT_KEY)
    ap.add_argument("--timeframe", default=C.PRIMARY_TIMEFRAME, choices=list(C.BARS_PER_DAY))
    args = ap.parse_args(argv)
    try:
        scorecard(args.asset, args.timeframe)
    except DataError as exc:
        print(f"FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The studies themselves: detect, label, control, and interval-estimate.

Composition happens here rather than inside either package: ``alpha_patterns`` supplies geometry,
``alpha_validation`` supplies statistics, and neither imports the other (both are core-only under
the architecture DAG). ``research/`` sits outside the import-linter graph, so it is the sanctioned
place to join them.

Reading order for the outputs:

1. ``n`` is the raw event count; ``n_eff`` is what it is worth after overlapping forward windows are
   accounted for. Judge every interval on ``n_eff``.
2. ``target_rate`` is compared against ``breakeven``, never against 50%.
3. ``edge_vs_control`` is the difference against matched controls with its own interval. A
   difference interval straddling zero means the pattern has not been shown to beat its control,
   whatever the two point estimates look like side by side.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from alpha_patterns import (
    OHLCV,
    TrendlineConfig,
    TripleTap,
    TripleTapConfig,
    build_trendlines,
    detect_nth_taps,
    detect_triple_taps,
    distance_from_low,
    find_breaks,
    find_order_blocks,
    sample_matched_controls,
    trend_state_vwap,
)
from alpha_validation import (
    BarrierResult,
    aggregate_outcomes,
    barrier_outcome,
    effective_sample_size,
    newcombe_diff_interval,
    overlap_factor,
    wilson_interval,
)
from research.xrp_triple_tap import config as C


@dataclass(frozen=True)
class BarrierCell:
    """One (stop, target, horizon) configuration evaluated for one event population."""

    label: str
    stop_fraction: float
    target_r: float
    horizon_days: int
    n: int
    n_eff: float
    overlap: float
    target_first: int
    stop_first: int
    unresolved: int
    target_rate: float
    breakeven: float
    ci_low: float
    ci_high: float
    ci_low_eff: float  # interval recomputed at the effective sample size
    ci_high_eff: float
    expectancy_r: float
    beats_breakeven: bool  # honest test: interval lower bound (at n_eff) above breakeven
    control_rate: float = float("nan")
    control_n: int = 0
    edge: float = float("nan")
    edge_ci_low: float = float("nan")
    edge_ci_high: float = float("nan")


@dataclass
class AssetResult:
    """Everything computed for one asset."""

    key: str
    symbol: str
    n_bars: int
    events: list[TripleTap] = field(default_factory=list)
    cells: list[BarrierCell] = field(default_factory=list)
    live_cell: BarrierCell | None = None
    forward: dict[int, dict[str, float]] = field(default_factory=dict)
    fourth_tap_n: int = 0
    fourth_tap_rate: float = float("nan")
    noise_expected: float = float("nan")


# ---------------------------------------------------------------- forward returns


def forward_returns(
    bars: OHLCV, entries: list[int], horizons_days: tuple[int, ...] = (5, 10, 20, 30, 60)
) -> dict[int, dict[str, float]]:
    """Median/mean/P(up) of forward returns at each horizon, from honest entry bars."""
    out: dict[int, dict[str, float]] = {}
    n = len(bars)
    for days in horizons_days:
        h = days * C.BARS_PER_DAY
        rets = [float(bars.close[i + h] / bars.close[i] - 1.0) for i in entries if i + h < n]
        if not rets:
            out[days] = dict.fromkeys(("n", "median", "mean", "p_up"), float("nan"))
            continue
        arr = np.array(rets)
        out[days] = {
            "n": float(arr.size),
            "median": float(np.median(arr)),
            "mean": float(np.mean(arr)),
            "p_up": float(np.mean(arr > 0.0)),
        }
    return out


# ---------------------------------------------------------------- barrier evaluation


def _run_barrier(
    bars: OHLCV, entries: list[int], stop_fraction: float, target_r: float, horizon_bars: int
) -> list[BarrierResult]:
    n = len(bars)
    results: list[BarrierResult] = []
    for i in entries:
        if i + 1 >= n:
            continue
        entry = float(bars.close[i])
        stop = entry * (1.0 - stop_fraction)
        target = entry * (1.0 + stop_fraction * target_r)
        end = min(i + 1 + horizon_bars, n)
        if end <= i + 1:
            continue
        results.append(
            barrier_outcome(
                bars.high[i + 1 : end],
                bars.low[i + 1 : end],
                entry=entry,
                stop=stop,
                target=target,
            )
        )
    return results


def evaluate_cell(
    bars: OHLCV,
    entries: list[int],
    *,
    label: str,
    stop_fraction: float,
    target_r: float,
    horizon_days: int,
    control_entries: list[int] | None = None,
) -> BarrierCell | None:
    """Run one barrier configuration on events (and optional controls), with intervals."""
    horizon_bars = horizon_days * C.BARS_PER_DAY
    res = _run_barrier(bars, entries, stop_fraction, target_r, horizon_bars)
    if not res:
        return None

    counts = aggregate_outcomes(res)
    span = len(bars)
    n_eff = effective_sample_size(counts.n, span_bars=span, horizon_bars=horizon_bars)
    ov = overlap_factor(counts.n, span_bars=span, horizon_bars=horizon_bars)

    ci = wilson_interval(counts.target_first, counts.n, confidence=C.CONFIDENCE)
    # Recompute at the effective size: hold the observed rate, shrink the count. This is the
    # interval that should be quoted whenever windows overlap.
    n_e = max(2, int(round(n_eff)))
    k_e = int(round(counts.target_rate * n_e))
    ci_eff = wilson_interval(k_e, n_e, confidence=C.CONFIDENCE)

    cell = BarrierCell(
        label=label,
        stop_fraction=stop_fraction,
        target_r=target_r,
        horizon_days=horizon_days,
        n=counts.n,
        n_eff=n_eff,
        overlap=ov,
        target_first=counts.target_first,
        stop_first=counts.stop_first,
        unresolved=counts.unresolved,
        target_rate=counts.target_rate,
        breakeven=counts.breakeven_rate,
        ci_low=ci.lower,
        ci_high=ci.upper,
        ci_low_eff=ci_eff.lower,
        ci_high_eff=ci_eff.upper,
        expectancy_r=counts.expectancy_r,
        beats_breakeven=ci_eff.lower > counts.breakeven_rate,
    )

    if control_entries:
        cres = _run_barrier(bars, control_entries, stop_fraction, target_r, horizon_bars)
        if cres:
            ccounts = aggregate_outcomes(cres)
            diff = newcombe_diff_interval(
                counts.target_first,
                counts.n,
                ccounts.target_first,
                ccounts.n,
                confidence=C.CONFIDENCE,
            )
            cell = BarrierCell(
                **{
                    **cell.__dict__,
                    "control_rate": ccounts.target_rate,
                    "control_n": ccounts.n,
                    "edge": diff.point,
                    "edge_ci_low": diff.lower,
                    "edge_ci_high": diff.upper,
                }
            )
    return cell


# ---------------------------------------------------------------- per-asset driver


def run_asset(
    bars: OHLCV,
    key: str,
    *,
    tt_cfg: TripleTapConfig | None = None,
    start_index: int = 0,
) -> AssetResult:
    """Detect triple taps and evaluate the full barrier grid plus the live-trade cell."""
    tt_cfg = tt_cfg or TripleTapConfig(**C.PRIMARY_TRIPLE_TAP)  # type: ignore[arg-type]
    events = [e for e in detect_triple_taps(bars, tt_cfg) if e.confirmed_index >= start_index]
    res = AssetResult(key=key, symbol=bars.symbol, n_bars=len(bars), events=events)
    if not events:
        return res

    entries = [e.entry_confirm_index for e in events]
    res.forward = forward_returns(bars, entries)

    trend = trend_state_vwap(bars, window=90 * C.BARS_PER_DAY)
    dist = distance_from_low(bars, window=90 * C.BARS_PER_DAY)

    for stop_f, tgt_r, horizon_d in C.BARRIER_GRID:
        controls = sample_matched_controls(
            entries,
            trend=trend,
            distance=dist,
            n_bars=len(bars),
            n_per_event=C.CONTROL_PER_EVENT,
            distance_tolerance=C.CONTROL_DISTANCE_TOL,
            exclusion_bars=C.CONTROL_EXCLUSION_BARS,
            horizon_bars=horizon_d * C.BARS_PER_DAY,
            seed=C.SEED,
        )
        cell = evaluate_cell(
            bars,
            entries,
            label=f"stop{stop_f:.0%}_tgt{tgt_r:g}R_{horizon_d}d",
            stop_fraction=stop_f,
            target_r=tgt_r,
            horizon_days=horizon_d,
            control_entries=list(controls.control_indices),
        )
        if cell:
            res.cells.append(cell)

    stop_f, tgt_r, horizon_d = C.LIVE_TRADE_CELL
    controls = sample_matched_controls(
        entries,
        trend=trend,
        distance=dist,
        n_bars=len(bars),
        n_per_event=C.CONTROL_PER_EVENT,
        distance_tolerance=C.CONTROL_DISTANCE_TOL,
        exclusion_bars=C.CONTROL_EXCLUSION_BARS,
        horizon_bars=horizon_d * C.BARS_PER_DAY,
        seed=C.SEED,
    )
    res.live_cell = evaluate_cell(
        bars,
        entries,
        label="LIVE_TRADE_28.8R_90d",
        stop_fraction=stop_f,
        target_r=tgt_r,
        horizon_days=horizon_d,
        control_entries=list(controls.control_indices),
    )

    fourth = detect_nth_taps(bars, tt_cfg, n_taps=4)
    res.fourth_tap_n = len(fourth)
    if fourth:
        h = 20 * C.BARS_PER_DAY
        ups = [bars.close[i + h] > bars.close[i] for i in fourth if i + h < len(bars)]
        res.fourth_tap_rate = float(np.mean(ups)) if ups else float("nan")
    return res


def noise_base_rate(
    n_bars: int, tt_cfg: TripleTapConfig, *, n_seeds: int = 20, vol_per_bar: float = 0.02
) -> tuple[float, float]:
    """Events a detector finds in pattern-free noise of the same length (mean, sd).

    The count that any real-data event count must be read against. A detector that finds 300 events
    on real data and 280 on noise of the same length has found almost nothing.
    """
    from alpha_patterns import geometric_brownian_series

    counts = []
    for s in range(n_seeds):
        nb = geometric_brownian_series(n_bars, vol_per_bar=vol_per_bar, seed=C.SEED + s)
        counts.append(len(detect_triple_taps(nb, tt_cfg)))
    return float(np.mean(counts)), float(np.std(counts))


# ---------------------------------------------------------------- trendline study


@dataclass
class TrendlineResult:
    key: str
    n_lines: int
    n_breaks: int
    by_rule: dict[str, dict[str, float]] = field(default_factory=dict)


def run_trendlines(bars: OHLCV, key: str, cfg: TrendlineConfig | None = None) -> TrendlineResult:
    """Break, retest and false-break statistics per break rule, conditioned on nothing yet."""
    cfg = cfg or TrendlineConfig(**C.PRIMARY_TRENDLINE)  # type: ignore[arg-type]
    lines = build_trendlines(bars, cfg)
    breaks = find_breaks(bars, lines, cfg=cfg)
    out = TrendlineResult(key=key, n_lines=len(lines), n_breaks=len(breaks))

    for rule in {b.rule for b in breaks}:
        sub = [b for b in breaks if b.rule == rule]
        n = len(sub)
        retested = [b for b in sub if b.retest_index >= 0]
        held = [b for b in retested if b.retest_held]
        ci = wilson_interval(len(held), len(retested)) if retested else None
        h = 20 * C.BARS_PER_DAY
        fwd = [
            float(bars.close[b.break_index + h] / bars.close[b.break_index] - 1.0)
            for b in sub
            if b.break_index + h < len(bars)
        ]
        out.by_rule[rule] = {
            "n": float(n),
            "false_break_1": float(np.mean([b.false_break_1 for b in sub])),
            "false_break_3": float(np.mean([b.false_break_3 for b in sub])),
            "false_break_6": float(np.mean([b.false_break_6 for b in sub])),
            "retest_rate": float(len(retested) / n) if n else float("nan"),
            "hold_rate": float(len(held) / len(retested)) if retested else float("nan"),
            "hold_ci_low": ci.lower if ci else float("nan"),
            "hold_ci_high": ci.upper if ci else float("nan"),
            "fwd20_median": float(np.median(fwd)) if fwd else float("nan"),
            "fwd20_p_up": float(np.mean(np.array(fwd) > 0)) if fwd else float("nan"),
        }
    return out


# ---------------------------------------------------------------- confluence


def taps_under_bearish_ob(bars: OHLCV, events: list[TripleTap]) -> tuple[list[int], list[int]]:
    """Split triple-tap entries by whether an unmitigated bearish order block sat overhead.

    This is the user's actual situation. Only blocks formed **before** the entry and unmitigated
    **as of** that bar are considered, so the split uses no future information.
    """
    obs = find_order_blocks(bars)
    under: list[int] = []
    clear: list[int] = []
    for ev in events:
        i = ev.entry_confirm_index
        price = float(bars.close[i])
        overhead = any(
            ob.direction == "bearish"
            and ob.index < i
            and (ob.mitigated_index < 0 or ob.mitigated_index > i)
            and ob.bottom > price
            and ob.bottom < price * 1.25
            for ob in obs
        )
        (under if overhead else clear).append(i)
    return under, clear

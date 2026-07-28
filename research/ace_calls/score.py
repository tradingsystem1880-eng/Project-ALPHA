"""Score Ace's calls: what happened, what a matched control would have got, and what it adds up to.

A single call cannot be judged — markets move, and a bullish call in a bull week looks like genius.
A *record* can be judged, and this module builds one. Three comparisons run on every call:

1. **What actually happened.** Best and worst excursion in the called direction inside the horizon,
   plus where it stood at the horizon. If the call carried explicit levels, whether target was
   reached before stop — which is the only version that corresponds to a real trade.
2. **A matched control.** The same bet on random dates in the *same trend state* on the *same
   asset*. This is the comparison that matters: it asks whether the caller beat someone who knew
   only the regime and guessed. Being long during an uptrend is not a skill.
3. **A base rate.** The unconditional frequency of that move on that asset over that horizon.

Then the aggregate: hit rate with a Wilson interval, the difference against controls with a
Newcombe interval, and an equal-risk equity curve. Aggregation is where a call record either shows
something or does not, and where the sample size becomes impossible to ignore.

**Two things this deliberately will not do.** It will not score a call whose horizon has not
elapsed — judging a call early judges it on a window the caller did not choose. And it will not
silently mix data tiers: a call on a close-only series has its excursions measured without intraday
extremes, which understates them, and every such row is marked.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from alpha_core import DataError
from alpha_patterns import trend_state_vwap
from alpha_validation import ProportionInterval, newcombe_diff_interval, wilson_interval
from research.ace_calls.prices import Series, Tier, as_ohlcv, canonical, load_series, tier_for

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW = REPO_ROOT / "research" / "ace_calls" / "raw"
OUT = REPO_ROOT / "research" / "ace_calls" / "analysis"

# --------------------------------------------------------------------------- pre-registration
# Fixed before the screenshots were read. A call record is the easiest thing in this whole project
# to score favourably by accident: pick the horizon after seeing the outcomes and almost any caller
# can be made to look good or bad at will. So the primary specification is nailed down here, and
# HORIZON_SWEEP exists so the report must show every horizon rather than the flattering one.

#: Default "the call worked" threshold when no explicit target was given, as a fraction.
DEFAULT_HIT = 0.10
#: Default horizon when a call names no timeframe. Short enough to resolve, long enough to matter.
DEFAULT_HORIZON_DAYS = 30
#: Every horizon the record is reported at. The primary is DEFAULT_HORIZON_DAYS; the rest are a
#: mandatory sensitivity display, not a menu.
HORIZON_SWEEP: tuple[int, ...] = (7, 14, 30, 90)
CONTROLS_PER_CALL = 300
TREND_WINDOW_DAYS = 90
SEED = 7

#: Rules for turning a statement into a scoreable call, fixed in advance:
#:  * direction — explicit long/short, or unambiguous directional language, becomes long/short.
#:    Anything hedged ("could", "watching", "if it breaks") is NEUTRAL and is excluded from the
#:    scored record while staying in the corpus. Retrospective commentary is never a call.
#:  * asset — the named ticker. A market-wide claim is scored against BTC as the proxy, stated.
#:  * horizon — the call's own if it names one, else DEFAULT_HORIZON_DAYS.
#:  * a call is scored ONLY once its full horizon has elapsed in the data.

Status = str  # "resolved" | "unresolved" | "no_data" | "before_data" | "bad_call"


@dataclass(frozen=True)
class Call:
    """One dated directional call, traceable to the screenshot it came from."""

    file: str
    date: str  # ISO YYYY-MM-DD
    asset: str
    direction: str  # long | short
    horizon_days: int = DEFAULT_HORIZON_DAYS
    claim: str = ""
    entry: float | None = None
    stop: float | None = None
    target: float | None = None

    @property
    def sign(self) -> int:
        if self.direction not in ("long", "short"):
            raise DataError(f"{self.file}: direction must be long|short, got {self.direction!r}")
        return 1 if self.direction == "long" else -1

    @property
    def has_levels(self) -> bool:
        """Whether the call specified both a target and a stop — a tradeable instruction."""
        return self.target is not None and self.stop is not None


@dataclass(frozen=True)
class Score:
    """What happened after one call, next to what a control would have done."""

    call: Call
    status: Status
    tier: Tier
    reason: str = ""

    index: int = -1
    entry_price: float = float("nan")
    best: float = float("nan")  # best excursion, signed to the called direction
    worst: float = float("nan")  # worst excursion — the drawdown the caller sat through
    end: float = float("nan")  # where it stood at the horizon
    hit: bool = False  # reached DEFAULT_HIT in the called direction
    target_first: bool | None = None  # levels only: target before stop
    control_rate: float = float("nan")
    control_n: int = 0
    trend_state: str = ""  # uptrend | downtrend | range, as of the call bar
    days_elapsed: int = 0

    @property
    def scoreable(self) -> bool:
        return self.status == "resolved"

    def line(self) -> str:
        if not self.scoreable:
            return (
                f"  {self.call.date}  {self.call.asset:<6} {self.call.direction:<5} "
                f"{self.call.horizon_days:>3}d  {self.status.upper():<12} {self.reason}"
            )
        tf = {True: "TGT", False: "STP", None: " - "}[self.target_first]
        return (
            f"  {self.call.date}  {self.call.asset:<6} {self.call.direction:<5} "
            f"{self.call.horizon_days:>3}d  {self.entry_price:>10.4f}  "
            f"best {self.best:>+7.1%}  worst {self.worst:>+7.1%}  end {self.end:>+7.1%}  "
            f"{'HIT ' if self.hit else 'miss'} {tf}  ctrl {self.control_rate:>5.1%}"
            f"{'' if self.tier == 'ohlcv' else '  [close-only]'}"
        )


def _excursions(series: Series, i: int, horizon: int, sign: int) -> tuple[float, float, float]:
    """Best, worst and end excursion over the next ``horizon`` bars, signed to the direction."""
    end = min(i + horizon + 1, len(series))
    base = float(series.close[i])
    hi = sign * (series.high[i + 1 : end] / base - 1.0)
    lo = sign * (series.low[i + 1 : end] / base - 1.0)
    close = sign * (series.close[i + 1 : end] / base - 1.0)
    # For a short, the "best" excursion comes from the series low and the "worst" from the high, so
    # take the extremes across both transformed arrays rather than assuming which one leads.
    return float(np.max(np.maximum(hi, lo))), float(np.min(np.minimum(hi, lo))), float(close[-1])


def _target_first(series: Series, call: Call, i: int, horizon: int) -> bool | None:
    """Whether the stated target was reached before the stated stop. None without both levels.

    Intrabar collisions resolve to the **stop**, the same pessimistic convention the barrier
    labeling in ``alpha_validation`` uses. A day that touched both is scored as a loss, because a
    trader holding through it cannot know which came first and the adverse assumption is the one
    that cannot flatter the record.
    """
    if not call.has_levels:
        return None
    end = min(i + horizon + 1, len(series))
    highs = series.high[i + 1 : end]
    lows = series.low[i + 1 : end]
    target, stop = float(call.target), float(call.stop)  # type: ignore[arg-type]

    for k in range(highs.size):
        if call.sign > 0:
            hit_stop = lows[k] <= stop
            hit_target = highs[k] >= target
        else:
            hit_stop = highs[k] >= stop
            hit_target = lows[k] <= target
        if hit_stop:
            return False  # pessimistic: stop wins a same-bar collision
        if hit_target:
            return True
    return False  # unresolved inside the horizon counts as not reaching target


def score_call(call: Call, rng: np.random.Generator) -> Score:
    """Realise one call against the best available series for its asset."""
    asset = canonical(call.asset)
    if tier_for(asset) == "none":
        return Score(call, "no_data", "none", reason=f"no price series for {asset}")

    try:
        series = load_series(asset)
    except DataError as exc:
        return Score(call, "no_data", "none", reason=str(exc))

    horizon = call.horizon_days  # daily bars throughout
    i = series.index_of(call.date)
    if i >= len(series):
        return Score(
            call,
            "unresolved",
            series.tier,
            reason=f"call date is past the end of the {asset} series ({series.last_date})",
        )
    if i == 0 and call.date[:10] < series.first_date:
        return Score(
            call,
            "before_data",
            series.tier,
            reason=f"call predates the {asset} series (starts {series.first_date})",
        )

    remaining = len(series) - i - 1
    if remaining < horizon:
        return Score(
            call,
            "unresolved",
            series.tier,
            reason=f"{remaining}/{horizon} bars elapsed — horizon has not completed",
            index=i,
            days_elapsed=remaining,
        )

    best, worst, end = _excursions(series, i, horizon, call.sign)
    bars = as_ohlcv(series)
    # np.asarray is load-bearing: trend_state_vwap returns a Python list[str]. Comparing a list
    # against one of its elements yields the scalar False, which numpy then broadcasts to an
    # all-False mask — so every call would silently find zero matched controls and come back
    # unscoreable. mypy caught this; the runtime never would have complained.
    trend = np.asarray(trend_state_vwap(bars, window=TREND_WINDOW_DAYS))

    # Matched controls: same trend state, at least one horizon away from the call itself so a
    # control cannot be the call wearing a different date.
    idx = np.arange(len(series))
    eligible = np.flatnonzero(
        (trend == trend[i]) & (idx < len(series) - horizon - 1) & (np.abs(idx - i) > horizon)
    )
    if eligible.size < 20:
        return Score(
            call,
            "unresolved",
            series.tier,
            reason=f"only {eligible.size} matched control bars in the same trend state",
            index=i,
        )
    picks = rng.choice(eligible, size=min(CONTROLS_PER_CALL, eligible.size), replace=False)
    control_hits = sum(
        1 for j in picks if _excursions(series, int(j), horizon, call.sign)[0] >= DEFAULT_HIT
    )

    return Score(
        call=call,
        status="resolved",
        tier=series.tier,
        index=i,
        entry_price=float(series.close[i]),
        best=best,
        worst=worst,
        end=end,
        hit=best >= DEFAULT_HIT,
        target_first=_target_first(series, call, i, horizon),
        control_rate=control_hits / picks.size,
        control_n=int(picks.size),
        trend_state=str(trend[i]),
        days_elapsed=horizon,
    )


@dataclass(frozen=True)
class Aggregate:
    """The record as a whole — where a call log either shows something or does not."""

    n_calls: int
    n_resolved: int
    n_hits: int
    hit_rate: float
    hit_interval: ProportionInterval
    control_rate: float
    control_n: int
    difference: ProportionInterval
    mean_best: float
    mean_worst: float
    mean_end: float
    n_with_levels: int
    n_target_first: int
    by_status: dict[str, int] = field(default_factory=dict)
    by_asset: dict[str, int] = field(default_factory=dict)
    by_tier: dict[str, int] = field(default_factory=dict)

    def report(self) -> str:
        lines = [
            f"  calls logged            {self.n_calls}",
            f"  resolved (scoreable)    {self.n_resolved}",
            f"  status breakdown        {self.by_status}",
            f"  assets                  {self.by_asset}",
            f"  data tier               {self.by_tier}",
        ]
        if self.n_resolved == 0:
            lines.append("\n  Nothing is scoreable yet. No verdict is possible.")
            return "\n".join(lines)
        w, d = self.hit_interval, self.difference
        lines += [
            "",
            f"  hit rate (>= {DEFAULT_HIT:.0%} in the called direction within the horizon)",
            f"    {self.n_hits}/{self.n_resolved} = {self.hit_rate:.1%}   "
            f"95% CI [{w.lower:.1%}, {w.upper:.1%}]",
            f"  matched controls        {self.control_rate:.1%} over {self.control_n:,} draws",
            f"  difference              {self.hit_rate - self.control_rate:+.1%}   "
            f"95% CI [{d.lower:+.1%}, {d.upper:+.1%}]",
            "",
            f"  mean best excursion     {self.mean_best:+.1%}",
            f"  mean worst excursion    {self.mean_worst:+.1%}   "
            "(the drawdown a follower sat through)",
            f"  mean at horizon         {self.mean_end:+.1%}",
        ]
        if self.n_with_levels:
            lines.append(
                f"  calls with target+stop  {self.n_with_levels}, of which "
                f"{self.n_target_first} reached target first "
                f"({self.n_target_first / self.n_with_levels:.0%})"
            )
        if self.n_resolved < 20:
            lines += [
                "",
                f"  READ THIS FIRST: {self.n_resolved} resolved call(s) cannot establish anything.",
                "  The interval above spans most of the unit line and would do so whatever the hit",
                "  rate turned out to be. Roughly 20-30 resolved calls make the comparison mean",
                "  something; below that this is a record being kept, not a verdict being reached.",
            ]
        return "\n".join(lines)


def aggregate(scores: list[Score]) -> Aggregate:
    """Pool the scored calls into a record with intervals on the headline numbers."""
    resolved = [s for s in scores if s.scoreable]
    by_status: dict[str, int] = {}
    by_asset: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    for s in scores:
        by_status[s.status] = by_status.get(s.status, 0) + 1
        by_asset[canonical(s.call.asset)] = by_asset.get(canonical(s.call.asset), 0) + 1
        by_tier[s.tier] = by_tier.get(s.tier, 0) + 1

    if not resolved:
        empty = wilson_interval(0, 1)
        return Aggregate(
            n_calls=len(scores),
            n_resolved=0,
            n_hits=0,
            hit_rate=float("nan"),
            hit_interval=empty,
            control_rate=float("nan"),
            control_n=0,
            difference=empty,
            mean_best=float("nan"),
            mean_worst=float("nan"),
            mean_end=float("nan"),
            n_with_levels=0,
            n_target_first=0,
            by_status=by_status,
            by_asset=by_asset,
            by_tier=by_tier,
        )

    hits = sum(1 for s in resolved if s.hit)
    n = len(resolved)
    ctrl_rate = float(np.mean([s.control_rate for s in resolved]))
    ctrl_n = int(sum(s.control_n for s in resolved))
    with_levels = [s for s in resolved if s.target_first is not None]

    return Aggregate(
        n_calls=len(scores),
        n_resolved=n,
        n_hits=hits,
        hit_rate=hits / n,
        hit_interval=wilson_interval(hits, n),
        control_rate=ctrl_rate,
        control_n=ctrl_n,
        difference=newcombe_diff_interval(hits, n, int(round(ctrl_rate * ctrl_n)), ctrl_n),
        mean_best=float(np.mean([s.best for s in resolved])),
        mean_worst=float(np.mean([s.worst for s in resolved])),
        mean_end=float(np.mean([s.end for s in resolved])),
        n_with_levels=len(with_levels),
        n_target_first=sum(1 for s in with_levels if s.target_first),
        by_status=by_status,
        by_asset=by_asset,
        by_tier=by_tier,
    )


def horizon_sweep(calls: list[Call], *, seed: int = SEED) -> list[tuple[int, Aggregate]]:
    """Re-score the whole record at every horizon in :data:`HORIZON_SWEEP`.

    Mandatory in the report. A caller whose hit rate is 60% at 90 days and 25% at 7 days has not
    made 60%-accurate calls; they have made calls that a long enough window eventually rescues, and
    only showing every horizon makes that visible. The overriding of each call's own horizon is
    deliberate here — the point is to hold the window fixed across the record.
    """
    out: list[tuple[int, Aggregate]] = []
    for horizon in HORIZON_SWEEP:
        rng = np.random.default_rng(seed)
        forced = [
            Call(
                file=c.file,
                date=c.date,
                asset=c.asset,
                direction=c.direction,
                horizon_days=horizon,
                claim=c.claim,
                entry=c.entry,
                stop=c.stop,
                target=c.target,
            )
            for c in calls
        ]
        out.append((horizon, aggregate([score_call(c, rng) for c in forced])))
    return out


def load_calls(path: Path) -> list[Call]:
    """Read the consolidated call file produced from the screenshot extraction."""
    if not path.exists():
        raise FileNotFoundError(f"{path} absent — build it from research/ace_calls/raw/ first")

    def num(row: dict[str, str], key: str) -> float | None:
        raw = (row.get(key) or "").strip()
        try:
            return float(raw) if raw else None
        except ValueError:
            return None

    out: list[Call] = []
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            if not (row.get("date") or "").strip():
                continue
            direction = (row.get("direction") or "").strip().lower()
            if direction not in ("long", "short"):
                continue  # neutral commentary is corpus material, not a scoreable call
            out.append(
                Call(
                    file=(row.get("file") or "").strip(),
                    date=row["date"].strip()[:10],
                    asset=(row.get("asset") or "").strip(),
                    direction=direction,
                    horizon_days=int(float(row.get("horizon_days") or DEFAULT_HORIZON_DAYS)),
                    claim=(row.get("claim") or "").strip(),
                    entry=num(row, "entry"),
                    stop=num(row, "stop"),
                    target=num(row, "target"),
                )
            )
    return sorted(out, key=lambda c: (c.date, c.asset))


def run(calls_path: Path, *, seed: int = SEED) -> tuple[list[Score], Aggregate]:
    """Score every call and pool them. The entry point the report and the CLI both use."""
    calls = load_calls(calls_path)
    rng = np.random.default_rng(seed)
    scores = [score_call(c, rng) for c in calls]
    return scores, aggregate(scores)


def main() -> int:
    calls_path = REPO_ROOT / "research" / "ace_calls" / "calls.csv"
    scores, agg = run(calls_path)

    print("=" * 108)
    print("ACE CALL RECORD")
    print("=" * 108)
    resolved = [s for s in scores if s.scoreable]
    if resolved:
        print(f"\n  RESOLVED ({len(resolved)}) — 'hit' = {DEFAULT_HIT:.0%} in the called direction")
        for s in resolved:
            print(s.line())
            if s.call.claim:
                print(f'      "{s.call.claim[:96]}"')
    for status in ("unresolved", "no_data", "before_data"):
        rows = [s for s in scores if s.status == status]
        if rows:
            print(f"\n  {status.upper()} ({len(rows)}):")
            for s in rows:
                print(s.line())

    print("\n" + "=" * 108)
    print(f"AGGREGATE — primary spec ({DEFAULT_HORIZON_DAYS}d horizon, {DEFAULT_HIT:.0%} hit)")
    print("=" * 108)
    print(agg.report())

    calls = load_calls(calls_path)
    if calls:
        print("\n" + "=" * 108)
        print("HORIZON SENSITIVITY — the whole record re-scored at every window")
        print("=" * 108)
        print("\n  A record that only works at one horizon has found a window, not an edge.\n")
        print(
            f"  {'horizon':>8} {'resolved':>9} {'hits':>6} {'rate':>8} {'control':>9} {'diff':>8}"
        )
        for horizon, a in horizon_sweep(calls):
            if a.n_resolved == 0:
                print(f"  {horizon:>7}d {a.n_resolved:>9} {'-':>6} {'-':>8} {'-':>9} {'-':>8}")
                continue
            print(
                f"  {horizon:>7}d {a.n_resolved:>9} {a.n_hits:>6} {a.hit_rate:>7.1%} "
                f"{a.control_rate:>8.1%} {a.hit_rate - a.control_rate:>+7.1%}"
            )

    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "n_calls": agg.n_calls,
        "n_resolved": agg.n_resolved,
        "hit_rate": agg.hit_rate,
        "hit_ci": [agg.hit_interval.lower, agg.hit_interval.upper],
        "control_rate": agg.control_rate,
        "difference_ci": [agg.difference.lower, agg.difference.upper],
        "by_status": agg.by_status,
        "by_asset": agg.by_asset,
        "by_tier": agg.by_tier,
        "scores": [
            {
                "file": s.call.file,
                "date": s.call.date,
                "asset": canonical(s.call.asset),
                "direction": s.call.direction,
                "horizon_days": s.call.horizon_days,
                "status": s.status,
                "tier": s.tier,
                "reason": s.reason,
                "entry_price": s.entry_price,
                "best": s.best,
                "worst": s.worst,
                "end": s.end,
                "hit": s.hit,
                "target_first": s.target_first,
                "control_rate": s.control_rate,
                "claim": s.call.claim,
            }
            for s in scores
        ],
    }
    (OUT / "call_scores.json").write_text(json.dumps(payload, indent=2, allow_nan=True))
    print(f"\nwrote {OUT / 'call_scores.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

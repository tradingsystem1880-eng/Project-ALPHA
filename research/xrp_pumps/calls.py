"""Score dated directional calls against matched controls — the harness for Ace's record.

A trading call is a testable object: a date, an asset, a direction. Judging one is impossible;
judging thirty is straightforward, and the machinery is the same either way. This module supplies
it, so that as more dated calls arrive they accumulate into a record rather than into an impression.

**What it measures, and why each part is there.**

- **Hit rate with a Wilson interval.** The headline, and useless alone.
- **The base rate over the same asset and horizon.** A caller who is bullish in a bull market is
  right most of the time and has demonstrated nothing. Every hit rate is quoted against what a
  coin-flip on the same days would have produced.
- **Matched controls.** Random dates drawn from bars in the *same trend state* as the call. This is
  a stricter comparison than the unconditional base rate: it asks whether the caller beat someone
  who simply knew the regime and guessed.
- **Timing against the detectors.** When a call names a structure, how many days before or after
  the algorithmic confirmation was it made? Naming a pattern the day after a detector confirms it
  is a different skill from naming it a week early.

**What it cannot do.** With two calls on file, nothing here carries a conclusion, and the module
says so in its own output rather than leaving the reader to work it out from the sample size. The
interval on 2 calls spans essentially the whole unit line.

Input format — ``research/xrp_pumps/calls.csv``::

    date,asset,direction,horizon_days,note
    2026-07-20,XRP,long,30,"whole crypto market on the verge of a breakout"

Run: ``python -m research.xrp_pumps.calls [--file ...] [--seed 7]``
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from alpha_core import DataError
from alpha_patterns import HSConfig, detect_head_shoulders, trend_state_vwap
from alpha_validation import newcombe_diff_interval, wilson_interval
from research.hs_quasimodo.data import bar_index_of, iso_of, load
from research.xrp_pumps import config as C
from research.xrp_pumps.features import source_for

REPO_ROOT = Path(__file__).resolve().parents[2]

#: A call "worked" if the asset moved this far in the called direction inside its horizon.
HIT_THRESHOLD = 0.10
CONTROLS_PER_CALL = 200


@dataclass(frozen=True)
class Call:
    """One dated directional call."""

    date: str
    asset: str
    direction: str  # "long" | "short"
    horizon_days: int
    note: str

    @property
    def sign(self) -> int:
        if self.direction not in ("long", "short"):
            raise DataError(f"direction must be long|short, got {self.direction!r}")
        return 1 if self.direction == "long" else -1


@dataclass(frozen=True)
class CallScore:
    """What actually happened after a call, and what a control would have got."""

    call: Call
    index: int
    entry: float
    best: float  # best move in the called direction within the horizon
    worst: float  # worst move (the drawdown the caller would have sat through)
    end: float  # move at the horizon
    hit: bool
    trend_state: float
    control_hit_rate: float
    control_n: int

    def line(self) -> str:
        return (
            f"  {self.call.date}  {self.call.asset:<5} {self.call.direction:<5} "
            f"{self.call.horizon_days:>3}d  entry {self.entry:>8.4f}  "
            f"best {self.best:>+7.1%}  worst {self.worst:>+7.1%}  end {self.end:>+7.1%}  "
            f"{'HIT ' if self.hit else 'miss'}  control {self.control_hit_rate:>5.1%}"
        )


def load_calls(path: Path) -> list[Call]:
    """Read the call file. Missing file is not an error — it means no calls have been logged yet."""
    if not path.exists():
        return []
    out: list[Call] = []
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            if not row.get("date"):
                continue
            out.append(
                Call(
                    date=row["date"].strip(),
                    asset=row.get("asset", C.SUBJECT_KEY).strip() or C.SUBJECT_KEY,
                    direction=row.get("direction", "long").strip().lower(),
                    horizon_days=int(row.get("horizon_days") or 30),
                    note=row.get("note", "").strip(),
                )
            )
    return sorted(out, key=lambda c: c.date)


def score_call(call: Call, timeframe: str, rng: np.random.Generator) -> CallScore:
    """Realise one call: what happened, and what the same bet on a matched random date would do.

    Controls are drawn from bars in the same trend state (price above or below its trailing 90-day
    VWAP), which removes the easiest way to look prescient — being bullish during an uptrend. The
    control set excludes bars within one horizon of the call itself, so a control cannot simply be
    the call in disguise.
    """
    bars, _ = load(source_for(call.asset), timeframe)  # type: ignore[arg-type]
    n = len(bars)
    horizon = C.bars(call.horizon_days, timeframe)
    idx = bar_index_of(bars, call.date)
    if idx >= n:
        raise DataError(f"call {call.date} is after the end of the {call.asset} series")
    if idx + horizon >= n:
        raise DataError(
            f"call {call.date}: only {n - idx - 1} bars remain, needs {horizon} — "
            "the horizon has not elapsed yet, so the call is unresolved"
        )

    trend = trend_state_vwap(bars, window=C.bars(90, timeframe))
    entry = float(bars.close[idx])
    sign = call.sign

    def moves(i: int) -> tuple[float, float, float]:
        window = bars.close[i + 1 : i + horizon + 1]
        base = float(bars.close[i])
        rel = sign * (window / base - 1.0)
        return float(np.max(rel)), float(np.min(rel)), float(rel[-1])

    best, worst, end = moves(idx)

    # Matched controls: same trend state, at least one horizon away from the call.
    eligible = np.flatnonzero(
        (trend == trend[idx])
        & (np.arange(n) < n - horizon - 1)
        & (np.abs(np.arange(n) - idx) > horizon)
    )
    if eligible.size < 20:
        raise DataError(f"call {call.date}: only {eligible.size} matched control bars")
    picks = rng.choice(eligible, size=min(CONTROLS_PER_CALL, eligible.size), replace=False)
    control_hits = sum(1 for j in picks if moves(int(j))[0] >= HIT_THRESHOLD)

    return CallScore(
        call=call,
        index=idx,
        entry=entry,
        best=best,
        worst=worst,
        end=end,
        hit=best >= HIT_THRESHOLD,
        trend_state=float(trend[idx]),
        control_hit_rate=control_hits / picks.size,
        control_n=int(picks.size),
    )


def detector_timing(call: Call, timeframe: str, *, window_days: int = 45) -> str:
    """How the call's date compares with the nearest algorithmic pattern confirmation.

    Naming a structure before a detector confirms it and naming it afterwards are different claims.
    This reports the gap in days to the nearest inverse-head-and-shoulders confirmation, signed so
    negative means the caller was **early**.
    """
    bars, _ = load(source_for(call.asset), timeframe)  # type: ignore[arg-type]
    idx = bar_index_of(bars, call.date)
    cfg = HSConfig(
        direction="bullish" if call.sign > 0 else "bearish",
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
    span = C.bars(window_days, timeframe)
    near = [e for e in detect_head_shoulders(bars, cfg) if abs(e.confirmed_index - idx) <= span]
    if not near:
        return "no matching structure confirmed within 45 days"
    closest = min(near, key=lambda e: abs(e.confirmed_index - idx))
    gap = closest.confirmed_index - idx
    when = "before the call" if gap < 0 else ("after the call" if gap > 0 else "same day")
    return (
        f"{closest.variant} confirmed {iso_of(bars, closest.confirmed_index)[:10]} "
        f"({abs(gap)} bars {when}; caller {'early' if gap > 0 else 'late' if gap < 0 else 'exact'})"
    )


def report(path: Path, timeframe: str, seed: int) -> list[CallScore]:
    """Score every logged call and print the record with its interval."""
    calls = load_calls(path)
    print("=" * 104)
    print(f"CALL RECORD — {path.relative_to(REPO_ROOT) if path.is_absolute() else path}")
    print("=" * 104)
    if not calls:
        print("  No calls logged. Add rows to the CSV and re-run.")
        return []

    rng = np.random.default_rng(seed)
    scores: list[CallScore] = []
    unresolved: list[tuple[Call, str]] = []
    for call in calls:
        try:
            scores.append(score_call(call, timeframe, rng))
        except DataError as exc:
            unresolved.append((call, str(exc)))

    if scores:
        print(f"\n  RESOLVED ({len(scores)}) — 'hit' = {HIT_THRESHOLD:.0%} in the called direction")
        for s in scores:
            print(s.line())
            if s.call.note:
                print(f'      "{s.call.note}"')
            print(f"      {detector_timing(s.call, timeframe)}")

        hits = sum(1 for s in scores if s.hit)
        n = len(scores)
        w = wilson_interval(hits, n)
        ctrl = float(np.mean([s.control_hit_rate for s in scores]))
        ctrl_n = int(sum(s.control_n for s in scores))
        diff = newcombe_diff_interval(hits, n, int(round(ctrl * ctrl_n)), ctrl_n)
        print(
            f"\n  hit rate {hits}/{n} = {hits / n:.0%}  95% CI [{w.lower:.0%}, {w.upper:.0%}]\n"
            f"  matched controls {ctrl:.0%} over {ctrl_n:,} draws\n"
            f"  difference {hits / n - ctrl:+.0%}  95% CI [{diff.lower:+.0%}, {diff.upper:+.0%}]"
        )
        if n < 20:
            print(
                f"\n  READ THIS BEFORE THE NUMBERS ABOVE: {n} call(s) cannot establish anything.\n"
                "  The interval spans most of the unit line and would do so whatever the hit rate\n"
                "  turned out to be. This harness exists so the record accumulates; it is not a\n"
                f"  verdict at n={n}. Roughly 20-30 dated calls make the comparison meaningful."
            )

    if unresolved:
        print(f"\n  UNRESOLVED ({len(unresolved)}) — the horizon has not elapsed yet.")
        print("  Progress so far is shown for information; it is NOT a result, because a call")
        print("  judged before its horizon is judged on a window the caller did not choose.")
        for call, _ in unresolved:
            print(
                f"  {call.date}  {call.asset:<5} {call.direction:<5} {call.horizon_days:>3}d  "
                f"{_progress(call, timeframe)}"
            )
            if call.note:
                print(f'      "{call.note}"')
    return scores


def _progress(call: Call, timeframe: str) -> str:
    """Where an unresolved call stands right now — elapsed fraction and the move so far."""
    try:
        bars, _ = load(source_for(call.asset), timeframe)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        return f"unreadable ({exc})"
    n = len(bars)
    idx = bar_index_of(bars, call.date)
    if idx >= n - 1:
        return "call date is at or beyond the end of the series"
    horizon = C.bars(call.horizon_days, timeframe)
    window = bars.close[idx + 1 :]
    rel = call.sign * (window / float(bars.close[idx]) - 1.0)
    elapsed = window.size
    return (
        f"{elapsed}/{horizon} bars elapsed ({elapsed / horizon:.0%})  "
        f"best {float(np.max(rel)):+.1%}  worst {float(np.min(rel)):+.1%}  "
        f"now {float(rel[-1]):+.1%}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score dated directional calls")
    ap.add_argument("--file", default=str(REPO_ROOT / C.ACE_CALLS_FILE))
    ap.add_argument("--timeframe", default=C.PRIMARY_TIMEFRAME, choices=list(C.BARS_PER_DAY))
    ap.add_argument("--seed", type=int, default=C.SEED)
    args = ap.parse_args(argv)
    report(Path(args.file), args.timeframe, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())

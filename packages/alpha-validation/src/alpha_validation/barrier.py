"""Triple-barrier outcome labeling and excursion statistics for path-dependent trade evaluation.

A forward *return* answers "where was price in N bars?". A trader never experiences that number,
because a stop removes them from the trade first. The honest evaluation of a setup is therefore a
**race**: starting at ``entry``, does price touch ``target`` or ``stop`` first, within ``horizon``
bars? That race — the "triple barrier" of López de Prado — is what this module measures.

The distinction matters enormously at high reward:risk. A setup can show a healthy median forward
return while losing money as a trade, because the path to that median runs through the stop.

**Intrabar ambiguity and why this module is deliberately pessimistic.** When a single bar's range
spans both barriers, OHLC data cannot say which was touched first. Assuming the favourable barrier
would flatter every result, so :func:`barrier_outcome` resolves ties to the **stop**. Reported
target-first rates are therefore lower bounds. Pass ``optimistic=True`` to measure the opposite
extreme and bracket the true value — if a verdict flips between the two, the bar resolution is too
coarse for the question being asked, and that itself is the finding.

Pure ``numpy``; fails loud (``DataError``) on degenerate input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from alpha_core import DataError
from alpha_validation.metrics import FloatArray, FloatSeq

Outcome = Literal["target", "stop", "unresolved"]


@dataclass(frozen=True)
class BarrierResult:
    """The resolution of one entry against a stop, a target, and a time limit."""

    outcome: Outcome
    bars_to_outcome: int  # -1 when unresolved within the horizon
    mfe: float  # maximum favourable excursion, as a signed fraction of entry price
    mae: float  # maximum adverse excursion, as a signed fraction of entry price (<= 0)
    entry: float
    stop: float
    target: float
    is_long: bool


@dataclass(frozen=True)
class BarrierCounts:
    """Aggregated outcomes over many entries — the input to a Wilson interval."""

    target_first: int
    stop_first: int
    unresolved: int
    n: int
    breakeven_rate: float  # 1/(1+R:R): the target-first rate at which the trade is EV-neutral
    reward_risk: float

    @property
    def target_rate(self) -> float:
        """Observed P(target first). Compare against ``breakeven_rate``, never against 50%."""
        return self.target_first / self.n if self.n else 0.0

    @property
    def expectancy_r(self) -> float:
        """Expected value per unit risked, in R. Unresolved entries are scored flat (0R)."""
        if not self.n:
            return 0.0
        return (self.target_first * self.reward_risk - self.stop_first) / self.n


def _as_path(highs: FloatSeq, lows: FloatSeq) -> tuple[FloatArray, FloatArray]:
    hi = np.asarray(highs, dtype=np.float64)
    lo = np.asarray(lows, dtype=np.float64)
    if hi.ndim != 1 or lo.ndim != 1:
        raise DataError(f"barrier path needs 1-D highs/lows, got {hi.shape}/{lo.shape}")
    if hi.size != lo.size:
        raise DataError(f"barrier path needs matching highs/lows, got {hi.size} vs {lo.size}")
    if hi.size == 0:
        raise DataError("barrier path needs at least one forward bar")
    if not (bool(np.all(np.isfinite(hi))) and bool(np.all(np.isfinite(lo)))):
        raise DataError("barrier path requires finite highs/lows")
    if bool(np.any(hi < lo)):
        raise DataError("barrier path has a bar whose high is below its low")
    return hi, lo


def barrier_outcome(
    highs: FloatSeq,
    lows: FloatSeq,
    *,
    entry: float,
    stop: float,
    target: float,
    optimistic: bool = False,
) -> BarrierResult:
    """Race ``target`` against ``stop`` over the forward path, returning the first touched.

    ``highs``/``lows`` are the bars *after* entry, in order. Direction is inferred: ``target >
    entry`` is a long, ``target < entry`` is a short. Same-bar collisions resolve to the stop unless
    ``optimistic`` is set (see the module docstring for why the default is pessimistic).
    """
    if not all(np.isfinite([entry, stop, target])):
        raise DataError("barrier_outcome requires finite entry/stop/target")
    if entry <= 0.0:
        raise DataError(f"barrier_outcome requires a positive entry price, got {entry}")
    if target == entry or stop == entry:
        raise DataError("barrier_outcome requires stop and target to differ from entry")

    is_long = target > entry
    if is_long and stop >= entry:
        raise DataError(f"long setup needs stop < entry, got stop={stop} entry={entry}")
    if not is_long and stop <= entry:
        raise DataError(f"short setup needs stop > entry, got stop={stop} entry={entry}")

    hi, lo = _as_path(highs, lows)

    # Running extremes let MFE/MAE be reported even when neither barrier is touched.
    if is_long:
        hit_target = hi >= target
        hit_stop = lo <= stop
        mfe = float(np.max(hi) / entry - 1.0)
        mae = float(np.min(lo) / entry - 1.0)
    else:
        hit_target = lo <= target
        hit_stop = hi >= stop
        mfe = float(1.0 - np.min(lo) / entry)
        mae = float(1.0 - np.max(hi) / entry)

    t_idx = int(np.argmax(hit_target)) if bool(hit_target.any()) else -1
    s_idx = int(np.argmax(hit_stop)) if bool(hit_stop.any()) else -1

    if t_idx < 0 and s_idx < 0:
        outcome: Outcome = "unresolved"
        bars = -1
    elif s_idx < 0 or (t_idx >= 0 and t_idx < s_idx):
        outcome, bars = "target", t_idx + 1
    elif t_idx < 0 or s_idx < t_idx:
        outcome, bars = "stop", s_idx + 1
    else:
        # Same bar touched both — the coarse-data tie, broken by the caller's chosen convention.
        outcome = "target" if optimistic else "stop"
        bars = t_idx + 1

    return BarrierResult(
        outcome=outcome,
        bars_to_outcome=bars,
        mfe=mfe,
        mae=mae,
        entry=entry,
        stop=stop,
        target=target,
        is_long=is_long,
    )


def aggregate_outcomes(results: list[BarrierResult]) -> BarrierCounts:
    """Tally a list of :class:`BarrierResult` into counts plus the breakeven bar to clear.

    ``breakeven_rate = 1/(1+R:R)`` is the target-first frequency at which the strategy merely breaks
    even. Every reported win rate must be read against this number, not against 50%: at 28.8:1 a
    3.4% hit rate is profitable, while at 2:1 a 33% hit rate is not.
    """
    if not results:
        raise DataError("aggregate_outcomes needs at least one result")

    first = results[0]
    reward = abs(first.target - first.entry)
    risk = abs(first.entry - first.stop)
    if risk <= 0.0:
        raise DataError("aggregate_outcomes needs a non-zero risk leg")
    rr = reward / risk

    return BarrierCounts(
        target_first=sum(1 for r in results if r.outcome == "target"),
        stop_first=sum(1 for r in results if r.outcome == "stop"),
        unresolved=sum(1 for r in results if r.outcome == "unresolved"),
        n=len(results),
        breakeven_rate=1.0 / (1.0 + rr),
        reward_risk=rr,
    )


def excursion_quantiles(
    results: list[BarrierResult], *, quantiles: tuple[float, ...] = (0.25, 0.5, 0.75, 0.9)
) -> dict[str, dict[float, float]]:
    """MFE/MAE distributions across events — where stops and targets *could* have been placed.

    The MAE distribution answers "how far does this setup normally go against me before working?",
    which is the empirical basis for stop placement; the MFE distribution bounds what target is
    realistically reachable.
    """
    if not results:
        raise DataError("excursion_quantiles needs at least one result")
    if any(not 0.0 <= q <= 1.0 for q in quantiles):
        raise DataError(f"quantiles must lie in [0, 1], got {quantiles}")

    mfe = np.array([r.mfe for r in results], dtype=np.float64)
    mae = np.array([r.mae for r in results], dtype=np.float64)
    return {
        "mfe": {q: float(np.quantile(mfe, q)) for q in quantiles},
        "mae": {q: float(np.quantile(mae, q)) for q in quantiles},
    }

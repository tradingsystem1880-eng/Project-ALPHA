"""Empirical null: how many "discoveries" does this battery produce when there is nothing to find?

Benjamini-Hochberg controls the false-discovery rate under an independence assumption these
conditions flatly violate. MACD, RSI, the stochastic and Williams %R all read the same momentum;
``ma_price_above_200`` and ``ichi_above_cloud`` agree on most bars; the twenty outcomes are four
horizons of five overlapping definitions. Applying BH to that and reporting the survivor count as
if it were a false-discovery bound would be arithmetic theatre.

So the survivor count is calibrated against a null instead of argued about. The construction is a
**circular shift of the outcomes against the conditions**:

* every condition keeps its exact autocorrelation, clustering and base rate;
* every outcome keeps its exact autocorrelation, clustering and base rate;
* the *alignment* between them — the only place a real edge can live — is destroyed.

A large shift makes ``outcome[i]`` describe what happened after some unrelated bar hundreds of days
away, so any surviving association is an artefact of the battery's size and its internal
correlations. Whatever number of survivors comes back is what this battery produces from nothing.

Circular shifting beats resampling the price series here for a specific reason: a bootstrap would
also have to rebuild every indicator, and any difference in how the surrogate's indicators behave
would confound the comparison. Shifting changes exactly one thing.

**How to read the output.** If the real run returns 43 survivors and the null returns a median of
40, the study found nothing and the 43 are the machinery humming. If the null returns a median of 2
with a 95th percentile of 6, then 43 is real signal — though still not necessarily *tradeable*
signal, which is a separate question the directional outcomes answer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from research.xrp_deep import config as C
from research.xrp_deep.conditions import build_conditions, screen
from research.xrp_deep.outcomes import Outcome, build_outcomes
from research.xrp_deep.panel import build_panel
from research.xrp_deep.study import Cell, run_battery

OUT = Path(__file__).resolve().parent / "out"

#: Shifts smaller than this leave the outcome nearly aligned with its own condition, which would
#: leak genuine signal into the null and make the null look stronger than it is.
MIN_SHIFT = 200


def shift_outcomes(outcomes: dict[str, Outcome], shift: int) -> dict[str, Outcome]:
    """Circularly roll every outcome, keeping its hit/valid pairing intact."""
    return {
        key: Outcome(
            key=o.key,
            hit=np.roll(o.hit, shift),
            valid=np.roll(o.valid, shift),
            horizon=o.horizon,
            description=o.description,
        )
        for key, o in outcomes.items()
    }


def _count(cells: list[Cell]) -> tuple[int, int]:
    """(survivors, survivors on a directional outcome)."""
    survivors = [c for c in cells if c.significant]
    directional = [
        c for c in survivors if c.outcome.startswith(("fwd_positive_", "barrier_", "beat_btc_"))
    ]
    return len(survivors), len(directional)


@dataclass(frozen=True)
class NullResult:
    """The null distribution of survivor counts, next to what the real run produced."""

    surrogates: int
    observed: int
    observed_directional: int
    counts: list[int]
    directional_counts: list[int]

    @property
    def median(self) -> float:
        return float(np.median(self.counts))

    @property
    def p95(self) -> float:
        return float(np.percentile(self.counts, 95))

    @property
    def pvalue(self) -> float:
        """Share of surrogates producing at least as many survivors as the real run.

        The honest headline statistic for the whole study: the probability that a battery this
        size, with these internal correlations, produces this many survivors from data containing
        no relationship at all.
        """
        counts = np.asarray(self.counts)
        return float((np.sum(counts >= self.observed) + 1) / (counts.size + 1))

    @property
    def directional_pvalue(self) -> float:
        counts = np.asarray(self.directional_counts)
        return float((np.sum(counts >= self.observed_directional) + 1) / (counts.size + 1))


def run_null(*, surrogates: int = C.NULL_SURROGATES, seed: int = C.SEED) -> NullResult:
    panel = build_panel()
    conditions, _ = screen(build_conditions(panel))
    outcomes = build_outcomes(panel)
    n = len(panel)

    observed, observed_directional = _count(run_battery(conditions, outcomes))

    rng = np.random.default_rng(seed)
    counts: list[int] = []
    directional: list[int] = []
    for _ in range(surrogates):
        shift = int(rng.integers(MIN_SHIFT, n - MIN_SHIFT))
        total, direc = _count(run_battery(conditions, shift_outcomes(outcomes, shift)))
        counts.append(total)
        directional.append(direc)
    return NullResult(surrogates, observed, observed_directional, counts, directional)


def main() -> int:
    result = run_null()

    print("=" * 96)
    print("EMPIRICAL NULL — what this battery finds in data with nothing in it")
    print("=" * 96)
    print(f"\n  surrogates              {result.surrogates} circular shifts")
    print("\n  ALL OUTCOMES")
    print(f"    observed survivors    {result.observed}")
    print(f"    null median           {result.median:.0f}")
    print(f"    null 95th percentile  {result.p95:.0f}")
    print(f"    null max              {max(result.counts)}")
    print(f"    p-value               {result.pvalue:.4f}")
    print("\n  DIRECTIONAL OUTCOMES ONLY (fwd_positive / barrier / beat_btc)")
    print(f"    observed survivors    {result.observed_directional}")
    print(f"    null median           {float(np.median(result.directional_counts)):.0f}")
    print(f"    null 95th percentile  {float(np.percentile(result.directional_counts, 95)):.0f}")
    print(f"    p-value               {result.directional_pvalue:.4f}")

    print("\n  reading:")
    if result.pvalue < 0.05:
        print(f"    The battery found more than chance explains (p={result.pvalue:.4f}).")
        print("    That licenses the *existence* of structure, not its tradeability — see")
        print("    the directional row above, which is the one a position depends on.")
    else:
        print(f"    The battery found no more than chance explains (p={result.pvalue:.4f}).")
        print("    Every survivor in study.py should be read as noise until proven otherwise.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nullcal.json").write_text(
        json.dumps(
            {
                "surrogates": result.surrogates,
                "observed": result.observed,
                "observed_directional": result.observed_directional,
                "null_median": result.median,
                "null_p95": result.p95,
                "null_max": max(result.counts),
                "pvalue": result.pvalue,
                "directional_pvalue": result.directional_pvalue,
                "counts": result.counts,
                "directional_counts": result.directional_counts,
            },
            indent=2,
        )
    )
    print(f"\nwrote {OUT / 'nullcal.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

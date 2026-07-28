"""Separate volatility effects from directional edge — the distinction the survivor list hides.

The full battery returns a long list of conditions that "predict" ``up_5``. It also returns most of
the same conditions predicting ``down_5``. Both cannot be a bullish signal, and the resolution is
that neither is a signal at all in the sense a position cares about: they are **volatility
forecasts**. A state like "Bollinger bands wide" or "price in the top decile of its year" raises the
probability of a 10% move in *either* direction, which is a real and well-known property of
markets, and completely useless to someone deciding whether to be long.

The test is a two-by-two:

* ``lift(up_H) > 0`` and ``lift(down_H) > 0``  → **volatility**: bigger moves, no side.
* ``lift(up_H) > 0`` and ``lift(down_H) < 0``  → **bullish**: more upside, less downside.
* ``lift(up_H) < 0`` and ``lift(down_H) > 0``  → **bearish**.
* both negative                                 → **quiet**: smaller moves either way.

Only the middle two are tradeable, and the study's directional outcomes (``fwd_positive_``,
``barrier_``, ``beat_btc_``) are the direct test of them. This module exists to quantify how much
of the apparent edge evaporates once that distinction is enforced, because "43 conditions survived
FDR" and "zero of them point in a direction" are the same result described two ways, and only one
of those descriptions is honest.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from research.xrp_deep import config as C
from research.xrp_deep.conditions import Condition, build_conditions, screen
from research.xrp_deep.outcomes import Outcome, build_outcomes
from research.xrp_deep.panel import Panel, build_panel

OUT = Path(__file__).resolve().parent / "out"


@dataclass(frozen=True)
class Directionality:
    """What a condition does to the up-move and down-move probabilities, side by side."""

    condition: str
    family: str
    horizon: int
    n: int
    up_lift: float
    down_lift: float
    #: P(up) - P(down) under the condition, minus the same difference under its complement. The
    #: single number that says whether a condition tilts the odds rather than widening them.
    directional_edge: float
    verdict: str

    def line(self) -> str:
        return (
            f"  {self.condition:24} {self.horizon:>3}d n={self.n:>5}  "
            f"up {self.up_lift:>+7.1%}  down {self.down_lift:>+7.1%}  "
            f"edge {self.directional_edge:>+7.1%}  {self.verdict}"
        )


def _rate(mask: np.ndarray, outcome: Outcome, valid: np.ndarray) -> float:
    sel = mask & valid
    n = int(sel.sum())
    return float(outcome.hit[sel].sum()) / n if n else float("nan")


def classify(
    condition: Condition, up: Outcome, down: Outcome, *, horizon: int
) -> Directionality | None:
    """Compare a condition's effect on upside and downside probability at one horizon."""
    valid = condition.valid & up.valid & down.valid
    on, off = condition.mask & valid, ~condition.mask & valid
    if int(on.sum()) < C.MIN_CONDITION_BARS or int(off.sum()) < C.MIN_CONDITION_BARS:
        return None

    up_on, up_off = _rate(condition.mask, up, valid), _rate(~condition.mask, up, valid)
    dn_on, dn_off = _rate(condition.mask, down, valid), _rate(~condition.mask, down, valid)
    if not all(np.isfinite(v) for v in (up_on, up_off, dn_on, dn_off)):
        return None

    up_lift, down_lift = up_on - up_off, dn_on - dn_off
    edge = (up_on - dn_on) - (up_off - dn_off)

    # A tolerance band, so a lift of +0.2% does not get called "bullish". Below it the condition
    # is doing nothing to that side at all, whatever the sign of the rounding.
    tol = 0.02
    if up_lift > tol and down_lift > tol:
        verdict = "VOLATILITY (both directions)"
    elif up_lift < -tol and down_lift < -tol:
        verdict = "quiet (smaller moves both ways)"
    elif up_lift > tol and down_lift < -tol:
        verdict = "BULLISH"
    elif up_lift < -tol and down_lift > tol:
        verdict = "BEARISH"
    else:
        verdict = "no effect"
    return Directionality(
        condition.key, condition.family, horizon, int(on.sum()), up_lift, down_lift, edge, verdict
    )


def run(panel: Panel | None = None) -> list[Directionality]:
    panel = panel or build_panel()
    conditions, _ = screen(build_conditions(panel))
    outcomes = build_outcomes(panel)
    rows: list[Directionality] = []
    for horizon in C.HORIZONS:
        up, down = outcomes[f"up_{horizon}"], outcomes[f"down_{horizon}"]
        for cond in conditions:
            row = classify(cond, up, down, horizon=horizon)
            if row is not None:
                rows.append(row)
    return rows


def main() -> int:
    rows = run()

    print("=" * 100)
    print("DIRECTIONALITY — is it a bigger move, or a move with a side?")
    print("=" * 100)

    counts = Counter(r.verdict for r in rows)
    total = len(rows)
    print(f"\n  {total} condition-horizon pairs\n")
    for verdict, count in counts.most_common():
        print(f"    {verdict:32} {count:>5}  ({count / total:>5.1%})")

    print("\n" + "=" * 100)
    print("THE STRONGEST VOLATILITY EFFECTS — real, and useless to a directional position")
    print("=" * 100 + "\n")
    vol = sorted(
        (r for r in rows if r.verdict.startswith("VOLATILITY")),
        key=lambda r: r.up_lift + r.down_lift,
        reverse=True,
    )
    for row in vol[:12]:
        print(row.line())

    print("\n" + "=" * 100)
    print("THE ONLY THING THAT MATTERS FOR A POSITION — conditions with a side")
    print("=" * 100 + "\n")
    sided = sorted(
        (r for r in rows if r.verdict in ("BULLISH", "BEARISH")),
        key=lambda r: abs(r.directional_edge),
        reverse=True,
    )
    if not sided:
        print("  Not one condition in the battery tilts the odds toward a direction at any")
        print("  horizon. Every effect the study found widens the distribution rather than")
        print("  shifting it.")
    for row in sided[:25]:
        print(row.line())

    print("\n" + "=" * 100)
    print("PRIMARY CONDITIONS AT THE PRIMARY HORIZON — the pre-registered read")
    print("=" * 100 + "\n")
    primaries = {f.primary for f in C.FAMILIES}
    for row in sorted(
        (r for r in rows if r.condition in primaries and r.horizon == C.PRIMARY_HORIZON),
        key=lambda r: r.directional_edge,
        reverse=True,
    ):
        print(row.line())

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "directionality.json").write_text(
        json.dumps(
            {
                "verdict_counts": dict(counts),
                "rows": [
                    {
                        "condition": r.condition,
                        "family": r.family,
                        "horizon": r.horizon,
                        "n": r.n,
                        "up_lift": r.up_lift,
                        "down_lift": r.down_lift,
                        "directional_edge": r.directional_edge,
                        "verdict": r.verdict,
                    }
                    for r in rows
                ],
            },
            indent=2,
        )
    )
    print(f"\nwrote {OUT / 'directionality.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

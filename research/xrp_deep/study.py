"""Run the battery: every condition against every outcome, with the multiplicity bill paid openly.

The arithmetic is the easy part. What makes this a study rather than a fishing expedition is what
surrounds it:

* **A disjoint complement.** Every lift compares P(outcome | condition) against
  P(outcome | NOT condition) on the same valid bars — never against the unconditional rate. The
  unconditional rate includes the condition's own bars, which shrinks every lift toward zero and
  makes a real effect look small and a fake one look harmless.
* **Overlap deflation.** A 30-day forward window stamped on every daily bar counts each
  observation about thirty times. ``conditional_lift`` takes the overlap factor and reports both
  nominal and effective counts; the p-values here are computed on the effective ones.
* **BH within family.** Never pooled: pooling twenty-four mechanisms into one correction destroys
  the power to detect any of them, for no gain in honesty.
* **Out-of-sample.** Everything is computed twice, in-sample and after :data:`config.OOS_SPLIT`.
  A condition that survives in-sample and reverses out-of-sample has told you what it is.

BH assumes something close to independence within a family, and these conditions are heavily
cross-correlated by construction. That assumption is not repaired here — it is *measured*, by
``nullcal.py``, which runs this identical battery against surrogate series containing no
predictability by construction and counts how many discoveries come back anyway. Read that number
before believing anything in this module's output.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from alpha_validation import LiftResult, apply_fdr, conditional_lift
from research.xrp_deep import config as C
from research.xrp_deep.conditions import Condition, build_conditions, by_family, screen
from research.xrp_deep.outcomes import Outcome, build_outcomes
from research.xrp_deep.panel import Panel, build_panel

OUT = Path(__file__).resolve().parent / "out"


@dataclass(frozen=True)
class Cell:
    """One condition-outcome test, in one sample."""

    condition: str
    family: str
    outcome: str
    sample: str  # "full" | "in" | "out"
    n_condition: int
    n_condition_eff: float
    rate_condition: float
    rate_complement: float
    lift: float
    diff_lower: float
    diff_upper: float
    pvalue: float
    qvalue: float
    rejected: bool

    @property
    def significant(self) -> bool:
        """Survived FDR *and* has an interval that excludes zero — both, not either."""
        return self.rejected and (self.diff_lower > 0.0 or self.diff_upper < 0.0)


def _to_cell(result: LiftResult, sample: str) -> Cell:
    return Cell(
        condition=result.condition,
        family=result.family,
        outcome=result.outcome,
        sample=sample,
        n_condition=result.n_condition,
        n_condition_eff=result.n_condition_eff,
        rate_condition=result.rate_condition,
        rate_complement=result.rate_complement,
        lift=result.lift,
        diff_lower=result.interval_difference.lower,
        diff_upper=result.interval_difference.upper,
        pvalue=result.pvalue,
        qvalue=result.qvalue if result.qvalue is not None else float("nan"),
        rejected=bool(result.rejected),
    )


def run_battery(
    conditions: list[Condition],
    outcomes: dict[str, Outcome],
    *,
    sample_mask: np.ndarray | None = None,
    sample: str = "full",
) -> list[Cell]:
    """Every condition against every outcome, FDR-corrected within each family.

    ``sample_mask`` restricts to a sub-period without recomputing any indicator — the indicators
    stay causal over the full history, which is what a trader standing in 2024 would actually have
    had. Recomputing them inside the sub-period would quietly change their warm-up and make the
    out-of-sample test a test of a different indicator.
    """
    cells: list[Cell] = []
    for family, members in by_family(conditions).items():
        family_results: list[LiftResult] = []
        for cond in members:
            for name, outcome in outcomes.items():
                valid = cond.valid & outcome.valid
                if sample_mask is not None:
                    valid = valid & sample_mask
                if int((cond.mask & valid).sum()) < C.MIN_CONDITION_BARS:
                    continue
                if int((~cond.mask & valid).sum()) < C.MIN_CONDITION_BARS:
                    continue
                family_results.append(
                    conditional_lift(
                        cond.mask,
                        outcome.hit,
                        label=cond.key,
                        outcome_label=name,
                        family=family,
                        valid=valid,
                        overlap=float(outcome.horizon),
                    )
                )
        cells.extend(_to_cell(r, sample) for r in apply_fdr(family_results, alpha=C.FDR_ALPHA))
    return cells


@dataclass
class StudyResult:
    """Everything the battery produced, plus the accounting needed to read it."""

    n_conditions: int
    n_outcomes: int
    n_tests: int
    dropped: list[str]
    full: list[Cell]
    in_sample: list[Cell]
    out_sample: list[Cell]
    panel_notes: list[str]

    @property
    def survivors(self) -> list[Cell]:
        """Full-sample cells that cleared FDR with an interval excluding zero."""
        return sorted(
            (c for c in self.full if c.significant), key=lambda c: abs(c.lift), reverse=True
        )

    def confirmed(self) -> list[Cell]:
        """Survivors whose out-of-sample lift keeps the same sign — the only real candidates."""
        oos = {(c.condition, c.outcome): c for c in self.out_sample}
        out: list[Cell] = []
        for cell in self.survivors:
            match = oos.get((cell.condition, cell.outcome))
            if match is not None and np.sign(match.lift) == np.sign(cell.lift):
                out.append(cell)
        return out


def run_study(panel: Panel | None = None) -> StudyResult:
    panel = panel or build_panel()
    built = build_conditions(panel)
    conditions, dropped = screen(built)
    outcomes = build_outcomes(panel)

    split = panel.index_of(C.OOS_SPLIT)
    n = len(panel)
    in_mask = np.zeros(n, dtype=bool)
    in_mask[:split] = True
    out_mask = ~in_mask

    full = run_battery(conditions, outcomes, sample="full")
    return StudyResult(
        n_conditions=len(conditions),
        n_outcomes=len(outcomes),
        n_tests=len(full),
        dropped=dropped,
        full=full,
        in_sample=run_battery(conditions, outcomes, sample_mask=in_mask, sample="in"),
        out_sample=run_battery(conditions, outcomes, sample_mask=out_mask, sample="out"),
        panel_notes=list(panel.notes),
    )


def _fmt(cell: Cell) -> str:
    return (
        f"  {cell.condition:24} {cell.outcome:16} n={cell.n_condition:>5} "
        f"(eff {cell.n_condition_eff:>5.0f})  {cell.rate_condition:>6.1%} vs "
        f"{cell.rate_complement:>6.1%}  lift {cell.lift:>+6.1%}  "
        f"[{cell.diff_lower:>+6.1%},{cell.diff_upper:>+6.1%}]  q={cell.qvalue:.3f}"
    )


def main() -> int:
    panel = build_panel()
    result = run_study(panel)

    print("=" * 112)
    print("XRP DEEP STUDY — the full battery")
    print("=" * 112)
    print(f"\n  bars                {len(panel)}  ({panel.dates[0]} .. {panel.dates[-1]})")
    print(f"  conditions kept     {result.n_conditions}")
    print(f"  outcomes            {result.n_outcomes}")
    print(f"  tests actually run  {result.n_tests}")
    print(f"  dropped as degenerate {len(result.dropped)}")
    for d in result.dropped:
        print(f"    - {d}")
    for note in result.panel_notes:
        print(f"  note: {note}")

    survivors = result.survivors
    confirmed = result.confirmed()
    print(f"\n  cleared FDR within family, interval excludes zero: {len(survivors)}")
    print(f"  ...of which hold their sign out of sample:          {len(confirmed)}")

    print("\n" + "=" * 112)
    print(f"SURVIVORS (full sample, BH q<{C.FDR_ALPHA} within family)")
    print("=" * 112)
    if not survivors:
        print("\n  Nothing survived. That is a result, not a failure.")
    for cell in survivors[:40]:
        mark = " OOS-CONFIRMED" if cell in confirmed else ""
        print(_fmt(cell) + mark)
    if len(survivors) > 40:
        print(f"  ... and {len(survivors) - 40} more")

    print("\n" + "=" * 112)
    print("PER-FAMILY SUMMARY — the whole distribution, not the best cells")
    print("=" * 112)
    print(f"\n  {'family':12} {'tests':>6} {'survive':>8} {'confirmed':>10} {'median |lift|':>14}")
    confirmed_set = {(c.condition, c.outcome) for c in confirmed}
    for fam in C.FAMILIES:
        rows = [c for c in result.full if c.family == fam.key]
        if not rows:
            continue
        surv = [c for c in rows if c.significant]
        conf = [c for c in rows if (c.condition, c.outcome) in confirmed_set]
        med = float(np.median([abs(c.lift) for c in rows]))
        print(f"  {fam.key:12} {len(rows):>6} {len(surv):>8} {len(conf):>10} {med:>13.1%}")

    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "bars": len(panel),
        "first_date": panel.dates[0],
        "last_date": panel.dates[-1],
        "n_conditions": result.n_conditions,
        "n_outcomes": result.n_outcomes,
        "n_tests": result.n_tests,
        "dropped": result.dropped,
        "panel_notes": result.panel_notes,
        "n_survivors": len(survivors),
        "n_confirmed": len(confirmed),
        "cells": [asdict(c) for c in result.full],
        "out_of_sample": [asdict(c) for c in result.out_sample],
    }
    (OUT / "study.json").write_text(json.dumps(payload, indent=2, allow_nan=True))
    print(f"\nwrote {OUT / 'study.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

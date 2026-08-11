# Robustness Review

**Protocol id:** `robustness-review` · **Packet kind:** `research_case`

## Purpose
Establish whether the measured effect survives the choices that should not matter — samples,
periods, regimes, parameter neighborhoods, and definitions.

## Method
1. From recorded exploration results, list every analytic choice that could have flattered the
   effect: window lengths, thresholds, detection parameters, sample boundaries.
2. Propose neighborhood sweeps over the REGISTERED grid only: the effect should degrade smoothly,
   not exist at a single setting. Cliff-edge effects are selection artifacts until proven
   otherwise.
3. Propose temporal stability views: rolling effect sizes, era splits (pre/post structural
   breaks), and decay after the idea's likely discovery date.
4. Propose regime decompositions along mechanism-relevant axes (volatility, trend, liquidity) —
   conditional existence is a finding, not a failure, but it must be stated.
5. Propose transportability checks on related instruments where the mechanism predicts presence
   AND absence; both directions are informative.
6. For each proposal state the expected pattern under a real effect vs a mined one.

## Output contract
Sensitivity-family proposals for the analysis plan; review commentary as `test_design` or
`completeness_review` notes.

## Boundaries
Robustness families are bounded by the registered budget and multiplicity accounting; unbounded
"try everything" sweeps are data mining wearing a lab coat.

# Falsification Design

**Protocol id:** `falsification-design` · **Packet kind:** `research_case`

## Purpose
Design the tests whose purpose is to DESTROY the hypothesis. A claim that has survived nothing
has demonstrated nothing.

## Method
1. For the registered claim, enumerate the distinct ways it could be falsely positive: chance
   under multiplicity, look-ahead leakage, confounder loading, artifact of bar construction,
   sample fragility.
2. Map each failure mode to a registered test: shuffled labels / permuted event times (chance),
   future-poisoned inputs must break detection (leakage), matched controls on confounder strata
   (loading), alternative bar constructions (artifact), subsample and temporal splits
   (fragility), randomised-price nulls (pattern illusions).
3. Add negative controls: populations or periods where the mechanism predicts NO effect — finding
   one there indicts the pipeline, not the market.
4. For every test fix in advance: the statistic, the pass/fail rule, and what a failure implies
   (abandon vs bound vs reformulate). Ambiguous falsifiers are not falsifiers.
5. Verify the registered stop rules cover falsifier failures — a failed falsifier must have
   consequences that cannot be argued away after the fact.

## Output contract
Falsifier and negative-control proposals (`test_design` notes) feeding the contract's
`required_falsifiers` and the analysis plan's falsification family.

## Boundaries
Falsifiers are frozen at approval; inventing friendlier ones after results exist is prohibited
by construction and would be visible in the contract lineage.

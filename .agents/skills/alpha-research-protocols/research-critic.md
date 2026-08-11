# Research Critic

**Protocol id:** `research-critic` · **Packet kind:** `validation`

## Purpose
Independently attack the case's current evidence in the adversarial-reviewer format. Assume the
work is wrong; your job is to find where.

## Method
1. From the validation packet, list every claim currently treated as established, each with its
   supporting artifact.
2. For each claim attempt at least one concrete refutation path: leakage (what future information
   could have entered?), selection (how many unrecorded attempts shadow this result?), confounder
   loading (which registered confounder remains unmatched?), fragility (which single choice, if
   flipped, kills it?), and measurement (does the statistic measure what the sentence says?).
3. Audit honesty surfaces: are NOT_TESTED dimensions displayed, are negative attempts ledgered,
   does any chart imply more than its caveat states?
4. Rank findings by severity: fatal (invalidates the claim), material (changes the conclusion's
   strength), cosmetic. Fatal findings must name the exact artifact and mechanism of failure.
5. State explicitly what evidence would change your assessment — a critique with no exit
   condition is posturing.

## Output contract
A structured critique note (`critique`) in the adversarial-reviewer format; fatal findings should
also propose the falsifier that would settle the question.

## Boundaries
The critic reads everything and decides nothing: no evidence status changes, no phase
transitions, no softening of language on request.

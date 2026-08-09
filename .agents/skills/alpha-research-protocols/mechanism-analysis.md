# Mechanism Analysis

**Protocol id:** `mechanism-analysis` · **Packet kind:** `research_case`

## Purpose
Interrogate why the phenomenon could exist, whether it should persist, and what else would
explain it — the difference between a pattern and an edge candidate.

## Method
1. Classify every candidate mechanism: risk premium, behavioural bias, structural/flow constraint,
   liquidity provision, information diffusion, or artifact (data, microstructure, methodology).
2. For each, ask: who is on the other side of the trade, why would they persistently accept it,
   and what would make them stop? A mechanism without a loser is usually an artifact.
3. Derive testable side-implications: if the mechanism is X, the effect should be stronger/weaker
   under conditions Y — these become falsification and robustness family candidates.
4. Review the registered confounders: which are resolved by design (matching), which need explicit
   tests, which remain open. Propose additions where coverage is thin.
5. Assess persistence: publication decay, crowding capacity, regime dependence, and whether the
   mechanism survives realistic frictions at the registered minimum effect.

## Output contract
A mechanism note (`confounder_review` or `synthesis`) with proposed confounder additions and
side-implication test candidates for the analysis plan.

## Boundaries
Mechanism plausibility is an argument, not evidence; the scorecard's mechanism dimension moves
only on recorded findings and screened claims.

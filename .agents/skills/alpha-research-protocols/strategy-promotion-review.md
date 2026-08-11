# Strategy-Promotion Review

**Protocol id:** `strategy-promotion-review` · **Packet kind:** `strategy_promotion`

## Purpose
Assess whether the research evidence is strong enough to justify starting strategy development —
the last gate before engineering effort is spent on the phenomenon.

## Method
1. Walk the edge-validation checklist against the packet: existence, magnitude vs the registered
   minimum effect, temporal and cross-asset stability, regime dependence, definition robustness,
   falsifier survival, artifact and leakage review, mechanism plausibility, cost headroom,
   sample sufficiency, residual uncertainty. Each answer must cite a finding or say NOT_TESTED.
2. Read the scorecard dimension by dimension; any dimension below its acceptable state needs an
   explicit argument for why promotion is still defensible — or the recommendation is to wait.
3. Review the negative ledger: what was tried and failed, and does the surviving claim depend on
   selection among those attempts?
4. State the strategy-development risks inherited from research: conditions under which the
   effect vanished, unresolved confounders, and the exact claim (and only that claim) that D2
   supported.
5. Recommend one of: ready for strategy research, more research (name the exact missing
   evidence), reformulate, or does-not-support-continuation. The owner decides on the CLI.

## Output contract
A promotion-readiness note (`completeness_review`) mapping checklist answers to citations; the
decision itself is owner-only.

## Boundaries
Never argue from expected profit. A SUPPORTED phenomenon with no cost headroom at the registered
minimum effect is a research success and a strategy non-starter — say so plainly.

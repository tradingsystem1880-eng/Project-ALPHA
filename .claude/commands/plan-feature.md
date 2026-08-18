---
description: Drive the alpha-feature-workflow front half - explore via subagents, then draft a dated plan doc
argument-hint: <feature or change description>
---

Plan the following Project ALPHA work: $ARGUMENTS

Follow `.agents/skills/alpha-feature-workflow/SKILL.md`. Steps:

1. If this is a trivial single-file fix, STOP and say "no plan needed — just do
   it", then do it with TDD. Never produce a 1-step plan.
2. Dispatch the `navigator` subagent with the concrete exploration questions;
   for changes touching quant/risk-tier paths also dispatch `invariants-auditor`
   in parallel. Do not explore inline — keep this context clean.
3. Dispatch the `test-architect` subagent for the failing-test specification.
4. Draft the dated plan doc at `docs/superpowers/plans/<today>-<slug>.md` (repo
   convention): context, slices of ≤ ~100 lines each with a per-slice verify
   command, explicit DAG / look-ahead / determinism impact, and the test plan.
5. Present the plan summary and wait for approval before implementing.

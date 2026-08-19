---
description: Drive the alpha-feature-workflow front half - explore via subagents, then draft a dated plan doc with a machine-checked FeaturePlan front block
argument-hint: <feature or change description>
---

Plan the following Project ALPHA work: $ARGUMENTS

Follow `.agents/skills/alpha-feature-workflow/SKILL.md`. Steps:

1. If this is a trivial single-file fix, STOP and say "no plan needed — just do
   it", then do it with TDD. Never produce a 1-step plan.
2. Dispatch the `navigator` subagent with the concrete exploration questions
   (it reads `.claude/state/repo-index.json` first); for changes touching
   quant/risk-tier paths also dispatch `invariants-auditor` in parallel. Do not
   explore inline — keep this context clean.
3. Dispatch the `test-architect` subagent for the failing-test specification.
4. Draft the dated plan doc at `docs/superpowers/plans/<today>-<slug>.md`. It
   MUST open with a fenced ```json front block whose fields match
   `scripts/harness_models.py::FeaturePlan` exactly — this is Karpathy §1–§3
   made structural, and `/implement` refuses to start without it. Prose
   sections follow the block: context, slices, test plan, DAG / look-ahead /
   determinism impact.
5. Run `uv run python scripts/gate.py plan-check <plan doc>` and paste its
   output; fix the block until it passes.
6. Present the plan summary (assumptions, rejected alternative, pre-mortem,
   slices) and wait for approval before implementing.

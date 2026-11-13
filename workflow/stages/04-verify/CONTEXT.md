---
owner: delivery pipeline
sources:
  - scripts/gate.py
  - scripts/harness_models.py
  - docs/roadmap/capabilities.toml
  - .claude/agents/*.md
  - scripts/handoff.py
verified: d0fffa796f8e
---

# Stage 04 — verify: prove it works

## Purpose

Show, with fresh evidence from this exact tree, that the change does what the plan said, and say
plainly what was not checked. A claim without a command and its result is not evidence.

## Inputs

- The branch from stage 03 and `docs/work/<task>/02-plan.md` (its slices' `verify` and
  `expected`, and its `tier_impact`).

## Read first

| Read | Section | When |
|---|---|---|
| [development loop](../../../docs/operations/development-loop.md) | What CI checks | always |
| [capability map](../../../docs/roadmap/capabilities.toml) | — | finding `proof_smoke` and `proof_synthetic`: read only the block naming the task or code |
| [quant source verification](../../../.agents/skills/quant-source-verification/SKILL.md) | Protocol | `tier_impact` has `quant` |
| [research integrity](../../../docs/reference/invariants/research-integrity.md) | Statistical evidence | the change computes or reports a statistic |

## Process

1. Run `uv run python scripts/gate.py check --base main` and every slice's `verify` again, now,
   on the last commit. Quote failures exactly; fix in stage 03 and come back.
2. Prove the workflow end to end: `grep -n "<task or module>" docs/roadmap/capabilities.toml`, then
   run that `[[capability]]` block's `proof_smoke` checks (`tests/smoke/`, marker `smoke`: they run
   the installed programs) and its `proof_synthetic` tests. If it lists none, or none exercises
   this change, write "no end-to-end check exists" and name the test that should (a slice or a
   backlog item).
3. When CI would run something heavier for this change (a component, the browser lanes, the slow
   oracles and mutation for quant files), run it with `uv run python scripts/gate.py component
   NAME` if the machine can, or list it as not run with the reason.
4. Review: `python3 scripts/handoff.py review --base main --task docs/work/<task>/` prints the
   reviewers the [routing rules](../../../docs/reference/model-routing.md#review-by-risk-tier)
   require for this diff and, for Claude-built work, runs Codex's review. The writer is never
   the only reviewer. Give each agent only the diff, never your reasoning.
5. Quant change: `quant-verifier` checks every formula, convention and default against the
   primary source, runs `tests/oracles/` for each changed primitive and recomputes values by
   hand; its `QuantVerificationReport` is FAIL unless all is verified. A FAIL goes back to 03.
   Findings of every reviewer are advisory: fix real defects or say why not.
6. Anything you could not run is written `UNVERIFIED:` with the reason; never "should pass".

## Outputs

`docs/work/<task>/04-verify.md` with exactly these headings:

- `## Commands run` — each command, the commit it ran on, and its result (counts, exit code).
- `## End-to-end check` — the test that proves the workflow and its result, or the statement
  that none exists and which one is needed.
- `## Not run` — every check CI or the plan would run that was not run here, and why.
- `## Review findings` — who built (from `03-build.json`), who reviewed with which model, and
  each finding with what was done about it.

## Checkpoint

The owner (or stage 05) reads `## Not run` and `## Review findings`. Landing waits while a
finding is open, a check failed, or something the plan promised is unverified without a reason.

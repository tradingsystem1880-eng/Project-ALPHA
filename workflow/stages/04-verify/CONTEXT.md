---
owner: delivery pipeline
sources:
  - scripts/gate.py
  - scripts/harness_models.py
  - docs/roadmap/capabilities.toml
  - .claude/agents/*.md
verified: 00f70c232ea5
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
| [capability map](../../../docs/roadmap/capabilities.toml) | — | always: the `proof_synthetic` tests of this task's capability |
| [quant source verification](../../../.agents/skills/quant-source-verification/SKILL.md) | Protocol | `tier_impact` has `quant` |
| [research integrity](../../../docs/reference/invariants/research-integrity.md) | Statistical evidence | the change computes or reports a statistic |

## Process

1. Run `uv run python scripts/gate.py check --base main` and every slice's `verify` again, now,
   on the last commit. Quote failures exactly; fix in stage 03 and come back.
2. Prove the workflow end to end: run the `proof_synthetic` tests listed for the task's
   capability in `docs/roadmap/capabilities.toml`. There is no `tests/smoke/` folder yet; if the
   capability lists none, or none exercises this change, write "no end-to-end check exists" and
   name the test that should (it becomes a slice or a backlog item).
3. When CI would run something heavier for this change (a component, the browser lanes, the slow
   oracles and mutation for quant files), run it with `uv run python scripts/gate.py component
   NAME` if the machine can, or list it as not run with the reason.
4. Quant change: the `quant-verifier` agent checks every formula, estimator convention and
   default against the primary source, runs the `tests/oracles/` suite for each changed primitive
   and recomputes values by hand; its `QuantVerificationReport` is FAIL unless every claim is
   verified, citations are complete and oracles exist. A FAIL goes back to stage 03.
5. Risk-tier, protected or quant change: the `reviewer` agent reviews the diff, given only the
   diff (never your reasoning). Its findings are advisory; fix real defects or say why not.
   An optional second opinion: `/codex-review`; dispose of each finding (agree, refute, out of
   scope) in this file.
6. Anything you could not run is written `UNVERIFIED:` with the reason; never "should pass".

## Outputs

`docs/work/<task>/04-verify.md` with exactly these headings:

- `## Commands run` — each command, the commit it ran on, and its result (counts, exit code).
- `## End-to-end check` — the test that proves the workflow and its result, or the statement
  that none exists and which one is needed.
- `## Not run` — every check CI or the plan would run that was not run here, and why.
- `## Review findings` — reviewer, quant-verifier and Codex findings with what was done about each,
  or "no review needed: tier_impact none".

## Checkpoint

The owner (or stage 05) reads `## Not run` and `## Review findings`. Landing waits while a
finding is open, a check failed, or something the plan promised is unverified without a reason.

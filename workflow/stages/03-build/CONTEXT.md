---
owner: delivery pipeline
sources:
  - scripts/handoff.py
  - scripts/codex_bridge.py
  - scripts/gate.py
  - tests/_tiers.py
  - .codex/config.toml
verified: 4bb90e5006d5dce5
---

# Stage 03 — build: plan to code

## Purpose

Make the plan true, one slice at a time, test first, in small commits on a branch.

## Inputs

- `docs/work/<task>/02-plan.md` as approved, with its `## Read first` table: read exactly those files and sections, plus the `CONTEXT.md` of each workspace
  you edit.
- On the small route (`workflow/CONTEXT.md`), no plan: the code area's `CONTEXT.md` and its Read first table stand in for it.

## Read first

| Read | Section | When |
|---|---|---|
| [tests workspace](../../../tests/CONTEXT.md) | How to change it | always: where each kind of test goes |
| [engineering rules](../../../docs/reference/invariants/engineering.md) | Errors | always |
| [testing invariants](../../../docs/reference/invariants/testing.md) | Bias guards | data access, a strategy or point-in-time semantics change |
| [engineering rules](../../../docs/reference/invariants/engineering.md) | Hash-bound source bytes | a file in `packages/alpha-research/src` changes |
| [engineering rules](../../../docs/reference/invariants/engineering.md) | Code size | the change adds lines to a large file or function |
| [development loop](../../../docs/operations/development-loop.md) | Evidence and recovery | a run failed and you are about to retry |
| [model routing](../../../docs/reference/model-routing.md) | Task classes | choosing the builder |

## Process

1. Work on a branch (`handoff.py` makes `build/<task>` in its own worktree). Set the plan's state to `In progress`.
2. Per slice: write its failing test and run it; it must fail for the expected reason (an assertion, not an import error). Write the least code that makes it
   pass, then run the slice's `verify` and compare with its `expected`.
3. Data, strategy or point-in-time changes need a `@pytest.mark.bias_guard` future-poison test; a new statistic needs an oracle in `tests/oracles/`. Never
   weaken a guard, an oracle or an assertion to get green.
4. Before committing, ask: does every changed line trace to this slice; what could be deleted; which assumption did it rely on; what input would break it
   (look-ahead, NaN, empty, a seed)? Add that test if it is cheap.
5. Run `uv run python scripts/gate.py check`, commit (`type(scope): summary`), and mark the slice `done` in the front block. A slice that deviates is reported
   in the plan, not hidden.
6. Hash-bound source: approvals made since ADR-0045 survive comments and formatting, older ones need exact bytes (no cosmetic edits; say in the plan that
   approvals will need renewing). Changing a quant-tier file makes CI add the slow oracles and the mutation gate for the touched modules.
7. Update the one owning document of every fact you changed, in the same branch.
8. Agents never run owner actions (approvals, decisions, D2, promotion, holdout reveal, paper or orders); stop and hand them to the owner.

## Outputs

- Commits on the branch, one or more per slice, with the plan's slice statuses kept true.
- `03-build.json`, the build record; from a brief, `brief.md` and `report.md` ([task folders](../../../docs/work/CONTEXT.md)).

## Checkpoint

Every slice is `done` or reported as deviated in the plan, `gate.py check` is green on the last commit, and `git diff --stat main...` matches the plan's
`files` (explain any difference).

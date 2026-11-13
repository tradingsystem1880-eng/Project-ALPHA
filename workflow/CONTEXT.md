---
owner: delivery pipeline
sources:
  - workflow/stages/*/CONTEXT.md
  - scripts/roadmap_index.py
  - scripts/handoff.py
  - tests/unit/test_plan_schema.py
  - tests/unit/test_filesystem_contract.py
verified: f89aa1bb78af
---

# Delivery pipeline — how a change gets made

## Purpose

Every change to ALPHA walks five stages, in order. Each stage reads the previous stage's file,
does one job, leaves one plain file the owner can read and edit, and stops at a checkpoint. Pick
the stage your task is in from the table below, open its `CONTEXT.md` and follow it; the rules a
stage needs are in the files its Read first table names.

| Stage | Takes in | Leaves behind | Command |
|---|---|---|---|
| [01 shape](stages/01-shape/CONTEXT.md) | the owner's idea, in their words | `01-brief.md`, or a backlog file | `/shape` |
| [02 plan](stages/02-plan/CONTEXT.md) | `01-brief.md` | `02-plan.md` | `/plan` |
| [03 build](stages/03-build/CONTEXT.md) | `02-plan.md` | commits on a branch | `/build` |
| [04 verify](stages/04-verify/CONTEXT.md) | the branch and `02-plan.md` | `04-verify.md` | `/verify` |
| [05 land](stages/05-land/CONTEXT.md) | `04-verify.md` | `05-handoff.md`, a pull request | `/land` |

Which stage am I in? No task folder yet: 01. A brief but no plan: 02. A plan whose slices are not
all `done`: 03. Slices done but no `04-verify.md`: 04. Otherwise: 05.

## Read first

| Read | Section | When |
|---|---|---|
| [documentation invariants](../docs/reference/invariants/documentation.md) | Feature plans | always |
| [engineering rules](../docs/reference/invariants/engineering.md) | Working style | always |
| [research integrity](../docs/reference/invariants/research-integrity.md) | — | the change touches data, strategies, statistics or owner actions |

## The task folder

- One folder per task: `docs/work/<yyyy-mm-dd>-<slug>/`, named after the day it was shaped and a
  few lowercase words (`2026-11-14-coverage-source-column`).
- It holds only the stage files `01-brief.md`, `02-plan.md`, `03-build.json` (the build record
  `scripts/handoff.py` writes), `04-verify.md` and `05-handoff.md`. A folder is committed only once it has a `02-plan.md`
  (the contract test checks this); an idea that must wait goes to the backlog instead.
- The owner may edit any stage file between stages; the next stage reads the edited file, not
  the agent's memory of it.
- Finished folders move to `docs/work/archive/<yyyy-mm>/` (stage 05). Plans finished before
  2026-11-14 are single files there.
- The small route skips the folder: a fix confined to one module and its tests, with an obvious
  test, or a documentation-only change. It runs stages 03–05 on a branch: 03 builds from a
  short brief (stage 03 names its headings) and the code area's `CONTEXT.md` in place of a plan,
  04's results go under `## Checks run` in the pull request, and 05 fills the template directly
  (no `05-handoff.md`, no close-out).

## How to change it

- Each stage file follows the shape checked by `tests/unit/test_filesystem_contract.py`:
  Purpose, Inputs, Read first, Process, Outputs, Checkpoint; at most 80 lines.
- A rule a stage needs belongs in a reference file (`docs/reference/`); the stage links it.
- Agents (`.claude/agents/`) and commands (`.claude/commands/`) are entry points into these
  stages and hold no rules of their own.

## Outputs

- The stage files of each task under `docs/work/`, and the pull request.
- The owning document for the plan and roadmap rules: `docs/reference/invariants/documentation.md`.

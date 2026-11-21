---
owner: delivery pipeline
sources:
  - workflow/stages/*/CONTEXT.md
  - workflow/README.md
verified: da30c360725762dc
---

# Delivery pipeline — how a change gets made

## Purpose

A planned change to ALPHA walks five stages, in order; the small route skips the stage files. Each stage reads the previous stage's file, does one job,
leaves one plain file the owner can read and edit, and stops at a checkpoint. Pick your stage from the table, open its `CONTEXT.md` and follow it.

| Stage | Takes in | Leaves behind | Command |
|---|---|---|---|
| [01 shape](stages/01-shape/CONTEXT.md) | the owner's idea, in their words | `01-brief.md`, or a backlog file | `/shape` |
| [02 plan](stages/02-plan/CONTEXT.md) | `01-brief.md` | `02-plan.md` | `/plan` |
| [03 build](stages/03-build/CONTEXT.md) | `02-plan.md` | commits on a branch | `/build` |
| [04 verify](stages/04-verify/CONTEXT.md) | the branch and `02-plan.md` | `04-verify.md` | `/verify` |
| [05 land](stages/05-land/CONTEXT.md) | `04-verify.md` | `05-handoff.md`, a pull request | `/land` |

## Read first

| Read | Section | When |
|---|---|---|
| [documentation invariants](../docs/reference/invariants/documentation.md) | Feature plans | always |
| [engineering rules](../docs/reference/invariants/engineering.md) | Working style | always |
| [what this part is for](../docs/reference/project/components/delivery-and-agent-tooling.md) | — | why it exists; before you keep, shelve or remove it |
| [README](README.md) | — | landing a change, task folders, the small route, stage rules |

## How to change it

- Landing a change, task folders and the shape of a stage file: [README](README.md#from-an-idea-to-a-merged-change).

## Outputs

- The stage files of each task on its branch (`docs/work/<task>/`), and the pull request, the lasting record.
- The owning document for the plan and roadmap rules: `docs/reference/invariants/documentation.md`.

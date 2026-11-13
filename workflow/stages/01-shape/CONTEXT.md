---
owner: delivery pipeline
sources:
  - docs/roadmap/backlog/*.md
  - docs/roadmap/wip-limit.json
  - scripts/status.py
  - tests/unit/test_status_page.py
verified: 40d916b11519
---

# Stage 01 — shape: idea to brief

## Purpose

Turn what the owner asked for into a short brief in their words, or park it as a backlog item.
Nothing is designed or built here; the job is to agree what "done" means before anyone plans.

## Inputs

- The owner's request, quoted exactly as they gave it (chat, issue, triage card).
- `STATUS.md` line "Work in progress", to see whether a new task may start.

## Read first

| Read | Section | When |
|---|---|---|
| [STATUS.md](../../../STATUS.md) | At a glance | always: the work-in-progress count and what is allowed |
| [roadmap index](../../../docs/roadmap/README.md) | — | `fs.py search` finds a plan or backlog item that may cover it |
| [documentation invariants](../../../docs/reference/invariants/documentation.md) | Roadmap index | writing a backlog file |
| [research integrity](../../../docs/reference/invariants/research-integrity.md) | Research before strategy | the idea is a market idea or a strategy |

## Process

1. Restate the request in one sentence and search for it: `uv run python scripts/fs.py search
   "<words>"` (live plans and backlog items rank first). If a live plan covers it, stop and say so.
2. Decide the size: the small route in [the pipeline](../../CONTEXT.md#the-task-folder) needs no
   task folder and is not counted against the cap. When unsure, ask the owner; say which you chose.
3. Check the work-in-progress limit. Count = live plans `In progress` or
   `Implemented – qualification pending`; the cap is `ceiling` in `docs/roadmap/wip-limit.json`
   (it falls to `limit`, 3, as work closes). When the count is at the cap, a new task may not
   start: write a backlog file instead and tell the owner which open work blocks it.
4. Ask at most three questions, and only ones that change what gets built; give your
   recommended answer with each. Record every other default in the brief.
5. A market idea is research, not a feature: it goes to the research pipeline (a research case),
   never straight to strategy code.
6. Write the output below in plain English the owner can read without the code.

## Outputs

Either a backlog file `docs/roadmap/backlog/<slug>.md` (copy an existing file: `**Status:**`
`Idea` or `Scoped` and `**Rough size:**` in the first 8 lines), then run
`uv run python scripts/roadmap_index.py`; or `docs/work/<yyyy-mm-dd>-<slug>/01-brief.md` with
exactly these headings:

- `## What the owner wants` — their words, quoted, then one plain sentence.
- `## What done looks like` — what will be true for them, not which files change.
- `## How they will see it` — one command or Workstation screen, or "nothing visible: internal".
- `## Out of scope` — what this task will not do.

The brief is committed together with its `02-plan.md`, never alone.

## Checkpoint

The owner reads `01-brief.md` (or the backlog file) and confirms or edits it. Stage 02 starts
from the confirmed brief; a brief the owner has not seen is not confirmed, unless the request
itself already said what done looks like and how to see it.

---
owner: delivery pipeline
sources:
  - scripts/status.py
  - scripts/roadmap_index.py
verified: af0137c5fd74
---

# Stage 01 — shape: idea to brief

## Purpose

Turn what the owner asked for into a short brief in their words, or park it as a backlog item.
Nothing is designed or built here; the job is to agree what "done" means before anyone plans.

## Inputs

- The owner's request, quoted exactly as they gave it (chat, issue, triage card).
- The open pull requests (`gh pr list`), to see what is already in flight.

## Read first

| Read | Section | When |
|---|---|---|
| [STATUS.md](../../../STATUS.md) | At a glance | always: what works and what waits for the owner |
| [component files](../../../docs/reference/project/overview.md) | Components | the request touches a part: read its file and the owner decisions log |
| [roadmap index](../../../docs/roadmap/README.md) | — | `fs.py search` finds a plan or backlog item that may cover it |
| [documentation invariants](../../../docs/reference/invariants/documentation.md) | Roadmap index | writing a backlog file |
| [research integrity](../../../docs/reference/invariants/research-integrity.md) | Research before strategy | the idea is a market idea or a strategy |

## Process

1. Restate the request in one sentence and search for it: `uv run python scripts/fs.py search
   "<words>"`. If a backlog item or an open pull request covers it, stop and say so.
2. Decide the size: the small route in [the pipeline](../../CONTEXT.md#the-task-folder) needs no
   task folder. When unsure, ask the owner; say which you chose.
3. Ask at most three questions, and only ones that change what gets built; give your
   recommended answer with each. Record every other default in the brief.
4. A request to shelve, delete or cut a part starts from its component file and the owner
   decisions log ([rule](../../../docs/reference/project/overview.md#before-you-recommend-removing-anything)).
   Being uninstalled, skipped or unfinished is a task to finish, not a reason to shelve.
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

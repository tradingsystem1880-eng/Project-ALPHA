---
owner: delivery pipeline
sources:
  - scripts/harness_models.py
  - scripts/harness_awareness.py
verified: aa600e57932d
---

# Stage 02 — plan: brief to plan

## Purpose

Turn the confirmed brief into a plan the owner can read and edit, and a builder (Claude or Codex)
can follow without asking: small slices, each with its own check, and the exact files and
sections to read first.

## Inputs

- `docs/work/<task>/01-brief.md`, as the owner left it.

## Read first

| Read | Section | When |
|---|---|---|
| [documentation invariants](../../../docs/reference/invariants/documentation.md) | Feature plans | always |
| [root routing](../../../CONTEXT.md) | Read first | always: find the workspace each change lands in |
| [component files](../../../docs/reference/project/overview.md) | Components | always: read the file of each part the plan changes |
| [capability map](../../../docs/roadmap/capabilities.toml) | — | the plan changes what a capability can do |
| [engineering rules](../../../docs/reference/invariants/engineering.md) | Quant tier | a file in the quant tier changes |
| [engineering rules](../../../docs/reference/invariants/engineering.md) | Hash-bound source bytes | `packages/alpha-research/src` would change |

## Process

1. Open the `CONTEXT.md` of every workspace the change touches and note the files and sections
   its Read first table names for this kind of change; `uv run python scripts/fs.py search
   "<words>"` finds anything else. Read only those; do not survey the repository.
2. Slice by behaviour and risk: each slice is one observable step with a failing test first, a
   focused `verify` command, the `expected` result and a `rollback`. At least two slices; a plan
   that would need one slice needed no plan.
3. State the assumptions you rely on and what verified each, the alternative you rejected, and
   at least two ways the plan could fail (the pre-mortem).
4. Set `tier_impact` honestly: `quant`, `risk`, `protected`, `dag`, `bias`, `determinism` or
   `none`. List every file in scope in `files` (the builder's diff is checked against it) and
   name protected files the change touches. State the task class ([model
   routing](../../../docs/reference/model-routing.md#task-classes)) as a `**Build class:**` line.
5. Name the one owning document each changed fact lives in (`docs_to_update`).
6. Check the plan: `uv run python scripts/gate.py plan-check docs/work/<task>/02-plan.md`, and fix
   the front block until it passes. Never weaken the schema to make a plan pass.

## Outputs

`docs/work/<task>/02-plan.md`, in this order:

1. `# <title>`, then within the first 12 lines one `**Delivery state:** Planned — <note>` line
   (vocabulary in the Feature plans rules; `In progress` once stage 03 starts), and one `**Build class:** small|standard|hard — <reason>` line.
2. `## For the owner` — at most 10 plain-English lines: what will change for them, how they will
   see it, what it will not do, anything they must decide.
3. The first fenced `json` block: a `FeaturePlan` (`scripts/harness_models.py`).
4. `## Read first` — a table `| Read | Section | When |` naming the exact files and sections the
   builder must read for this task (workspace files, invariants, the code it changes).
5. `## Slices`, `## Test plan`, `## Look-ahead, determinism and import impact` — short prose.

If a backlog file described this work, delete it in the same commit.

## Checkpoint

The owner reads `## For the owner` and the slices, and edits or approves. Building starts only on
an approved plan; when the request already authorised the work, say which part of it did.

---
owner: project layer
sources:
  - workflow/CONTEXT.md
  - scripts/CONTEXT.md
  - tests/CONTEXT.md
  - docs/CONTEXT.md
  - tools/alpha-eval/CONTEXT.md
  - docs/reference/model-routing.md
verified: a79d832d
---

# Delivery and agent tooling

How ALPHA itself is changed: the five-stage delivery pipeline, the one check (the gate), the test
suite with its look-ahead guards and statistical oracles, the agent benchmark, and this file
system that tells every agent what to read.

## Why it exists

ALPHA is built mostly by AI agents for an owner who is not a programmer. The owner has said the
project "is constantly a mess" and should "never get to a point of mess"
([owner decisions](../owner-decisions.md#2026-11-14-steady-progress-never-a-mess)). This part keeps
work small, checked, recorded and readable, so progress is steady and nothing is lost.

## Its job in the research loop

None directly. It protects the loop: tests guard against look-ahead and wrong statistics, and the
file system makes sure an agent knows what each part is for before changing it.

## Intended design

- Every change walks the [delivery pipeline](../../../../workflow/CONTEXT.md): shape, plan, build,
  verify, land. CI on the pull request is the merge gate ([ADR-0039](../../../adr/0039-ci-is-the-merge-gate.md)).
- Codex builds, Claude plans, decides and reviews
  ([owner decisions](../owner-decisions.md#2026-11-14-codex-builds-claude-plans); details in
  [model routing](../../model-routing.md)).
- The file system follows the Interpretable Context Methodology adapted to a codebase
  ([ADR-0040](../../../adr/0040-one-file-system-atlas-retired.md)). This project layer is its
  stable reference about purpose; the routing files and invariants say how to change code.

## What is real today

The gate, the pipeline and the file system are in use; `uv run python scripts/gate.py check` runs
the local check. This part has no owner-facing capability on [STATUS.md](../../../../STATUS.md).

## Where it lives

- **Workspaces:** `workflow`, `scripts`, `tests`, `docs`, `tools/alpha-eval`
- **Capabilities:** none
- Code: `scripts/` (gate, file-system tools, hand-off), `tests/`, `tools/alpha-eval/`, `.claude/`.
- How to change it: [workflow/CONTEXT.md](../../../../workflow/CONTEXT.md),
  [scripts/CONTEXT.md](../../../../scripts/CONTEXT.md), [tests/CONTEXT.md](../../../../tests/CONTEXT.md),
  [docs/CONTEXT.md](../../../CONTEXT.md), [tools/alpha-eval/CONTEXT.md](../../../../tools/alpha-eval/CONTEXT.md).
- Backlog: [weekly mutation sweep](../../../roadmap/backlog/weekly-mutation-sweep.md).
- Decision records: [ADR-0034](../../../adr/0034-agent-operating-system-v2.md),
  [ADR-0037](../../../adr/0037-agent-neutral-research-engineering.md),
  [ADR-0039](../../../adr/0039-ci-is-the-merge-gate.md),
  [ADR-0040](../../../adr/0040-one-file-system-atlas-retired.md),
  [ADR-0041](../../../adr/0041-no-hidden-test-suite.md).

## Decisions and open questions

- Triage decisions, 2026-11-14 under the owner's delegation ([triage sheet](../../../roadmap/triage-2026-11.md)): card 12 KEEP; card 14
  DELETE (both old clean-up plans archived, the failing weekly mutation sweep moved to the backlog);
  card G DELETE (the delivery-task backlog item closed, replaced by
  [model routing](../../model-routing.md) and `scripts/handoff.py`). Owner to confirm: archiving
  the old hand-off pilot folder outside the repository is left to you.

## Never

- Never weaken bias guards, oracles or the guarded holdout path to make a change pass.
- Never copy a fact into a second file; link to its one home.
- The rules: [engineering rules](../../invariants/engineering.md),
  [testing invariants](../../invariants/testing.md) and
  [documentation invariants](../../invariants/documentation.md).

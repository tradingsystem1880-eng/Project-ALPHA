---
owner: project layer
sources:
  - packages/alpha-research/CONTEXT.md
  - packages/alpha-study/CONTEXT.md
  - research/CONTEXT.md
  - docs/reference/invariants/cli-research.md
verified: a79d832d
---

# Research cases and owner approval

A research case is the record of one market question from idea to decision: what will be tested,
on which data, with what budget, what happened, and what the owner decided. Owner approval is the
only way anything in ALPHA becomes evidence or moves forward.

## Why it exists

Research must come before strategy, and only the owner may decide what is true enough to act on.
With live capital as the end goal, every decision needs a clear, unforgeable record of who
decided, on what evidence ([owner decisions](../owner-decisions.md#2026-11-14-precision-and-live-capital)).

## Its job in the research loop

Steps 1 and 7 of the [research loop](../overview.md#the-research-loop): it captures the question
and its contract at the start, and records the owner's decision at the end. In between it keeps
history split into phases so a result is confirmed on data it was not discovered on: D0 (a
synthetic pilot), D1 (discovery), D2 (one-shot confirmation) and D3 (a final holdout that research
never sees).

## Intended design

- The control store (a local database owned by the [command line](command-line.md)) holds cases,
  jobs, evidence and the owner's signed receipts.
- Each owner act needs an explicit local confirmation tied to that exact act
  ([ADR-0038](../../../adr/0038-local-confirmation-and-terminal-archive-charts.md)); no screen,
  agent or model can stand in for the owner.
- The phase split and gate packets are pure, fixed code whose bytes feed approval hashes.

## What is real today

See the capabilities below on [STATUS.md](../../../../STATUS.md).

## Where it lives

- **Workspaces:** `packages/alpha-research`, `packages/alpha-study`, `research`
- **Capabilities:** `research-cases`, `quick-screening`
- Code: `packages/alpha-research/src/`, `packages/alpha-study/src/`; cases, decisions and the control
  store in `apps/alpha-cli/src/alpha_cli/` (`research_cmds.py`, `control_store.py`, `owner_auth.py`).
- Tests: `tests/smoke/test_research_smoke.py`, and the research tests under `tests/unit/`.
- How to run a case, stage by stage (idea, data, screen, confirm, validate, decide): the
  [research pipeline](../../../../research/CONTEXT.md) and its [research method](../../research-method.md).
- How to change it: [packages/alpha-research/CONTEXT.md](../../../../packages/alpha-research/CONTEXT.md),
  [packages/alpha-study/CONTEXT.md](../../../../packages/alpha-study/CONTEXT.md).
- Backlog: [D0 generalisation](../../../roadmap/backlog/d0-generalisation.md).
- Decision records: [ADR-0019](../../../adr/0019-governed-research-cases-before-strategy-development.md),
  [ADR-0026](../../../adr/0026-d2-confirmation-readiness-gate-promotion-override.md),
  [ADR-0027](../../../adr/0027-tiered-research-readiness-semantics.md),
  [ADR-0030](../../../adr/0030-touch-id-owner-presence-for-research-actions.md),
  [ADR-0038](../../../adr/0038-local-confirmation-and-terminal-archive-charts.md).

## Decisions and open questions

- No owner decision recorded in the log for this part yet.

## Never

- Never infer an approval: not from silence, a past approval, a green check or a model's answer.
- Never add a new route for owner authority, and never reveal the final holdout to research.
- Never make cosmetic edits under `packages/alpha-research/src`; its bytes feed approval hashes.
- The rules: [owner authority](../../invariants/research-integrity.md#owner-authority),
  [research invariants](../../invariants/research.md) and
  [command line research](../../invariants/cli-research.md).

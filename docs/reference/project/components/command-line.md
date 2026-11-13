---
owner: project layer
sources:
  - apps/alpha-cli/CONTEXT.md
  - packages/alpha-core/CONTEXT.md
  - docs/ARCHITECTURE.md
verified: f89aa1bb78af
---

# Command line

The `alpha` command is the one place that joins all the other parts: data, rules, the engine,
the statistics, research cases and the workers. It owns the control store (the local database of
cases, jobs, evidence and the owner's receipts). Underneath everything sits a small shared core of
basic types, errors and settings (`alpha-core`), listed here because it has no job of its own.

## Why it exists

If several programs could each run experiments or record decisions, nobody could be sure which
result is the real one or who approved it. One composer means one route for every action, which
the browser screens and AI tools must go through as well
([ADR-0002](../../../adr/0002-cli-sole-composer-subprocess-surfaces.md)).

## Its job in the research loop

It runs every step of the [research loop](../overview.md#the-research-loop) on request: it starts
the workers (including [RD-Agent](rd-agent.md) jobs), runs backtests and checks, and records the
owner's decisions.

## Intended design

- The packages form layers that may only import downward ([ADR-0001](../../../adr/0001-strict-layered-dag.md));
  the command line is at the top of the research layers.
- The [Workstation](web-workstation.md) and the [AI tool server](ai-assistants.md) call it as a
  separate process and never import its internals.
- The control store is the development control plane ([ADR-0014](../../../adr/0014-cli-owned-development-control-plane.md)).

## What is real today

Every capability on [STATUS.md](../../../../STATUS.md) runs through it; each is claimed by the part
it belongs to.

## Where it lives

- **Workspaces:** `apps/alpha-cli`, `packages/alpha-core`
- **Capabilities:** none
- Code: `apps/alpha-cli/src/alpha_cli/`, `packages/alpha-core/src/alpha_core/`.
- Commands: [command reference](../../commands.md) (generated).
- How to change it: [apps/alpha-cli/CONTEXT.md](../../../../apps/alpha-cli/CONTEXT.md),
  [packages/alpha-core/CONTEXT.md](../../../../packages/alpha-core/CONTEXT.md).
- Decision records: [ADR-0001](../../../adr/0001-strict-layered-dag.md),
  [ADR-0002](../../../adr/0002-cli-sole-composer-subprocess-surfaces.md),
  [ADR-0014](../../../adr/0014-cli-owned-development-control-plane.md),
  [ADR-0015](../../../adr/0015-evidence-ledger-not-agent-memory.md).

## Decisions and open questions

- No owner decision about this part is in the [owner decisions log](../owner-decisions.md) yet.

## Never

- Never grant authority the owner did not give, and never route live capital.
- Never let another surface bypass it to run an action or read the control store directly.
- The rules: [engineering rules](../../invariants/engineering.md#import-layers),
  [subprocess boundary](../../invariants/engineering.md#subprocess-boundary) and
  [command line control store](../../invariants/cli-control-store.md).

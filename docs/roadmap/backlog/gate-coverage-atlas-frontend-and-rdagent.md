# Gate coverage for the Atlas frontend and workers/rdagent

**Status:** Scoped
**Rough size:** S

## Problem / why

The canonical gate has six components (backend, frontend, literature, qlib, atlas, eval). The
Atlas component runs only the Python project; `tools/alpha-atlas/frontend` (its own `oxlint` and
`vitest` scripts) is not gated. `workers/rdagent` has its own lock and project but no tests
directory and no gate component.

## What "done" looks like

Atlas frontend lint/test run inside the atlas component (or a new one), and a decision recorded
for `workers/rdagent`: either a gate component with tests, or an explicit documented exclusion.

## Dependencies

Changes to `scripts/gate_components.py` are protected and need owner acknowledgement.

## Sources

- [Development loop](../../operations/development-loop.md)
- [Atlas README](../../../tools/alpha-atlas/README.md) and [RD-Agent worker README](../../../workers/rdagent/README.md)

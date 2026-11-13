# Gate coverage for workers/rdagent

**Status:** Scoped
**Rough size:** S

## Problem / why

CI runs five gate components (backend, frontend, literature, qlib, eval). `workers/rdagent` has
its own lock and project but no tests directory and no gate component, so nothing checks it on a
pull request.

## What "done" looks like

A decision recorded for `workers/rdagent`: either a gate component with tests (added to
`scripts/gate_components.py`, a CI job and the `ci-ok` job's `needs`), or an explicit documented
exclusion.

## Dependencies

Changes to `scripts/gate_components.py` and `.github/workflows/` are protected and need owner
acknowledgement.

## Sources

- [Development loop](../../operations/development-loop.md)
- [RD-Agent worker README](../../../workers/rdagent/README.md)

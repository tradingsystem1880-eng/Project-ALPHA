---
owner: development tooling
sources:
  - scripts/gate.py
  - scripts/gate_components.py
  - scripts/gate_select.py
  - scripts/gate_preflight.py
  - scripts/fs*.py
  - scripts/commands_reference.py
  - scripts/roadmap_index.py
  - scripts/setup.sh
verified: 3686090948c9d166
---

# scripts workspace

## Purpose

The developer and CI tooling: the gate, test selection, file-system tools, generators and agent hooks. They never read owner data, credentials or hidden tests.

## Read first

| Read | Section | When |
|---|---|---|
| [engineering rules](../docs/reference/invariants/engineering.md) | Checks and commits | always |
| [testing invariants](../docs/reference/invariants/testing.md) | Markers and tiers | always |
| [checks](../docs/reference/checks.md) | — | adding, moving or retiming a CI job or check |
| [agent harness](../docs/operations/claude-code-harness.md) | — | changing agent hooks, deny rules or harness settings |
| [research integrity](../docs/reference/invariants/research-integrity.md) | Protected and hidden tests | changing search, hooks or test selection |
| [what this part is for](../docs/reference/project/components/delivery-and-agent-tooling.md) | — | why it exists; before you keep, shelve or remove it |
| [checks](../docs/reference/checks.md) | Scripts code map | finding a script or its tests |

## How to change it

- Code, tests and protected files: [scripts code map](../docs/reference/checks.md#scripts-code-map); check with `uv run python scripts/gate.py check`.

## Outputs

- The owning document: `docs/reference/invariants/testing.md` for the gate and sweeps;
  `docs/reference/invariants/documentation.md` for generators.

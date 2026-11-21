---
owner: command line application
sources:
  - apps/alpha-cli/src/**
  - apps/alpha-cli/pyproject.toml
verified: e51b66c1cc378fb6
---

# alpha-cli workspace
## Purpose
The `alpha` CLI composes data, strategies, the engine, validation, research and models, and owns the SQLite control store.
It must never grant authority the owner did not give, and never route live capital.

## Read first
| Read | Section | When |
|---|---|---|
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Owner authority | always |
| [engineering rules](../../docs/reference/invariants/engineering.md) | Subprocess boundary | always |
| [engineering rules](../../docs/reference/invariants/engineering.md) | Hash-bound source bytes | always |
| [command reference](../../docs/reference/commands.md) | — | finding a command or its options |
| [command line research](../../docs/reference/invariants/cli-research.md) | — | research cases, contracts, D0/D1/D2 runs, `research_*` |
| [command line control store](../../docs/reference/invariants/cli-control-store.md) | — | the SQLite control store, migrations, owner receipts, jobs |
| [command line runs](../../docs/reference/invariants/cli-runs.md) | — | backtest, validate, rule tests, tools, suites, nightly run |
| [command line native](../../docs/reference/invariants/cli-native.md) | — | native fixtures and rule jobs, RD-Agent loops, `native_*` |
| [what this part is for](../../docs/reference/project/components/command-line.md) | — | why it exists; before you keep, shelve or remove it |
| [invariants router](../../docs/reference/invariants/README.md) | Command line | other areas: setups, data, ml, paper, assistant, follow |
| [toolbox](../../docs/reference/project/components/toolbox.md) | — | `alpha tool`: adding a test; the honesty rules |
| [alpha-cli README](README.md) | Code map | finding a module or its tests |

## How to change it
- Code and tests: [code map](README.md#code-map). A new or changed command: [change loop](README.md#change-loop).
- Check: `uv run python scripts/gate.py check`.
- Owner approvals bind code structure, not bytes: [approvals](README.md#approvals-bind-structure).

## Outputs
- Tests and the owning `cli-*.md` page: see the [code map](README.md#code-map) and [change loop](README.md#change-loop).

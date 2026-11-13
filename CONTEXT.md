---
owner: file system routing
sources:
  - packages/*/pyproject.toml
  - apps/*/pyproject.toml
  - workers/*/pyproject.toml
  - tools/*/pyproject.toml
verified: 1ac86fc02443
---

# Project ALPHA — where to start

## Purpose

This file routes a task to the one area that owns it. Pick the row that matches your task, open
that area's `CONTEXT.md`, and read only what its Read first table names. Rules live in the files
it points to, never here.

## Read first

| Read | Section | When |
|---|---|---|
| [packages/alpha-core/CONTEXT.md](packages/alpha-core/CONTEXT.md) | — | domain types, typed errors, settings, cost helpers |
| [packages/alpha-data/CONTEXT.md](packages/alpha-data/CONTEXT.md) | — | point-in-time store, snapshots, crypto storage (commands, reports: alpha-cli) |
| [packages/alpha-patterns/CONTEXT.md](packages/alpha-patterns/CONTEXT.md) | — | chart-pattern geometry and indicators |
| [packages/alpha-strategies/CONTEXT.md](packages/alpha-strategies/CONTEXT.md) | — | trading signals, sizing, strategy rules |
| [packages/alpha-backtest/CONTEXT.md](packages/alpha-backtest/CONTEXT.md) | — | the Nautilus backtest harness, fills, fees |
| [packages/alpha-validation/CONTEXT.md](packages/alpha-validation/CONTEXT.md) | — | statistics: walk-forward, nulls, bootstrap, Deflated Sharpe, CPCV |
| [packages/alpha-research/CONTEXT.md](packages/alpha-research/CONTEXT.md) | — | phase split, event studies, gate packet values (assembly: alpha-cli) |
| [packages/alpha-forecast/CONTEXT.md](packages/alpha-forecast/CONTEXT.md) | — | the Kronos forecasting model |
| [packages/alpha-study/CONTEXT.md](packages/alpha-study/CONTEXT.md) | — | study projections over research data (no authority) |
| [apps/alpha-cli/CONTEXT.md](apps/alpha-cli/CONTEXT.md) | — | any `alpha` command or report, research cases, gate packets, control store, jobs |
| [apps/alpha-web/CONTEXT.md](apps/alpha-web/CONTEXT.md) | — | the Workstation web app: API routes or browser panels |
| [apps/alpha-mcp/CONTEXT.md](apps/alpha-mcp/CONTEXT.md) | — | the MCP server's tools |
| [workers/qlib/CONTEXT.md](workers/qlib/CONTEXT.md) | — | the isolated Qlib machine-learning worker |
| [workers/literature/CONTEXT.md](workers/literature/CONTEXT.md) | — | the literature acquisition worker |
| [workers/rdagent/CONTEXT.md](workers/rdagent/CONTEXT.md) | — | the RD-Agent native-loop worker |
| [tools/alpha-eval/CONTEXT.md](tools/alpha-eval/CONTEXT.md) | — | the agent benchmark and evaluation tool |
| [scripts/CONTEXT.md](scripts/CONTEXT.md) | — | the gate, CI steps, file-system tools, generators |
| [tests/CONTEXT.md](tests/CONTEXT.md) | — | test layout, markers, bias guards, oracles |
| [docs/CONTEXT.md](docs/CONTEXT.md) | — | documentation, ADRs, plans, this file system |
| `workflow/` (coming) | — | delivering a change stage by stage: shape, plan, build, verify, land |
| `research/stages/` (coming) | — | running a research case stage by stage: idea to decision |

A task that spans areas: start at the area whose code you change first; its Read first table
links the others it depends on.

## One home per fact

| Fact | Its one home |
|---|---|
| Commands and options | [docs/reference/commands.md](docs/reference/commands.md) (generated) |
| Rules that must not break | [docs/reference/invariants/](docs/reference/invariants/research-integrity.md) |
| Decisions and their reasons | [docs/adr/](docs/adr/README.md) |
| Package layers and data folders | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Current status | `STATUS.md` (coming, generated) |
| History | git log and pull requests |
| Glossary | `docs/reference/glossary.md` (coming) |

When a fact changes, update its one home and link to it from elsewhere; never copy it.

## Finding anything else

- `uv run python scripts/fs.py orient` lists the areas and their module counts.
- `uv run python scripts/fs.py search "<words>"` finds ranked excerpts, live documents first.
- `uv run python scripts/fs.py stale` lists documents whose sources changed since they were verified.

## How to change it

- Add a row when a workspace is added; `tests/unit/test_filesystem_contract.py` fails otherwise.
- Keep this file routing only: rules go in `docs/reference/`, steps in the workspace file.

## Outputs

- None of its own. A finished change updates the one owning document its workspace names.

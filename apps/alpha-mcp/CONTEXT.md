---
owner: model context protocol server
sources:
  - apps/alpha-mcp/src/**
  - apps/alpha-mcp/pyproject.toml
verified: 1ac86fc02443
---

# alpha-mcp workspace

## Purpose

A stdio MCP (Model Context Protocol) server that lets an AI client call bounded `alpha` commands.
It sits on top of the import graph: it imports only `alpha_core` and public `alpha_cli` seams
(import-linter contracts "alpha_mcp imports only public platform surfaces" and "alpha_mcp sits
atop the DAG") and runs the CLI as a subprocess. It can never approve or decide research, consume
D2 confirmation, reveal a holdout or place orders.

## Read first

| Read | Section | When |
|---|---|---|
| [MCP invariants](../../docs/reference/invariants/mcp.md) | — | always |
| [engineering rules](../../docs/reference/invariants/engineering.md) | Subprocess boundary | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Owner authority | always |
| [command reference](../../docs/reference/commands.md) | — | finding the command a tool wraps |

## How to change it

- Code: `apps/alpha-mcp/src/alpha_mcp/` (`server.py` holds the tools and each tool's option
  allowlist; `_invoke.py` runs the CLI).
- Tests: `tests/unit/test_mcp_invoke.py`, `tests/integration/test_mcp_server.py`,
  `tests/integration/test_research_mcp.py` (pins the exact tool list and count).
- Adding or removing a tool: update the expected tool set in `tests/integration/test_research_mcp.py`,
  then run `uv run python scripts/check_openapi_operations.py --write` (the capability matrix records
  the tool count).
- Check: `uv run python scripts/gate.py check`.

## Outputs

- Tests: a test that the new tool refuses options outside its allowlist.
- The owning document: `docs/reference/invariants/mcp.md`; regenerated
  `docs/governance/capability-authority-matrix.md`.

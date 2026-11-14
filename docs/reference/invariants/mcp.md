---
owner: model context protocol server
sources:
  - apps/alpha-mcp/src/alpha_mcp/**
  - tests/unit/test_mcp_invoke.py
  - tests/integration/test_mcp_server.py
  - tests/integration/test_research_mcp.py
  - tests/unit/test_codex_investigation.py
verified: 1724a5befe5d
---

# MCP invariants

Rules for `apps/alpha-mcp/`, the Model Context Protocol server that gives AI agents typed tools over the `alpha` CLI.
It is a surface like the web backend: it composes nothing and has no authority of its own.

## What the server is

- `server.py` is a stdio FastMCP server named `alpha`, started by `uv run alpha-mcp` (the repo `.mcp.json` launches it in
  Claude Code). Every tool reads `ALPHA_DATA_DIR` through `AlphaSettings`, so it shares one store with the CLI and web.
- `investigation_server.py` is a separate, private facade bound to one investigation case. The CLI starts it for a Codex
  investigation (`alpha_cli/codex_policy.py`). Its three tools take no arguments and each runs
  `alpha research diagnostic investigation-tool <case> <action>`. Keep it argument-free.
- Surfaces subprocess the CLI and never run the engine in-process — see
  [engineering § Subprocess boundary](engineering.md#subprocess-boundary) and
  [ADR-0002](../../adr/0002-cli-sole-composer-subprocess-surfaces.md).

## Calling the CLI

- Spawn `alpha` only through `_invoke.run_alpha` (run-producing actions) or `_invoke.run_json` (bounded `--json`
  projections with a timeout). `_control.py` builds typed CLI projections on top of `run_json`.
- `run_alpha` parses `-> run <id>`, then reads that run's manifest from the named run-type directory with the bounded,
  artifact-verified reader. A non-zero exit, a missing run id, or a manifest that fails validation is an error — fail loud.
- Pass the child only the closed environment from `_invoke._cli_environment` (process basics and bulk-data paths). No
  parent credentials cross. Enforced by `tests/unit/test_mcp_invoke.py::test_mcp_cli_environment_excludes_parent_credentials`.
- Heavyweight children reserve capacity (`alpha_cli.job_capacity`), keep a durable lease heartbeat
  (`alpha_cli.durable_lease`), and are reaped on cancel or error before capacity is released. A failed journal update
  aborts the action. Enforced by `tests/unit/test_mcp_invoke.py`.
- Legacy run reads (`_runs.py`) are paged deterministically and size-bounded, and reject non-finite or over-deep JSON.

## Allowed alpha_cli imports

- The import-linter contract `alpha_mcp imports only public platform surfaces` (root `pyproject.toml`) forbids every
  engine, data, research and study package and `alpha_web`, including indirect imports. Unlike the web backend it has
  no `ignore_imports` exception. See [engineering § Import layers](engineering.md#import-layers).
- Seams in use: `run_projection`, `catalog` (`known_strategies`, `strategy_params`), `run_store`, `artifact_contract`,
  `durable_lease`, `job_capacity`, `suite_catalog`. Do not import `alpha_cli.owner_auth` or any control-store module.

## Tool inputs

- Common knobs are typed parameters. The deprecated `options` dict accepts only that tool's closed vocabulary
  (`{"lookback": "5"}` → `--lookback 5`) — never arbitrary CLI flags. At most 32 options, values at most 256 characters,
  no NUL/CR/LF, boolean flags with an empty value, no duplicates after `_`→`-` normalisation.
- Strategy `params` accept only that strategy's declared `--param` names, at most 16, finite numeric values.
- `model`/`tokenizer` must be `fake` or a managed repository id — never a filesystem path. Revisions and snapshot ids
  must be safe opaque ids. Optimisation grids are bounded (axes, values per axis, total configurations).
- Validate inputs before the CLI is called.
  Enforced by `tests/integration/test_mcp_server.py` (closed options, counted and length-bounded inputs, path-like model
  rejection, control-plane bounds).
- Outputs are strict bounded Pydantic models in `_types.py`; typed v3 control tools publish named output schemas.

## Authority

- No MCP tool approves, rejects or decides research, consumes or launches D2 (the confirmation stage), reveals a
  holdout, writes corroborated evidence, or touches paper trading, brokers or orders. MCP has no owner-auth access.
  [ADR-0022](../../adr/0022-codex-collaboration-surface.md),
  [ADR-0030](../../adr/0030-touch-id-owner-presence-for-research-actions.md).
  See [research-integrity § Owner authority](research-integrity.md#owner-authority) and
  [research-integrity § No live capital](research-integrity.md#no-live-capital).
- Research tools are exactly `research_capture`, `research_get`, `research_propose`, `research_launch`,
  `research_status` and `research_report`, and no tool name may contain `approve`, `decide`, `decision`, `reveal`, `d2`,
  `order` or `paper`. Enforced by
  `tests/integration/test_research_mcp.py::test_research_mcp_surface_is_pinned_without_owner_authority`.
- Agent output is commentary or a draft, never evidence. Research source page reads return bounded, project-bound
  slices of the hash-verified extraction labelled `UNTRUSTED_SOURCE`; they do not screen claims or advance state.

## Changing the tool set

- The tool surface is pinned. Adding or removing a tool means, in the same change:
  - update `_EXPECTED_MCP_TOOLS` and the `assert len(names) == N` count in `tests/integration/test_research_mcp.py`
    (`tests/unit/test_repo_awareness_drift.py` checks the count equals the `@mcp.tool` decorators in `server.py`);
  - run `uv run python scripts/check_openapi_operations.py --write` to regenerate the
    [capability matrix](../../governance/capability-authority-matrix.md), which records the tool count.
- Every new tool must be a read or a draft-write within its typed contract. [ADR-0022](../../adr/0022-codex-collaboration-surface.md)
- When a CLI command or flag that a tool wraps is added, renamed or removed, update the tool in `server.py` and its
  option allowlist to match. No test catches a stale wrapper until the tool is called.

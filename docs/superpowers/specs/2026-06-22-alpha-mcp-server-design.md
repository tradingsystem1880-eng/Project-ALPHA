# Design — `alpha-mcp`: an MCP server over Project ALPHA (QuantPad parity Phase 3)

> **Implemented-state pointer (2026-07-18):** This historical plan predates forecast tools and the
> public run-store/catalog seams. The shipped MCP surface contains exactly 12 tools; use
> [`CLAUDE.md`](../../../CLAUDE.md) and [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) for the
> current contract.

## Context

QuantPad's headline UX is a **conversational agent** that builds and evaluates strategies for
you. Project ALPHA already exposes its full research loop through the `alpha` Typer CLI
(`data`, `backtest`, `validate`, `optim`, `propfirm`, `report`). Phase 3 of the QuantPad-parity
roadmap puts a **conversational surface** on top of that CLI by shipping an **MCP server** — so a
Claude agent (Claude Code, Claude Desktop) can drive ALPHA in natural language: *"pull AAPL, run
the gauntlet on a momentum strategy, then check it against a Topstep combine."* No API keys, $0,
native to a project "operated entirely by AI agents."

This is the third of four phases (Phase 1 = A–F Verdict, PR #8; Phase 2 = prop-firm Monte Carlo,
PR #9; Phase 4 = web IDE). It is a **new app surface**, not a change to existing packages.

## Decisions (user-approved)

- **Subprocess integration.** Each tool shells out to the installed `alpha` CLI and returns the
  byte-stable manifest the CLI already writes. **Zero `alpha_cli` refactor**, guaranteed parity
  (it literally runs the CLI), and full process isolation (the nautilus engine never runs inside
  the long-lived server process). The cost — a CLI process spawn per action call — is acceptable
  for a single-user local agent.
- **Full tool surface (~10 tools)** — one per CLI capability, plus run/strategy discovery.

## Architecture

A new uv workspace member `apps/alpha-mcp/` containing a single stdio **FastMCP** server (the
official `mcp` Python SDK, `mcp.server.fastmcp.FastMCP`). It sits at the very top of the import
DAG: it may depend on `alpha-cli` (for the static strategy registry only) but **nothing imports
it**.

```
apps/alpha-mcp/
  pyproject.toml                 # name=alpha-mcp; deps: mcp, alpha-cli (workspace); script: alpha-mcp
  src/alpha_mcp/
    __init__.py
    server.py                    # FastMCP instance + main(); registers the tools
    _invoke.py                   # _run_alpha(args) subprocess core + manifest read + run_id parse
    _runs.py                     # filesystem reads: get_run / list_runs (no subprocess)
  tests/ (under repo tests/)     # unit + in-memory-Client integration
```

### The subprocess core — `_invoke.py`

A single helper underpins every action tool:

```python
def run_alpha(args: list[str], *, data_dir: Path) -> dict[str, Any]:
    """Run `alpha <args>`, returning the resulting run's manifest (or the stdout summary)."""
```

- Runs `alpha <args>` via `subprocess.run([...], capture_output=True, text=True, env=...)`,
  inheriting `ALPHA_*` env (so the server and CLI share one `data_dir`).
- **Non-zero exit → raise** an exception carrying stderr. FastMCP turns it into a tool error the
  agent reads verbatim (fail-loud: "train_size 60 < warmup floor 274", unknown strategy, etc.).
- **Success →** parse the `-> run <run_id>` token the action commands already print, then read and
  return `data_dir/<run-type>/<run_id>/manifest.json`. A `data pull` (no manifest) returns its
  stdout summary as `{"stdout": ...}`.
- The run-type directory is resolved from the command (e.g. `validate`/`backtest run` → `runs/`,
  `optim` → `optim/`, `propfirm` → `propfirm/`, etc.), reusing the same `_RUN_DIRS` set the
  `report` command searches.

### Tools (`server.py`)

Action tools (subprocess → manifest):

| Tool | Invokes |
|---|---|
| `data_pull(symbol, source="yfinance", start=None, end=None)` | `alpha data pull …` |
| `backtest_run(symbol, strategy="ts_momentum", params=None, …)` | `alpha backtest run …` |
| `backtest_portfolio(symbols, strategy, weighting="equal", …)` | `alpha backtest portfolio …` |
| `backtest_cross_sectional(symbols, …)` | `alpha backtest cross-sectional …` |
| `validate(symbol, strategy, …)` | `alpha validate …` |
| `optim_grid(symbol, grid, strategy, …)` | `alpha optim grid …` |
| `propfirm_run(symbol=None, from_run=None, firm=None, …)` | `alpha propfirm run …` |

Read tools (no subprocess):

| Tool | Does |
|---|---|
| `get_run(run_id)` | read `manifest.json` from the matching run dir (fail loud if absent) |
| `list_runs()` | scan the run-type dirs under `data_dir`, return `[{run_id, command, label}]` |
| `list_strategies()` | return `alpha_cli._strategies.known_strategies()` (static registry) |

Each action tool builds the CLI arg list from its typed parameters (numbers/strings →
`--flag value`, repeatable `--param name=value`), then calls `run_alpha`. Tool docstrings are the
agent-facing contract — they state what each does, the key parameters, and that results are the
stored manifest.

### Packaging & client wiring

- `apps/alpha-mcp/pyproject.toml`: `name = "alpha-mcp"`, deps `mcp` + `alpha-cli` (workspace),
  `[project.scripts] alpha-mcp = "alpha_mcp.server:main"`. Add `alpha-mcp = { workspace = true }`
  to the root `[tool.uv.sources]` (the `apps/*` workspace glob already includes the directory).
- Repo-root **`.mcp.json`** so Claude Code auto-launches it:
  `{"mcpServers": {"alpha": {"command": "uv", "args": ["run", "alpha-mcp"]}}}`. The README/CLAUDE.md
  documents the equivalent Claude Desktop `claude_desktop_config.json` entry.
- **import-linter:** add `alpha_mcp` to `root_packages` and a forbidden contract giving it the top
  of the DAG (it may import `alpha_cli`; the existing five contracts already forbid every other
  package from importing it, and a new contract asserts nothing imports `alpha_mcp`).

### Determinism & error handling

Determinism is entirely the CLI's: identical tool args → identical `alpha` args → identical
`run_id` → idempotent (re-running overwrites the same manifest byte-for-byte). The server adds no
seeds or wall-clock. Every failure mode is the CLI's, surfaced verbatim through the tool error.

## Testing (TDD, no network)

- **Unit** (`tests/unit/test_mcp_invoke.py`): `run_alpha` builds the right arg list, parses the
  `-> run <id>` token, reads the manifest, and raises on non-zero exit — `subprocess.run`
  monkeypatched, no engine.
- **Integration** (`tests/integration/test_mcp_server.py`): drive the registered tools through the
  MCP SDK's in-memory client against a temp `ALPHA_DATA_DIR` seeded with the existing `seed_store`
  fixture, with small strategy params. A real `alpha` subprocess runs end-to-end; assert the
  returned manifest (`command`, metrics, run_id) and that `get_run`/`list_runs` round-trip it.
  Marked not-network.
- The full CI gate (ruff, format, `lint-imports` incl. the new contract, `mypy --strict`, pytest)
  must pass before each commit, mirroring CI.

## Out of scope (v1)

- MCP **resources** / prompts (tools-only for broad client support) — possible fast-follow.
- A live/streaming progress channel for long runs (tool calls are synchronous request/response).
- Auth / multi-user (local single-user stdio server).
- Phase 4 web IDE (separate phase).

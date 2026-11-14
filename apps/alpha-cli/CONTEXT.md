---
owner: command line application
sources:
  - apps/alpha-cli/src/**
  - apps/alpha-cli/pyproject.toml
verified: 98155932eeca
---

# alpha-cli workspace

## Purpose

The `alpha` command line: the only layer that composes data, strategies, the engine, validation,
research and models, and the owner of the SQLite control store (projects, jobs, evidence, owner
receipts). It may import every package below it; nothing but the surfaces' public seams may import
it, and the web app and MCP server call it as a subprocess. It must never grant authority the owner
did not give, and never route live capital.

## Read first

| Read | Section | When |
|---|---|---|
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Owner authority | always |
| [engineering rules](../../docs/reference/invariants/engineering.md) | Subprocess boundary | always |
| [engineering rules](../../docs/reference/invariants/engineering.md) | Hash-bound source bytes | always |
| [command reference](../../docs/reference/commands.md) | — | finding a command or its options |
| [command line research](../../docs/reference/invariants/cli-research.md) | Projections and dossiers | gate packets, case projections or dossiers |
| [command line research](../../docs/reference/invariants/cli-research.md) | — | research cases, contracts, D0/D1/D2 runs, owner decisions, `research_*` |
| [command line control store](../../docs/reference/invariants/cli-control-store.md) | — | the SQLite control store, migrations, owner receipts, jobs |
| [command line runs](../../docs/reference/invariants/cli-runs.md) | — | backtest, validate, optimise, suites, figures, rules, scans |
| [command line crypto data](../../docs/reference/invariants/cli-crypto-data.md) | Read-only queries | a read-only report or query, such as bar coverage |
| [command line crypto data](../../docs/reference/invariants/cli-crypto-data.md) | — | `alpha data` or `alpha crypto-data` acquisition, storage or backfill |
| [command line native](../../docs/reference/invariants/cli-native.md) | — | native fixtures and rule jobs, RD-Agent loops, `native_*` |
| [command line machine learning](../../docs/reference/invariants/cli-ml.md) | — | the Qlib worker exchange or Kronos forecasts, `ml_*` |
| [command line paper](../../docs/reference/invariants/cli-paper.md) | — | paper sessions, IBKR Paper, the crypto sandbox, providers |
| [command line assistant](../../docs/reference/invariants/cli-assistant.md) | — | the assistant, Codex and investigation commands |
| [architecture](../../docs/ARCHITECTURE.md) | Runtime data-directory layout | adding a folder under the data directory |
| [bounded discovery workflow](../../docs/operations/bounded-research-workflow.md) | — | running a bounded discovery or frozen-rule study |
| [Codex investigations runbook](../../docs/operations/codex-investigations.md) | — | running or changing a recorded-run investigation |
| [local operations runbook](../../docs/operations/README.md) | — | daily Tiingo data, IBKR Paper setup or the acceptance steps |
| [what this part is for](../../docs/reference/project/components/command-line.md) | — | why it exists; before you keep, shelve or remove it |

## How to change it

Code is flat in `apps/alpha-cli/src/alpha_cli/` (178 modules; `_name.py` = private helper,
`*_cmds.py` = one Typer command group, wired in `main.py`). Where to look:

| Sub-area | Modules (count) | Tests in `tests/unit/` |
|---|---|---|
| Research cases | `research_*` (22), `_research_cmd_parts`, `_research_artifact_io`, `_structural_digest`, `study_semantic` | `test_research_*` |
| Control store | `control_store`, `_control_*`, `owner_auth*`, `durable_lease`, `job_capacity`, `project_*` | `test_control_*`, `test_owner_*` |
| Runs, validation | `_artifacts`, `_identity`, `_seeds`, `_runner`, `_gauntlet`, `_optim`, `run_*`, `_suite*` | `test_run*`, `test_gauntlet*`, `test_suite_*` |
| Crypto, daily data | `_crypto_*` (15; incl. `_crypto_snapshot_members`), `crypto_*` (4), `data_cmds` | `test_crypto_*`, `test_tiingo_*`, `test_alpaca_*` |
| Native jobs | `_native_*` (20), `native_*` (6), `daily_*` (3) | `test_native_*`, `test_daily_*` |
| Machine learning | `ml_*` (6), `_ml_*` (2), `_forecast*` (3), `forecast_cmds` | `test_ml_*`, `test_forecast_*` |
| Paper, providers | `paper_*` (5), `_paper`, `_ibkr_paper`, `ibkr_what_if`, `provider*` (3) | `test_paper_*`, `test_provider_*` |
| Advisory models | `assistant_*` (6), `codex_*` (5), `investigation_*` (8), `comparison_acquisition*` | `test_assistant_*`, `test_codex_*` |

Many integration tests in `tests/integration/` use the same prefixes. Shared helpers live once: `_cli_json` (JSON emit and
option parsing), `_research_artifact_io` (D1/D2 artifact publication and reads) and `alpha_core.atomic` (atomic file writes);
do not add a private copy.

- Check: `uv run python scripts/gate.py check`. Engine imports stay lazy; keep `import alpha_cli`
  light (`tests/unit/test_public_seams.py`).
- Owner approvals bind code structure, not bytes ([ADR-0045](../../docs/adr/0045-approvals-bind-code-structure.md)): editing
  `research_intake.py`, `research_runtime.py`, `research_crypto_data.py` or `research_crypto_runtime.py` invalidates them only
  when behaviour changes (comments and formatting are free); control-store and owner-auth files feed daily native rule
  approvals the same way (see the native file). `_structural_digest.py` itself is guarded: any edit invalidates every approval.
- A new or changed command: run `uv run python scripts/commands_reference.py` and commit the page.
  If the web or MCP surface exposes it, also run `uv run python scripts/check_openapi_operations.py --write`.

## Outputs

- Tests for the changed sub-area (above); a bias guard for any new data read; an integration test
  through the real command for any new command.
- The owning document: the sub-area's `docs/reference/invariants/cli-*.md` file; regenerated
  `docs/reference/commands.md` when commands change.

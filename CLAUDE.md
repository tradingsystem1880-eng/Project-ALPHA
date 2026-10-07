# Project ALPHA — Agent Operating Manual

Authority: `docs/governance/capability-authority-matrix.md`.

Private single-owner research platform: validate edge after costs. Python 3.12; uv. No hosting or distribution.

## Rules (path-scoped)

Before edits, read applicable `.claude/rules/`. Load `karpathy-guidelines` for code work,
`incremental-implementation` for multi-file changes, `code-simplification` for refactors,
`code-review-and-quality` before merge, and `verification-before-completion` before success claims.
Use `alpha-feature-workflow` for nontrivial changes; quant changes also require primary-source
verification. Skills: `.agents/skills/`. Keep one mutator per overlapping slice.

Rules: `00-karpathy.md`, `alpha-core.md`, `alpha-data.md`, `alpha-strategies.md`,
`alpha-backtest.md`, `alpha-validation.md`, `alpha-research.md`, `alpha-forecast.md`,
`alpha-patterns.md`, `alpha-study.md`, `alpha-cli.md`, `alpha-mcp.md`, `alpha-web.md`,
`quant.md`, `tests.md`, `docs.md`.

## Architecture DAG

[pyproject.toml](pyproject.toml) import-linter contracts are executable boundaries:
core imports nothing internal; data/patterns/research/validation/forecast depend on core;
strategies on core+patterns; backtest on core+data; study on core+data+patterns+research.
Only `alpha_cli` composes engine and validation. Web/MCP sit above core and supported public CLI
seams; actions and engine-backed projections subprocess CLI, never the engine in-process.
Study is projection-only: no persistence or approval authority. Isolate Qlib/literature workers. Run `uv run lint-imports` after import changes.

## Scientific and application invariants

- All data/strategy reads use point-in-time `as_of`; bias guards poison future data and have leaky
  controls. Decide at close t, fill at open t+1. Corporate actions have knowledge/application clocks;
  dividends are cash at pay_date. Details: [domain contracts](docs/operations/research-platform-contracts.md).
- Fail loud on invalid/non-finite/disordered data and degenerate statistics. No swallowed errors.
  Polars is default; pandas only at sanctioned vendor edges. Keep strict typing.
- Runs, snapshots, receipts and admitted evidence are immutable and hash-bound. Preserve historical
  readers/migrations. Seeds and execution fingerprints are deterministic; D0/D1 protocol seeds
  are frozen, not settings-derived. Reverify reads; retirement preserves bytes.
- Research precedes strategy. D1 stays in discovery; owner-approved D2 is one-shot. Promotion
  requires verified evidence and owner decision. Screening and Monte Carlo path risk are not proof of edge.
- Explicit local owner confirmation (ADR-0038), paper opt-ins, provider/venue/unit boundaries and no-live-capital
  routing remain mandatory. UI/MCP output, account state and engineering checks confer no authority.
  Existing owner-auth actions remain the bounded path; no inferred approvals.
- Tests under `tests/holdout/` may run, but agents never read or edit them. Proposed tests go in
  `tests/holdout_seed/`. No owner data, credentials or hidden tests in discovery indexes.
- Research ships CLI-first. The [edge workspace](docs/superpowers/plans/2026-09-30-edge-workspace.md) connects
  charts, verified conditions and bounded advisory Codex. Drafts confer no authority. Grey terminal
  docks, verified archive charts and local click confirmation follow ADR-0038.

## Commands

- Canonical aggregate: `uv run python scripts/gate.py full`.
- Shared component check: `uv run python scripts/gate.py component NAME`, where NAME is
  `backend`, `frontend`, `literature`, `qlib`, `atlas` or `eval`; full requires all components.
- Discovery: `uv run python scripts/gate.py orient`; `alpha info commands --all --json`;
  `alpha info procedures --json`. Default command catalog remains launch-form compatible.
- Install: `uv sync --locked`. Tests: `uv run pytest -q -m "not network"`; bias guards:
  `uv run pytest -q -m bias_guard`. Component definitions own exact gate steps.

**2026-09-16:** [delivery record](docs/superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md).
Shared checks, discovery, V2 plans and frozen-input screening are implemented. Install thin Git
guards in new checkouts. Claude adapters provide orientation and native-boundary safety only.
Require a fresh full stamp; never bypass checks.
[ADR-0037](docs/adr/0037-agent-neutral-research-engineering.md) separates engineering
ceremony changes from unchanged application authority.
[Harness operations](docs/operations/claude-code-harness.md): checks, screening, intake, exceptions.

Benchmark: [Codex-only; preserve history; enforce isolation](tools/alpha-eval/README.md).

## Sources of current truth

Before governed work read [architecture](docs/ARCHITECTURE.md), the [ADR index](docs/adr/README.md),
rules and [build record](docs/BUILD-STATUS.md). Contracts:
[research platform](docs/operations/research-platform-contracts.md). Use source and fresh tests. Provider acceptance requires receipts; absent/failed live evidence cannot pass.

Update this manual and append `docs/BUILD-STATUS.md` when behavior changes.
Preserve user work; local checks are not aggregate acceptance.

UI: [terminal guide](apps/alpha-web/frontend/README.md): Bokeh research, optional market charts,
UTC windows, exact exports and project-free browsing.

# Project ALPHA — Agent Operating Manual

Authority: `docs/governance/capability-authority-matrix.md`.

Private owner research: validate edge after costs. Python 3.12/uv; no hosting/distribution.

## Rules (path-scoped)

Load `karpathy-guidelines`; `incremental-implementation` for multi-file work;
`code-simplification` for refactors; `code-review-and-quality` before merge;
`verification-before-completion` before claims. Use `alpha-feature-workflow` for nontrivial work;
quant changes need primary sources. Skills: `.agents/skills/`. One mutator per overlapping slice.

Applicable rules: `00-karpathy.md`, `alpha-core.md`, `alpha-data.md`, `alpha-strategies.md`,
`alpha-backtest.md`, `alpha-validation.md`, `alpha-research.md`, `alpha-forecast.md`,
`alpha-patterns.md`, `alpha-study.md`, `alpha-cli.md`, `alpha-mcp.md`, `alpha-web.md`,
`quant.md`, `tests.md`, `docs.md`.

## Architecture DAG

[pyproject.toml](pyproject.toml) import-linter enforces boundaries:
core imports nothing internal; data/patterns/research/validation/forecast import only core;
strategies on core+patterns; backtest on core+data; study on core+data+patterns+research.
Only `alpha_cli` composes engine and validation. Web/MCP sit above core and supported public CLI
seams; actions and engine-backed projections subprocess CLI, never the engine in-process.
Study is projection-only: no persistence or approval authority. Isolate Qlib/literature workers. Run `uv run lint-imports` after import changes.

## Scientific and application invariants

- All data/strategy reads use point-in-time `as_of`; bias guards poison future data and have leaky
  controls. Decide at close t, fill at open t+1. Corporate actions have knowledge/application clocks;
  dividends are cash at pay_date. Details: [domain contracts](docs/operations/research-platform-contracts.md).
- Fail loud on invalid/non-finite/disordered data and degenerate statistics. No swallowed errors.
  Retry WAL SQLITE_BUSY within its existing budget. Polars is default; pandas only at sanctioned
  vendor edges. Keep strict typing.
- Runs, snapshots, receipts and admitted evidence are immutable and hash-bound. Keep historical
  readers/migrations. Seeds/execution fingerprints are deterministic; D0/D1 seeds
  are frozen, not settings-derived. Reverify reads/copy generations; retirement/retries preserve bytes.
- Research precedes strategy. D1 stays in discovery; owner-approved D2 is one-shot. Promotion
  requires verified evidence and owner decision. Screening and Monte Carlo path risk are not proof of edge.
- Explicit local owner confirmation (ADR-0038), paper opt-ins, provider/venue/unit boundaries and no-live-capital
  routing remain mandatory. UI/MCP output, account state and engineering checks confer no authority.
  Existing owner-auth actions remain the bounded path; no inferred approvals.
- Tests under `tests/holdout/` may run, but agents never read or edit them. Proposed tests go in
  `tests/holdout_seed/`. No owner data, credentials or hidden tests in discovery indexes.
- Research ships CLI-first. The [edge workspace](docs/superpowers/plans/2026-09-30-edge-workspace.md) connects
  charts, conditions and advisory Codex. Drafts confer no authority; terminal docks, verified
  charts and local confirmation follow ADR-0038.

## Commands

- Full (size guard): `uv run python scripts/gate.py full`.
- Components: `uv run python scripts/gate.py component NAME` (`backend`, `frontend`,
  `literature`, `qlib`, `atlas`, `eval`); full requires all.
- Discovery: `uv run python scripts/gate.py orient`; `alpha info commands --all --json`;
  `alpha info procedures --json`. Default catalog remains launch-form compatible.
- Install: `uv sync --locked`; cloud: [README](README.md).
- Tests: `uv run pytest -q -m "not network"`; bias: `uv run pytest -q -m bias_guard`.
  Gate owns Linux pytest; build before browsers.
- Semgrep uses shared fail-closed `scripts/semgrep_runner.py`, pinned and checked at 1.181.0.

**2026-09-16:** [delivery](docs/superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md),
[ADR-0037](docs/adr/0037-agent-neutral-research-engineering.md): agent-neutral checks; application
authority unchanged. Install Git guards in new checkouts; require a fresh full stamp; never bypass checks.
[Harness](docs/operations/claude-code-harness.md): checkpoint, mutant cap, intake, CSS staging.
[Benchmark](tools/alpha-eval/README.md): Codex-only; preserve history. Research:
[bounded CLI workflow](docs/operations/bounded-research-workflow.md),
[Codex investigations](docs/operations/codex-investigations.md) are advisory.

## Current evidence

Read [architecture](docs/ARCHITECTURE.md), [ADRs](docs/adr/README.md),
rules in `.claude/rules/`, [build record](docs/BUILD-STATUS.md) and [contracts](docs/operations/research-platform-contracts.md).
Use fresh source/tests. Provider acceptance requires passing receipts.

[Development loop](docs/operations/development-loop.md): focused checks.
Behavior changes: update this manual and append `docs/BUILD-STATUS.md`.
Preserve user work; local checks do not confer acceptance.

UI: [terminal guide](apps/alpha-web/frontend/README.md): charts, UTC, exact exports, no-project browsing.
ML: v1/LightGBM; v2/rank_ensemble_v1.

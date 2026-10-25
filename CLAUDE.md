# Project ALPHA — Agent Operating Manual

Authority: `docs/governance/capability-authority-matrix.md`.

Private owner research: validate edge after costs. Python 3.12/uv; no hosting/distribution.

## Rules (path-scoped)

Load `karpathy-guidelines`; multi-file work: `incremental-implementation`; refactors: `code-simplification`;
before merge: `code-review-and-quality`; before claims: `verification-before-completion`. Use
`alpha-feature-workflow` for nontrivial work; quant changes need primary sources. Skills:
`.agents/skills/`. One mutator per overlapping slice.

Applicable rules: `00-karpathy.md`, `alpha-core.md`, `alpha-data.md`, `alpha-strategies.md`,
`alpha-backtest.md`, `alpha-validation.md`, `alpha-research.md`, `alpha-forecast.md`,
`alpha-patterns.md`, `alpha-study.md`, `alpha-cli.md`, `alpha-mcp.md`, `alpha-web.md`,
`quant.md`, `tests.md`, `docs.md`.

## Architecture DAG

[pyproject.toml](pyproject.toml) import-linter enforces: core imports nothing internal; data/patterns/research/validation/forecast import only core; strategies use core+patterns; backtest core+data; study uses core+data+patterns+research. Only `alpha_cli` composes engine and validation. Web/MCP sit above core and supported public CLI seams; actions and engine-backed projections subprocess CLI, never engine in-process. Study is projection-only: no persistence or approval authority. Isolate Qlib/literature workers. Run `uv run lint-imports` after import changes.

## Scientific and application invariants

- All data/strategy reads use point-in-time `as_of`; bias guards poison future data and have leaky controls.
  Decide at close t, fill at open t+1. Corporate actions have knowledge/application clocks; dividends
  are cash at pay_date. See [domain contracts](docs/operations/research-platform-contracts.md).
- Fail loud on invalid/non-finite/disordered data or degenerate statistics; never swallow errors. Type
  interrupted Stooq reads; retry WAL SQLITE_BUSY within existing budget. Polars default; pandas only
  at sanctioned vendor edges; type strictly.
- Tiingo transport: type-only.
- Runs/snapshots/receipts/admitted evidence are immutable and hash-bound. Keep historical
  readers/migrations. Seeds/execution fingerprints are deterministic; D0/D1 seeds are frozen, not
  settings-derived. Reverify reads/copy generations; retirement/retries preserve bytes.
- Research precedes strategy. D1 stays in discovery; owner-approved D2 is one-shot. Promote only
  after verified evidence and owner decision. Screening and Monte Carlo path risk are not proof of edge.
- Require explicit local owner confirmation (ADR-0038), paper opt-ins, provider/venue/unit boundaries
  and no-live-capital routing. UI/MCP output, account state and engineering checks confer no authority.
  Existing owner-auth actions are the bounded path; infer no approvals.
- Agents may run tests in `tests/holdout/` but never read or edit them. Put proposed tests in
  `tests/holdout_seed/`. Keep owner data, credentials and hidden tests out of discovery indexes.
- Research is CLI-first. The [edge workspace](docs/superpowers/plans/2026-09-30-edge-workspace.md) links
  charts, conditions and advisory Codex. Drafts confer no authority; terminal docks, verified charts
  and local confirmation follow ADR-0038.

## Commands

- Full (size guard): `uv run python scripts/gate.py full`.
- Components: `uv run python scripts/gate.py component NAME` (`backend`, `frontend`,
  `literature`, `qlib`, `atlas`, `eval`); empty steps fail; full needs all.
- Discover: `uv run python scripts/gate.py orient`; `alpha info commands --all --json`;
  `alpha info procedures --json`. Catalog is launch-form compatible.
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

## Evidence

Read [architecture](docs/ARCHITECTURE.md), [ADRs](docs/adr/README.md), `.claude/rules/`,
[build record + schema](docs/BUILD-STATUS.md) and [contracts](docs/operations/research-platform-contracts.md).
Use fresh source/tests. Provider acceptance requires passing receipts.

[Development loop](docs/operations/development-loop.md): focused checks.
Behavior changes: update this manual and append `docs/BUILD-STATUS.md`.
Preserve user work; local checks do not confer acceptance.

UI: [terminal guide](apps/alpha-web/frontend/README.md): charts, UTC, exact exports, no-project browsing. RunDetail binds summary, figures and trade state to the selected run; distinguishes trade loading/error from empty; exports only loaded rows.
ML: v1/LightGBM; v2/rank_ensemble_v1.

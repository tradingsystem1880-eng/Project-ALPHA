# ALPHA Operating Manual

Authority: `docs/governance/capability-authority-matrix.md`.

Private research. Python 3.12/uv; no hosting/distribution.

## Rules (path-scoped)

Load `karpathy-guidelines`; multi-file work: `incremental-implementation`; refactors: `code-simplification`;
merge: `code-review-and-quality`; claims: `verification-before-completion`. Use
`alpha-feature-workflow` for nontrivial work; quant needs primary sources. Skills:
`.agents/skills/`. One mutator per slice.

Rules: `00-karpathy.md`, `alpha-core.md`, `alpha-data.md`, `alpha-strategies.md`,
`alpha-backtest.md`, `alpha-validation.md`, `alpha-research.md`, `alpha-forecast.md`,
`alpha-patterns.md`, `alpha-study.md`, `alpha-cli.md`, `alpha-mcp.md`, `alpha-web.md`,
`quant.md`, `tests.md`, `docs.md`.

## Import DAG

[pyproject.toml](pyproject.toml) import-linter enforces: core imports nothing internal; data/patterns/research/validation/forecast import only core; strategies core+patterns; backtest core+data; study core+data+patterns+research. Only `alpha_cli` composes engine and validation. Web/MCP sit above core and supported public CLI seams; actions and engine-backed projections subprocess CLI, never engine in-process. Study is projection-only: no persistence or approval authority. Isolate Qlib/literature workers. Import changes: `uv run lint-imports`.

## Invariants

- All data/strategy reads use aware-UTC point-in-time `as_of`; bias guards poison future data and have leaky controls.
  Decide at close t, fill at open t+1. Corporate actions have knowledge/application clocks; dividends
  are cash at pay_date. [Query contracts](docs/operations/research-platform-contracts.md).
- Fail loud on invalid/non-finite/disordered data or degenerate statistics; never swallow errors. Type
  interrupted Stooq reads; retry WAL SQLITE_BUSY within existing budget. Polars default; pandas only
  at sanctioned vendor edges; type strictly. Tiingo transport: type-only.
- Runs/snapshots/receipts/admitted evidence are immutable and hash-bound. Preserve
  readers/migrations. Seeds/execution fingerprints are deterministic; D0/D1 seeds are frozen, not
  settings-derived. Reverify reads/copy generations; retirement/retries preserve bytes.
- Research precedes strategy. D1 stays discovery-only; owner-approved D2 is one-shot. Promote after
  verified evidence and owner decision. Screening/Monte Carlo path risk is not proof of edge.
  D1: CLI rules.
- Require explicit local owner confirmation (ADR-0038), paper opt-ins, provider/venue/unit boundaries
  and no-live-capital routing. UI/MCP output, account state and engineering checks confer no authority.
  Existing owner-auth actions are the bounded path; infer no approvals.
- Agents may run tests in `tests/holdout/` but never read or edit them. Put proposed tests in
  `tests/holdout_seed/`. Keep owner data, credentials and hidden tests out of discovery indexes.
- Research is CLI-first. [Edge workspace](docs/superpowers/plans/2026-09-30-edge-workspace.md) links
  charts, conditions and advisory Codex. Drafts confer no authority; terminal docks, verified charts
  and local confirmation follow ADR-0038.

## Commands

- Full: `uv run python scripts/gate.py full`.
- Components: `uv run python scripts/gate.py component NAME` (`backend`, `frontend`,
  `literature`, `qlib`, `atlas`, `eval`); empty steps fail; full needs all.
- Discover: `uv run python scripts/gate.py orient`; `alpha info commands --all --json`;
  `alpha info procedures --json`. [Map](docs/context/README.md).
- Install: `uv sync --locked`; cloud: [README](README.md).
- Tests: `uv run pytest -q -m "not network"`; bias: `uv run pytest -q -m bias_guard`.
  Gate owns Linux pytest; build before browsers.
- Semgrep uses fail-closed `scripts/semgrep_runner.py`, pinned and checked at 1.181.0.

**2026-09-16:** [delivery](docs/superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md),
[ADR-0037](docs/adr/0037-agent-neutral-research-engineering.md): agent-neutral checks; application
authority unchanged. Install Git guards; require a fresh full stamp; no bypass.
[Harness](docs/operations/claude-code-harness.md); [README](docs/operations/readme-maintenance.md).
[Benchmark](tools/alpha-eval/README.md); research [workflow](docs/operations/bounded-research-workflow.md) and [Codex investigations](docs/operations/codex-investigations.md) remain advisory.

## Evidence

See [architecture](docs/ARCHITECTURE.md), [ADRs](docs/adr/README.md), `.claude/rules/` and
[build record + schema](docs/BUILD-STATUS.md).
Provider acceptance requires passing receipts. Binance opt-in caps: HTTP attempts/body bytes.

[Development loop](docs/operations/development-loop.md): focused checks, owned tests, UV cache.
Behavior changes: update manual/build. Local checks confer no acceptance.

UI: [terminal guide](apps/alpha-web/frontend/README.md): UTC charts, exact exports, no-project browsing. RunDetail binds selected-run outputs and loading/error/empty states.
ML: v1/LightGBM; v2/rank ensemble; v3/tabular (workers/qlib/README.md). Missing worker blocks; refit grants no admission.

Native rule/control (Linux only): local confirmation, pinned LoopBase/LoopMeta, canonical engine, immutable artifacts,
full-charge accounting; strict integer IDs/counts and finite curves; no public/scientific authority. [Plan/handoff](docs/superpowers/plans/2026-10-26-native-rule-authority.md).

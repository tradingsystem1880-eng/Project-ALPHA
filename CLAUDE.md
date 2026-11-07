# ALPHA Operating Manual

Authority: `docs/governance/capability-authority-matrix.md`.

Private research. Python 3.12/uv; no hosting/distribution.

## Rules (path-scoped)

Skills in `.agents/skills/`: always `karpathy-guidelines`; multi-file `incremental-implementation`;
refactors `code-simplification`; merge `code-review-and-quality`; claims `verification-before-completion`.
`alpha-feature-workflow` for nontrivial work; quant primary sources. One mutator/slice.

Rules: `00-karpathy.md`, `alpha-core.md`, `alpha-data.md`, `alpha-strategies.md`,
`alpha-backtest.md`, `alpha-validation.md`, `alpha-research.md`, `alpha-forecast.md`,
`alpha-patterns.md`, `alpha-study.md`, `alpha-cli.md`, `alpha-mcp.md`, `alpha-web.md`,
`quant.md`, `tests.md`, `docs.md`.

## Import DAG

[pyproject.toml](pyproject.toml) import-linter enforces: core imports nothing internal; data/patterns/research/validation/forecast import only core; strategies core+patterns; backtest core+data; study core+data+patterns+research. Only `alpha_cli` composes engine/validation. Web/MCP use core and supported public CLI seams; actions/engine-backed projections subprocess CLI, never engine in-process. Study is projection-only: no persistence/approval authority. Isolate Qlib/literature workers. Import changes: `uv run lint-imports`.

## Invariants

- All data/strategy reads: aware-UTC point-in-time `as_of`; bias guards poison future data with leaky controls.
  Decide at close t, fill at open t+1. Corporate actions have knowledge/application clocks; dividends
  are cash at pay_date. [Query contracts](docs/operations/research-platform-contracts.md).
- Fail loud on invalid/non-finite/disordered data or degenerate statistics; never swallow errors. Type
  interrupted Stooq reads; retry WAL SQLITE_BUSY within existing budget. Polars default; pandas only
  at sanctioned vendor edges; type strictly. Tiingo transport: type-only.
- Immutable, hash-bound runs/snapshots/receipts/admitted evidence; preserve readers/migrations.
  Deterministic seeds/execution fingerprints; D0/D1 seeds are frozen, not
  settings-derived. Reverify reads/copy generations; retirement/retries preserve bytes.
- Research before strategy: discovery-only D1; owner-approved one-shot D2. Promotion needs
  verified evidence and owner decision. Screening/Monte Carlo path risk is not proof of edge.
  D1: CLI rules.
- Require explicit local owner confirmation (ADR-0038), paper opt-ins, provider/venue/unit boundaries
  and no-live-capital routing. UI/MCP output, account state and engineering checks confer no authority.
  Use existing bounded owner-auth actions; infer no approvals.
- Agents may run `tests/holdout/` but never read/edit it. Put proposed tests in
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
- Setup: `uv sync --locked`; backend CI: gate. [Run](README.md).
- Tests: `uv run pytest -q -m "not network"`; bias: `uv run pytest -q -m bias_guard`.
  Gate owns Linux pytest; build before browsers.
- `scripts/semgrep_runner.py`: fail-closed Semgrep, pinned/checked 1.181.0.

[ADR-0037](docs/adr/0037-agent-neutral-research-engineering.md): agent-neutral checks; application
authority unchanged. Install Git guards; require a fresh full stamp; no bypass.
[Harness](docs/operations/claude-code-harness.md); [README](docs/operations/readme-maintenance.md).
[Benchmark](tools/alpha-eval/README.md); research [workflow](docs/operations/bounded-research-workflow.md) and [Codex investigations](docs/operations/codex-investigations.md) remain advisory.

## Evidence

See [architecture](docs/ARCHITECTURE.md), [ADRs](docs/adr/README.md), `.claude/rules/` and
[build record + schema](docs/BUILD-STATUS.md).
Provider acceptance needs passing receipts. Binance opt-in caps: HTTP attempts/body bytes.
Bybit funding: native identity/clocks; offline bounded reads, raw retention and pagination.
[Handoff](docs/operations/2026-11-05-offline-funding-delivery.md) retains production refusal/admission gates.

[Development loop](docs/operations/development-loop.md): focused checks, owned tests, UV cache.
Behavior: update manual/build. Cancel needs journal publication.

UI: [guide](apps/alpha-web/frontend/README.md): UTC charts, exact exports, no-project browsing. RunDetail binds selected-run outputs/loading/error/empty states. Card opt-in.
ML: v1/LightGBM; v2/rank; v3/tabular (workers/qlib/README.md). W09 journal grants no admission/accounting; absent worker blocks.

Native fixtures: confirmed owner, pinned LoopBase/LoopMeta, immutable artifacts, full charges; no market authority.
[Authority](docs/superpowers/plans/2026-10-26-native-rule-authority.md).
[Packet3](docs/superpowers/plans/2026-10-31-packet3-daily-rule.md): daily route; market data blocked.

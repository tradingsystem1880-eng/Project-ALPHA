# ALPHA Manual
Authority: `docs/governance/capability-authority-matrix.md`.

Private research. Python 3.12/uv; no hosting/distribution.

## Rules

`.agents/skills/`: always `karpathy-guidelines`; multi-file `incremental-implementation`;
refactors `code-simplification`; merge `code-review-and-quality`; claims `verification-before-completion`.
`alpha-feature-workflow` for nontrivial work; quant primary sources. One mutator/slice.

Rules: `00-karpathy.md`, `alpha-core.md`, `alpha-data.md`, `alpha-strategies.md`,
`alpha-backtest.md`, `alpha-validation.md`, `alpha-research.md`, `alpha-forecast.md`,
`alpha-patterns.md`, `alpha-study.md`, `alpha-cli.md`, `alpha-mcp.md`, `alpha-web.md`,
`quant.md`, `tests.md`, `docs.md`.

## DAG
Obey [DAG](docs/ARCHITECTURE.md#2-the-layered-dag)/[contracts](pyproject.toml); `uv run lint-imports`. Web/MCP actions/engine-backed projections subprocess `alpha_cli`, never engine in-process. Study: projection-only, no persistence/approval authority. Isolate Qlib/literature workers.

## Invariants

- All data/strategy reads: aware-UTC point-in-time `as_of`; future-poison bias guards with leaky controls.
  Decide close t, fill open t+1. Corporate actions: knowledge/application clocks; dividends: cash at pay_date. [Query contracts](docs/operations/research-platform-contracts.md).
- Fail loud on invalid/non-finite/disordered data or degenerate statistics; swallow no errors. Type
  interrupted Stooq reads; retry WAL SQLITE_BUSY within existing budget. Polars default; pandas only
  at sanctioned vendor edges; type strictly. Tiingo transport: type-only.
- Immutable, hash-bound runs/snapshots/receipts/admitted evidence; preserve readers/migrations.
  Deterministic seeds/execution fingerprints; D0/D1 seeds frozen, not settings-derived. Reverify reads/copy generations; retirement/retries preserve bytes.
- Research before strategy: discovery-only D1 (CLI rules); owner-approved one-shot D2. Promotion
  needs verified evidence + owner decision. Screening/Monte Carlo path risk is not proof of edge.
- Require explicit local owner confirmation (ADR-0038), paper opt-ins, provider/venue/unit boundaries,
  no-live-capital routing. UI/MCP output/account state/checks: no authority.
  Bounded owner-auth actions; infer no approvals.
- Agents may run, never read/edit `tests/holdout/`; propose tests in `tests/holdout_seed/`.
  Exclude owner data, credentials and hidden tests from discovery indexes.
- Research: CLI-first. [Edge workspace](docs/superpowers/plans/2026-09-30-edge-workspace.md) links
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
  Gate owns Linux pytest; build before all browser lanes.
- `scripts/semgrep_runner.py`: fail-closed Semgrep, pinned/checked 1.181.0.

[ADR-0037](docs/adr/0037-agent-neutral-research-engineering.md): agent-neutral checks; application
authority unchanged. Install Git guards; require fresh full stamp; no bypass.
[Harness](docs/operations/claude-code-harness.md); [README](docs/operations/readme-maintenance.md).
Advisory: [Benchmark](tools/alpha-eval/README.md), research [workflow](docs/operations/bounded-research-workflow.md), [Codex investigations](docs/operations/codex-investigations.md).

## Evidence
[Guide](docs/operations/finance-math-evidence.md) governs edition/license/source anchors.
Metadata is not book-text/governed evidence or ingestion; numerical checks confer no research authority.

[ADRs](docs/adr/README.md), rules, [build/schema](docs/BUILD-STATUS.md).
Providers need PASS receipts. Binance opt-in caps: attempts/body bytes.
Bybit funding: native identity/clocks; bounded offline reads, raw retention/pagination.
[Handoff](docs/operations/2026-11-05-offline-funding-delivery.md) retains production refusal/admission gates.

[Development loop](docs/operations/development-loop.md): focused checks, owned tests/cache.
Update manual/build. Publish cancel journals.
Web→CLI passes `MPLCONFIGDIR` verbatim if set (Matplotlib config/cache).

UI: [guide](apps/alpha-web/frontend/README.md): UTC charts/exact exports, no-project browsing; RunDetail selected-run/loading/error/empty binding; card opt-in.
ML: v1/LightGBM, v2/rank, v3/tabular ([Qlib](workers/qlib/README.md));
Feature recipe v1 defaults; explicit v2 corrects 40 columns, not full native parity; W09 grants no admission/accounting; absent worker blocks.

Synthetic qrun → SignalReplay/Nautilus: saved Results are unadmitted, not approved research.

Native fixtures: owner-confirmed, LoopBase/LoopMeta pinned, immutable artifacts/full charges; stock RDLoop journals pre-spawn; no inference/evidence/market authority.
[Authority](docs/superpowers/plans/2026-10-26-native-rule-authority.md).
[Packet3](docs/superpowers/plans/2026-10-31-packet3-daily-rule.md): daily route; market data blocked.

# Project ALPHA — Agent Operating Manual

Authority: `docs/governance/capability-authority-matrix.md`.

Authoritative instructions for this private, single-owner, local research platform. Python 3.12;
uv workspace. Distribution, hosting and multi-user work are out of scope.

## Rules (path-scoped)

Read applicable files in `.claude/rules/` before edits. Load `karpathy-guidelines` for code work,
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
Study remains projection-only with no persistence or approval authority. Preserve isolated
Qlib/literature workers. Run `uv run lint-imports` after import changes.

## Scientific and application invariants

- All data/strategy reads use point-in-time `as_of`; bias guards poison future data and have leaky
  controls. Decide at close t, fill at open t+1. Corporate actions have knowledge/application clocks;
  dividends are cash at pay_date. Details: [domain contracts](docs/operations/research-platform-contracts.md).
- Fail loud on invalid/non-finite/disordered data and degenerate statistics. No swallowed errors.
  Polars is default; pandas only at sanctioned vendor edges. Keep strict typing.
- Runs, snapshots, receipts and admitted evidence are immutable and hash-bound. Preserve historical
  readers/migrations. Seeds and execution fingerprints are deterministic; D0/D1 protocol seeds
  are frozen, not settings-derived. Reverify admitted evidence on reads.
- Research precedes strategy. D1 stays in discovery; owner-approved D2 is one-shot. Promotion
  requires verified evidence and owner decision. Screening and Monte Carlo path risk are not proof of edge.
- Application owner-presence, paper opt-ins, provider/venue/unit boundaries and no-live-capital
  routing remain mandatory. UI/MCP output, account state and engineering checks confer no authority.
  Existing owner-auth actions remain the bounded path; no inferred approvals.
- Tests under `tests/holdout/` may run, but agents never read or edit them. Proposed tests go in
  `tests/holdout_seed/`. No owner data, credentials or hidden tests in discovery indexes.
- REST/MCP/Trader Terminal surfaces remain frozen; new research ships CLI-first. No new surface,
  paper, broker, order or promotion authority follows from this refactor.

## Commands and engineering transition

- Canonical aggregate: `uv run python scripts/gate.py full`.
- Shared component check: `uv run python scripts/gate.py component NAME`, where NAME is
  `backend`, `frontend`, `literature`, `qlib` or `atlas`; full requires all components.
- Discovery: `uv run python scripts/gate.py orient`; `alpha info commands --all --json`;
  `alpha info procedures --json`. Default command catalog remains launch-form compatible.
- Install: `uv sync --locked`. Tests: `uv run pytest -q -m "not network"`; bias guards:
  `uv run pytest -q -m bias_guard`. Component definitions own exact gate steps.

**Implemented (2026-09-16):** [delivery and verification record](docs/superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md).
Shared checks, discovery, V2 plans and frozen-input screening are implemented. Thin Git guards
are installed locally; other checkouts require installation. Claude adapters retain orientation
and native-boundary safety only. Require a fresh full stamp; do not bypass active checks.
[ADR-0036](docs/adr/0036-agent-neutral-research-engineering.md) separates engineering
ceremony changes from unchanged application authority.
[Harness operations](docs/operations/claude-code-harness.md): checks, screening, intake, exceptions.

## Sources of current truth

Read [architecture](docs/ARCHITECTURE.md), the [ADR index](docs/adr/README.md), applicable rules,
and the dated [build record](docs/BUILD-STATUS.md) before changing governed behavior. Domain
contract details and authoritative design links live in
[research-platform contracts](docs/operations/research-platform-contracts.md). Use current source
and fresh test results over historical completion claims. Provider acceptance is receipt-driven;
missing/failed live evidence is not a software pass.

Update operating instructions and append delivery status to `docs/BUILD-STATUS.md`.
Preserve user work and distinguish local verification from full acceptance.

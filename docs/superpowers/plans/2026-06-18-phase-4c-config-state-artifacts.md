# Phase 4c — Paper config + session-artifact schema (offline)

> **For agentic workers:** TDD per `CLAUDE.md`. Creates the `alpha-paper` package skeleton and its
> **offline** foundations so 4d can drop a live `TradingNode` onto a tested base. No node, no async,
> no network here.

**Goal:** typed paper-session configuration + the on-disk session artifact schema. Live sessions are
wall-clock-driven and therefore NOT reproducible, so the integrity artifacts are **append-only
provenance + a structured audit log**, not the byte-stable hash the backtest manifest uses.

## What landed

- **`AlphaSettings`** (`alpha_core/config.py`) gains paper fields, all defaulted so the public-data
  sandbox path needs no secrets: `paper_exchange`, `paper_venue`, `paper_symbol`, `paper_api_key`,
  `paper_api_secret`, `paper_use_testnet`. Credentials come ONLY from env/`.env`.
- **New package `alpha-paper`** (`packages/alpha-paper`, deps: `alpha-core`, `polars`):
  - `errors.PaperError(AlphaError)` — typed fail-loud error for the subsystem.
  - `config.PaperSpec` — frozen dataclass mirroring `RunSpec`'s pre-registered strategy/cost params
    (the basis of backtest↔paper parity) plus paper fields (`symbol/exchange/venue,
    duration_seconds`). Crypto-convention defaults (long-short, MARGIN, 365-day year). `min_train`
    warmup floor identical to `RunSpec.min_train` (drives history priming in 4d).
    `paper_spec_from_settings(settings, **overrides)` builder.
  - `artifacts.py` — `new_session_id` (injectable clock/suffix → deterministic tests),
    `session_dir`, `write_session`/`read_session` (`session.json`, refuses credential-like keys
    fail-loud), `AuditLog` (append-only flush-per-record `audit.log.jsonl`, injectable clock), and
    `write_equity_curve` (`equity_curve.parquet`, reuses the backtest's `(ts, equity)` pattern).
    Fills/positions/reconciliation parquet are deferred to 4e (no speculative writers).
- **Import-linter:** `alpha_paper` registered; new contract *"alpha_paper does not import the
  backtest engine or the cli"*; `alpha_paper` added to every lower layer's forbidden list. **7
  contracts kept.**

## Tests (offline)
`tests/unit/test_paper_config.py` (defaults, `min_train`, settings→spec overrides);
`tests/unit/test_paper_artifacts.py` (id format, dir layout, `session.json` round-trip + **secret
refusal**, audit JSON-lines ordering, equity parquet round-trip).

## Done = Phase 4c complete
Gate green (ruff · format · lint-imports 7-kept · mypy --strict 110 files · 190 tests). Secrets never
serialized; DAG holds.

**Next:** Phase 4d — sandbox `TradingNode` assembly behind a seam + a `FixtureLiveDataClient` for
deterministic offline replay (do-nothing strategy sees all bars, places 0 orders).

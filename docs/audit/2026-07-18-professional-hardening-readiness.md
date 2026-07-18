# Professional Hardening Readiness Audit — 2026-07-18

**Scope:** the shipped Project ALPHA product. This audit does not add the explicitly deferred live
paper-data adapter, FRED/non-OHLCV store, full-engine cross-sectional execution, or Kronos
fine-tuning.

**Delivery policy:** preserve the unpublished Workstation cleanup commits, deliver from
`chore/professional-hardening-2026-07` through a merge-commit PR, and create no release tag.

## Verdict

**Ready for merge-commit delivery.** The deterministic product gates are green, every owned Python
package and frontend surface is covered by an enforced quality floor, all 11 wheels build and
import as version `1.0.0`, and the live provider/model smokes found no unresolved code failure.
There are no known unresolved critical or high-severity hardening findings.

## Completed hardening

1. **Canonical input contract.** `ParamSpec` owns strategy parameter names, defaults, types,
   inclusive/exclusive bounds, and UI metadata. Backtest, validation, optimization, portfolio,
   prop-firm, paper, and forecast-cache paths normalize before `RunSpec` construction or hashing.
   Optimization axes use the same validation and reject duplicate normalized trials. Existing
   valid serialization and run ids remain stable; canonical JSON rejects non-finite values.
2. **Crash-consistent artifacts.** Package-local unique-temp writers atomically replace files.
   Required sidecars publish before `manifest.json`; forecast cache metadata publishes before the
   atomic `signals.parquet` completion gate. Incomplete caches repair deterministically, corrupt
   artifacts fail with typed errors, and activity announces only readable completed runs.
3. **Architecture and packaging.** Public `alpha_cli.catalog` and `alpha_cli.run_store` seams remove
   private CLI imports and duplicated surface constants. Twelve import-linter contracts protect the
   full DAG and keep MCP/web free of numeric, validation, engine, and model stacks. Direct
   dependencies, installed-metadata versions, typing markers, and wheel contents are explicit.
4. **Web contracts.** Stable JSON endpoints use strict Pydantic response models. OpenAPI and
   generated TypeScript are deterministic and drift-gated. Unknown-run and request-validation
   semantics are consistent while valid wire payloads remain compatible, apart from added
   exclusive-bound metadata.
5. **Quality and maintenance.** CI enforces the locked environment, Ruff, formatting, architecture,
   strict mypy, warnings-as-errors tests, 93% Python coverage, all wheel builds/imports, zero-warning
   frontend lint, V8 coverage, generated types, TypeScript/Vite build, and committed-asset freshness.
   The operating manual, architecture, user guide, frontend guide, ADR index, historical-spec
   pointers, and changelog now describe the shipped system.

## Verification evidence

| Gate | Result |
|---|---|
| Lockfile / locked sync | passed |
| Ruff / format | passed; 264 Python files checked |
| Import architecture | passed; 12/12 contracts |
| Strict mypy | passed; 261 source files |
| Offline Python suite | passed; 665 tests, 4 network tests deselected |
| Owned-source Python coverage | 93.88% lines (required: 93%) |
| Bias guards | 32 tests included in the offline suite |
| Frontend lint | passed with zero warnings |
| Frontend tests | 24 passed |
| Frontend V8 coverage | 11.81% statements, 14.95% branches, 7.69% functions, 11.95% lines |
| Generated contracts | OpenAPI and TypeScript fresh |
| SPA build/assets | TypeScript/Vite passed; committed assets byte-identical |
| Wheels | all 11 built and isolated-imported as `1.0.0` |

The frontend integer floors are the post-cleanup measured floors: 11% statements, 14% branches,
7% functions, and 11% lines. Vendored Kronos and generated/build artifacts are excluded from owned
coverage.

## Live smoke record

Executed `uv run pytest -m network -q -rs` on 2026-07-18:

- **Yahoo / yfinance:** passed, including AAPL's August 2020 4:1 split action.
- **CCXT / Coinbase:** passed for BTC/USD daily OHLCV.
- **Kronos:** passed against real Hugging Face weights on CPU; same-seed output was bit-reproducible
  and sampled paths were independent.
- **Stooq:** the provider withheld CSV data behind its anti-bot/per-IP gate. The first attempt
  revealed an untyped HTTP 403 escape; that code failure was fixed with an offline regression test.
  The rerun cleanly produced the documented typed provider limitation and skipped without masking
  parser-shape errors.

These outcomes do not weaken deterministic tests. Stooq remains best-effort; Yahoo is the supported
reliable equity/ETF source. Kronos local/offline weight policy remains governed by ADR-0010.

## Compatibility and remaining risk

- Complete existing runs remain readable. New invalid inputs fail earlier by design.
- Valid HTTP response shapes remain compatible; generated TypeScript is now authoritative.
- Provider availability, egress policy, and locally present model weights remain environmental.
- Historical specs and research remain point-in-time records and now point to the current-state
  manuals where their assumptions were superseded.

# Changelog

All notable changes to Project ALPHA are documented here. The project follows semantic versioning;
package metadata remains at `1.0.0` until a release is explicitly cut.

## Unreleased

### Added

- A dated post-v2 architecture audit, provider/control-plane and crypto-paper implementation spec,
  dependency/license matrix, and risk register.
- ADR-0011 for evidence-gated external integrations and ADR-0012 separating operational paper
  sessions from deterministic research runs.
- A CLI-owned, credential-redacted provider registry and local-only system readiness projection,
  exposed by `alpha info providers/system`, `/api/providers`, `/api/system`, a Providers · System
  panel, and provider-driven Data Explorer choices.
- Opt-in `alpha paper run` for public Binance `LIVE` data with local Nautilus sandbox execution
  only, including verified same-venue warmup, graceful lifecycle/disposal, and four supported rule
  strategies.
- A public `ExecutionEventSink` protocol and durable atomic `data_dir/paper/<uuid>` operational
  journal with session/event CLI and API reads, stale-heartbeat reporting, job `session_id`, and a
  SANDBOX Paper Monitor.
- Supported lightweight `alpha_cli.catalog` and `alpha_cli.run_store` interfaces for strategy
  metadata, run-type metadata, run-id validation, and manifest discovery.
- Strict Pydantic response contracts for stable Workstation JSON endpoints, deterministic OpenAPI,
  and generated authoritative TypeScript API definitions.
- Owned-source Python and frontend V8 coverage gates, generated-contract freshness checks, and
  isolated build/import verification for all 11 wheels.

### Changed

- Architecture governance now reflects all 12 named import contracts/current packages, the
  sanctioned yfinance pandas edge, the frontend-owned panel registry, and the explicit root-license
  distribution gate.
- CCXT now accepts only `coinbase|binance` and records venue-qualified snapshot provenance such as
  `ccxt:binance`; per-symbol pull provenance is copied into hashed snapshot sidecars and mismatched
  exchange relabelling is rejected. Historical source construction derives from the registry.
- `VolTargetStrategy` can prime PIT history without orders and normalizes paper quantities to live
  instrument increments while preserving existing SIM behavior. Strategy metadata now declares
  `supports_live_paper`; Kronos remains explicitly unsupported.
- NautilusTrader is pinned to `1.228.0` for the reviewed Binance-data/sandbox-factory API; upgrades
  require a deliberate compatibility review.
- Strategy parameters and optimization axes now share the `ParamSpec` catalog for defaults, types,
  bounds, and UI metadata. Invalid, duplicate, unknown, fractional-integer, and non-finite inputs
  fail before run-id generation.
- Run, forecast, cache, snapshot, data-store, tear-sheet, and workspace publication now use unique
  temporary files plus atomic replacement. Manifests remain the run completion marker; forecast
  cache `signals.parquet` remains its completion marker.
- MCP and web surfaces depend only on `alpha_core` and the public lightweight CLI seams; 12 import
  contracts enforce the full dependency DAG and surface outbound boundaries.
- Workstation lint, tests/coverage, generated types, TypeScript/Vite build, and committed assets are
  mandatory zero-warning CI gates.
- Package versions derive from installed distribution metadata, direct runtime dependencies are
  declared, and all typed packages include `py.typed`.
- Current documentation now matches the 12-tool MCP surface, Vite/TanStack Workstation, atomic
  artifacts, current package contracts, ADR-0010, and deliberately deferred product scope.

### Fixed

- Unknown runs now return 404 consistently; invalid workspace slugs and bounded request parameters
  return 422, while known runs without optional equity/trade artifacts retain empty responses.
- Concurrent or interrupted writers cannot expose a completion marker for partial artifacts, and
  corrupt/incomplete caches are repaired or rejected with typed errors.
- Stooq HTTP/provider rejections are converted to typed `DataError`s instead of leaking urllib
  exceptions.
- Removed a literal NUL from `DataTable.tsx` and split the justified Fast Refresh helpers without
  changing rendered behavior.
- Repaired stale seven-contract/numbered-boundary documentation, the yfinance pandas exception,
  malformed architecture fallback, and the nonexistent panel-manifest endpoint claim.

### Deferred

- Real or exchange-testnet execution, additional paper venues, Kronos live-cache semantics,
  FRED/non-OHLCV macro storage, full-engine cross-sectional execution, and model fine-tuning remain
  intentionally out of scope. The Binance network smoke and UTC-rollover sandbox soak remain
  opt-in operational acceptance gates.

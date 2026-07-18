# Changelog

All notable changes to Project ALPHA are documented here. The project follows semantic versioning;
package metadata remains at `1.0.0` until a release is explicitly cut.

## Unreleased

### Added

- Supported lightweight `alpha_cli.catalog` and `alpha_cli.run_store` interfaces for strategy
  metadata, run-type metadata, run-id validation, and manifest discovery.
- Strict Pydantic response contracts for stable Workstation JSON endpoints, deterministic OpenAPI,
  and generated authoritative TypeScript API definitions.
- Owned-source Python and frontend V8 coverage gates, generated-contract freshness checks, and
  isolated build/import verification for all 11 wheels.

### Changed

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

### Deferred

- Live paper-market data, FRED/non-OHLCV macro storage, full-engine cross-sectional execution, and
  model fine-tuning remain intentionally out of scope.

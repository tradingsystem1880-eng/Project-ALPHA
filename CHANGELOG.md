# Changelog

All notable changes to Project ALPHA are documented here. The project follows semantic versioning;
package metadata remains at `1.0.0` until a release is explicitly cut.

## Unreleased

**Release state:** Workstation v3 is implemented and its offline release gate passed on 2026-07-19.
R-22 still blocks distribution; the R-14 public Binance quote smoke passed locally on 2026-08-04,
while durable Binance readiness evidence and the R-24 UTC-rollover soak remain open. Daily-data/IBKR
Paper hardening is implemented offline; current-universe Tiingo qualification and every real IBKR
Paper acceptance scenario remain pending.

### Added

- Project-scoped QuantPad OAuth MCP registration plus ADR-0018 and operator guidance that routes
  symbol/schema/coverage discovery and small previews through MCP, bulk bars/ticks/L1/L2 through the
  official REST/Python API, and keeps all QuantPad output research-only pending a receipt-backed
  adapter, qualification, and retention-license evidence.
- macOS keychain service conventions for QuantPad, Tiingo, and the masked IBKR Paper account, plus a
  staged Dell i5/16-GB operations-host evaluation that grants no paper or canonical-data authority.
- Authoritative Tiingo stock/ETF EOD ingestion with immutable raw response receipts, canonical and
  provider symbol identity, raw OHLCV, explicit split/dividend actions, adjusted-price consistency
  checks, and versioned provenance that preserves legacy store/snapshot reads.
- Provider candidates, quality reports, quarantine, correction old/new hashes, no-delete merging,
  immutable pre-promotion backups, fail-closed promotion markers, and explicit review/rollback data
  commands. Yahoo Finance and Stooq remain comparison-only once Tiingo is canonical.
- A wake-safe exchange-calendar daily scheduler and launchd example that qualify Tiingo, freeze the
  exact snapshot, run the registered deterministic strategy through Nautilus, and publish an
  immutable next-session `OrderIntent`; crash recovery resumes an already-published exact snapshot
  without a second vendor fetch.
- Native Nautilus IBKR Paper preflight/execution with loopback port 4002, DU-account and instrument/
  client-ID allowlists, digest-pinned gateway configuration, dual enable flags, exact intent release,
  one-shot cross-process intent claims, account/journal reconciliation, overnight-position delta
  seeding, hard equity-paper risk, exact quote/cutoff checks, cancellation/expiration events, and
  safe stop.
- Paper journal schema v2 with v1 Binance readability, machine-derived readiness requirements,
  reconciliation/safe-stop commands, a readiness API, source-quality candle provenance, and
  low-volume paper intent/order/fill markers on the existing Lightweight Charts surface.
- ADR-0017, an implemented current-state/threat-model specification, local operations runbook, and
  expanded dependency/license and risk records for Tiingo, exchange calendars, Nautilus IB extras,
  IBKR, and the gateway image boundary.

- Workstation v3 specifications and ADR-0013 through ADR-0016 covering causal run artifacts,
  lifecycle/holdout governance, cited evidence, and an isolated Qlib boundary.
- Manifest, run-identity, and artifact-contract v3 with strategy execution fingerprints, semantic
  seed namespaces, immutable completed directories, per-artifact hashes/schema/size/row counts,
  and backward-compatible v1/v2 readers.
- Deterministic decision, order, fill, indicator, annotation, and native tear-sheet artifacts for
  new observed runs; legacy runs surface `trace_unavailable` instead of hindsight reconstruction.
- A CLI-owned WAL SQLite control plane for strategy projects, immutable versions/experiments,
  lifecycle stages, all attempts, sealed/final-holdout audit, frozen decisions, durable jobs, and
  append-only evidence revisions.
- `alpha project`, `alpha suite`, `alpha evidence`, and `alpha ml` command groups plus typed REST
  projections and a 42-tool bounded MCP surface (12 retained generic + 30 typed v3 tools), including
  durable job cancellation/reconciliation.
- Six curated linked Workstation desks: Market, Development, Kronos, ML Research, Portfolio & Risk,
  and Operations, with v2→v3 saved-layout migration and preserved free-form layouts.
- Native dark quant and ML tear sheets, causal trade/pattern overlays, complete-sample Kronos K-line
  views, forecast calibration/provenance, Asset Memory, visible agent context, and `AgentBrief`
  export.
- A separately locked `workers/qlib` process pinned to `pyqlib==0.9.7` and `lightgbm==4.6.0`, with
  fold-local feature/model training, strict timestamped prediction exchange, fake-worker tests,
  and canonical ALPHA replay. Qlib and worker-only dependencies do not enter the root environment.
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

- Receipt and order-intent readers now reject coercive JSON types; candidate repair re-verifies its
  quality identity and immutable raw-response hash; approved quarantines remain retry-idempotent;
  invalid thresholds and corrupt canonical comparison prices fail with typed data errors.
- The frontend lock now resolves transitive build-time PostCSS 8.5.25, clearing the prior moderate
  source-map path advisory without changing the direct Vite dependency.
- Release-candidate live smokes passed for Binance public quotes, CCXT history, Kronos, Yahoo, and a
  short AAPL Tiingo receipt→promotion→snapshot→candle cycle; Stooq produced its documented anti-bot
  skip. These do not replace durable readiness, UTC rollover, or Tiingo-universe qualification.

- NautilusTrader remains exactly `1.228.0` but now installs its reviewed `ib` and `docker` extras;
  `exchange-calendars==4.13.2` is pinned for session completeness and wake-safe UTC scheduling.
- Stock/ETF paper decisions now flow only through Tiingo receipt → quality gate → canonical store →
  immutable snapshot → Nautilus simulation → immutable intent → native IBKR Paper. React/FastAPI and
  the direct Lightweight Charts integration remain the sole visual stack.

- Live Workstation jobs now remain ahead of terminal history and expose exact elapsed time, current
  operation, output activity, accessible progress, and cancellation from one dense status card.
  ETA and percentage are explicitly indeterminate until a comparable successful command completes
  in the same server session; later estimates use the visible same-command median rather than a
  fabricated duration. Expanded rows show only the live log instead of duplicating status controls.
  UI-launched heavyweight Kronos/Qlib children run at reduced OS scheduling priority so chart and
  input work remain favored while research continues.
- QuantStats-Lumi HTML is now byte-deterministic: scoped Matplotlib SVG salts are fixed and volatile
  metadata is removed, so the audit export can be pinned by immutable v3 manifests.
- The primary research experience is Python-authored native chart/tear-sheet data; React renders
  typed artifacts and never computes metrics, verdicts, or causal trade stories.
- Long-running development and ML actions use durable UUID jobs with heartbeats, logs, cancellation,
  restart reconciliation, and a default one-heavy-worker concurrency policy.
- OOS and final-holdout runs now prime causal history without attaching an engine, then execute a
  fresh portfolio. Published metrics, equity, decisions, orders, fills, trades, indicators, and
  annotations are scoped from that same scored execution.
- Qlib daily panel rows/predictions are close-stamped (`session_ts + 23h`) and imported predictions
  execute as one synchronized, costed multi-asset ALPHA replay. Qlib diagnostics remain advisory and
  the replay remains labeled model-not-recomputed under counterfactual paths.
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
- MCP and web surfaces depend only on `alpha_core` and supported CLI-owned catalog, run-store,
  artifact-verification/projection, capacity, lease, and paper-store seams. Bounded artifact reads may
  use Polars; engine, gauntlet, Nautilus, Qlib, and Kronos composition stays out of process. Twelve
  import contracts enforce the dependency DAG and surface outbound boundaries.
- Workstation lint, tests/coverage, generated types, TypeScript/Vite build, and committed assets are
  mandatory zero-warning CI gates.
- Package versions derive from installed distribution metadata, direct runtime dependencies are
  declared, and all typed packages include `py.typed`.
- Current documentation now matches the 42-tool MCP surface (12 retained legacy + 30 typed v3
  tools), six-desk Vite/TanStack Workstation, v3 immutable artifacts/control plane, isolated Qlib
  boundary, current package contracts, ADR-0010 through ADR-0016, and deliberately deferred scope.

### Fixed

- Curated desks now scope run selection and artifact requests by capability, including portfolio and
  cross-sectional compatibility, forecast-only Kronos evidence, and canonical ML replay evidence.
  Incompatible runs display a typed state without probing unrelated risk or artifact endpoints.
- Hidden Dockview tabs now suspend their panel effects and polling. Causal chart overlays expose
  execution/decision/all layers, cap only the visual marker set deterministically, retain selected
  evidence, and keep the complete returned event table available.
- Immutable run projections use a bounded LRU cache, chart/native payloads are reduced and gzip
  compressed, and API failures surface clean typed detail without terminal formatting noise.
- Governed `suite:qlib` jobs now reconcile their managed exchange, project, and canonical replay
  lineage in the ML desk. Loading, blocked, failed, successful-empty, and trained states remain
  distinct in both ML control and diagnostics.
- Native tear sheets now distinguish an artifact that explicitly declares data unavailable from an
  artifact that was never emitted. Vector annotations render through one chart primitive instead of
  one series per annotation, preserving deterministic anchors without dense-series overhead.
- Identity-matched reruns now normalize JSON-domain containers before immutable-manifest comparison,
  preventing tuple/list representation differences from producing false conflicts while preserving
  byte-mismatch failure.
- PIT forecast poison tests resolve the emitted v3 identity instead of assuming a source change can
  reuse the old run id; strategy-source fingerprints now correctly separate those runs.
- Generic control-plane calls can no longer spoof terminal analytical stages, link unverified runs,
  bypass canonical holdout prerequisites, reserve suite job kinds, or create an extra heavyweight
  Qlib/Kronos job. Reveal revalidates the complete verified prerequisite lineage.
- Direct REST, MCP, Qlib, Kronos, and suite launches now reserve one shared heavyweight capacity
  class in the same SQLite write transaction that creates the durable job. Concurrent and
  cross-surface launches cannot pass a check-then-create race, and terminal state releases capacity.
- Direct Workstation, ML, and MCP children renew their durable lease independently of stdout. A
  failed renewal terminates and reaps the caller-owned process group before terminal publication;
  audited cancellation follows the same TERM-to-KILL path and cannot later publish success/failure.
- Real Qlib folds now exclude a terminal target without a following open and enforce the one-session
  open-to-open label horizon at both train/validation and validation/test boundaries, even when a
  caller declares zero purge or embargo.
- Causal decision IDs now come from the finalized global execution sequence, so orders, indicators,
  vector annotations, REST projections, and chart selection cannot drift after interleaved fills.
- Point-in-time `AgentBrief` reads now reconstruct append-only project scope, stage/run state, and
  holdout audit events at the requested cutoff; later reveal, contamination, and version changes are
  excluded by construction.
- Evidence citations verify v3 manifest/artifact hashes. MCP-created findings force agent provenance
  and `draft`, preventing an agent from impersonating a human reviewer or self-corroborating.
- Evidence records and revisions now reject a strategy-version/experiment pair unless the immutable
  experiment was created from that exact version, preventing internally impossible Asset Memory and
  `AgentBrief` lineage.
- Run-linked chart windows now filter bars and all decisions/orders/fills/trades/indicators/vector
  anchors together. Native tear sheets deterministically bound dense series and expose
  original/returned/truncated metadata.
- Saved v2 layouts migrate through a complete alias table, preserve the legacy source, reject an
  unknown component atomically, and persist v3 only after Dockview accepts the document.
- Development jobs rehydrate after reload, expose loading/empty/error/retry states, and persist
  cancellation requests for the owning worker. Workspaces surface non-2xx mutations instead of
  implying success.
- Production-browser Playwright/axe coverage now exercises all six desks, keyboard navigation,
  supported viewports, layout integrity, and serious/critical accessibility findings.
- Pixel baselines now cover all six desks at both 1440x900 and 1920x1080; the shell also removes
  decorative top-bar gradients and command-palette blur while retaining functional loading and
  SANDBOX hazard encoding.
- Python coverage now reports two decimal places, so the 93% gate cannot pass by rounding a value
  below 93.00%; focused durable-launch failure tests keep the true measured result above the floor.
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

- Live-capital routing, strategy-generated futures orders, automatic rolls, and futures strategy
  validation remain absent. Futures are limited to an explicit dated micro-contract connectivity
  probe after owner prerequisites are available.
- Massive, Databento, QuantConnect/LEAN, MetaTrader, and Streamlit remain outside this milestone.
  Reconsider paid intraday/futures feeds only when a measured universe or research requirement
  exceeds Tiingo EOD and CCXT.
- Live broker/exchange execution, intraday/microstructure ingestion, Qlib single-asset equivalence,
  counterfactual Qlib retraining, and an efficient frontier remain outside v3. Null results from the
  current ML replay are labeled as model-not-recomputed under counterfactual paths.
- Live or exchange-testnet execution, paper venues beyond IBKR/Sandbox, Kronos live-cache semantics,
  FRED/non-OHLCV macro storage, full-engine cross-sectional execution, and model fine-tuning remain
  intentionally out of scope. The Binance network smoke and UTC-rollover sandbox soak remain
  opt-in operational acceptance gates.

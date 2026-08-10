# Changelog

All notable changes to Project ALPHA are documented here. The project follows semantic versioning;
package metadata remains at `1.0.0` until a release is explicitly cut.

## Unreleased

**Release state:** The research-first R1–R6 program is integrated and scientifically hardened as of
2026-08-11, but is not production-complete. The owner real-case pilot, dual security review, and
distribution-license review remain open. Workstation v3 is implemented and its offline release
gate passed on 2026-07-19.
R-22 still blocks distribution; the R-14 public Binance quote smoke passed locally on 2026-08-04,
while durable Binance readiness evidence and the R-24 UTC-rollover soak remain open. Daily-data/IBKR
Paper hardening is implemented offline; current-universe Tiingo qualification and every real IBKR
Paper acceptance scenario remain pending.

### Added

- Python-authoritative tiered research readiness with stable blocker codes and evidence references,
  conservative required-control aggregation, a low-cluster D2 reliability floor, and promotion
  admission that requires both mechanical `SUPPORTED` evidence and promotion readiness.
- ADR-0027 for tiered readiness semantics and ADR-0028 for separately governed market-state,
  calibrated-Kronos, and Qlib rank-ensemble candidates.
- A server-rendered research discovery trace that reads immutable D1 chart-data artifacts and
  presents both the causal trace and its evidence table in the integrated Workstation.
- Causal, content-addressed `MarketStateV1` contracts and artifacts for separately aligned equity
  and 24/7 crypto universes, with frozen windows, thresholds, benchmark, and sparse-state fallback.
- Governed Kronos rolling-origin conformal calibration with a preregistered random-walk blend,
  validation-frozen fit, raw/calibrated proper scores and coverage, state-conditioned diagnostics,
  and fail-closed `kronos_calibrated` candidate assessments that retain research-only authority.
- Additive Qlib contract v2 and `rank_ensemble_v1`: unchanged v1 LightGBM plus pinned Qlib ridge,
  equal-weight percentile-rank combination, member/disagreement artifacts, deterministic replay,
  feature stability, and fixed cost-sensitivity diagnostics.
- Six server-rendered advanced-modeling figures for market-state performance, calibration
  reliability, abstention, ensemble disagreement, feature stability, and cost sensitivity.

### Changed

- Kronos validation reliability is now scored as a genuine rolling origin: every validation point
  selects its preregistered blend and conformal radius from prior validation origins only. The final
  fit remains frozen before OOS evaluation, and a future-poison regression pins the boundary.
- The frontend renders backend research projections directly; unused TypeScript scorecard/checklist
  derivations, parity fixtures, obsolete R5/R6 admission flags, and their stale branches were
  removed. Repeated D0/D1/D2 checkpoint mechanics now share narrow helpers without rewriting the
  control store.
- Frontend delivery gates now enforce meaningful coverage on pure models, exercise rendered
  workflows with Playwright, and resolve all high/critical npm audit findings.

- A repository-local development-skill suite covering Karpathy-style surgical work, incremental
  implementation, behavior-preserving simplification, five-axis code/PR review, and fresh
  verification before completion claims, with mandatory task routing in `CLAUDE.md`.
- Research Scientist Gate 0 and deterministic Gate 1 foundation: authoritative spec, ADR-0019/0020,
  risk/dependency decisions, repository-native Research Scientist/adversarial-reviewer skills,
  additive schema-v2 research contracts and phase/execution/D2/attempt/decision histories,
  deterministic capture and approval-ready draft materialization, a bounded local CLI D0 pilot,
  tamper-checked dossier projection, and the first-party `alpha_research` package for equal-duration
  research data, chronological D1/D2/D3 topology, causal double-bottom
  detection, prospective power, confirmation outcomes, point-in-time event observations, overlap
  purging, exact pre-event matching, cluster-bootstrap inference, a frozen Holm secondary family,
  and deterministic Matplotlib charts with embedded teaching/lineage metadata. Fail-closed
  acquisition validators, six bounded MCP tools, six matching strict REST/OpenAPI operations, and a
  registered Research Cockpit are included. Closed cases also receive one deterministic content-
  addressed terminal ResearchGatePacket whose empirical fields remain `NOT_TESTED` without typed
  D1/D2 evidence. Fresh projects are research-governed at creation and immediately capture a case;
  only pre-program migrated/imported projects are grandfathered. Evidence allocation is group-
  atomic across chronologically ordered eligible date/session/dependency groups, using 60/20/20 by
  default and never splitting one dependence group across zones. Deterministic dossiers export to
  `data_dir/research/projects/<project_id>`. The Cockpit captures/reads/proposes, launches only an
  already approved D0 pilot, reads status/report, and explains the thesis, competing explanations,
  native-unit budget, owner boundary, and D2/D3 firewall. MCP/REST have no approval, decision, D2,
  deep-research, Python, paper, or order authority. The acceptance fixture is synthetic 60-minute
  proxy data only; source network/download workers, qualified real intraday data, case-list/source-
  pack UI, production D1/D2 admission/approval/consumption, autonomous loops, complete empirical
  evidence/chart workflow, verified owner-presence authentication, strategy/holdout evidence, and
  paper/order authority remain hard-gated. Owner-only CLI actions currently rely on the trusted
  local operator boundary; an actor label is not cryptographic proof of human presence.
- Gate 1 authority hardening: project/case capture is atomic and retry-idempotent; migrated
  grandfathering is migration-only; one SQLite writer lock spans the exact v1 backup snapshot,
  additive schema work, and v2 version commit, while stale backups fail a logical
  source-equivalence check; D0
  is bound to the exact registered synthetic double-bottom fixture and one artifact-complete v3 run
  with a content-derived identity plus a canonical hashed raw-measurement D0 acceptance artifact;
  admission mechanically reruns the detector, null, four-observation boundary-embargo, and power
  criteria instead of trusting manifest pass flags. Completed D0 reads repeat that recomputation and
  bind the stored acceptance selector to the current manifest before recovery, status/dossier, or
  packet projection. D0 launches now atomically reserve one of three lifetime slots and fixed budget
  before compute; crashes consume reservations, terminal links are one-to-one, and budget ledgers
  cannot double-debit linked attempts. Typed D1 evidence cannot enter through `pilot`, and research
  runs cannot enter the generic corroborated-evidence ledger. Unsupported material choices cannot
  become approval-ready. Successful D0 work returns one owner disposition action, evidence-free/D0-
  only cases cannot claim `CONTRADICTED`, rejected exploration and pre-D2 revision have finite public
  CLI paths, and generic REST jobs cannot invoke governed research owner actions.
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
  isolated build/import verification for all 12 wheels.

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

- 2026-08-07 independent Research Scientist audit (six read-only reviewers; 0 critical/high,
  7 medium findings — all fixed): control-store steady-state opens are now write-free (a read-only
  schema probe replaces per-open script execution, so reads never contend for the writer lock and a
  lost governance row fails loud instead of silently regenerating from the caller-controlled
  `created_at` date rule); double-bottom knowledge time covers the first trough's left pivot window
  (latent look-ahead under delayed publication; the canonical D0 fixture's acceptance bytes are
  unchanged); TESTED D2 gate evidence now requires a numeric `confirmation_claim` whose
  classification is recomputed via `classify_confirmation` with every check boolean bound to its
  numeric fact (producer attestations that disagree with the numbers fail loud; D1 and NOT_TESTED
  evidence cannot carry a claim; INVALID requires a stated reason); a well-formed foreign D0
  registered generation now fails with an explicit generation-mismatch error — never one implying
  tampering — under a documented policy that any registered-constant change must bump the fixture
  version; the MCP research launch uses the 120-second launch-class timeout instead of the 30-second
  projection default (a mid-compute kill permanently consumes a lifetime launch slot); a successful
  pilot whose completed-attempt store write fails is never recorded as a failed attempt (the
  append-only ledger cannot be falsified; the resume/re-run recovery path is exercised end to end);
  and web research routes return a typed 4xx instead of a 500 for option-shaped path values.
  Hardening added with the fixes: cluster-bootstrap estimates below ten effective clusters carry an
  explicit `low_cluster_count` flag, size-skewed dependency groups that would leave the final
  holdout under 10% of observations fail loud, the complete 48-tool MCP surface and the exact
  research tool subset are pinned in tests, Playwright research fixtures are typed against the
  generated contract, content-identity digests and both deliberate canonical-JSON conventions are
  golden-pinned, duplicated revise-reuse/bootstrap/D0-measurement logic is consolidated behind
  single helpers with byte-identical behavior, and the D0 power seed is documented as
  protocol-frozen (never settings-derived, preserving machine-independent acceptance verification).
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

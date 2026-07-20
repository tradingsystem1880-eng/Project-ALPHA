# Risk Register — Provider/Paper + Workstation v3

- **Opened:** 2026-07-19
- **Track:** Post-v2 Recommended and owner-approved Workstation v3
- **Risk owner:** Project ALPHA owner; implementation agents supply controls/evidence but cannot
  accept financial, legal, or distribution risk on the owner's behalf

## Rating and Closure Rules

- Likelihood/impact: Low, Medium, High.
- A risk marked **Gate** blocks declaring the feature complete until its evidence is green.
- A risk marked **Owner decision** cannot be closed by implementation alone.
- Tests must assert the control. Documentation or a UI label alone does not close a safety risk.
- A network smoke is evidence for connectivity only, never permission for real execution.

**Implementation checkpoint (2026-07-19):** the provider/paper controls and Workstation v3
identity, causal evidence, control-plane, agent, ML, surface, migration, and browser controls are
implemented and passed the final full root/frontend/worker offline acceptance run. R-22 remains an
owner-decision blocker; R-14's opt-in real Binance connectivity smoke and R-24's reviewed
UTC-rollover sandbox soak remain pending evidence.

**Offline release evidence — passed 2026-07-19:** 1,136 offline Python tests passed with five
deselected and 93.13% coverage; 39 dedicated bias guards passed; all 12 import contracts, strict
mypy across 334 files, Ruff/format, OpenAPI freshness, 11 wheel builds, and 11 installed-version
imports passed. The isolated worker passed lock/sync, Ruff/format, strict mypy, nine tests, and two
root isolation tests. Frontend lint passed with zero warnings, Vitest passed 91/91, generated
TypeScript and the 182-module production bundle were stable, and Playwright passed 26 tests with
ten intentional viewport-specific skips. All six desks were checked at 1280x720, 1440x900, and
1920x1080; twelve 1440/1920 pixel baselines passed; axe found zero serious/critical WCAG 2.2 A/AA
violations. Target Mac mini (`Mac16,10`, Apple M4, 10 cores, 16 GB) probes met the 1.5-second cold
shell, 100 ms cached-switch, and 60 Hz 25,000-bar/200-annotation budgets. Generated contracts and
committed SPA assets were clean. This evidence does not close R-22, R-14's network acceptance, or
R-24's UTC-rollover acceptance.

## Register

| ID | Risk | Likelihood | Impact | Required controls | Closure evidence | Owner/status |
|---|---|---:|---:|---|---|---|
| R-01 | A real Binance execution client is constructed or credentials gain order authority | Low | High | Hard-code sandbox execution factory/config at venue `BINANCE`; no execution-mode or real key/secret CLI fields; type/factory deny tests | Fake-node/config tests prove only `SandboxLiveExecClientFactory`; repository search/review finds no Binance execution factory in the paper path | CLI/paper owner — **Gate** |
| R-02 | Paper launches without explicit opt-in | Medium | High | `ALPHA_PAPER_ENABLED=false` default; strict Boolean parser; check before session/network/node construction; disabled UI state | Unit/API/frontend tests for missing, false, malformed, and true values; disabled path records no network call | Core/config + CLI owners — **Gate** |
| R-03 | Wrong-venue history primes a Binance session | Medium | High | Persist pull source/version per symbol; reject snapshot relabelling; copy provenance into a hashed sidecar; require `ccxt:binance` and exact symbol | Snapshot/admission tests for Coinbase relabelling, mutable manifest relabelling, missing/legacy provenance, tampered sidecar, and valid Binance | Data + CLI owners — **Gate** |
| R-04 | Future or incomplete daily bars enter warmup (look-ahead) | Low | High | Load through PIT seam and require each daily UTC close boundary (`ts + 1 day`) to be knowable at launch; bias guard | Current-day/future-poison paper test and boundary timestamp tests | Data/strategy owners — **Gate** |
| R-05 | Stale or insufficient history changes first live decision | Medium | High | Explicit crypto freshness threshold; `warmup_for` minimum; no implicit repair fetch; actionable error | Tests one unit inside/outside freshness boundary and warmup minimum; UTC-rollover soak | Strategy/paper owner — **Gate** |
| R-06 | Priming emits orders/events or shifts strategy cadence | Medium | High | Dedicated `prime_history` path only mutates historical windows; no `_signal`, lifecycle, sink, or order calls; same class/config | Spy strategy/order factory/sink tests; first-live-decision cadence parity against equivalent feed | Strategy owner — **Gate** |
| R-07 | Venue size precision causes rejection or unintended notional | Medium | High | Normalize only paper quantities with resolved instrument size precision/increment; reject/skip zero-after-rounding; preserve SIM path | Fractional quantity tests at increment boundaries and byte-compatible existing SIM fixtures | Strategy/engine owner — **Gate** |
| R-08 | Network time, PID, heartbeat, or sink changes research IDs/artifacts | Low | High | Paper store outside `RUN_DIRS`; sink absent from `RunSpec`/hash; no session fields in research manifests; ADR-0012 | Run-id and manifest regression tests before/after optional sink/paper additions | CLI/artifact owner — **Gate** |
| R-09 | Credentials leak through provider/system/API/session/error output | Low | High | Registry stores env names; projection computes Boolean presence only; payload allowlists; sanitize terminal error; no SDK config repr | Redaction tests seed distinctive secret values and assert absence from CLI JSON, API JSON, events, logs, exceptions | Provider/web owners — **Gate** |
| R-10 | Partial/crashed writes appear as committed session state or events | Medium | Medium | Unique temp file + atomic replace; monotonically committed sequence; ignore temp files; explicit malformed committed-file error/recovery behavior | Crash injection, concurrent writer, partial session/event, missing directory, and recovery tests | Paper-store owner — **Gate** |
| R-11 | Stale heartbeat leads to killing an unrelated reused PID | Low | High | Stale is informational; cancellation only through the in-memory known child job/process group; no raw PID-kill API or recovery action | API/frontend tests show stale state and no kill; cancellation tests target only registered live job | Web/job owner — **Gate** |
| R-12 | Session journal becomes an unbounded market-data firehose | Medium | Medium | Event-type allowlist excludes bars/ticks; cursor-incremental reads; persist lifecycle/order/fill/rejection/position/warnings only | Sink/store tests reject high-volume market-data types and prove monotonic `after` reads | Core/paper-store owner — **Gate** |
| R-13 | Nautilus adapter API drift breaks assembly or changes behavior | Medium | High | Exact `nautilus-trader==1.228.0` pin across direct manifests; deliberate upgrade checklist with fake-node + network smoke | Lock check, dependency tests, documented compatibility review before any version change | Build/paper owners — **Gate** |
| R-14 | Public Binance outage/rate limit/time skew leaves an ambiguous session | Medium | Medium | Fail loud; heartbeat/status transition; terminal error; unconditional node disposal; no retry loop that duplicates orders | Factory/run exception tests, disconnect simulation, terminal journal assertion, network smoke | Paper owner — **Gate** |
| R-15 | Signal handling leaves node/resources running or mislabels cancellation | Medium | Medium | Register SIGINT/SIGTERM clean stop; add strategy/factories before build; `dispose` in `finally`; idempotent terminal transition | Fake-node ordered-call assertions for success, signal, build/run failure, and double-stop | Paper owner — **Gate** |
| R-16 | Kronos enters paper without causal live forecast-cache semantics | Low | High | `supports_live_paper=false`; explicit fail-loud guidance; no metadata default that auto-enables new strategies | Catalog/admission/frontend tests reject Kronos and unknown strategies | Strategy/catalog owner — **Gate** |
| R-17 | Provider choices drift between CLI, API, and Data Explorer | Medium | Medium | One immutable CLI registry and JSON projection; Data Explorer derives sources/options; frontend never hard-codes a parallel source list | Registry uniqueness/filter tests, CLI/API parity, frontend dynamic-option tests | Provider/web owners — **Gate** |
| R-18 | System status accidentally performs network probes or exposes machine-sensitive data | Low | Medium | Local stat/import/version/env-presence checks only; bounded path/status schema; `/healthz` unchanged | Network functions patched to fail if invoked; stable system response tests | Provider/web owners — **Gate** |
| R-19 | Disk exhaustion prevents heartbeat/event publication | Medium | Medium | Report free space in system panel; atomic failures transition/error where possible; never delete research/session data automatically | Low-space/write-failure tests with typed error; monitor surfaces terminal publication failure | System/paper-store owners — Open operational risk |
| R-20 | Web/OpenAPI/frontend drift makes safety state invisible or cancellation wrong | Medium | Medium | Strict Pydantic models, generated TypeScript freshness, panel error/disabled/stale/cancel tests, committed asset check | Full frontend gate plus generated OpenAPI check and clean built assets | Web/frontend owners — **Gate** |
| R-21 | An upstream recommendation expands scope or compromises deterministic authority | Medium | High | ADR-0011 evidence gate; standalone spec for each Ambitious integration; immutable worker boundary; ALPHA validation remains authoritative | Dependency diff matches approved matrix; no prohibited new runtime package | Architecture/build owners — **Gate** |
| R-22 | ALPHA is distributed without a root license decision or required notices | Medium | High | No implicit license; matrix and README warning; distribution/release blocked pending owner selection and legal review | Root license decision, exact SBOM/notices, reviewed release checklist | Owner — **Owner decision / blocker** |
| R-23 | "SANDBOX" is mistaken for profitable, validated, testnet, or real execution evidence | Medium | High | Permanent SANDBOX banner; session plane separate from validation; no passed/verdict field; docs distinguish local fills from exchange execution | API schema lacks validation status; frontend copy tests; ADR-0012 | Product/owner — **Gate** |
| R-24 | Crypto 24/7 cadence or UTC rollover exposes a timestamp/session bug | Medium | High | Calendar-day cadence; UTC timestamps; separately opted-in soak crossing UTC midnight; inspect heartbeat/position/events | Reviewed soak record with no stale heartbeat, duplicate decision, precision, reconciliation, or shutdown defect | Owner + paper owner — Phase-4 completion gate |
| R-25 | Parameter-only IDs alias runs from different strategy source revisions | Medium | High | Manifest/run identity v3 includes execution fingerprint; completed directories immutable; conflicting bytes fail | Identity sensitivity, legacy-read, and immutable-rerun tests | CLI/artifact owner — **Verified offline 2026-07-19** |
| R-26 | Chart/OOS/holdout evidence is reconstructed with hindsight or contaminated by a discovery-period portfolio | Medium | High | Persist prefix-emitted traces; causally prime history without an engine; execute a fresh scored portfolio; scope decisions/orders/fills/trades/indicators/annotations and metrics from that same run | Future-poison prefix stability, close/open reconciliation, and OOS/holdout tests proving no pre-boundary position or event survives | Strategy/engine/artifact owners — **Verified offline 2026-07-19** |
| R-27 | Optimization, an agent, or a spoofed terminal stage bypasses sealed-holdout governance | Medium | High | Terminal analytical states are suite-owned; verify expected v3 run kind/hash/evidence/prerequisites; dated one-shot reveal; post-reveal changes contaminate lineage | Terminal-transition denial, forged/tampered run rejection, prerequisite rebuild, reveal, contamination, and stale-propagation tests | Development-control owner — **Verified offline 2026-07-19** |
| R-28 | SQLite control state is partial, concurrent, or mistaken for analytical evidence | Low | High | Transactional migrations/events outside `RUN_DIRS`; immutable content hashes; canonical metrics remain run artifacts | Migration, conflict, concurrency, crash/restart, and run-separation tests | CLI/control owner — **Verified offline 2026-07-19** |
| R-29 | Research memory or an AgentBrief leaks later/tampered evidence, scope, stage, or holdout state; accepts an impossible version/experiment lineage; or accepts a citation whose artifact hash no longer matches | Medium | High | Separate data cutoff/knowledge time; append-only evidence revisions and `project_scope_events`; one point-in-time scope/stage/run/holdout read snapshot; fail-closed legacy scope fallback; exact experiment-to-version match; verify source v3 manifest and cited artifact hash before admission | Evidence and AgentBrief future-poison, historical scope/reselection, pre/post-reveal, revision-chain, lineage-mismatch, artifact-tamper, source-integrity, and negative-result tests | Evidence/control owner — **Verified offline 2026-07-19** |
| R-30 | An agent bypasses gates, impersonates a human/reviewer, corroborates its own claim, reveals holdout, launches paper, or executes arbitrary code | Low | High | Typed bounded actions; retained deprecated option maps use closed per-tool key/value/count/length bounds; managed model/tokenizer values reject filesystem-like paths; action responses cap manifest reads and verify declared v3 artifacts; MCP evidence writes force agent provenance + draft; no raw SQL/dynamic Python; owner-only transitions absent | MCP/API allowlist, option/path rejection, manifest tamper/oversize, author/status spoof, payload, authority, and rejection tests | MCP/web/control owners — **Verified offline 2026-07-19** |
| R-31 | Qlib or worker-only dependencies enter the root/web/MCP runtime | Medium | High | Separate project/lock/process; import and lock deny tests; JSON/Parquet-only exchange | Root lock/import graph checks and independent worker gate | ML/build owners — **Verified offline 2026-07-19** |
| R-32 | ML normalization, labels, folds, or predictions leak future data, including treating a complete daily OHLCV row as known at midnight or admitting a terminal target with no following open | Medium | High | Fold-local fit; effective purge/embargo minimum of one session for the open-to-open label horizon; `available_at = session_ts + 23h`; target must immediately follow origin and itself have a following aligned open; strict source-panel equality; no pickle | Feature/label future-poison, midnight and terminal-target rejection, zero-buffer boundary rejection, duplicate/non-finite/wrong-hash/fold-overlap rejection, and synchronized replay tests | ML/data/CLI owners — **Verified offline 2026-07-19** |
| R-33 | The Workstation presents fabricated analytics, frontend-computed verdicts, or a marker/anchor that maps to the wrong execution event | Medium | High | Python-authored typed artifacts only; decision linkage uses the finalized global execution-sequence ID across decisions/orders/fills/indicators/annotations; duplicate/orphan references fail; one backend/frontend date window filters bars and every evidence series; legacy/missing states explicit; no fake frontier | Global-ID reconciliation with interleaved fill/decision events, duplicate/orphan rejection, API/renderer parity, range-filtered markers/annotations, old-run `trace_unavailable`, copy, and visual tests | Engine/artifact/web/frontend owners — **Verified offline 2026-07-19** |
| R-34 | A caller uses an arbitrary durable job kind or a different launch surface to bypass reserved suite ownership or the one-heavyweight Kronos/Qlib limit | Medium | High | Reserve `suite:*` kinds; generic creation rejects them; one shared capacity class covers REST, MCP, direct Qlib/Kronos, and suite kinds; active-state check and insert share one `BEGIN IMMEDIATE` transaction | Reserved-kind, direct/direct concurrency, direct/suite concurrency, REST/MCP conflict, and terminal-release tests | CLI/control owner — **Verified offline 2026-07-19** |
| R-35 | A direct or suite heavyweight child ignores cancellation, runs without a renewable lease, is overwritten by a later success state, or is reconciled through an unsafe PID action | Medium | High | Persist idempotent cancellation requests; direct Workstation/MCP children use isolated process groups and an independent heartbeat/cancel lease capped at ten seconds; suites poll cancellation continuously and heartbeat each live step at five seconds; renewal/poll failure fails the journal; cancellation uses TERM→bounded grace→KILL/reap; direct lease stop/join precedes any subsequent caller terminal publication; stale reconciliation is logical only and exposes no raw PID API | Silent-child heartbeat, renewal/poll failure, in-flight direct and suite cancellation, process reap, no-later-terminal, capacity release, reload rehydration, stale/fresh reconciliation, and idempotence tests | CLI/web/MCP owners — **Verified offline 2026-07-19** |
| R-36 | v2→v3 layout migration partially writes, drops an unknown panel, or destroys the only recoverable legacy layout | Medium | Medium | Complete alias table; reject unknown components atomically; preserve legacy keys; persist v3 only after Dockview accepts the whole migrated document | Real-shaped v2 fixture, unknown-component rejection, Dockview-failure, and legacy-preservation tests | Frontend owner — **Verified offline 2026-07-19** |
| R-37 | Tear sheets, chart bundles, comparisons, or retained legacy MCP reads create unbounded memory/token payloads | Medium | Medium | Typed request caps, deterministic downsampling/windowing, pagination, endpoint-preserving series, and bounds metadata | Min/max rejection, original/returned/truncated assertions, stable sampling, and legacy-read cap tests | CLI/web/MCP owners — **Verified offline 2026-07-19** |
| R-38 | Dense desktop styling is unusable by keyboard, relies on color alone, or ships serious/critical accessibility defects | Medium | High | Named controls/regions, visible focus, textual chart alternatives, non-color labels, and Playwright axe A/AA gate | Six-desk keyboard checks and zero serious/critical axe findings at required viewports | Frontend owner — **Verified offline 2026-07-19** |
| R-39 | The terminal fails supported desk sizes or misses cold-shell/workspace-switch/chart-navigation performance budgets | Medium | Medium | Test 1280x720, 1440x900, and 1920x1080; production-preview performance probes for 1.5s cold shell, <100ms cached switch, and 25k bars/200 annotations navigation | Recorded bounded timing/animation evidence on the target profile plus responsive screenshots | Frontend/release owners — **Target verified 2026-07-19** |
| R-40 | REST clients cannot select a stable v3 contract, allowing incompatible schema drift | Medium | Medium | Explicit `/api/v3` aliases for development, ML, chart, native-tearsheet, and forecast-path contracts; retain `/api` compatibility routes; generated TypeScript freshness | Versioned/legacy parity and bounds tests, OpenAPI diff check, and generated-client build | Web/API owners — **Verified offline 2026-07-19** |

## Residual-Risk Decisions

The following remain accepted only within the stated personal sandbox scope:

- Public Binance data can be delayed, unavailable, rate-limited, revised, or venue-specific.
- Nautilus sandbox fills are simulations; they do not prove exchange queue position, latency,
  slippage, fee, rejection, liquidation, or operational behavior.
- A local JSON journal is sufficient for one process/user but is not a multi-host transaction log.
- Stale heartbeat detection and reconciliation report a logical journal state only. If a surface
  owner crashes, its operating-system child may survive; ALPHA does not recover by persisted PID,
  cannot prove physical heavyweight capacity is free, and requires the operator to confirm/reap any
  orphan before reconciling and relaunching.
- Historical free-vendor data retains survivorship/provider-adjustment limitations.

Any move to real or testnet exchange execution, remote hosting, multiple users/hosts, or automated
recovery reopens R-01, R-09, R-11, R-14, R-19, R-22, R-23, and R-24 and requires a new threat/risk
model.

## Review Cadence

Review this register:

- at each implementation slice that closes a Gate risk;
- before the full offline acceptance gate;
- after the Binance network smoke and UTC-rollover soak;
- on any Nautilus/provider upgrade or new provider;
- before any distribution/license decision; and
- immediately after any unexpected order, reconciliation warning, stale session, or corrupt journal.

# Risk Register — Provider/Paper + Workstation v3 + Research Scientist

- **Opened:** 2026-07-19
- **Track:** Post-v2, owner-approved Workstation v3, and Research Scientist program
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
implemented and passed the final full root/frontend/worker offline acceptance run. R-22 is retired
under the owner's permanent private/local-only scope; R-14's opt-in real Binance connectivity smoke
and R-24's reviewed UTC-rollover sandbox soak remain pending evidence.

**Daily-data/IBKR checkpoint (2026-08-03):** Tiingo receipt qualification, correction/quarantine
promotion recovery, exchange-calendar scheduling, immutable Nautilus decision intents, native
IBKR Paper boundary/reconciliation/risk, journal v2, readiness projection, and chart monitoring are
implemented offline. This does not close the current-universe Tiingo qualification, R-14, R-24, or
any real IBKR Paper scenario; the readiness report must remain pending until machine evidence exists.

**QuantPad research checkpoint (2026-08-04):** OAuth MCP discovery and official API/SDK bulk access
are approved as external research interfaces only. No QuantPad payload is canonical, validation, or
paper evidence until an adapter and qualification gate exist; permanent retention remains a license
evidence gate.

**Release-candidate checkpoint (2026-08-04):** the R-14 public Binance quote smoke, CCXT history,
Kronos live smoke, and Yahoo history passed locally; Stooq produced its documented anti-bot skip.
This closes the standalone connectivity probe only. Durable readiness evidence, R-24 UTC rollover,
Tiingo universe qualification, and all real IBKR scenarios remain open.

**Research Scientist foundation checkpoint (2026-08-06):** Gate 0 authority and skills plus the
deterministic Gate 1 foundation are implemented: schema-v2 research records/state machines,
atomic retry-idempotent fresh-project capture, migration-only grandfathering with source-bound v1 backup,
capture-to-approval-ready-draft CLI flow, canonical
`data_dir/research/projects/<project_id>/` tamper-checked dossier projection, bounded local D0 pilot,
research-only D0/data/topology/detector/power/confirmation/artifact primitives, bounded MCP and
strict REST routes, and a registered Cockpit for capture/read/propose/approved-D0-launch/
status/report, plus a content-addressed terminal packet that fails closed to `NOT_TESTED` without
typed D1/D2 evidence. Gate 2 has request-boundary validation primitives only and performs no network
request. MCP/REST/Cockpit cannot approve, reject, decide, consume D2, run deep research, or trade;
the generic REST job route also blocks governed research commands. The D0 pilot is bound to the
one approval-ready synthetic fingerprint (`alpha_synthetic_fixture` / `SYNTHETIC_SPY` / UTC /
equal 60-minute bars / 240-minute pattern window), the registered causal double-bottom operator,
and one artifact-complete v3 immutable run whose identifier is derived from the contract, fixture,
and execution fingerprints. Its canonical hashed acceptance artifact contains raw measurements;
the control plane mechanically reruns the detector, null, exact four-observation boundary-embargo,
and power criteria and rejects approved implementation-fingerprint drift before compute. It cannot
admit typed D1 evidence, claim `CONTRADICTED` without typed
non-synthetic evidence, or enter the generic corroborated-evidence ledger. Successful D0 work moves
directly to one owner-owned research-disposition action because production D1 is unavailable. No
qualified real-market data, D1/D2 runner, source download worker, autonomous/ML loop, strategy
evidence, verified owner-presence authentication, or execution authority exists. Local owner CLI
actor fields are trusted-operator audit semantics, not cryptographic identity. R-50–R-57 remain
open until their full closure evidence is green.

**Research Scientist audit/hardening checkpoint (2026-08-07):** an independent six-reviewer
read-only audit of the complete uncommitted program found 0 critical/high and 7 medium findings;
all were fixed test-first before merge (PR #36). Material to this register: steady-state control
store opens no longer execute schema scripts (reads cannot contend for the writer lock and a lost
governance row fails loud instead of regenerating from the caller-controlled date rule — closes
the R-57 backfill-resurrection vector); double-bottom knowledge time now covers the left pivot
window (closes a latent R-53 look-ahead under delayed publication); TESTED D2 gate evidence
requires a numeric `confirmation_claim` recomputed via `classify_confirmation` with each check
boolean bound to its numeric fact (hardens the R-53/R-56 producer-attestation vector before D2
ships); foreign D0 registered generations fail with an explicit generation-mismatch error under a
documented fixture-version bump policy; the MCP research launch uses the 120-second launch-class
timeout so an infrastructure default cannot burn an R-50 lifetime launch slot; a successful pilot
can never be recorded as a failed attempt (append-only ledger honesty, with the resume/re-run
recovery executed in tests); cluster-bootstrap estimates below ten effective clusters carry a
typed `low_cluster_count` flag and size-skewed topologies below a 10% holdout observation share
fail loud; and the complete 48-tool MCP surface, content-identity digests, and both deliberate
canonical-JSON conventions are golden-pinned. Full offline Python and frontend gates re-verified
green on the branch head. R-50–R-57 gate states are otherwise unchanged.

The Gate 0 design review also covered the owner-supplied local inputs
`/Users/hunternovotny/Desktop/Beast-Mode/docs/research/deep-research-report-1.md` and
`/Users/hunternovotny/Desktop/Beast-Mode/docs/research/deep-research-report-2.md`. ALPHA retains
their typed handoffs, adversarial critique, negative-knowledge ledger, append-only/versioned
conflict/recovery, staged walking skeleton, and human-gate patterns. It rejects LangGraph/vector/
graph/imported-runtime authority, generated-code execution, arbitrary thresholds or profit claims,
and autonomous capital. The reports remain design inputs only, never empirical evidence.

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
committed SPA assets were clean. R-22 was later retired by the permanent private/local-only scope;
this evidence does not close R-14's network acceptance or R-24's UTC-rollover acceptance.

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
| R-14 | Public Binance outage/rate limit/time skew leaves an ambiguous session | Medium | Medium | Fail loud; heartbeat/status transition; terminal error; unconditional node disposal; no retry loop that duplicates orders | Factory/run exception tests, disconnect simulation, terminal journal assertion, network smoke | Paper owner — **Public quote smoke passed 2026-08-04; durable operational evidence pending** |
| R-15 | Signal handling leaves node/resources running or mislabels cancellation | Medium | Medium | Register SIGINT/SIGTERM clean stop; add strategy/factories before build; `dispose` in `finally`; idempotent terminal transition | Fake-node ordered-call assertions for success, signal, build/run failure, and double-stop | Paper owner — **Gate** |
| R-16 | Kronos enters paper without causal live forecast-cache semantics | Low | High | `supports_live_paper=false`; explicit fail-loud guidance; no metadata default that auto-enables new strategies | Catalog/admission/frontend tests reject Kronos and unknown strategies | Strategy/catalog owner — **Gate** |
| R-17 | Provider choices drift between CLI, API, and Data Explorer | Medium | Medium | One immutable CLI registry and JSON projection; Data Explorer derives sources/options; frontend never hard-codes a parallel source list | Registry uniqueness/filter tests, CLI/API parity, frontend dynamic-option tests | Provider/web owners — **Gate** |
| R-18 | System status accidentally performs network probes or exposes machine-sensitive data | Low | Medium | Local stat/import/version/env-presence checks only; bounded path/status schema; `/healthz` unchanged | Network functions patched to fail if invoked; stable system response tests | Provider/web owners — **Gate** |
| R-19 | Disk exhaustion prevents heartbeat/event publication | Medium | Medium | Report free space in system panel; atomic failures transition/error where possible; never delete research/session data automatically | Low-space/write-failure tests with typed error; monitor surfaces terminal publication failure | System/paper-store owners — Open operational risk |
| R-20 | Web/OpenAPI/frontend drift makes safety state invisible or cancellation wrong | Medium | Medium | Strict Pydantic models, generated TypeScript freshness, panel error/disabled/stale/cancel tests, committed asset check | Full frontend gate plus generated OpenAPI check and clean built assets | Web/frontend owners — **Gate** |
| R-21 | An upstream recommendation expands scope or compromises deterministic authority | Medium | High | ADR-0011 evidence gate; standalone spec for each Ambitious integration; immutable worker boundary; ALPHA validation remains authoritative | Dependency diff matches approved matrix; no prohibited new runtime package | Architecture/build owners — **Gate** |
| R-22 | ALPHA is distributed or made available to others despite its private local-only scope | Low | High | No sale, publication, sharing, hosting, or multi-user access; preserve third-party notices and service/data terms locally; reopen distribution governance before any scope change | Owner's 2026-08-11 permanent private, single-owner, local-device scope decision recorded in `CLAUDE.md`, architecture, and dependency matrix | Owner — **Retired for current scope; reopen on scope change** |
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
| R-34 | A caller uses an arbitrary durable job kind or a different launch surface to bypass reserved suite/research ownership or the one-heavyweight limit | Medium | High | Reserve `suite:*` and `research:*` kinds; generic creation rejects them; one shared capacity class covers REST, MCP, direct Qlib/Kronos, suite kinds, and future research jobs; active-state check and insert share one `BEGIN IMMEDIATE` transaction | Reserved-kind including research, direct/direct concurrency, direct/suite concurrency, REST/MCP conflict, and terminal-release tests | CLI/control owner — **Verified offline foundation 2026-08-06; production research workers gated** |
| R-35 | A direct or suite heavyweight child ignores cancellation, runs without a renewable lease, is overwritten by a later success state, or is reconciled through an unsafe PID action | Medium | High | Persist idempotent cancellation requests; direct Workstation/MCP children use isolated process groups and an independent heartbeat/cancel lease capped at ten seconds; suites poll cancellation continuously and heartbeat each live step at five seconds; renewal/poll failure fails the journal; cancellation uses TERM→bounded grace→KILL/reap; direct lease stop/join precedes any subsequent caller terminal publication; stale reconciliation is logical only and exposes no raw PID API | Silent-child heartbeat, renewal/poll failure, in-flight direct and suite cancellation, process reap, no-later-terminal, capacity release, reload rehydration, stale/fresh reconciliation, and idempotence tests | CLI/web/MCP owners — **Verified offline 2026-07-19** |
| R-36 | A legacy v2 workspace migration partially writes, drops an unknown panel, or destroys the only recoverable layout | Medium | Medium | Complete alias table; reject unknown components atomically; preserve legacy keys; persist the fixed-screen workspace only after the whole migrated document validates | Real-shaped v2 fixture, unknown-component rejection, validation-failure, and legacy-preservation tests | Frontend owner — **Verified offline 2026-07-19; legacy compatibility only** |
| R-37 | Tear sheets, chart bundles, comparisons, or retained legacy MCP reads create unbounded memory/token payloads | Medium | Medium | Typed request caps, deterministic downsampling/windowing, pagination, endpoint-preserving series, and bounds metadata | Min/max rejection, original/returned/truncated assertions, stable sampling, and legacy-read cap tests | CLI/web/MCP owners — **Verified offline 2026-07-19** |
| R-38 | Dense desktop styling is unusable by keyboard, relies on color alone, or ships serious/critical accessibility defects | Medium | High | Named controls/regions, visible focus, textual chart alternatives, non-color labels, and Playwright axe A/AA gate | Six-desk keyboard checks and zero serious/critical axe findings at required viewports | Frontend owner — **Verified offline 2026-07-19** |
| R-39 | The terminal fails supported desk sizes or misses cold-shell/workspace-switch/chart-navigation performance budgets | Medium | Medium | Test 1280x720, 1440x900, and 1920x1080; production-preview performance probes for 1.5s cold shell, <100ms cached switch, and 25k bars/200 annotations navigation | Recorded bounded timing/animation evidence on the target profile plus responsive screenshots | Frontend/release owners — **Target verified 2026-07-19** |
| R-40 | REST clients cannot select a stable v3 contract, allowing incompatible schema drift | Medium | Medium | Explicit `/api/v3` aliases for development, ML, chart, native-tearsheet, and forecast-path contracts; retain `/api` compatibility routes; generated TypeScript freshness | Versioned/legacy parity and bounds tests, OpenAPI diff check, and generated-client build | Web/API owners — **Verified offline 2026-07-19** |
| R-41 | Tiingo is promoted despite gaps, invalid/duplicate bars, action conflicts, or unexplained comparison differences | Medium | High | Immutable receipt/candidate; raw-basis parsing; exchange-calendar/action/cross-source gate; authority allowlist; quarantine with no fallback | Parser/quality/quarantine tests plus zero unresolved current-universe discrepancies above 1% on non-action dates | Data + owner — **Short AAPL live pipeline passed 2026-08-04; universe qualification gate** |
| R-42 | A correction or crash leaves partial canonical data or silently deletes history | Low | High | Merge without absent-row deletion; old/new correction hashes; atomic peer writes; immutable pre-promotion backup and blocking marker; automatic/explicit exact rollback; repair re-verifies raw receipt bytes and identity | Idempotency, correction, receipt tamper, failure injection, legacy-read, backup hash, and rollback tests | Data owner — **Verified offline 2026-08-04** |
| R-43 | IB clients connect to a live port/account, remote gateway, mutable image, or unapproved client/instrument | Low | High | No live mode; force loopback/4002/DU account/digest/client-ID/instrument allowlists; dual independent flags before node construction | Boundary deny tests and real evidence report with zero live-port attempts | CLI/broker owner — **Offline controls verified; operational gate** |
| R-44 | A later quote/config creates an order different from the approved deterministic decision | Low | High | Scheduler runs Nautilus on the exact snapshot; immutable intent binds strategy/version/params/NAV/snapshot/instrument/target/session/cutoff/risk; release revalidates every field; intent hash is client-order ID | Intent sensitivity/tamper/expiry/idempotency and CLI mismatch tests; zero duplicate live callbacks | CLI/strategy owner — **Verified offline 2026-08-03** |
| R-45 | Reconnect, uncertain submission, journal drift, or overnight position causes duplicate/unexplained broker state | Medium | High | Native Nautilus execution reconciliation; permanent one-shot intent release claim; intent-before-submit journal; journal-expected position seeds the target delta; reject open orders/unexpected instruments/mismatch; never resubmit an ambiguous intent | Duplicate-process, overnight-unit, cancellation/expiration, disconnect/restart/partial-fill/callback injection plus real overnight gateway-restart cycle with zero unresolved state | Broker/paper owner — **Offline controls partial; real broker gate** |
| R-46 | IBKR Paper fills are mistaken for live execution quality or futures research validity | High | High | Permanent paper labeling; readiness says futures research unsupported; explicit dated micro probes only; no strategy futures/rolls/live route | UI/API copy and readiness tests; one owner-directed micro probe remains connectivity evidence only | Product/owner — **Gate** |
| R-47 | Mac sleep, DST, or a missed timer skips/duplicates a daily decision or trades after cutoff | Medium | High | Five-minute short launchd tick; UTC exchange calendar and correction window; immutable per-session outcome/crash marker; resume from an already-published exact snapshot; exact next-session expiry | Calendar/DST/weekend/wake tests, post-snapshot interruption recovery without refetch, and target-host sleep/wake observation | Operations owner — **Offline verified; target-host evidence pending** |
| R-48 | Tiingo/QuantPad/IBKR secrets or full account identity reach logs, journal, API, browser, or repository | Low | High | Header-only vendor tokens; OAuth MCP where supported; redacted errors/metadata; keychain/Docker-secret operations; masked account alias; no browser vendor/broker clients | Distinctive-secret failure tests, repository/log/API scan, real gateway evidence scenario | Data/broker/web owners — **Offline controls verified; operational scan gate** |
| R-49 | QuantPad preview/bulk data is scraped, over-retained, relabeled as canonical, or used as futures/L2 validation without sufficient contract/history evidence | Medium | High | MCP preview bounds; official API/SDK only; scratch-data label; no direct strategy/paper path; receipt-backed adapter and written retention permission required before promotion/archive | OAuth/tool smoke, schema/coverage samples, terms response, adapter quality/correction tests, dated-contract and 30-day-L2 limitation evidence | Data/owner — **External evidence gate** |
| R-50 | A research agent silently changes the thesis, protocol, search family, budget, or owner decision after seeing results, or an actor string is mistaken for verified owner presence | Medium | High | Immutable exploration/confirmation contracts; one `next_action` and `responsibility`; bounded ask/act policy; material recommendations come only from registered answer bundles; generic jobs reject owner actions; every closed research-lifecycle UI action requires a fresh one-use Touch ID assertion bound to action, project, artifact hash, revision, consequence, and reason; the verified credential determines the actor; CLI recovery is separately audited | Transition/authority tests reject unavailable choices, stale revisions, budget expansion, REST/MCP bypass, assertion replay/expiry/origin/action/payload/counter mismatches, D2 reuse, and owner impersonation | Research control owner — **Verified offline 2026-08-13; live enrollment remains an owner ceremony** |
| R-51 | Scholarly search stores unauthorized full text, misses versions/retractions, or presents weak metadata as credible evidence | Medium | High | Owner-clicked OpenAlex/Crossref/arXiv/Unpaywall discovery; deterministic DOI/content-key deduplication; explicit access, version, and retraction metadata; only HTTPS direct-PDF acquisition; content-addressed query/response/budget/byte/extraction receipts; no paywall bypass; anchored claims require later owner screening | Duplicate/version/retraction/access fixtures, MIME/redirect/size/hash denial, malformed/encrypted/image-only extraction states, anchor tamper checks, and isolated discovery-to-pack integration | Research source + owner — **Offline workflow verified 2026-08-13; external-provider walkthrough remains receipt-dependent** |
| R-52 | Instructions in papers, webpages, repositories, or datasets alter agent authority or reach shell, credentials, or project instructions | Medium | High | Treat all external bytes and extracted text as `UNTRUSTED_SOURCE`; isolated worker receives a closed argument list, allowlisted hosts, minimal environment, and resource bounds; no generated-code execution; Codex can draft but cannot screen claims or freeze packs | Hostile PDF/body, archive, prompt-injection, credential-isolation, anchor-reverification, and no-authority-path tests | Agent/security owners — **Offline controls verified 2026-08-13** |
| R-53 | Overlap, serial dependence, confounding, parameter search, chart selection, or ML leakage creates a false research edge | High | High | D0 synthetic validation bound to the exact canonical chart/outcome protocol, one registered operator, and one artifact-complete v3 immutable run with a content-derived identity plus canonical hashed raw-measurement acceptance; admission and every completed-D0 recovery/status/dossier/phase/packet read mechanically rerun detector, null, exact four-observation boundary-embargo, and power criteria, bind the stored acceptance selector to the current manifest, and reject implementation-fingerprint drift; default chronological 60/20/20 allocation over indivisible eligible date/session/dependency groups; any alternative event-blind and owner-approved before D1 with D3 at least 20%; D1 adaptive ledger; one-shot D2; D3 prohibited to research; prospective power before D2; frozen families; block-aware uncertainty; matched/negative/placebo controls; multiplicity controls; six protocol-selected headline charts | D0 contract-mutation, forged/downgraded/incomplete-run, post-admission artifact/manifest rewrite, stored-selector corruption, implementation-drift, D1/D2 authority and reuse denial, group-atomic topology/access, point-in-time matching, overlap purge, cluster bootstrap, Holm-family, deterministic-chart, synthetic planted/null/weekday-confounder, and future-poison tests; broader FDR/Reality Check/SPA/DSR/CPCV/PBO and fold-local ML remain strategy-development gates | Research/validation owners — **D0/D1/one-shot-D2 mechanics verified offline; live qualified-case evidence remains case-specific** |
| R-54 | Research-only intraday bars or event-study output enter the canonical daily store, validation, holdout, paper readiness, or order path | Medium | High | ADR-0020 research-only dataset/type scope; explicit chart fingerprint and `available_at`; equal-duration collections reject mixed 240/150-minute observations; no daily snapshot or strategy/paper link; later intraday strategy requires a new ADR | Type/path denial, provider-authority, mixed-duration rejection, DST/early-close, pivot-availability, future-poison, and no-promotion/no-paper tests | Research data + architecture owners — **Synthetic boundary tested; real-data Gate 4 open** |
| R-55 | An agent overfits its own benchmark, rewrites an active skill, or self-approves a prompt/skill improvement | Medium | High | Separate strategy and agent-improvement loops; frozen corpus/scorer; one mutable candidate; keep/reject log; candidate staging; owner approval; no active-skill writes from the evaluator | Benchmark contamination/sensitivity tests, active-skill write denial, scorer hash checks, failed-candidate retention, and owner-only activation | Agent-evaluation owner — **Gate 5 open** |
| R-56 | A literature review, event-study association, Research Gate Packet, or attractive chart is mistaken for a validated, profitable, paper-ready strategy | High | High | Separate scientific outcome `SUPPORTED|CONTRADICTED|INCONCLUSIVE|INVALID` from owner disposition `advance_to_strategy|revise|park|reject`; anchored screened claims and cited recommendations remain decision support; standalone work is permanent non-evidence; PaperAcceptanceV2 rederives typed callback facts and ignores producer pass flags; no expected-profit backlog score | Schema/copy tests reject validated/pass/paper/order fields, generic-evidence admission and forged paper facts; UI labels uncertainty and valid next action; end-to-end acceptance stops before strategy/D3/holdout/paper unless each later gate independently passes | Product/research owner — **Research boundary and forged-event denial verified offline 2026-08-13; broker-paper scenarios remain pending** |
| R-57 | A fresh project or strategy version bypasses the Research Case while migration compatibility silently becomes a permanent escape hatch | Medium | High | Schema-v2 project research-governance marker; public project/case creation is one atomic retry-idempotent transaction; governed strategy versions require the approved confirmation contract and owner advance decision; only verified migration may emit pre-launch grandfathering; one SQLite writer lock spans the exact v1 backup snapshot, all additive DDL, and version commit; an existing backup must logically match that locked source | Fault injection at every capture write boundary, stale-backup, backdated-forgery, migration failure/retry, concurrent writer/migrator, default/create/version-link tests distinguish grandfathered records from fresh governed projects and deny unlinked strategy versions | Research/control owner — **Gate 1 foundation implemented; empirical advancement remains hard-gated** |
| R-58 | Monte Carlo scenarios are mistaken for proof of edge, majority-voted, calibrated with future data, or bypassed after a warning | High | High | Separate required post-robustness stage; canonical OOS account returns; training-frozen prior-known regime labels; exact-calendar Kronos OHLCV with raw-output validation and fresh full-engine replay; permanent pretraining caveat; independent grades; no vote; exact-hash CLI-only owner disposition; downstream evidence rebuild | Statistical recovery/degeneracy, future-poison, exact timestamp, physical candle, FakeForecaster engine/cost, failed-null continuation, tamper, non-estimability, warning-review, thin-surface authority, deterministic chart, OpenAPI, frontend, and end-to-end holdout-boundary tests | Validation/control owners — **Implemented offline 2026-08-12; real post-cutoff Kronos calibration remains strategy-specific evidence** |

### 2026-08-03 Live UI Hardening Evidence

- **R-33:** capability-scoped panels reject incompatible runs without relabeling evidence; native
  missing/explicit-unavailable states are distinct; causal execution/decision/all layers preserve
  the full returned event table behind a deterministic visual marker cap.
- **R-37:** immutable projections use a bounded LRU, native/chart payload limits remain explicit,
  and loopback JSON responses are gzip-compressed without changing artifact authority.
- **R-39:** inactive fixed-screen side panes issue no requests until activated; vector annotations use a
  single canvas primitive; the 25k-bar/200-annotation probe compares interactive cadence with an
  adjacent no-input rAF baseline. Running jobs expose exact elapsed/current work, avoid invented ETA,
  and lower UI-launched heavyweight scheduling priority so desk input remains favored.
- **R-40:** OpenAPI and generated TypeScript were regenerated byte-identically, and versioned and
  compatibility projections remained green in the full offline test suite.

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
- Tiingo data/service limits and revisions remain external; its adjusted fields are a check, never
  canonical prices. IBKR Paper top-of-book simulation cannot establish live queue/fill quality.
- QuantPad is historical research access, not a live feed. Its short L2 window and continuous-future
  presentation cannot establish long-horizon microstructure or dated-contract strategy validity.
- Scholarly literature can establish precedent, mechanism, or method but cannot prove a current
  executable edge; source availability, versions, retractions, and service terms remain external.
- Research-only intraday event studies are association evidence and cannot inherit daily validation
  or paper authority without the separate ADR-0020 promotion program.
- The reviewed gateway digest, paper permissions, market-data subscriptions, and account operation
  remain owner prerequisites; a digest alone does not establish image trust or license suitability.

Any move to live capital, exchange testnet execution, remote hosting, multiple users/hosts, sharing,
sale, publication, distribution, or automated recovery reopens R-01, R-09, R-11, R-14, R-19, R-22,
R-23, R-24, and R-43–R-48 and
requires a separate ADR and threat/risk model.

## Review Cadence

Review this register:

- at each implementation slice that closes a Gate risk;
- before the full offline acceptance gate;
- after the Binance network smoke and UTC-rollover soak;
- after Tiingo universe qualification and each real IBKR equity/futures evidence run;
- on any Nautilus/provider upgrade or new provider, including a QuantPad adapter;
- at each Research Scientist delivery gate, source-client/service change, protocol/scorecard change,
  or agent-skill activation;
- before any distribution/license decision; and
- immediately after any unexpected order, reconciliation warning, stale session, or corrupt journal.

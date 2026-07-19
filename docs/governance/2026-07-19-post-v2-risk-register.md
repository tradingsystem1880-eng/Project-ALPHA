# Risk Register — Provider Control Plane + Crypto Paper Trading

- **Opened:** 2026-07-19
- **Track:** Post-v2 Recommended
- **Risk owner:** Project ALPHA owner; implementation agents supply controls/evidence but cannot
  accept financial, legal, or distribution risk on the owner's behalf

## Rating and Closure Rules

- Likelihood/impact: Low, Medium, High.
- A risk marked **Gate** blocks declaring the feature complete until its evidence is green.
- A risk marked **Owner decision** cannot be closed by implementation alone.
- Tests must assert the control. Documentation or a UI label alone does not close a safety risk.
- A network smoke is evidence for connectivity only, never permission for real execution.

**Implementation checkpoint (2026-07-19):** the offline controls and focused deterministic tests for
the provider, admission, strategy, node, journal, API, and panel paths are implemented. Gate risks
remain subject to the final full Python/frontend acceptance run. R-22 remains an owner-decision
blocker; R-24 and the real Binance connectivity portion of R-14 remain pending opt-in evidence.

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

## Residual-Risk Decisions

The following remain accepted only within the stated personal sandbox scope:

- Public Binance data can be delayed, unavailable, rate-limited, revised, or venue-specific.
- Nautilus sandbox fills are simulations; they do not prove exchange queue position, latency,
  slippage, fee, rejection, liquidation, or operational behavior.
- A local JSON journal is sufficient for one process/user but is not a multi-host transaction log.
- Stale heartbeat detection reports uncertainty; it does not guarantee whether an orphan process is
  alive.
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

# Project ALPHA Post-v2 Architecture Audit

- **Audit date:** 2026-07-19
- **Baseline:** shipped Workstation v2 on `main`, before the Recommended-track delta
- **Scope:** capability reuse, architecture fit, provider control, crypto paper execution,
  operational monitoring, dependency/license posture
- **Readiness call:** **Bounded Recommended-track implementation complete offline; network/UTC soak
  acceptance pending; not ready for real-order execution or distribution.**

## Executive Finding

The attached greenfield workstation prompt describes a system ALPHA largely already has. Replacing
or duplicating the Nautilus engine, Workstation, point-in-time data spine, validation gauntlet, MCP,
options, risk, forecasting, or research surfaces would reduce reliability. The valid post-v2 delta
is surgical:

1. make provider/configuration readiness discoverable from one CLI-owned registry;
2. complete crypto-first paper execution with public Binance market data and Nautilus **sandbox
   execution only**;
3. journal operational sessions outside deterministic research artifacts; and
4. require evidence and license review before any later upstream adoption.

The existing twelve-contract DAG supports this without a new package or a parallel composer.

**Same-day implementation closeout:** the provider/system registry and projections, CCXT Binance
provenance, opt-in sandbox-only paper node, no-order strategy priming, venue quantity normalization,
durable session journal, CLI/API reads, and Workstation control/monitor panels are implemented with
offline deterministic tests. The separately marked real Binance connection/quote smoke and one
owner-initiated UTC-rollover sandbox soak remain acceptance evidence, not assumptions.

## Audit Method and Evidence

- Read the authoritative `CLAUDE.md`, current architecture, all accepted ADRs, root/package
  manifests, `uv.lock`, CLI paper scaffold, data adapters/snapshot code, strategy registry/base
  class, Workstation backend, and frontend panel registry.
- Re-ran dependency/architecture baseline checks before implementation: locked sync, all 12 import
  contracts, and representative offline tests were green.
- Compared the attached repository recommendations against capabilities already shipped in ALPHA.
- Inspected the installed NautilusTrader `1.228.0` Binance data and sandbox execution factory APIs.
- Checked the repository root for a project license declaration; none exists. The vendored Kronos
  subtree's upstream license does not license ALPHA as a whole.

This is an engineering inventory, not legal advice. Distribution requires an owner-selected root
license and a release-time dependency/license review.

## Existing Capability Map

| Requested capability | Existing ALPHA authority | Audit disposition |
|---|---|---|
| Event-driven backtest/execution | Nautilus-backed `alpha_backtest`; common strategy classes | Keep; do not add a second engine |
| Backtest/live parity | shared Nautilus strategies and Phase-4 sandbox scaffold | Complete the existing seam |
| Point-in-time data | `alpha_data` raw store, corporate-action clocks, `as_of`, hashed snapshots | Keep authoritative |
| Provider adapters | yfinance, CCXT, Stooq; Finnhub screener edge | Add discovery/config registry, not an aggregation framework |
| Statistical validation | walk-forward, two-tier null, BCa, DSR, CPCV, PBO, Reality Check/SPA | Keep authoritative for research claims |
| Forecast/ML | Kronos facade, offline weights, cache provenance, skill evaluation | Keep; no Qlib runtime in this track |
| Options/risk | `alpha_options` Black–Scholes/IV/Greeks; scenario analytics | Keep; no FinancePy/Vollib runtime required now |
| Workstation | React/Dockview terminal, typed FastAPI/SSE backend, generated contracts | Extend with provider/system and paper panels |
| Conversational control | `alpha_mcp`, which subprocesses the CLI | Keep; no in-web LLM or TradingAgents authority |
| Deterministic artifacts | content-addressed IDs, atomic manifest-last publication | Preserve byte compatibility |
| Paper data client | not complete | Add public Binance live data |
| Paper execution client | Nautilus sandbox config scaffold exists | Finish assembly; prohibit Binance execution client |
| Durable paper monitoring | absent | Add separate atomic JSON session journal |
| Provider/system readiness | choices duplicated or implicit | Add one CLI-owned control plane |
| Root licensing | no declared project license | Block distribution pending owner decision |

## Genuine Gaps

### G1 — Provider/configuration control is implicit

The Data Explorer and CLI source choices can drift because they do not derive from one capability
registry. Credential presence and local readiness are not visible without inspecting environment
variables and files.

**Required boundary:** CLI owns `ProviderDefinition`; web surfaces consume JSON projections.
Provider SDKs never enter the Workstation process.

### G2 — Paper-node assembly is incomplete

The scaffold builds config objects but does not yet register both live-data and sandbox-execution
factories, add the strategy before build, prime verified same-venue history, or guarantee disposal
on signals/failure.

**Required boundary:** public Binance data client + local Nautilus sandbox execution at venue
`BINANCE`; no exchange execution client and no real-order credentials.

### G3 — Operational state has no durable home

Research manifests cannot safely carry PID, heartbeat, wall-clock status, or mutable order events.
An in-memory-only monitor would lose the audit trail on a crash.

**Required boundary:** `data_dir/paper/<uuid>/`, separate APIs, and ADR-0012.

### G4 — Upstream adoption and license posture were not explicit

The broad repository list mixes useful architecture references, overlapping frameworks, copyleft
software, and dependency-heavy research environments. ALPHA also has no root project license.

**Required boundary:** ADR-0011, the dated matrix, and an explicit distribution gate.

## Normalized Consistency Findings

| Severity | Baseline location | Contradiction or ambiguity | Resolution |
|---|---|---|---|
| High | `docs/adr/0001-strict-layered-dag.md:13-29` | Described seven contracts and omitted forecast/options/screener plus surface outbound controls | Reconciled to the 12 named contracts/current packages |
| Medium | `docs/adr/0002-cli-sole-composer-subprocess-surfaces.md:24-27` | Used stale numbered contract references | Replaced with stable named boundaries |
| Medium | `CLAUDE.md:23` and `docs/ARCHITECTURE.md:166` | Called pandas a two-edge exception while yfinance is a sanctioned pandas vendor edge | Reconciled to three explicit edges |
| Medium | `docs/ARCHITECTURE.md:53-72` | ASCII fallback had duplicate fences and a disconnected hidden connector | Repaired the fallback into one rendered block |
| Medium | `apps/alpha-web/src/alpha_web/app.py:8-9` and Workstation historical spec | Claimed a panel-manifest route that does not exist | Removed from current docs/code claim; historical spec reconciled to frontend registry |
| High | repository root | No root license, while package metadata is publishable/buildable | Recorded as an explicit distribution blocker; no license inferred |
| High | Phase-4 docs/scaffold | "paper" could be mistaken for exchange testnet or real execution | New spec and ADR require Nautilus sandbox-only routing and opt-in |

No critical contradiction remains in the approved design. High-severity implementation controls are
mapped to tests and release gates below.

## Implementation Tracks

| Track | Scope | Benefit | Exclusions | Decision |
|---|---|---|---|---|
| Conservative | provider registry, provider/system JSON, Data Explorer visibility | Removes configuration drift with minimal operational risk | no live-data node, no paper journal | Valid stopping point |
| **Recommended** | Conservative + Binance historical provenance + public live data + local sandbox execution + durable monitor | Completes safe crypto paper workflow using existing engine and UI | no real execution, no Kronos live strategy, no new upstream suite | **Chosen** |
| Ambitious | separate ML/AI/derivatives workers, additional brokers/providers, multi-venue operations | Broadens research and venue coverage | cannot enter this change without standalone specs/gates | Deferred |

## Upstream Disposition

| Candidate | Evidence-based disposition |
|---|---|
| NautilusTrader | Already authoritative; pin `1.228.0` for the reviewed Binance/sandbox adapter API |
| OpenBB | Provider architecture reference only; no AGPL runtime adoption in this track |
| Qlib | Defer to a separate environment; immutable snapshots in, timestamped OOS signals/provenance out; ALPHA validation remains authoritative |
| Vollib | Possible future options parity oracle; no current capability gap justifies a dependency |
| FinancePy | Defer to a product-specific external worker and explicit GPL review |
| TradingAgents | Research-assistance candidate only; never execution authority |
| TensorTrade | Isolated RL research candidate only; output must re-enter normal validation/execution controls |
| Alpaca/Twelve Data | Not required for public Binance sandbox paper; reconsider only for a named provider/broker use case |

## Acceptance Evidence Required

The Recommended track is complete only when all of the following are green:

- provider IDs/capabilities/options are unique, validated, and credential values are impossible to
  serialize;
- `ccxt:binance` snapshot provenance is verified and the requested symbol is present;
- warmup rejects future, stale, mismatched, and insufficient history and cannot emit an order;
- fake-node tests prove strategy registration precedes build, both factories are registered,
  graceful signal shutdown works, and disposal is unconditional;
- no code path constructs a Binance execution factory/client;
- live quantities use the venue instrument increment/precision while existing SIM fixtures remain
  byte-compatible;
- session/event publication is atomic and recovery tests cover partial sessions, malformed IDs, and
  stale heartbeats;
- web contracts, generated TypeScript, panel tests, lint, coverage, build, and committed assets are
  fresh;
- full offline Python gate, bias guards, import contracts, strict mypy, and isolated wheels pass;
- a separately opted-in `network` smoke proves a public Binance quote/data connection; and
- before Phase 4 is called operationally complete, one opt-in UTC-rollover sandbox soak is reviewed.

## Readiness Call

The bounded Recommended track is **implemented offline** and ready for final deterministic gates plus
the separately opted-in network smoke/UTC-rollover soak. It is **not ready** for real-order routing,
Kronos live paper use, distribution, remote hosting, or any Ambitious-track dependency. Those are
new decisions, not implied follow-ups.

Companion documents:

- [implementation specification](../superpowers/specs/2026-07-19-provider-control-plane-crypto-paper-design.md)
- [dependency/license matrix](../governance/2026-07-19-dependency-license-matrix.md)
- [risk register](../governance/2026-07-19-post-v2-risk-register.md)
- [ADR-0011](../adr/0011-evidence-gated-external-integrations.md)
- [ADR-0012](../adr/0012-operational-paper-sessions.md)

# ADR-0011: Evidence-gated adoption of external integrations

**Status:** Accepted
**Date:** 2026-07-19
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

ALPHA is already a shipped workstation, not a greenfield quant stack. It has a Nautilus-backed
engine, a point-in-time data spine, deterministic validation artifacts, forecasting, options,
risk, MCP, and a dockable Workstation. A broad upstream-repository recommendation can still be
useful, but adopting every recommended project would duplicate working capabilities, expand the
trusted supply chain, weaken the enforced DAG, and introduce incompatible license and dependency
constraints.

Repository popularity is evidence about community interest, not evidence that ALPHA has a gap or
that a dependency belongs in its runtime. The project needs a repeatable adoption gate that starts
from the capability already present in this repository.

## Decision

Every external integration is **evidence-gated**. Before code or a runtime dependency is added, its
proposal must record:

1. the concrete missing user capability and why an existing ALPHA package cannot supply it;
2. the smallest adapter or process boundary that can supply the capability without bypassing the
   CLI sole-composer rule, PIT firewall, or deterministic artifact contracts;
3. upstream maintenance, release, API-stability, provenance, and security evidence;
4. direct and transitive dependency impact, including conflicts with the locked Python/numpy line;
5. license and distribution implications, with copyleft components isolated where appropriate;
6. deterministic/offline behavior, failure semantics, secrets handling, and test doubles;
7. an exit path: how the provider can be disabled, replaced, or removed without rewriting callers;
8. an acceptance plan with offline CI coverage and a separately marked network smoke when needed.

The CLI-owned provider registry is the capability-discovery seam for market-data providers. UI
code consumes that projection and never imports provider SDKs. Credential metadata exposes names
and presence only, never values.

For the 2026-07-19 post-v2 track:

- retain NautilusTrader as the authoritative backtest and execution engine and pin its Binance
  adapter API deliberately;
- implement the provider/control-plane abstraction locally, using OpenBB only as an architecture
  reference;
- defer Qlib to a separately specified environment and immutable snapshot/signal boundary;
- keep the existing `alpha_options` implementation; treat Vollib only as a possible future parity
  oracle and FinancePy as a separately reviewed external-worker candidate;
- keep TradingAgents and TensorTrade research-only, with no execution authority;
- add no OpenBB, Qlib, FinancePy, TradingAgents, TensorTrade, Alpaca, or Twelve Data dependency in
  this track.

The dated [dependency/license matrix](../governance/2026-07-19-dependency-license-matrix.md) records
the current disposition. ALPHA itself has no declared root project license; distribution remains
blocked until the owner makes that decision explicitly.

**Code anchors:** `apps/alpha-cli/src/alpha_cli/providers.py` (provider registry),
`apps/alpha-cli/src/alpha_cli/info_cmds.py` (public projection), root `pyproject.toml` and `uv.lock`
(approved dependency set), and the twelve named import-linter boundaries in root `pyproject.toml`.

## Options Considered

### Option A: evidence-gated adapters behind existing seams (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Moderate, paid once through an explicit review template |
| Cost | Lowest durable cost; only proven capabilities enter the lockfile |
| Correctness-risk | Low; PIT, determinism, CLI composition, and failure behavior stay testable |
| Fit | Excellent for a mature, single-user, $0 workstation |

### Option B: adopt the recommended upstream suite wholesale

| Dimension | Assessment |
|---|---|
| Complexity | Very high; overlapping engines, stores, experiment systems, and UIs |
| Cost | High dependency, maintenance, licensing, and cognitive cost |
| Correctness-risk | High; parallel paths can bypass ALPHA's provenance and validation controls |
| Fit | Poor; treats a mature repository as greenfield |

### Option C: reject all external integrations

| Dimension | Assessment |
|---|---|
| Complexity | Low initially |
| Cost | High when ALPHA must maintain solved venue and provider behavior itself |
| Correctness-risk | Medium; hand-rolled adapters can be less reliable than reviewed upstream code |
| Fit | Poor; blocks narrow, justified reuse such as Nautilus venue adapters |

## Trade-off Analysis

The gate adds documentation and review work before adoption. That friction is intentional: it
forces a proposed dependency to beat the already-shipped baseline on a named capability. It does
not favor building everything locally; it favors the smallest robust implementation whose legal,
operational, and deterministic behavior can be proven.

## Consequences

- **Easier:** keeping the runtime small; explaining why a dependency exists; replacing providers;
  preventing UI-to-SDK coupling; auditing secrets and licenses.
- **Harder:** adding a library based only on popularity or a broad feature list; unreviewed
  experiments must remain outside the authoritative runtime.
- **Revisit when:** a new capability has a standalone spec and passes all eight evidence items, or
  an adopted integration's maintenance/license posture changes materially.

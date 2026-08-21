# ADR-0035: Govern generic study composition as a projection layer

**Status:** Accepted
**Date:** 2026-08-21
**Deciders:** Project ALPHA owner and AI build agents

## Context

The attached `/Users/hunternovotny/Desktop/deep-research-report.md` proposes a broad
generic research framework and a portfolio of external quantitative libraries. Its
useful architectural principle is that Project ALPHA remains the authority and that
external capabilities are adapters or isolated workers. Its proposed autonomous MCP
D1 writes, additional ledgers, and new schemas cannot be adopted independently of the
existing research program.

Project ALPHA already has authoritative `alpha_research` primitives, `alpha_cli`
orchestration, immutable research contracts and artifacts, D0/D1/D2 boundaries,
attempt and decision histories, Touch ID owner actions, promotion dossiers, and a
deliberately pinned 62-tool MCP surface. A second research control plane would create
competing sources of truth and could weaken the existing fail-closed boundaries.

The repository is permanently private and local-only. That scope does not remove
third-party licence, provider terms, entitlement, or data-retention obligations.

## Decision

Create `alpha-study` only as a research-plane composition and projection package.
It may compose approved, read-oriented seams from `alpha_core`, `alpha_data`,
`alpha_patterns`, and `alpha_research`. It owns no research authority, persistence,
approval, D1/D2 transition, promotion, paper, broker, or order capability.

The package boundary is:

```text
alpha-study → approved core/data/patterns/research projections
alpha-cli   → may compose alpha-study and existing research authority
alpha-mcp   → existing public CLI/platform seams only; no direct alpha-study authority
alpha-web   → existing public CLI/platform projections only; no analytical authority
```

`alpha-patterns` remains core-only pure geometry. A third-party indicator adapter must
not be placed in `alpha_patterns` unless a separate DAG decision explicitly changes
that rule; the default location is an optional adapter boundary owned by the study
composition layer.

The proposed contracts map to existing authority as follows:

| Proposed contract | Existing authority | Rule |
|---|---|---|
| `EventTableV1` | Existing point-in-time research observations, artifacts, dataset snapshots, and operator outputs | Projection only; availability, venue, unit, vintage, and lineage semantics must be explicit before implementation. |
| `ExplorationMandateV1` | Existing owner-approved research contract, frozen `ResearchAnalysisPlanV1`, D1 topology, launch reservation, attempt, and phase histories | Derived refinement only; no second approval or budget ledger and owner-only D1 remains unchanged. |
| `OperatorRegistrationV1` | Git-owned operator implementation plus the existing contract fingerprint and code/dependency/environment identity | Closed source registry keyed to exact code hash; mutable detector definitions do not enter SQLite. |
| `DetectorValidationV1` | Existing D0 attempt/run, raw fixture measurements, and mechanical admission/reverification | Versioned D0 artifact referenced by the registration; it cannot accept producer-supplied pass flags or imply empirical truth. |
| `StudyWorkspaceManifestV1` | Existing control-store, run-manifest, chart, dataset, and promotion references | Generated non-authoritative projection; no raw-data copy or independent state. |
| `FindingV1` | Existing typed research evidence, Gate Packet, attempt ledger, and decision view | Findings remain stage- and evidence-bound; they cannot imply promotion or paper readiness. |
| `MechanismGraphV1` | Existing hypothesis, confounder, falsification, stability, screened-claim, context-packet, and note records | Generated explanatory projection; advisor statements remain non-authoritative proposals and graph bytes are never read back as authority. |

No proposed contract is implementation-ready until its exact serialization, canonical
hash, immutable source, revision binding, availability/vintage semantics, error behavior,
and read/write authority are documented. Domain-specific macro and cross-sectional
projections must not be forced into an under-specified universal event row.

## Governance boundaries

- D1 remains owner-only through the existing trusted CLI and approved research contract.
- D2 remains sealed, one-shot, and owner-authorized through the existing executor.
- Promotion, holdout, paper, broker, and order authority remain unchanged.
- MCP remains pinned at 62 tools. This ADR adds no MCP tool and grants no MCP owner
  mutation, semantic labeling, D1 launch, D2, or promotion capability.
- Touch ID owner presence and exact payload/revision binding remain the authority for
  closed research-lifecycle actions.
- Blind semantic delivery is split deliberately. Its first slice obtains each cutoff from the
  mechanically recomputed `d0_acceptance.json` measurement event and rejects unless normalized
  identities and clocks in integrity-checked `events.json` and `chart-data.json.events` exactly
  match that acceptance source. A caller or browser never supplies the time, and the read path
  does not rerun the detector. That slice cannot claim an owner label or freeze. A later additive
  SQLite v5 slice may add append-only
  semantic-definition/review events only with exact Touch ID receipt, payload-hash, and
  case-revision binding; it does not create a second research authority or any MCP capability.
- External packages are not dependencies of this ADR or S0. Future adapters/workers
  require separate version, lock, licence, provenance, isolation, and acceptance review.
- Existing ALPHA data authority remains provider-, venue-, family-, unit-, frequency-,
  and timestamp-specific. An adapter may not silently substitute any of those fields.
- The final deletion or replacement of legacy orchestration requires old/new parity and
  explicit owner approval.

## Staged implementation

The dated FeaturePlan at
`docs/superpowers/plans/2026-08-21-generic-study-composition.md` is normative for
execution order, verification, rollback, and scope. Its slices are:

1. S0: plan and ADR only.
2. S1: authority and contract map.
3. S2: empty `alpha-study` package seam and import boundary.
4. S3: strict canonical projections and provenance.
5. S4: one existing operator parity slice with D0/bias/determinism checks.
6. S5a: nonpersistent server-masked semantic read projection from verified D0 artifacts.
7. S5b: additive SQLite v5 semantic definition/review events and Touch ID binding.
8. S5c: semantic presentation inside the existing Research screen.
9. S6: owner-only D1 integration mapped to existing contracts and ledgers.
10. S7: individually approved external adapters/workers/oracles.
11. S8: acceptance studies, UI projections, and cleanup only after parity.

Every slice is additive and independently revertable. No later slice may widen scope
because an external library or a favorable research result makes it convenient.

## Non-decisions

This ADR does not:

- authorize any runtime implementation by itself;
- authorize autonomous Codex, Luna, Terra, or any other agent to approve or launch D1;
- create a second D1/D2, evidence, attempt, approval, or promotion store;
- change the MCP tool count or add MCP capabilities;
- approve TA-Lib, Twelve Data, Alphalens, mplfinance, Qlib, RD-Agent, PyPortfolioOpt,
  Riskfolio-Lib, `bt`, Zipline Reloaded, pfhedge, pybotters, or any other dependency;
- replace `alpha-backtest` or treat an external backtester as authoritative;
- authorize broker, exchange, paper, order, execution, distribution, hosting, or
  multi-user behavior;
- treat advisor or multi-agent agreement as empirical evidence.

## Acceptance

The owner's instruction to implement the approved staged plan accepts the projection-only
boundary and contract map. Runtime implementation remains conditional on these invariants:

- the 62-tool MCP pin and owner-only D1 boundary remain unchanged;
- each proposed contract maps to one existing authority with no competing source;
- event clocks and feature/vintage lineage are sufficient for all approved domains;
- external dependencies are deferred until their own adapter decisions;
- every implementation slice has a verified command, expected result, and rollback;
- private local-only scope and third-party compliance boundaries remain intact.

S0 acceptance was limited to `gate.py plan-check`, ADR existence, and whitespace validation.
S1 adds this accepted authority map and synchronizes the ADR index, operating manual, and
append-only delivery history without changing runtime behavior.

## Consequences

Positive consequences:

- Generic study composition can be added without weakening the established research
  authority or creating a second control plane.
- Existing D0/D1/D2, evidence, owner-presence, data-lineage, and promotion contracts
  remain the single source of truth.
- External capabilities can be evaluated independently after the internal seam is
  proven.
- Each slice has a bounded rollback and a concrete verification gate.

Costs and limitations:

- The report's broad feature list is intentionally deferred.
- Contract reconciliation is required before any new schema or package code.
- Some desired cross-domain views may need separate domain projections rather than one
  universal row type.
- Runtime changes will require current-state documentation updates in the same slice;
  S0 deliberately makes no such changes.

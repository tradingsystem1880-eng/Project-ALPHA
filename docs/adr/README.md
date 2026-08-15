# Architecture Decision Records

This folder records the **load-bearing decisions** behind Project ALPHA's architecture — the ones with real alternatives that were considered and rejected. The stable map (DAG, layers, data flow) lives in [`../ARCHITECTURE.md`](../ARCHITECTURE.md); each record below captures the *why* and the trade-offs for one decision, anchored to the code that implements it.

## Index

| Number | Title | Status | Date |
|---|---|---|---|
| [0001](0001-strict-layered-dag.md) | Strict layered DAG enforced by import-linter | Accepted | 2026-06-26 |
| [0002](0002-cli-sole-composer-subprocess-surfaces.md) | `alpha_cli` is the sole composer; surfaces subprocess the CLI | Accepted | 2026-06-26 |
| [0003](0003-t+1-fill-encoding.md) | t+1 fills via a dual-event feed encoding | Accepted | 2026-06-26 |
| [0004](0004-two-clock-corporate-actions.md) | Two-clock corporate actions (knowledge time vs ex-date) | Accepted | 2026-06-26 |
| [0005](0005-point-in-time-firewall.md) | A single point-in-time `as_of` firewall | Accepted | 2026-06-26 |
| [0006](0006-two-tier-null-model.md) | Two-tier null model (returns-level + full-engine) | Accepted | 2026-06-26 |
| [0007](0007-deterministic-run-id-and-seeds.md) | Historical v1/v2 content IDs + positional child seeds | Superseded for v3 by 0013 | 2026-06-26 |
| [0008](0008-vendored-kronos-and-alpha-forecast-layer.md) | Vendored Kronos model behind a layer-1 `alpha_forecast` facade | Accepted | 2026-07-04 |
| [0009](0009-forecast-leakage-and-tier2-cost-policy.md) | Pretrain-leakage policy + cache-first engine integration | Accepted | 2026-07-04 |
| [0010](0010-local-kronos-weights-offline-policy.md) | Local Kronos weights + code-wired offline loading policy | Accepted | 2026-07-18 |
| [0011](0011-evidence-gated-external-integrations.md) | Evidence-gated adoption of external integrations | Accepted | 2026-07-19 |
| [0012](0012-operational-paper-sessions.md) | Operational paper sessions remain separate from deterministic research runs | Accepted | 2026-07-19 |
| [0013](0013-run-identity-v3-and-causal-artifacts.md) | Version run identity and publish causal artifact contracts | Accepted | 2026-07-19 |
| [0014](0014-cli-owned-development-control-plane.md) | Keep development lifecycle state in a CLI-owned control plane | Accepted | 2026-07-19 |
| [0015](0015-evidence-ledger-not-agent-memory.md) | Store cited evidence revisions, not an agent truth database | Accepted | 2026-07-19 |
| [0016](0016-isolated-qlib-worker.md) | Isolate Qlib behind immutable JSON/Parquet exchange contracts | Accepted | 2026-07-19 |
| [0017](0017-authoritative-daily-data-and-broker-paper-boundary.md) | Qualify authoritative daily data before releasing broker-paper intents | Accepted | 2026-08-03 |
| [0018](0018-quantpad-external-research-data-boundary.md) | Split QuantPad discovery from bulk research-data access | Accepted | 2026-08-04 |
| [0019](0019-governed-research-cases-before-strategy-development.md) | Govern finite research cases before strategy development | Accepted | 2026-08-06 |
| [0020](0020-intraday-event-research-is-not-daily-validation-evidence.md) | Keep intraday event research outside daily validation and paper evidence | Accepted | 2026-08-06 |
| [0021](0021-research-workstation-read-plane-and-command-center.md) | Research workstation read plane and the Research Command Center desk | Accepted | 2026-08-07 |
| [0022](0022-codex-collaboration-surface.md) | Codex collaboration surface — context packets, protocol library, AI boundary | Accepted | 2026-08-07 |
| [0023](0023-research-dataset-registration-and-quantpad-lane.md) | Research dataset registration and the QuantPad qualification lane | Accepted | 2026-08-07 |
| [0024](0024-literature-acquisition-worker-and-claim-model.md) | Lawful literature acquisition worker and the claim-level evidence model | Accepted | 2026-08-07 |
| [0025](0025-empirical-d1-research-runner-admission.md) | Empirical D1 research-runner admission | Accepted | 2026-08-07 |
| [0026](0026-d2-confirmation-readiness-gate-promotion-override.md) | D2 confirmation authority, readiness gate, promotion packet, exploratory override | Accepted | 2026-08-07 |
| [0027](0027-tiered-research-readiness-semantics.md) | Tiered research readiness is Python-authoritative and non-numeric | Accepted | 2026-08-11 |
| [0028](0028-governed-market-state-and-model-candidates.md) | Govern market state, calibrated Kronos, and Qlib rank ensembles as separate candidates | Accepted | 2026-08-11 |
| [0029](0029-four-family-monte-carlo-validation.md) | Require four-family Monte Carlo path-risk validation | Accepted | 2026-08-12 |
| [0030](0030-touch-id-owner-presence-for-research-actions.md) | Require fresh Touch ID for Workstation research authority | Accepted | 2026-08-13 |
| [0031](0031-provider-readiness-and-paper-acceptance-v2.md) | Separate provider checks, paper acceptance, and IBKR what-if previews | Accepted | 2026-08-13 |
| [0032](0032-governed-crypto-data-house.md) | Govern crypto data by dataset family | Accepted | 2026-08-14 |
| [0033](0033-governed-crypto-crowding-research-and-sandbox-basis.md) | Govern crypto crowding research separately from sandbox basis development | Accepted | 2026-08-15 |

## Conventions

- **Numbering:** zero-padded, sequential, never reused. A superseded ADR keeps its number and links forward to the one that replaces it.
- **Status:** one of `Proposed` · `Accepted` · `Superseded`. Accepted records capture approved
  load-bearing decisions; implementation status is reported separately in `CLAUDE.md` and the
  changelog.
- **Structure:** Every record keeps the Status/Date/Deciders header plus explicit `Context`,
  `Decision`, and `Consequences` sections. Options and trade-offs must be recorded in proportion to
  the decision: concise bullets are acceptable for a narrow choice; a comparison table or separate
  trade-off section is preferred when several viable options need dimension-by-dimension analysis.
  Implementation-backed records cite the most precise practical `file:symbol` or test anchors so
  the decision can be checked against the code.
- **Deciders:** the AI agents that build and operate the platform (per [`CLAUDE.md`](../../CLAUDE.md)); there is no separate human sign-off step.

## Candidate future ADRs

Decisions that are real but currently documented inline in [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §5 and [`CLAUDE.md`](../../CLAUDE.md) rather than as standalone records — promote to an ADR here if deeper rationale is later wanted:

- **Polars as the default dataframe** (pandas confined to the yfinance adapter/parser, tear-sheet rendering edge, and Kronos facade — see ADR-0008).

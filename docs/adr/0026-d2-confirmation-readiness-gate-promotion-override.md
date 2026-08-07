# ADR-0026: D2 confirmation authority, readiness gate, promotion packet, exploratory override

**Status:** Proposed
**Date:** 2026-08-07
**Deciders:** Project ALPHA owner and AI build agents

## Context

With D1 admitted (ADR-0025), the remaining research-first pieces are the one-shot D2
confirmation, a transparent readiness gate ahead of the owner's decision, automatic carry-forward
of research artifacts into strategy development, and enforceable anti-premature-backtesting
controls in the UI. The store already reserves everything D2 needs (sealed/authorized/consumed/
contaminated events bound to the immutable boundary hash, the child confirmation contract with
frozen family/alpha/power/minimum-effect, mechanical classification recomputed by readers,
`advance_to_strategy` requiring `SUPPORTED`). What does not exist: the `run confirm` runner, a
scorecard, a promotion context packet, and any UI-level gating or recorded override.

## Decision

- **D2 runner.** `alpha research run confirm` executes the sealed one-shot confirmation under the
  immutable `ResearchD2BoundaryV1` and the owner-approved child confirmation contract, emitting
  `REGISTERED CONFIRMATORY` artifacts and the D2 `authorized → consumed` (or `contaminated`)
  events. Confirmation approval and D2 transitions are un-disabled in this phase; the mechanical
  classification remains the only source of the scientific outcome.
- **Readiness gate.** The decision surface renders the fourteen edge-validation questions
  (existence, magnitude, stability, breadth, regime dependence, definition survival,
  falsification, artifact/leakage risk, mechanism, cost realism, sample adequacy, residual
  uncertainty) each answered by a typed finding or `NOT_TESTED`, plus the Readiness Scorecard:
  per-dimension enumerated states derived from the findings vocabulary, dual-implemented in
  Python and TypeScript with drift-guard parity fixtures, **with no numeric aggregate anywhere**.
- **Promotion packet.** `advance_to_strategy` records a `strategy_promotion` context packet
  (hypothesis card, gate-packet reference, dataset refs, screened claims, confounder ledger,
  falsification and stability results, limitations, negative-attempt summary, open questions).
  `get_agent_brief` resolves `research_contract_strategy_links` and embeds the packet reference,
  so strategy work — including Codex's first strategy brief — starts from the complete research
  inheritance.
- **Anti-premature controls.** Project projections gain `research_gate_state ∈ {not_required,
  open, passed, overridden}`. StrategyLab, DevelopmentCenter, and Pipeline disable
  strategy-creation/optimisation affordances for `open` research-required projects, showing the
  reason and case link. The only bypass is the owner-only CLI
  `alpha project override-research-gate --actor … --reason …`, recorded as an append-only project
  scope event; runs under an overridden gate carry `EXPLORATORY / RESEARCH GATE NOT COMPLETED`
  in their manifests, RunBrowser rows, tear sheets, and the Operations desk. An overridden run
  can never present itself as validated research.

## Implementation anchors

- Spec: `docs/superpowers/specs/2026-08-07-research-first-workstation-design.md` §10, §11, §15
- Phase plan: `docs/superpowers/plans/2026-08-07-research-first-R6-confirmation-promotion.md`
- D2 machinery: `transition_research_d2_state`, `record_research_decision`,
  `create_strategy_version` in `apps/alpha-cli/src/alpha_cli/control_store.py`
- Brief: `get_agent_brief_context`; scope events: `project_scope_events`
- Drift-guard precedent: `apps/alpha-web/frontend/src/explain/bands.ts` ↔
  `packages/alpha-validation/src/alpha_validation/verdict.py`

## Consequences

- The research gate becomes a visible, multidimensional, honestly-uncertain decision surface;
  statistical significance can never silently stand in for tradable edge.
- Strategy development inherits the research automatically and losslessly; nothing restarts from
  memory.
- Premature backtesting is structurally discouraged but not forbidden: the recorded, watermarked
  override preserves owner freedom while making the epistemic status of every such run
  permanently visible.

# ADR-0025: Empirical D1 research-runner admission

**Status:** Proposed
**Date:** 2026-08-07
**Deciders:** Project ALPHA owner and AI build agents

## Context

Production empirical research is hard-disabled by `_UNRELEASED_EMPIRICAL_RESEARCH_ENABLED = False`
at three enforcement sites (confirmation approval, D2 transitions, D1/D2 attempt admission), and
`alpha research run deep` fails with "not shipped." The machinery around the gap is already
built: the reserved heavyweight job kind `research:event-study`, the reserved run command
`research_deep` mapped to evidence zone D1, the fully specified and validated
`ResearchGateEvidenceV1` artifact contract, budget/stop-rule/launch-reservation enforcement, and
the pure statistical primitives. The research-first redesign requires real pre-strategy
phenomenon testing — event studies, conditional forward returns, stability, falsification
families — on registered `research_only` datasets.

## Decision

- **Preregistered analysis plans.** Extend the exploration contract with `analysis_plan`: the
  per-hypothesis registered selection of test families (event study, conditional forward
  returns, quantile analysis, information coefficient, lead/lag, temporal/regime/subsample
  stability, transportability, sensitivity neighborhoods, placebo/negative controls, leakage
  diagnostics), each with its registered grid and multiplicity family, frozen at exploration
  approval. Blanket batteries are rejected at draft validation; off-plan work is
  exploratory-by-declaration, ledgered and multiplicity-counted, never headline.
- **The D1 runner.** `alpha research run deep` executes only the registered plan on registered
  dataset refs, as durable `research:event-study` jobs (durable lease, heartbeat, cancellation,
  restart-resume from checkpoints), debiting native-unit budgets and honoring stop rules and
  continuation triggers. Each analysis emits immutable v3 artifacts, registered EXPLORATORY
  charts, and the typed `ResearchGateEvidenceV1` artifact. Admission mechanically re-verifies
  run identity, zone, markers, and acceptance-relevant numbers — producer pass-flags are never
  authority (the established D0 pattern).
- **New pure modules.** `alpha_research/conditional_returns.py`, `stability.py`, `ic.py`,
  `leadlag.py` — core-only, deterministic, fail-loud — joining the existing event-study,
  matching, bootstrap, power, and multiple-testing primitives.
- **Scope of the un-disable.** This ADR admits **D1 only**: attempt admission for
  `deep_research` and the exploratory evidence path. Confirmation approval and every D2
  transition remain hard-disabled until ADR-0026. The flag change is the final commit of the
  phase, landing only after the planted-pattern, planted-confounder, pure-null,
  future-poison, kill-and-resume, and budget-exhaustion acceptance scenarios pass.
- **Real-data lane.** The Gate-4 SPY intraday lane runs on ADR-0023-qualified data; if QuantPad
  retention/licensing evidence stalls, the fallback is a registered chart contract on existing
  Tiingo-derived daily data so the runner's admission is never blocked on licensing.

## Implementation anchors

- Spec: `docs/superpowers/specs/2026-08-07-research-first-workstation-design.md` §9
- Phase plan: `docs/superpowers/plans/2026-08-07-research-first-R5-experiment-engine.md`
- Hard-disable flag + sites: `apps/alpha-cli/src/alpha_cli/control_store.py`
- Reserved kind: `apps/alpha-cli/src/alpha_cli/job_capacity.py`; reserved command mapping:
  `_require_research_run` in `control_store.py`
- Evidence contract: `packages/alpha-research/src/alpha_research/gate_packet.py`
  (`ResearchGateEvidenceV1`)

## Consequences

- The phenomenon can finally be tested before any strategy exists, with uncertainty, purge,
  matching, multiplicity, and falsification handled by governed runners rather than notebooks.
- Selection pressure is accounted for structurally: everything attempted is ledgered; only
  registered families can headline.
- Un-disabling D1 raises the scientific stakes; the acceptance suite and the last-commit flag
  policy make that an explicit, owner-visible transition rather than a side effect.

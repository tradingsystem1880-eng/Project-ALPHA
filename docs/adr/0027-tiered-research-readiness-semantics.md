# ADR-0027: Tiered research readiness is Python-authoritative and non-numeric

**Status:** Accepted
**Date:** 2026-08-11
**Deciders:** Project ALPHA owner and AI build agents

## Context

The original scorecard described useful evidence dimensions but could still present a supportive
headline when required controls were incomplete. A separate TypeScript implementation duplicated
part of the authority and made drift possible. Low-cluster D2 evidence could also retain a
`SUPPORTED` classification even though its registered reliability floor had failed.

## Decision

- One Python derivation publishes additive `confirmation_readiness` and `promotion_readiness`
  projections. Each is `ready` or `blocked`, with stable blocker codes and evidence references;
  there is no aggregate score.
- Confirmation is blocked when the primary or economic hurdle, multiplicity, power, any required
  falsifier, or any preregistered required family has not passed. Control aggregation is
  conservative: `FAILED` outranks `INCONCLUSIVE`, which outranks `PASSED`.
- The single mechanical D2 classifier returns `INCONCLUSIVE` below the frozen cluster reliability
  floor. Production, store admission, read projections, CLI, REST, and decisions all use it.
- `advance_to_strategy` requires both a mechanically `SUPPORTED` outcome and promotion readiness.
- An owner override remains an exploratory strategy-work exception only. Its permanent watermark
  cannot create passed research evidence, readiness, or a promotion dossier.
- Frontends render the backend projection directly. The TypeScript scorecard/checklist twins and
  their parity fixtures are removed.

## Consequences

Existing records, routes, commands, and immutable decisions remain compatible; readiness fields are
additive. Legacy records may now project a stricter current readiness state without being rewritten.
The semantics are testable at one authority seam and cannot be averaged into a misleading score.

## Implementation anchors

- `apps/alpha-cli/src/alpha_cli/research_readiness.py`
- `apps/alpha-cli/src/alpha_cli/research_gate_packet.py`
- `apps/alpha-cli/src/alpha_cli/control_store.py`
- `packages/alpha-research/src/alpha_research/confirmation.py`
- `tests/integration/test_research_program_acceptance.py`


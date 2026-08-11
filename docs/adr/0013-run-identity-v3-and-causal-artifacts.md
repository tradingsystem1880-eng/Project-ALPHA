# ADR-0013: Version run identity and publish causal artifact contracts

**Status:** Accepted
**Date:** 2026-07-19
**Deciders:** Owner-approved Workstation v3 plan and AI build agents

## Context

Schema-v2 run identifiers cover normalized parameters but do not prove which strategy source code
executed. Completed legacy runs also have no causal decision/order/fill/indicator contract. Adding
required sidecars to old directories would mutate evidence and make completion ambiguous.

## Decision

New research runs use `schema_version = 3`, `run_identity_version = 3`, and
`artifact_contract_version = 3`. Identity includes a stable strategy execution/source
fingerprint in addition to normalized inputs, snapshot, and seed. The manifest contains a sorted
artifact map with each artifact's contract version, SHA-256, byte size, and row count where
applicable.

All required sidecars are written and verified before the atomic manifest completion marker.
Completed run directories are immutable: an identical rerun verifies existing bytes; a mismatch
under the same identity fails. Legacy v1/v2 readers remain supported and old runs are never
backfilled. Causal traces record stable sequence IDs and distinct decision/order/fill/trade times;
unknown indicators, reasons, or patterns remain absent.

Random seeds are derived from stable semantic namespaces rather than positional `spawn(n)` slots.
OOS and final-holdout runs prime trailing strategy history without attaching an engine, then start a
fresh portfolio at the scored boundary. Their metrics and chart sidecars are scoped from that same
execution; discovery positions, orders, fills, and trades never cross the boundary.

## Implementation anchors

- `apps/alpha-cli/src/alpha_cli/_runner.py:run_identity_for` plus
  `apps/alpha-cli/src/alpha_cli/_identity.py:execution_fingerprint` / `strategy_fingerprint`
  implement versioned content identity; `apps/alpha-cli/src/alpha_cli/_seeds.py:semantic_seed`
  implements semantic namespaces.
- `apps/alpha-cli/src/alpha_cli/artifact_contract.py` and
  `apps/alpha-cli/src/alpha_cli/_artifacts.py:write_manifest` verify/publish the immutable artifact
  map and reject identity-matched byte conflicts.
- `apps/alpha-cli/src/alpha_cli/_runner.py:fresh_oos_execution` and
  `fresh_scored_execution` enforce the fresh portfolio boundary and matching causal scope.
- `packages/alpha-backtest/src/alpha_backtest/results.py` is the canonical trace/result schema.
- Regression evidence: `tests/unit/test_manifest_v3.py`,
  `tests/integration/test_backtest_oos_cli.py`,
  `tests/integration/test_backtest_holdout_cli.py`, and the v3 bias-guard suite.

## Options considered

- Mutate old runs: rejected because it destroys immutable evidence semantics.
- Keep parameter-only identity: rejected because different source revisions can alias.
- Version identity/artifacts additively: chosen for causality, compatibility, and fail-loud behavior.

## Consequences

- Easier: provenance checks, chart reconciliation, compatibility, deterministic agent reads.
- Harder: source fingerprint plumbing and strict publication verification.
- Revisit: only through a new identity/contract version; never reinterpret v3 in place.

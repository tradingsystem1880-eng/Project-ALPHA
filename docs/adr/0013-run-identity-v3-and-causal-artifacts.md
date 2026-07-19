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

## Options considered

- Mutate old runs: rejected because it destroys immutable evidence semantics.
- Keep parameter-only identity: rejected because different source revisions can alias.
- Version identity/artifacts additively: chosen for causality, compatibility, and fail-loud behavior.

## Consequences

- Easier: provenance checks, chart reconciliation, compatibility, deterministic agent reads.
- Harder: source fingerprint plumbing and strict publication verification.
- Revisit: only through a new identity/contract version; never reinterpret v3 in place.

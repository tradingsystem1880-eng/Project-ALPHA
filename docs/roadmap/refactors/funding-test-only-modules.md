# Wire in or remove the test-only funding modules

**Risk:** L

## Scope

`packages/alpha-data/src/alpha_data/crypto/funding_ingestion.py` (79 lines) and
`packages/alpha-data/src/alpha_data/crypto/providers/funding_transport.py` (204 lines) are imported
only by tests (`tests/unit/test_funding_bounded_transport.py`, `test_funding_raw_retention.py`). They
come from the 2026-11-05 offline funding plans (now archived as Completed via PR #117), which state
the bounded transport/retention path is "not registered with production CLI/API/MCP" and keeps the
production full-page refusal.

## Why

Production modules that nothing in production imports are either unfinished features or dead code;
the delivery record should say which.

## Invariants at risk

- The production full-page refusal for funding acquisition must remain until a live route is
  admitted.
- `alpha_data` is an execution package and some of its files feed identity hashes; removal changes
  `execution_fingerprint`.

## Proof required before/after

- Before: a decision recorded against the
  [offline funding delivery](../../operations/2026-11-05-offline-funding-delivery.md): wire in
  (behind the ControlStore-owned acquisition backlog item) or remove.
- After (remove): tests and modules deleted together, README and runbook updated; (wire in): the
  production route passes its own admission and receipts.

## Suggested slicing

One change either way; removal is small, wiring in depends on
[ControlStore-owned durable acquisition](../backlog/controlstore-durable-acquisition.md).

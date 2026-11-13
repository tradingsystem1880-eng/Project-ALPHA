# Split control_store.py behind the unchanged ControlStore facade

**Risk:** H

## Scope

`apps/alpha-cli/src/alpha_cli/control_store.py`: 14,027 lines, 287 function definitions in the file;
the `ControlStore` class spans 11,963 lines with 221 methods (116 public). Schema version 7 with six
migration functions (`_migrate_schema_v1`–`_v6`) and legacy readers; schema DDL including the
append-only owner-event triggers lives in `_control_schema.py`. 96 Python files import or reference
`control_store`.

## Why

A single 14k-line class is the hardest file in the repository to review and the most likely place
for merge conflicts.

## Invariants at risk

- The public `ControlStore` API (method names, signatures, transaction boundaries) stays unchanged.
- Schema migrations and legacy readers must keep reading every historical database version.
- The append-only owner-event ledger (no-update/no-delete triggers on `owner_action_receipts` and
  owner credential events) and the owner-auth seam must be preserved exactly.
- Stored row bytes and canonical JSON in the ledger must stay byte-identical.

## Proof required before/after

- Before: migration tests from each recorded schema version (1–6) to 7 over fixture databases;
  a public-API snapshot (method names and signatures); ledger append-only tests.
- After: the same tests pass; fixture databases produce identical rows; protected test tiers and the
  full gate pass.

## Suggested slicing

1. Move module-level helpers and constants out (no class change).
2. Extract cohesive method groups (research, semantic ledger, owner auth, datasets) into mixins or
   internal services that the facade delegates to, one group per change.
3. Keep migrations in their own module with their tests.

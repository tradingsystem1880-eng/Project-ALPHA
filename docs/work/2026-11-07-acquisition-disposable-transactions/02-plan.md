# Disposable acquisition transactions

**Delivery state:** Blocked — shelved 2026-11-14 (triage card 2, owner's delegation): code merged but not wired into any command; kept for a future download-budget policy and durable acquisition journal. Earlier state: Implemented – qualification pending

This candidate is independent of preserved resume tree a20c88091c9951ea98b5202e6b1dfc999e8a79d0
and verification-I/O tree 7953dcde1759b3a3094dd4325d1dcde9a55c12f9. It shares their base
3f7b23185c29b2542605bd41b9485016c2ef3e79 but does not include their source delta.

```json
{
  "schema_version": 1,
  "title": "Disposable acquisition transactions",
  "context": "W05/W02/W19 confirmed a supplied-active-connection, fixture-only namespace contract with the pending ControlStore owner. This isolated fragment adapts inactive F5 without activating it or editing another owner's files.",
  "assumptions": [
    {"statement": "The caller guarantees BEGIN IMMEDIATE for writes; connection.in_transaction alone cannot prove lock mode.", "verified_by": "Existing ControlStore._transaction and explicit fixture wrappers"},
    {"statement": "Explicit fixture policies and history flags grant no operational authority or real history continuity.", "verified_by": "No production opener, migration registry, command, sender or Ledger imports the new fragment"}
  ],
  "alternatives_considered": ["Add HTTP accounting to Ledger v1: rejected; progress is not quota authority.", "Edit pending ControlStore or allocate v8: rejected; fixture-only contract and owner exclusion.", "Add another database or adopt research reservations: rejected; wrong physical/domain authority."],
  "pre_mortem": ["A replay allocates another attempt after a lost commit acknowledgment.", "A multi-dimension failure leaves a partial debit.", "Unknown consumption or a new period restores apparent headroom.", "Synthetic transactions are mistaken for enforced sender ownership."],
  "slices": [
    {"title": "Define bounded fixture schema and transaction reducer", "verify": "Scoped public unit tests plus strict typing/lint", "expected": "Caller-owned transactions, exact replay, atomic full-vector debits, conservative cancellation and unknown states", "rollback": "Remove inactive fragment; no production artifact or schema was created", "status": "done"},
    {"title": "Verify multiprocess contention and crash/reopen", "verify": "Owned-process synthetic integration selection and independent source review", "expected": "One winner for remaining allowance, same-event uncertain commit resolution, schema coexistence", "rollback": "Remove fixture tests and module; preserved candidates remain unchanged", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/work/2026-11-07-acquisition-disposable-transactions/02-plan.md"],
  "out_of_scope": ["Production initialization or migrations", "Real quota policy and host designation", "Provider or network calls", "Sender fencing or permits", "ControlStore and Ledger wiring", "Release/refund/reset", "Rights/readiness/snapshot work", "Private/protected tests or full gates", "Transfers or publication"],
  "files": ["apps/alpha-cli/src/alpha_cli/_market_data_acquisition_accounting.py", "tests/unit/test_market_data_acquisition_accounting.py", "tests/integration/test_market_data_acquisition_transactions.py"]
}
```

The new `md_acquisition_` tables are explicitly installed only by disposable tests.
Fragment version 1 is independent of global user_version. The facade requires an active
caller-owned connection and never opens/closes it or commits/rolls back the outer transaction.
Writes use an internal savepoint for operation atomicity; caller still owns BEGIN IMMEDIATE,
final commit/rollback, busy handling and uncertain-commit resolution. No lock mode is inferred.
A returned attempt dictionary is bookkeeping, never a send or publication permit.

Explicit immutable fixture policies define campaign/generation, dimensions, positive limits
and weights, total-cap or finite non-overlapping [start,end) periods. Every reservation
must debit every declared dimension at exactly its declared weight. No default limits,
rolling window, provider reset discovery or actual billing inference. Dimensions and
allowances belong to the declared fixture scope; cross-scope/shared-IP authority is not
established. A fixture declaration is not a real campaign registration or cap-reset right.

Events and projections are validated under the caller's pinned transaction before operations.
Exact event/payload replay is idempotent; conflicting replay fails. Retry ordinals advance
only after a confirmed terminal predecessor. Reserved/intent/unknown predecessors cannot
be retried. Cancellation does not refund, and pre-intent cancellation prevents later intent.
Unknown outcome or unavailable history blocks new scope reservations without clearing any
debits. Unfinished prior-period debits prevent moving that dimension to a new period;
clock rollback, changed policy/generation and omitted dimensions refuse before mutation.
Transport success/failure is recorded only as caller-supplied synthetic bookkeeping.

The schema is strict and not healed. Temporary namespace shadows and temporary triggers
attached to domain tables are refused; unrelated temporary objects remain compatible. Bounded reconstruction checks events against scopes,
attempts and debits. Maximum 2,048 events, 8,192 UTF-8 bytes per event/projection body,
16 policy period definitions/charges, and corresponding finite table inspection counts
are engineering fixture bounds, not provider limits. SQL engine I/O, physical memory,
whole-store rollback and coordinated consistent tampering are not bounded/proven by this
validation. Fixture complete-history and generation values are assumptions, not authority.

Multiprocess fixtures use temporary WAL SQLite databases with FULL synchronous and explicit
BEGIN IMMEDIATE; kill/reopen tests exercise committed/uncommitted transactions. Lost commit
acknowledgment is modeled by reopening with the same event identity after killing at a known
boundary; this is not a general filesystem/power-loss proof or actual sender uncertainty test.
Coexistence checks historical ControlStore DDL objects and unchanged global user_version;
it does not qualify a current retained schema-7 store or production migration.

No legacy artifact hashes are checked here: opaque history references do not prove artifact
integrity. The preserved resume verifier remains the separately tested implementation for
that job. Sender lifecycle/quiescence, old-writer cutover, real store continuity, effectful
migration and restore, and whole-file Ledger reload/decision/write exclusion remain future
integration requirements. No SQL transaction may wait for file locks or do provider/artifact
I/O; concrete future lock order still needs source review. QuantPad stays excluded.

README review: no change proposed. This adds no supported command, setup, admitted provider,
real store action or usable operational capability. Shared manual/build/Atlas edits remain
excluded by the coordinating owner; this candidate-local plan records implemented limits.
Focused synthetic passes/source approval do not qualify release, private coverage or live data.

Independent review corrected two required findings: contention fixtures now use distinct logical
requests and require allowance exhaustion; TEMP namespace shadows/attached triggers now fail
before domain reads or mutation. Final counts and exact-tree source verdict are retained in
the separate delivery receipts. No native/release approval is implied.

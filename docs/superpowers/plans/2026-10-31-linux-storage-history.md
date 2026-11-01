# Linux storage preparation without replacing research history

Status: implemented and qualified with public Linux fixtures; guarded delivery requires the exact-tree full gate and independent review. No runtime or scientific admission.

```json
{
  "schema_version": 1,
  "title": "Inspect retained daily history before Linux storage selection",
  "context": "Use the existing Linux-native identity backend without replacing Mac archives or authoritative research history.",
  "assumptions": [
    {
      "statement": "cloud_root_identity requires retained co-located control and bulk.",
      "verified_by": "crypto_bulk_store.py and crypto/root_identity.py source and public backend fixtures"
    },
    {
      "statement": "Ordinary list methods may initialize or migrate; the read-only opener does not.",
      "verified_by": "ControlStore._transaction, _open_readonly and _readonly_transaction"
    }
  ],
  "alternatives_considered": [
    "Live Mac/Linux bridge: unnecessary new transport, response ownership and effect-time binding infrastructure.",
    "Fresh empty ledger: rejected because it could bypass database-wide exposure history."
  ],
  "pre_mortem": [
    "A paged/malformed result is mistaken for no prior exposure; global counts and unknown states prevent that inference.",
    "A nominal read initializes/migrates real state; use only the schema-checked read-only opener."
  ],
  "slices": [
    {
      "title": "Bounded read-only daily-history metadata",
      "verify": "uv run pytest -q tests/unit/test_daily_rule_history.py",
      "expected": "Fixture records/schema unchanged; prior/unknown exposure visible beyond pagination.",
      "rollback": "Revert projection/delegate source changes; no real store/schema was modified.",
      "status": "done"
    },
    {
      "title": "Explicit-root inspection and honest storage guidance",
      "verify": "uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-10-31-linux-storage-history.md",
      "expected": "Inspection grants no initialization/migration/execution authority; plan and links validate.",
      "rollback": "Revert script/documentation additions; no runtime configuration was installed.",
      "status": "done"
    }
  ],
  "tier_impact": [
    "protected"
  ],
  "docs_to_update": [
    "README.md",
    "CLAUDE.md",
    "workers/rdagent/README.md",
    "docs/BUILD-STATUS.md"
  ],
  "out_of_scope": [
    "new storage backends",
    "real DB migration",
    "host security/credential changes",
    "runtime/study activation"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/_native_daily_rule_history.py",
    "apps/alpha-cli/src/alpha_cli/control_store.py",
    "scripts/inspect_daily_rule_history.py",
    "tests/unit/test_daily_rule_history.py"
  ]
}
```

The existing `cloud_root_identity` backend can use one explicitly retained Linux
mount for control and bulk. Temporary task duration does not make `/tmp`, tmpfs,
overlay or an unretained VM disk acceptable. A separate execution root must not
bypass the database-wide fixed-rule exposure guard. Original Mac storage, its UUID
checks and all authoritative records remain unchanged.

A live Mac/Linux identity bridge would add a trusted transport, response ownership
and effect-time volume/open binding. Nonces and shared JSON alone do not establish
those properties. No bridge is needed for an independently designated Linux root.

## Slices

1. Add a bounded, metadata-only daily-rule history projection through the existing
   `ControlStore._readonly_transaction()`. Count prior daily deep reservations
   across the whole selected store; pagination must not hide older consumption.
   Missing, old, malformed or incomplete history is unknown, never empty.
   Verify: focused unit tests for no creation/migration, privacy, aggregate counts,
   truncation and malformed metadata.
2. Expose an explicit-root operator inspection script and document the existing
   Linux storage option and activation prerequisites. The script reads no `.env`,
   writes no config/history and grants no admission or migration authority.
   Verify: script tests, read-only WAL snapshot and schema guards, lint/types and
   independent review; run required final gates before any commit.

## Scope and invariants

Only CLI metadata projection/composition, its operator script, public fixture tests
and documentation change. No database schema, allowance, lifecycle, storage
backend or numerical implementation changes. The CLI may import core; no DAG edge
changes. No market rows, timestamps, as-of logic, seeds or statistics are consumed.
No hidden suite or opaque evidence content is inspected. Engineering fixtures
confer no research authority.

The original `5bd99c56` source checkpoint remains historical evidence. This reader
was integrated onto fetched main `fcec79b91c18467ff818c1f7d03684a9908ac9de`; the separate
bootstrap-validation repair owns its script/tests. Shared documentation and Atlas
outputs are reconciled against the delivery base before final qualification.

## Activation remains separate

Qualify a retained mount, capacity/reserve, confinement, SQLite/lock coherence,
Linux supervisor, private container engine, exact image and closed profiles. Then
inspect authoritative history and resolve every prior/unknown reservation before
designating a new root or binding real inputs and exact local owner confirmation.
This work does not migrate a database, restore stale state or authorize effects.

## Verification and remaining release work

The corrected focused native check passed 41 tests (38 new history cases and three existing
read-only schema/snapshot cases); ruff and mypy passed. Independent advisory findings about
duplicate routing keys, NUL/byte bounds and plan metadata were corrected with regressions.
A fresh independent review also found SQLite integer offset overflow; the API now rejects
out-of-range offsets with a typed error before opening history, with API/script regressions.
The metadata scan is capped at 10,000 records per inspected collection, 1 MiB per contract
and 16 MiB total contract JSON before classification. No real history was inspected.

Two unchanged Linux-storage fixtures could not pass their Linux-path assumptions on macOS;
their result is unverified here, not waived. Full component qualification remains pending.
A separate source-only Docker metadata probe verified a genuine Linux process namespace
and an inspected no-network/no-credential/no-socket read-only source mount. Its internal
backing space failed the unchanged 100 GB reserve. Docker denied a separate read-only
Expansion bind before container creation; no setting was changed and that bind was not
retried. No numerical study or storage-root activation occurred.

## Linux integration qualification (2026-11-01)

The original source patch was recovered through the supported Library helper and verified
at 40,697 bytes with SHA256
`506c51c6808e065d0c9656243b4ae22745a3073178b105ad95b85c33b1413f91`.
The handwritten production reader, delegate and operator script are unchanged. Integration
appends the original build entry after newer history, uses the existing README link in the
size-limited manual, updates this plan, adds three public regressions for corrupt/missing
databases and a live uncommitted writer, and regenerates Atlas normally.

Linux focused verification passed 54 history/read-only tests and all 28 cloud-root storage
tests, including the unchanged temporary-root and symlink cases that were unverified on Mac.
No real history, Mac connection or study was used. SQLite may use WAL/SHM sidecars; read-only
means no domain records, schema, journal settings or allowance are written by this reader.
The existing Packet3 through-delivery absence-only exception applies to this retained work;
private coverage remains UNVERIFIED. Full checks and exact-tree independent review remain
mandatory; focused results do not replace them.

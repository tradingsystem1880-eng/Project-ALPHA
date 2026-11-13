# W09 durable diagnostic associations

**Delivery state:** Completed

Connect retained-worker observations to existing inert D1 reservation identities in
the existing job journal. This verifies record associations, not a Qlib admission,
resource interpretation, fitted-state proof or charge settlement. Rule reservations
and jobs owned by the native supervisor are excluded. No live records are touched.

```json
{
  "schema_version": 1,
  "title": "Durably associate W09 diagnostics with existing reservations",
  "context": "Retain observed component prefixes across interrupted or duplicate delivery without changing accounting, numerical computation or native admission.",
  "assumptions": [
    {"statement": "Inert D1 reservations can bind a declared manifest without dispatch.", "verified_by": "control_store.py build_d1_native_invocation_spec and reserve_d1_native_research_launch"},
    {"statement": "The owner authorizes this bounded connection but not excluded policy changes.", "verified_by": "Current task-specific owner authorization; Packet 4 checklist retains policy prerequisites"}
  ],
  "alternatives_considered": [
    "Component attempt rows: rejected because they alter existing accounting semantics.",
    "Second durable ledger: rejected; use the existing transactional job journal."
  ],
  "pre_mortem": [
    "Lost acknowledgement repeats activity: identical delivery is idempotent and never dispatches computation.",
    "Crash is recorded as success: incomplete observations stay unknown; terminal errors retain earlier completed calls.",
    "A rule reservation is relabeled as Qlib: reject rule contracts and supervisor claims."
  ],
  "slices": [
    {"title": "Bounded observation prefixes and worker checkpoints", "verify": "Focused editable worker and prefix tests", "expected": "Synchronous opt-in checkpoints precede calls; failures preserve genuine completed observations and existing output parity.", "rollback": "Remove private checkpoint option; normal worker behavior is unchanged.", "status": "done"},
    {"title": "Existing-record diagnostic journal and recovery", "verify": "Isolated ControlStore synthetic recovery tests", "expected": "Atomic idempotent journal writes, exact scope and prefix validation, failed/unknown distinction, unchanged reservation accounting and attempt rows.", "rollback": "Disable private writer; retain existing journal history without admitting evidence.", "status": "done"},
    {"title": "Independent review and durable candidate", "verify": "Focused checks and independent source review", "expected": "Preserve source and failure evidence; identify the exact new absence-exception and delivery scope before final qualification.", "rollback": "Hold candidate without publication or inferred private-suite pass.", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/work/2026-11-02-w09-durable-observations.md", "README.md", "CLAUDE.md", "workers/qlib/README.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["native admission", "charging/refunds/retry/reuse policy", "real-data execution", "data acquisition", "Mac activity", "v3 numerical changes", "new ledger", "protected-test reads or edits"]
}
```

Worker/CLI separation remains JSON-only. Look-ahead, folds, recipes, predictions and
artifact serialization stay unchanged. Shared README/manual/build/Atlas reconciliation
follows the canonical-checklist and backend-setup deliveries. The earlier observation
private-suite exception was not reused for this durable connection.


## Current bounded evidence

Implemented diagnostic association over existing `job_events`, with serialized
transaction/cursor writes and compact immutable deltas. The initial binding retains
complete protocol metadata for reopening without the original planning object or
worker files. Existing project-owned `ex_` experiment references are supported;
legacy UUID-only planning identities remain inert and cannot pass record membership.
No reservation, attempt, link or execution-state mutation is part of this mechanism.
The store reports pre-existing attempt/run references as unverified, not admitted runs.

Historical focused evidence at the preserved source boundary: 108 root cases pass (44 new storage,
recovery and prefix cases plus 64 existing planning/binding cases); 62 covering worker
cases pass, including existing v3/reference tests, ordinary v1/v2 synthetic artifact
parity, checkpoint acknowledgement failures, and a separate-process JSON handshake
with termination after durable entry before acknowledgement. Storage fixtures use
artificial rows in disposable databases. They do not manufacture scientific adoption
or establish a valid Qlib execution route. No live records or protected data were used.

Independent source review found and prompted fixes for unsupported checkpoint-enabled
v3, preprocessing completion acknowledgement handling, bounded SQLite payload transfer,
malformed persisted mappings, completed-graph revalidation, durable manifest retention,
and bool/float aliasing in exact JSON scope identities. Original failed fixture/type/
transport checks and reviewer evidence are retained in scratch. Final independent
source assessment found no remaining required source findings and independently passed
108 root and 62 worker tests, targeted Ruff/mypy and all 13 import contracts. No full gate, coverage result, formal delivery review, commit/push or PR is inferred
from these focused results.

The owner separately approved this bounded durable slice and necessary fixes through
normal guarded delivery of `feat/w09-durable-observations` into Project-ALPHA main,
including an absence-only private-suite exception. Private coverage remains UNVERIFIED;
actual failures and all public requirements still block. The preserved candidate was
verified byte-for-byte, then integrated without source conflicts onto PR113 main
`df82703240b469056144afa64b968511876fe1d6`. README/manual/build and Atlas are reconciled
in this candidate. This completed header describes the bounded implementation plan;
fresh exact-tree public qualification, final independent review and normal Git/hosted
guards determine delivery acceptance in their separate receipts. No scientific, charging, retry, refund,
reuse, research activation or real-data decision is made by this implementation.

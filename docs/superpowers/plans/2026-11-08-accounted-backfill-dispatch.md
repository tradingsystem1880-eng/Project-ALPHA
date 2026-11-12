# Connect backfill to explicit disposable window-dispatch accounting

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

Canonical v9 W05/W02 market-data slice C calls for persistent budget use across retries
and resumes, bounded acquisition and no history/exposure reset. This successor connects
existing code rather than adding another catalog, scheduler, ledger or accounting store.
Preserved predecessor:3cda66c1db8136ae79d51594bd2ac9fba89d7774; cumulative base:3f7b23185c29b2542605bd41b9485016c2ef3e79.

The exact compatible unit is a SYNTHETIC ACQUISITION-WINDOW DISPATCH. run_backfill's
acquire callback covers a whole window, potentially containing multiple HTTP pages,
attempts, retries or cache reads. No existing hook proves HTTP consumption there. This
implementation therefore does NOT close durable provider quota, wire bytes, billing or
shared-IP accounting. Explicit fixture policy values are engineering inputs only.

```json
{
  "schema_version": 1,
  "title": "Connect backfill to explicit disposable window dispatch accounting",
  "context": "An opt-in internal run_backfill connection to the existing supplied-transaction synthetic namespace, preserving default CLI behavior and all admission/storage/publication guards.",
  "assumptions": [
    {"statement": "The caller exclusively lends an idle disposable SQLite connection with declared finite busy timeout, WAL/FULL and foreign keys enabled.", "verified_by": "PID/thread checks, active-transaction rejection before filesystem locking, configuration rechecks and synthetic contention/crash tests"},
    {"statement": "A dispatch-return bookkeeping success is not artifact qualification or complete historical coverage.", "verified_by": "Existing ingestion/quality and completed artifact hash verification remain separate; prior account-success/progress-gap blocks refetch under any retry label"},
    {"statement": "The scope and full policy/history are explicitly supplied test assumptions, not operational authority or real retained-history continuity.", "verified_by": "synthetic_only schema; no database opener, DDL registration, ControlStore wiring, CLI option or provider activation"}
  ],
  "alternatives_considered": ["Count one opaque window as one HTTP request: rejected as false accounting.", "Add a second budget file or reuse W09 reservations: rejected; the existing namespace is the sole supplied bookkeeping store.", "Automatically retry or expire orphan ownership: rejected; uncertainty stays charged and blocks scope progression.", "Require another operational policy decision for a synthetic fixed-topology test: unnecessary; no operational designation is made."],
  "pre_mortem": ["An accounting refusal enters ordinary DataError splitting/continuation.", "Two progress files dispatch the same reserved request.", "Success commits but missing progress allows retry under a new label.", "Mutable callback configuration redirects settlement to another scope.", "An external cancellation/history marker arrives during callback and is ignored.", "Forced-process test cleanup touches a poisoned multiprocessing Event lock."],
  "slices": [
    {"title": "Connect real window orchestration to supplied transactions", "verify": "Synthetic native provider→raw/normalized manifest→Ledger replay plus matching policy/charge/history/ownership and cancellation failure cases", "expected": "Reserve+intent commit before one callback, settle before existing progress publication; defaultNone unchanged; no implicit policy or refunds", "rollback": "Stop using optional fixture adapter, revert helper/import and additive facade readers; no persisted schema changes or live store migration", "status": "done"},
    {"title": "Verify competing owners and uncertain boundaries", "verify": "Owned-process same/different request contention, same Ledger ownership, process kill before/after commit and during callback, lost acknowledgment and publication-failure replay; strict types/lint/imports and independent source review", "expected": "At most one participating unresolved scope dispatch, durable nonrefunded debit, conservative blocked reconciliation and no automatic refetch", "rollback": "Retain original artifacts and existing event readers; never erase committed debits/history or reset a real campaign", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/superpowers/plans/2026-11-08-accounted-backfill-dispatch.md"],
  "out_of_scope": ["Real ControlStore/schema migration or host/quota-scope designation", "HTTP quota, socket bytes or provider billing inference", "Live sender or legacy-binary fencing", "Rights/readiness/snapshot/restore expansion", "Provider calls, credentials, actual retained roots or studies", "CLI/API/UI activation or other owners' paths", "Protected/full gates, installations, transfers or publication"],
  "files": ["apps/alpha-cli/src/alpha_cli/_crypto_backfill.py", "apps/alpha-cli/src/alpha_cli/_crypto_backfill_accounting.py", "apps/alpha-cli/src/alpha_cli/_market_data_acquisition_accounting.py", "tests/integration/test_accounted_backfill.py", "tests/integration/test_accounted_backfill_process.py"]
}
```

## Existing ownership and concrete connection

W05 owns run_backfill, its native acquisition callback and window identities. W02 owns
cooperative Ledger exclusion, crash/reopen and conservative uncertain state; W19's existing
SQLite namespace/retained-store model is reused. The pending ControlStore facade/schema
and paper/RD/science/UI paths remain untouched. No physical accounting authority is selected.

run_backfill now accepts fixture_accounting=None, an internal optional object. Normal CLI
backfill never supplies it and has no new store/policy/provider option. None explicitly
retains legacy behavior; invalid supplied objects or missing required constructor inputs
fail closed. The adapter is not a generic runtime configuration, live permit or sandbox for
arbitrary Python code. Tests supply only controlled synthetic acquisition callbacks.

FixtureBackfillAccounting accepts the existing caller-owned idle sqlite3 connection, full
FixturePolicy, complete Charge vector, scope, explicit attempt label, bookkeeping clock,
cancellation predicate, declared busy timeout and synthetic_window_dispatch unit basis.
There are no inferred/default allowance values. Its frozen inputs cannot be accidentally
reassigned during callback. SQLite connection configuration is checked again before
transactions. The native connection remains exclusively caller-owned and is never opened,
migrated, reset or closed by the adapter.

The only accounting-facade additions are bounded validated find_attempt and scope_attempts
read projections. They distinguish absent identity from corrupt/unavailable history; they
use the existing reconstruction limits, tables, event types and version1 serialization.
No new persistence schema, parallel ledger or W09/research accounting is introduced.

## Ordering and identity

1. Verify borrowed connection/PID/thread ownership before touching a filesystem lock.
2. Existing Ledger.exclusive takes its cooperative persistent sidecar lock and reloads.
3. Existing completed artifacts are hash/identity verified outside SQL; opt-in additionally
   requires matching scope/full immutable policy/request/reserve charge vector and successful
   uncancelled accounting. Missing legacy accounting is unavailable, never assumed zero.
4. Under a short BEGIN IMMEDIATE, validate history/policy and atomically reserve a NEW attempt
   plus intent. Only confirmed commit permits this caller to proceed to its synthetic callback.
   An existing attempt never causes another dispatch. Any reserved/intent/unknown scope attempt
   blocks a new one, without TTL, stealing or a fabricated quiescence assertion.
5. Invoke the existing acquisition callback with the exact native arguments, outside SQLite.
6. Under a new transaction, recheck original scope/request/attempt, policy, cancellation and
   history. Record success only for a returned typed acquisition result; this means dispatch
   returned, not that artifacts or provider history are scientifically qualified.
7. Only after confirmed settlement does the existing Ledger record normal completed progress.

Lock order is Ledger first, then short SQLite transaction. No SQLite transaction may wait
for a file lock or cover provider/artifact callback I/O. The caller must not independently
use the borrowed connection concurrently or leave a transaction open inside callback. The
adapter detects observed violations; it cannot forcibly preempt arbitrary callback work.

Request hashes bind provider/family/instrument and exact native base/quote/category/frequency,
period/start/end. Attempt IDs also bind scope and an explicitly supplied stable label.
No automatic new label/attempt, provider-period selection or campaign reset is performed.
Known terminal failure/cancellation can use another explicit label subject to the same full
policy/cap. Any prior success for the same request blocks dispatch when progress is missing,
regardless of label; normal verified completed progress is the sole skip path. No reconstruction
of missing success receipts or automatic re-fetch is added.

## Cancellation, uncertainty and reconciliation

Cancellation before reservation creates no debit. Once reserved/intent is committed, all
charges stay consumed by application accounting. Recognized cancellation before callback
or after its return records cancelled and suppresses progress publication; it grants no
refund and is not a claim that a provider was never contacted. An external cancellation or
history change during callback is checked at settlement. It cannot preempt a running callback.

Callback exceptions, termination and commit uncertainty never enter the old per-window
DataError splitting/continuation path. Dedicated fatal codes contain no callback text or
cause representation in progress. Exception display suppression is not clearing reachable
Python context or traceback frame locals. KeyboardInterrupt/BaseException is reconciled
best-effort and propagated; no arbitrary callback cancellation guarantee is claimed.

A committed unresolved intent blocks restart, including other progress files and new labels.
reconcile_uncertain performs only one-way existing unknown/unavailable events; no release,
refund, reset, expiry, no-send certification or owner-acknowledgment override exists. If a
marker cannot be persisted, the fatal exception exposes reconciliation_persisted=False;
retained unresolved intent remains blocking to participating callers. Commit acknowledgment
loss after terminal outcome never rewrites that outcome; scope history is marked unavailable.

Artifact-success/accounting-success/progress-publication are not one cross-store transaction.
A crash or Ledger replacement failure after successful dispatch prevents re-fetch and requires
external authoritative evidence/reconciliation before further use. No generic successful
recovery or restored-history authority is fabricated. Whole-store rollback, coordinated
history tampering, old binaries and external nonparticipating senders are not fenced here.

## Executed scope and bounds

Synthetic end-to-end tests reuse the existing native Bybit parser/ingestion/retention and
completed-window verifier, with injected public-format bytes and a temporary synthetic
storage identity/capacity. They do not lower production reserve checks or call any provider.
Other cases verify exact replay, changed labels after publication failure, missing/corrupt
history, absent policy, altered connection settings, cancellation, simultaneous processes,
same Ledger exclusion and kill/reopen before commit, after intent commit and during callback.
Lost acknowledgment is explicitly injected around native SQLite commit; it is not a power-loss
or actual billing experiment. Forced-kill cleanup avoids touching a multiprocessing Event
whose dead owner may have held an internal lock; interrupted development logs are retained.

Existing accounting event/body/table bounds remain. Request identity is capped at the same
8192-byte engineering magnitude. Caller-declared SQLite busy timeout bounds lock contention,
not total execution time, filesystem I/O or memory. Application window charges, in-memory
RequestBudget HTTP counters, raw artifact bytes and actual provider billing stay separate.
An HTTP transport-level hook and actual policy/account/host/period/retained-history decisions
remain prerequisites before any effectful durable provider-quota implementation.

No shared README/manual/build/Atlas or generated outputs are changed under the coordinating
owner's scope. This candidate-local record documents the inactive opt-in connection; normal
user setup/CLI remains unchanged. Full/private/release gates and native attestations remain
unrun. Independent review is available Codex (no authorized Claude route/tool/executable);
there is no installation, authentication workaround, source transfer or publication.

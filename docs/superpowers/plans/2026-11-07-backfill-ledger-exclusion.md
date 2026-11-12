# Cooperative whole-file backfill progress exclusion

This is a separate successor to preserved resume/I/O tree
7953dcde1759b3a3094dd4325d1dcde9a55c12f9 on base
3f7b23185c29b2542605bd41b9485016c2ef3e79. Its accounting sibling
b714462ff8e0e3d5f677e0421b09fdaecb59212c is not included. Original patches and
receipts stay unchanged; exact new inventory/checks/source review are separate.

```json
{
  "schema_version": 1,
  "title": "Cooperative whole-file backfill progress exclusion",
  "context": "W05/W02 closes the demonstrated lost-update race in existing v1 Ledger writers without assigning durable quota or acquisition authority. run_backfill is the sole production Ledger caller; record/save handle its split/failure/completion writes.",
  "assumptions": [
    {"statement": "Current supported backfill paths do not hold a SQLite transaction or storage admission lock around run_backfill.", "verified_by": "crypto_data_cmds backfill/acquire composition and source-only navigator review"},
    {"statement": "Cooperating current writers share one persistent sidecar per canonical progress path; external/legacy writers can ignore or replace it.", "verified_by": "All current record/save/run paths use Ledger.exclusive; no fencing/legacy cutover claim"}
  ],
  "alternatives_considered": ["Lock only save: rejected; stale cached decisions still discard updates or duplicate work.", "Merge stale windows automatically: rejected; conflicts and retained split topology need explicit verification.", "Use SQLite or the retirement lock: rejected; wrong authority/scope and unnecessary dependencies."],
  "pre_mortem": ["A nested save unlocks the outer run.", "Two processes lock different inodes after a sidecar unlink.", "A stale direct save overwrites another completed window.", "A child inherits the parent's lock authority or explicitly unlocks its shared descriptor."],
  "slices": [
    {"title": "Own reload through atomic replacement", "verify": "Scoped public lock/resume unit cases, lint and strict types", "expected": "Stable nonblocking sidecar, owned reload/preflight/decision, direct stale-write refusal and unique staging cleanup", "rollback": "Revert source only while all current writers are quiescent; retained JSONv1 remains readable", "status": "done"},
    {"title": "Exercise process contention and interruption", "verify": "Owned-process synthetic cases and affected resume/CLI/storage regression selection; independent exact-tree source review", "expected": "Contender refusal before callbacks, fresh reopen preserves windows, interruption cleans ownership without torn JSON", "rollback": "Keep sidecar files; do not delete active locks or reinterpret interrupted acquisition", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/superpowers/plans/2026-11-07-backfill-ledger-exclusion.md"],
  "out_of_scope": ["Provider/network calls or retained stores", "Durable quota", "ControlStore or accounting wiring", "Legacy-writer fencing/cutover", "Real sender quiescence", "Restore/power-loss durability", "Protected/full gates", "Shared docs/Atlas", "Transfers/publication"],
  "files": ["apps/alpha-cli/src/alpha_cli/_crypto_backfill.py", "tests/unit/test_crypto_backfill_lock.py", "tests/integration/test_crypto_backfill_lock_process.py"]
}
```

`Ledger.exclusive(refresh=True)` owns an executing run before its authoritative reload,
all requested completion/hash/retirement/identity preflight, deduplication/splitting,
synthetic-or-existing acquisition callbacks and progress replacement. A contender fails
immediately through LOCK_NB before callbacks; this is a bounded lock-acquisition attempt,
not a deadline on arbitrary callback work or total run length. It holds one file resource
for the whole run, including different requested windows. No new CLI or allowance policy.

`record` and `save` acquire the same lock outside an owning run and compare retained raw
bytes with their loaded baseline. Stale snapshots fail without overwrite or automatic
merge. Nested same-owner calls retain the outer lock. Ownership is bound to PID and
thread; inherited objects cannot mutate or explicitly unlock the parent's shared open-file
description. Forked children may retain descriptors and delay kernel lock release until
exit; no containment/quiescence promise follows. Close-on-exec does not close at fork.

The canonical resource resolves parent aliases and relative components. Leaf ledger/lock
symlinks, hardlinks and nonregular objects are rejected; checks compare open descriptors
with pathname identity. Persistent `.lock` sidecars are never unlinked by this code.
Directory/sidecar replacement by nonparticipants can invalidate ownership, which is checked
before callbacks and replacement; these checks do not eliminate an adversarial check/use
race, bind different copied/renamed ledger resources to one campaign, or prevent legacy
binaries ignoring the lock. No storage-root identity/admission decision is inferred.

Replacement uses unique temporary files and cleanup on failure/KeyboardInterrupt; JSONv1
and existing receipt/frame formats remain unchanged. Replace-before-acknowledgment failure
may leave the complete new file; reopen and verify retained evidence instead of assuming
rollback. No fsync/power-loss claim. Kill during a real external call could leave effects
without progress, and this slice cannot prove no send or authorize automatic refetch.
The existing unfinished-window semantics remain; synthetic kill fixtures contain no effects.
Progress JSON reads and callback work acquire no new byte/time cap; the predecessor's
explicit artifact-verification cap remains separate and unchanged.

Dry-run takes a read-only snapshot and creates no directory/sidecar, acquires no ownership,
and performs no verification/acquisition callbacks. It is not a serialized execution plan.
Actual production mutators are run_backfill split/failure/done → Ledger.record → save;
there are no other source callers of Ledger. Current supported backfill families avoid
event-capture ControlStore scope. No SQLite transaction or storage-admission lock is added
or held while waiting for progress ownership; LOCK_NB never waits. Existing storage admission
is for retirement/snapshot work, independent of this resource. Future callers introducing
nested locks must re-audit a consistent order; this slice grants no generic locking order.

Ordinary synthetic cases exercise stale instances/processes, contending distinct windows,
nested save, canonical aliases, hardlink/symlink/FIFO refusal, lock replacement, thread/fork
ownership, interrupted replace before/after publication, killed owner/reopen, cancellation
in preflight/acquire and dry-run non-effects. Existing resume/CLI tests retain receipt,
root, retirement, quality, raw/hash and split-child checks. All runtime fixtures use temp
paths and injected callbacks. Source review and focused tests are not live qualification.

README review: no change proposed; supported commands, storage admission and setup are
unchanged. This candidate-local plan records the new cooperative exclusion and its limits;
shared manual/build/Atlas files remain excluded under the coordinating owner's instruction.
Before publication, coordinating integration must reconcile actual main and exact-tree gates.
QuantPad stays excluded. No commit, transfer, provider access or publication in this slice.

Independent source review identified a same-object pre-acquisition thread race: losing
cleanup could clear another thread's ownership token. A deterministic failing regression
was saved, then cleanup was restricted to the exact token installed by that invocation.
Final exact-tree review/check results belong to the separate delivery receipt.

# Native stock fixture inspection (offline successor)

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

Canonical checklist: Library `libfile_181ac6079dcc8191b222b76c1f10bf17`, version 9,
W02 and T09/T10 require truthful interrupted/failed evidence tied to one attempt.
T07 restart continuation remains open: a checkpoint cannot restore the live owner or
its outside-pickle counters. This slice grants no continuation authority.

Base candidate tree: fb9095ecf29e405045fab9a672497941d65d96da, base commit
3f7b23185c29b2542605bd41b9485016c2ef3e79. Preserve that candidate unchanged.

1. Persist bounded, atomic advisory stage-attempt snapshots from the existing worker.
   Keep consume-before-spawn, native lifecycle and success receipt unchanged. Test native
   resume/cancel/exhaust/tamper with fresh synthetic inputs only.
2. Add an operator JSON inspection command using an existing read-only ControlStore
   snapshot and canonical event validation. Reject unsafe paths/identities and incomplete
   evidence; never load pickle, launch a process, take an owner lock or reset allowance.
   Test reopened inspection, wrong identity, missing/corrupt artifacts and no DB writes.
3. Independently review final delta and document the command/remaining requirements.

Verify only new public scoped tests and existing relevant public native checks, Ruff and
scoped types. Broad gates/private suite stay excluded and unverified under current task
restrictions. No shared generated outputs, ControlStore, frontend, science or accounting
edits. DAG: CLI consumes existing store/worker contracts; worker has no CLI dependency.
No market data, statistics, as-of or look-ahead behavior changes. Determinism: fixed
stage sequence and request digest; snapshots are advisory, not a ledger or spend cap.

README review: no change: this diagnostic remains explicitly unqualified synthetic
engineering, with its operator command documented in a dedicated new guide. Shared
README/CLAUDE/generated files are outside this successor's owned scope.

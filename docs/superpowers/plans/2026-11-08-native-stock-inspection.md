# Native stock fixture inspection (offline successor)

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

```json
{
  "schema_version": 1,
  "title": "Native stock fixture inspection (offline successor)",
  "context": "Canonical checklist W02 and T09/T10 require truthful interrupted/failed evidence tied to one attempt; this successor adds advisory stage-attempt snapshots and a read-only operator inspection command. T07 restart continuation stays open. Front block added 2026-11-13 during the plan status pass; every field restates this plan's own text. Implementation slices are marked done because the named code and tests exist in candidate a631e8e7; review slices stay pending unless the text records a review.",
  "assumptions": [
    {
      "statement": "A checkpoint cannot restore the live owner or its outside-pickle counters, so no continuation authority is granted.",
      "verified_by": "Plan text on T07 restart continuation."
    },
    {
      "statement": "Base candidate tree fb9095ec on base commit 3f7b2318 is preserved unchanged.",
      "verified_by": "Plan text 'Preserve that candidate unchanged'."
    }
  ],
  "alternatives_considered": [
    "Treating snapshots as a ledger or spend cap; rejected: snapshots are advisory only."
  ],
  "pre_mortem": [
    "Inspection could load pickle, launch a process, take an owner lock or reset allowance; the command must never do so.",
    "Unsafe paths/identities or incomplete evidence could be reported as valid; they must be rejected."
  ],
  "slices": [
    {
      "title": "Persist bounded atomic advisory stage-attempt snapshots",
      "verify": "Native resume/cancel/exhaust/tamper tests with fresh synthetic inputs",
      "expected": "Consume-before-spawn, native lifecycle and success receipt unchanged",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [],
      "status": "done"
    },
    {
      "title": "Operator JSON inspection command",
      "verify": "Reopened inspection, wrong identity, missing/corrupt artifacts and no-DB-write tests",
      "expected": "Read-only ControlStore snapshot and canonical event validation; unsafe input rejected",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [
        "apps/alpha-cli/src/alpha_cli/native_stock_inspect.py"
      ],
      "status": "done"
    },
    {
      "title": "Independent review and documentation of the command",
      "verify": "Independent review of the final delta; new public scoped tests, Ruff and scoped types",
      "expected": "Command and remaining requirements documented in a dedicated guide",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [
        "docs/operations/native-stock-inspection.md"
      ],
      "status": "pending"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/operations/native-stock-inspection.md"
  ],
  "out_of_scope": [
    "T07 continuation authority.",
    "ControlStore, frontend, science or accounting edits.",
    "Market data, statistics, as-of or look-ahead behavior changes.",
    "Broad/full or private gates, publication, transfers and installs.",
    "Shared generated outputs and shared README/CLAUDE documentation."
  ]
}
```

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

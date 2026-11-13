# Native stock snapshot validation prerequisite

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

```json
{
  "schema_version": 1,
  "title": "Native stock snapshot validation prerequisite",
  "context": "Canonical v9 W02/T10 requires truthful wrong/missing/changed artifact evidence; extract the existing exact validator into a bounded byte-snapshot API and add current-artifact-only validation to the read-only inspector. Front block added 2026-11-13 during the plan status pass; every field restates this plan's own text. Implementation slices are marked done because the named code and tests exist in candidate a631e8e7; review slices stay pending unless the text records a review.",
  "assumptions": [
    {
      "statement": "T07 cannot be implemented as cross-owner restart under the current contracts.",
      "verified_by": "Plan text: original PID/retained lock and outside-pickle guard are required."
    },
    {
      "statement": "Prior inspector successor ed0b58ee and its exports remain unchanged.",
      "verified_by": "Plan text."
    }
  ],
  "alternatives_considered": [
    "Borrowing the study-only rule_result schema or creating new resume/accounting authority; rejected, durable stock binding stays unavailable."
  ],
  "pre_mortem": [
    "Repeated reads could validate one generation and hash another; the wrapper reads each artifact once and hashes the same bytes.",
    "Advisory progress could be used to authorize or restore state; validation must not depend on it."
  ],
  "slices": [
    {
      "title": "Bounded byte-snapshot validator API",
      "verify": "Bad lengths/types/identity and repeated-read/mixed-generation regression tests",
      "expected": "One contract implementation; checkpoints never deserialized",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [],
      "status": "done"
    },
    {
      "title": "Current-artifact-only validation in the read-only inspector",
      "verify": "Guarded directory-FD read tests with canonical dispatch identity",
      "expected": "Legacy/failed runs without a success receipt unavailable; incomplete/mismatched success artifacts fail",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [
        "apps/alpha-cli/src/alpha_cli/native_stock_inspect.py"
      ],
      "status": "done"
    },
    {
      "title": "Focused synthetic tests, native success journey and independent review",
      "verify": "New focused synthetic tests and independent Codex review",
      "expected": "Frozen predecessor/successor trees and exact delta artifacts recorded",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [],
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
    "Worker, ControlStore and accounting changes.",
    "Market/as-of/statistical changes and live inference.",
    "Broad/full or private gates, publication, transfers and installs.",
    "Shared generated outputs and shared README/CLAUDE documentation."
  ]
}
```

Canonical v9 (Library libfile_181ac6079dcc8191b222b76c1f10bf17) W02/T10
requires truthful wrong/missing/changed artifact evidence. T07 cannot be implemented
as cross-owner restart under the current contracts: original PID/retained lock and
outside-pickle guard are required, and consumed invocation cannot be relaunched.

The prior inspector successor ed0b58ee32aa72b25aa5a50fdd281a1748d0cfbb and exports
remain unchanged. Stock finish validates bytes but does not persist a receipt hash:
rule_result is study-only; StockFixtureLaunch requires study=None. Do not borrow that
schema or create new resume/accounting authority. Durable stock binding stays unavailable.

1. Extract the existing exact validator into a bounded byte-snapshot API, retaining one
   contract implementation. The path wrapper reads each fixed artifact once, validates
   and hashes those same immutable bytes, never deserializing a checkpoint. Test bad
   lengths/types/identity and repeated-read/mixed-generation regression.
2. Add current-artifact-only validation to the read-only inspector using its guarded
   directory-FD reads and canonical dispatch identity. Legacy/failed runs without a
   success receipt remain unavailable; incomplete/mismatched success artifacts fail.
   Do not depend on advisory progress to authorize or restore anything.
3. Run new focused synthetic tests/native success journey and independent Codex review.
   Claude is unavailable via existing tool/session; no installation/auth change.

DAG: CLI reuses existing stock fixture contract; no worker/ControlStore/accounting
changes. No market/as-of/statistical changes. Synthetic fixture determinism is unchanged.
No shared generated outputs. README/CLAUDE no_change: this is an explicitly unqualified
operator diagnostic, described in its owned guide; broader shared docs are outside scope.
No full/private gates, transfer, publication or live inference. Frozen predecessor and
successor trees plus exact delta artifacts will be recorded outside the candidate.

# Retained-owner native result recovery

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

```json
{
  "schema_version": 1,
  "title": "Retained-owner native result recovery",
  "context": "Canonical v9 W02/T10 requires exact attempt-bound receipts; complete the existing owner→receipt→durable observation→artifact recovery workflow by persisting the stock receipt hash the finish step currently discards. Front block added 2026-11-13 during the plan status pass; every field restates this plan's own text. Implementation slices are marked done because the named code and tests exist in candidate a631e8e7; review slices stay pending unless the text records a review.",
  "assumptions": [
    {
      "statement": "The stock worker already stops after coding and resumes in the same child with the same outside-pickle guard.",
      "verified_by": "Plan text on the T07 boundary."
    },
    {
      "statement": "Legacy rows without the new observation remain readable and report unavailable.",
      "verified_by": "Plan slice 1 text."
    }
  ],
  "alternatives_considered": [
    "A new resume loop or mid-stage retry; rejected: complete the existing workflow, not a new loop."
  ],
  "pre_mortem": [
    "A byte match could be read as scientific, ownership or resume authority; it is only an owner-observed artifact fact.",
    "Duplicate dispatch, lost owner, stale profile or tampered bytes could be accepted; the journey test rejects each."
  ],
  "slices": [
    {
      "title": "Optional StockRDLoopObservationV1 in sealed native_outcome",
      "verify": "Validation tests for claim, consumption, start, exit 0 and POSIX cleanup",
      "expected": "Validated before commit; legacy rows readable and unavailable",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [],
      "status": "done"
    },
    {
      "title": "Match artifact-byte snapshot to the durable owner observation",
      "verify": "Selected current profile/request declarations required for completed recovery",
      "expected": "Byte match recorded as an owner-observed artifact fact only",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [],
      "status": "done"
    },
    {
      "title": "Fresh synthetic recovery journey and independent review",
      "verify": "Checkpoint stop, same-guard remaining stages, owner capture, new-process recovery; focused public tests",
      "expected": "Reservations and consumption unchanged; duplicate/lost-owner/stale/tampered cases rejected",
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
    "ControlStore/schema/ledger/reservation/refund/budget/state-transition changes.",
    "Worker continuation semantics, market/as-of/statistical logic, data, provider/model calls and installs.",
    "Broad/full or private gates, publication, transfers and installs.",
    "Shared generated outputs and shared README/CLAUDE documentation."
  ]
}
```

Canonical v9 W02/T10 (Library libfile_181ac6079dcc8191b222b76c1f10bf17) requires
exact attempt-bound receipts and rejection of changed artifacts. Preserve predecessor
7e643bab52be6fcf2bd8c9fc9b9f2b5dd5c35622 and every export.

T07 boundary: existing stock worker already stops after coding and uses native RDLoop.load
in the SAME child process with the SAME outside-pickle Effects guard, then completes three
remaining stages. Upstream step_n is a post-stage stop. BaseException closes the guard;
no additional midstage retry/resume exists. Original supervisor issuingPID/retainedlock
and once-consumed dispatch stay mandatory. Do not reopen cancelled guards or grant takeover.

The next real native workflow gap is owner-result persistence: finish already validates
stock receipt bytes, but currently discards their hash because stock.study=None. Complete
that existing owner→receipt→durable observation→artifact recovery workflow, not a new loop.

1. Add distinct optional StockRDLoopObservationV1 {schema,receipt_sha256} stock_result to
   existing sealed native_outcome. Freeze nested strings, detach journal copies, validate
   exact stock claim+consumption+start+exit0+POSIX cleanup and no rule observation/uncertainty.
   Validate before committing; legacy rows without it remain readable and unavailable.
2. Match the already validated artifact-byte snapshot to that durable owner observation;
   require selected current profile/request declarations for completed result recovery.
   A byte match is an owner-observed artifact fact, not scientific/ownership/resume authority.
3. Execute a fresh synthetic native checkpoint-stop→sameguard remainingstages→owner capture
   →newprocess recovery journey. Reject duplicate dispatch, lostowner, staleprofile, tampered
   exact bytes and malformed observations. Assert reservations/consumption remain unchanged.
   Run focused public tests, independent Codex review (existing Claude unavailable), exact
   tree/delta and complete dependency metadata. No broad/private gates.

No ControlStore/schema/ledger/reservation/refund/budget/state-transition changes. Only native
observation validation/persistence and its consumer change. No worker continuation semantics,
market/as-of/statistical logic, data, provider/model calls or installs. No source transfers,
publication or shared generated edits. README/CLAUDE no_change: dedicated owned operator guide
records this unqualified workflow; broad shared docs stay outside scope. Existing base→7e
cumulative patch f21b29747592e277ea0b485d4992d6eefe08a891f726f68516afa8c622192a23 is retained.

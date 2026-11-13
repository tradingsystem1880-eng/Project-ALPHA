# W09 invocation-local component observations

**Delivery state:** Completed

The bounded implementation, focused source review and scope decision are complete.
Normal final-tree qualification, delivery review and publication receipts determine
engineering delivery; this does not close native Packet4 parity or grant execution.

Continue the retained v1/v2 worker through its existing private `FitInvocation` seam.
Packet4 requires scientific/resource/evaluator adoption before native execution;
inert instrumentation and ordinary synthetic engineering qualification confer no such
authority. The earlier planning-only private exception did not cover this slice; the
separate owner-approved observation scope is recorded below.

```json
{
  "schema_version": 1,
  "title": "Observe retained W09 calls without admitting native execution",
  "context": "Add opt-in invocation-local observations and structural plan bindings while preserving worker computations, serialized results and ControlStore authority.",
  "assumptions": [
    {"statement": "Instrumentation is permitted before native policy adoption.", "verified_by": "feature-readiness-checklist-2026-10-27.md Packet4; existing private FitInvocation seam"},
    {"statement": "The delivered planning-only private absence exception does not cover execution observation behavior.", "verified_by": ".claude/agents/independent-reviewer.md W09 planning scope"}
  ],
  "alternatives_considered": [
    "New persistent v1/v2 artifacts: rejected to retain the serialization boundary.",
    "Reuse W11 graph classification: rejected because its reference recipes and component names differ."
  ],
  "pre_mortem": [
    "A prediction failure erases a successful fit: close the actual fit observation before predicting, and retain failed prediction separately.",
    "Invocation traces are mistaken for durable accounting: structural binding always denies admission, fitted-state verification and resource authority.",
    "Assembly becomes a learned fit: record a distinct assemble operation and preserve the fixed numerical recipe."
  ],
  "slices": [
    {"title": "Opt-in retained worker observations", "verify": "Worker focused synthetic observation tests", "expected": "Actual preprocessing, fit, prediction and assembly events preserve returns, failures, state and unchanged output bytes.", "rollback": "Remove opt-in instrumentation; retained computations remain intact.", "status": "done"},
    {"title": "Structural binding to existing W09 identities", "verify": "Editable unit tests for observation binding", "expected": "Reject unsupported, swapped, missing, duplicate, stale and crossfold observations; matching local observations confer no accounting or fitted-state authority.", "rollback": "Remove structural binding API; planning identities stay inert.", "status": "done"},
    {"title": "Focused verification and independent review", "verify": "Focused tests, lint, types, plan-check and independent source review", "expected": "Preserve durable candidate and evidence; resolve the exact private-suite/delivery scope before aggregate qualification or publication.", "rollback": "Retain patch and findings without bypass or publication.", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/work/2026-11-02-w09-component-observations.md", "README.md", "CLAUDE.md", "workers/qlib/README.md", "docs/BUILD-STATUS.md", ".claude/agents/independent-reviewer.md"],
  "out_of_scope": ["native admission or research execution", "real-data fits or acquisition", "resource charging/refund/retry/reuse policy", "new ledger or scheduler", "promotion", "worker serialization changes", "v3 computation or W11 graph changes", "protected test exposure", "Mac operations"]
}
```

The import DAG remains unchanged: workers never import alpha_cli or ControlStore.
The CLI may inspect portable diagnostic mappings but never imports the worker process.
Observation hashes bind exact row identities/values, request/fold context, and returned
state. Current source comparison is distinct from attestation of executing binaries.
No new look-ahead behavior, model, scientific policy, durable accounting or data access.

## Focused evidence and delivery qualification

Base is verified PR110 merge `2a6aa175d1b075eab8dff6b006a27c74e8c2a5e4`.
The initial seven new worker regressions failed against the prior schema3-only trace
guard/missing snapshot API. That red log and subsequent lint/type fixture corrections
are preserved; no prior failed result is credited as passing.

Current focused evidence: 64 root planning/binding tests; 40 covering worker tests across
the new v1/v2 observations, existing FitTrace, rank ensemble and W11 native-boundary
regressions (38 mocked/unit cases plus two unchanged real synthetic parity cases).
Ordinary real-worker synthetic fixtures compare every artifact byte with
observation off/on for both schemas; they do not acquire data or conduct research.
Actual portable snapshots from those fixtures also bind through the isolated root API,
with runtime dependency/fitted-state/accounting authority still unverified or false.
Targeted Ruff/mypy, 13 import contracts, manual byte limit and plan shape checks pass.
The existing Atlas generator refreshed source navigation. Independent source review
found missing prediction/assembly output shape checks. Four regressions reproduced the
defect before exact per-call output fields and nonmissing score links corrected it;
the red log is retained, all 64 root tests pass, and actual saved synthetic snapshots
still bind through the corrected validator. Independent re-review at native tree
`2f3f04fa24f81f23f7d3cf5d85e0a1a72eb886af6083207e0d4609c08ee416be`
found no remaining required source changes; it independently passed 64 root tests,
13 new mocked worker cases, targeted lint/types and whitespace checks. The earlier
independently passing real synthetic cases remain applicable to unchanged worker code.

No full aggregate, current-tree coverage claim, commit, push or PR is inferred from
focused checks. This focused source assessment is not formal delivery approval.

The owner separately approved an absence-only private-suite exception for this bounded
observation slice and necessary corrections, then normal commit/push, draft PR, ready
transition and merge of `feat/w09-component-observations` into `main` in
`tradingsystem1880-eng/Project-ALPHA`, after all public checks, the unchanged 93% floor
and final independent review pass. The corresponding reviewer scope record preserves
all exclusions, exact-tree gates, README evidence, normal attestations and Git guards.
Authorization provenance is retained privately. Present-suite failures and other
unrunnable checks still block. This is not a standing exception for later work.

Private coverage is UNVERIFIED, never PASS. Native admission/execution, real-data fits,
durable accounting/retry/refund/reuse/resource policy and promotion remain outside this
engineering slice. Exact final-tree qualification and delivery review are recorded by
the existing gate; the scoped absence exception does not fabricate any test pass.

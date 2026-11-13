# Packet4/W09 inert planning contracts

**Delivery state:** Completed

The bounded inert implementation is complete. Final engineering delivery requires the
normal exact-tree qualification/review records; this does not close native Packet4 parity.
This is the first engineering slice of [existing Packet4/W09](../../../../context/feature-readiness-checklist-2026-10-27.md#packet-4-govern-qlib-fits-and-prove-native-parity).
No charging, variant, ancestry, reuse or protected-release policy is assigned. The retained
v1/v2 worker computations and native rule route remain unchanged.

```json
{
  "schema_version": 1,
  "title": "Prepare inert W09 v1/v2 planning contracts",
  "context": "Bind declared existing-record and input references to a finite descriptive operation graph and complete first-party worker-source fingerprint; readiness remains blocked.",
  "assumptions": [
    {
      "statement": "Packet4 adoption is required before execution, not inert source preparation.",
      "verified_by": "feature-readiness-checklist-2026-10-27.md Packet4 and build-readiness-handoff-2026-10-27.md engineering work"
    },
    {
      "statement": "W09 v1/v2 computations differ from W11 schema3 provenance references.",
      "verified_by": "workers/qlib/src/alpha_qlib_worker/real.py _fold_model and ml_refit.py _validate_model"
    }
  ],
  "alternatives_considered": [
    "Enabling a native Qlib branch now: rejected while policy, panel and runtime mappings remain unverified.",
    "Reuse W11 schema3 as W09: rejected because the existing v1/v2 computation and protocol identities must be preserved."
  ],
  "pre_mortem": [
    "A finite fit count is mistaken for approved allowance: report descriptive operations only and keep policy/execution blocked.",
    "Rank code or a newly added dependency changes unnoticed: fingerprint the complete worker package, schemas, project and lock, rejecting unstable or linked input."
  ],
  "slices": [
    {
      "title": "Typed identities and finite fixed-recipe manifest",
      "verify": "uv run pytest -q tests/unit/test_ml_native_plan.py",
      "expected": "Canonical v1/v2 graph identities; reject unsupported recipes, operations and dependencies; assembly is not fitting.",
      "rollback": "Remove only new inert module and public tests; existing computation unchanged.",
      "status": "done"
    },
    {
      "title": "Dependency fingerprint and blocked readiness",
      "verify": "uv run pytest -q tests/unit/test_ml_native_plan.py",
      "expected": "Source/schema/lock changes invalidate identity; matching metadata cannot grant execution, reuse or qualification.",
      "rollback": "Remove new planning API only; no records or worker state exist.",
      "status": "done"
    },
    {
      "title": "Focused verification and independent source review",
      "verify": "Focused pure tests, Ruff, mypy, import contracts, plan-check and independent review",
      "expected": "Preserve focused evidence; fresh final-tree public gate, independent review and normal guards remain required for delivery.",
      "rollback": "Keep unique workspace source and review findings; no bypass or publication.",
      "status": "done"
    }
  ],
  "tier_impact": [
    "determinism"
  ],
  "docs_to_update": [
    "docs/superpowers/plans/2026-11-01-w09-planning-contracts.md",
    "README.md",
    "CLAUDE.md",
    "workers/qlib/README.md",
    "docs/BUILD-STATUS.md",
    ".claude/agents/independent-reviewer.md"
  ],
  "out_of_scope": [
    "native registration/admission",
    "native research/model-study execution",
    "real-data fitting",
    "resource-unit or variant policy",
    "reuse authorization",
    "real stores/data acquisition",
    "private test source access",
    "bootstrap-owner source/tests",
    "Qlib upgrades/model families",
    "Mac operations"
  ]
}
```

## Implemented boundary

`ml_native_plan.py` describes current `real._fold_model`: a train-only normalizer,
two label transforms and LightGBM fitting; v2 adds a train-only ridge fit and fixed
rank assembly. This finite graph is descriptive metadata, not approved spend units
or independent trials. Project/experiment/contract and request/panel/snapshot references
are declared, not authenticated or read from a real store. The API does not inspect
panel/evaluation contents or claim a validated worker request.

The supported first-party worker package, schemas, project and lock are fingerprinted,
including rank code and newly added dependencies. The read-only inventory covered 23
files on this checkout without importing the worker. W09 supplies a byte limit on both
snapshot passes. The existing `ml_refit._file_snapshot` helper now supports bounded,
unbuffered, chunked reads capped at remaining bytes, with precise oversize errors and
mutation rejection. Default callers retain their existing behavior and result identities.
These are source-read safeguards, not an approved native resource allowance.

Planning IDs are never completed operations or fitted-state evidence. The exact recipe
graph rejects completed-operation claims; readiness remains `BLOCKED`, with observed
operations unknown, fitted-state verification false, no approved resource units, and
execution/reuse/counterfactual/promotion flags false. No CLI command, native registry
entry, execution hook, ledger or scheduler is added. Policy, panel, runtime and parity
prerequisites remain unverified.

## Preparation evidence and integration

The source was prepared on reader merge `4e3ca30d49b6c403bc70c59bbad14f33b5bad720`.
Its 37,452-byte held patch (SHA256
`e2c4dcffeff6525be727e1dafa3262e44d7946ae6b96869e909ccc4e3a0769ba`)
reapplied byte-identically after verified bootstrap merge
`babd340e1dc02212242e8ce608949f99d6ab952c`. Shared README/manual/build guidance and
Atlas are reconciled on that base; bootstrap source/tests are not changed by this slice.

Focused mocked tests passed 42 cases, including empty/exact boundary, initial oversize
without content reads, growth beyond the bound without overread, mutation within the
bound, DAG/identity rejection and bounded worker-fingerprint calls. Ruff, mypy, plan
validation and all 13 import contracts passed during preparation. Independent source
review found no required changes and independently passed all 42 mocked tests, Ruff
and mypy. Corrected source-review binding:
`3628c15207cfe64165e9d4adbe8c9cc82389416c3c02ab43f5fa8c0cdc25ffac`.
These earlier source checks are not a final aggregate or delivery-review claim for the
integrated tree. Missing-module red evidence, intermediate failures, the initial
prechecked-size limitation and its corrected byte-bound regressions remain preserved
in task-local evidence.

The initial preparation handoff temporarily excluded fits and publication. That was
a bounded engineering handoff, not an owner ban on ordinary synthetic qualification.
The owner subsequently authorized existing synthetic engineering fixtures and normal
guarded publication of this inert slice after base/docs reconciliation and all required
checks/review. It grants no native research or real-data model execution.

## Task-scoped private-suite absence decision

On 2026-11-02 the owner explicitly approved an absence-only exception through delivery
for this bounded W09 planning slice and necessary corrections, with publication from
`feat/w09-planning-contracts` into `main` in `tradingsystem1880-eng/Project-ALPHA`.
The matching [reviewer scope record](../../../../../.claude/agents/independent-reviewer.md#w09-inert-planning-through-delivery-absence-exception--2026-11-02)
retains its narrow limits. Authorization provenance is retained privately.

Only documented absence of the authentic private suite is informational/nonblocking.
Private coverage remains UNVERIFIED, never PASS; no private source is read or edited.
Present-suite failures, other unrunnable required checks and software findings still
block. All public checks, unchanged 93% coverage floor/exclusions, fresh exact-tree
qualification, independent review, README evidence, attestation and Git guards remain
mandatory. This is task-scoped through necessary corrections, not a universal per-tree
exception or a waiver for later features. Research admission and scientific policy
remain separate from engineering delivery.

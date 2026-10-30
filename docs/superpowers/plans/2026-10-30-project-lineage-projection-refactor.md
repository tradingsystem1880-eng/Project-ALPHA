# Repository cleanup and bounded refactors

**Delivery state:** Expanded cloud-cleanup/refactor implementation; final assembled qualification and task-scoped private-suite decision remain pending. The prior passed checkpoint is preserved separately.

The repository-wide cleanup retains the bounded maintainability plan's behavior-preservation
constraint. It consolidates nested-history projection policy and removes the planned test-only
`changed_paths` wrapper. Stage ordering, errors, tail slicing, CLI arguments and comparison-base
selection remain intact. Current PR95/96 status and cloud ledger dispositions are reconciled in
the existing plans; physical Mac scope stays separately blocked. No product feature is removed.

```json
{
  "schema_version": 1,
  "title": "Repository cleanup and bounded refactors",
  "context": "Owner-directed repository-wide cleanup and behavior-preserving refactor. Consolidate project history policy, remove the existing foundation plan's redundant changed_paths wrapper, reconcile delivered PR95/96 status, and close observed cloud branch/path/operation preservation dispositions without guessing physical Mac state.",
  "assumptions": [
    {
      "statement": "Both collections apply the same history validation and tail policy, with distinct diagnostic labels.",
      "verified_by": "Source inspection at f847581f and baseline characterization tests."
    },
    {
      "statement": "The changed_paths wrapper has only three test callers; production uses comparison_context directly.",
      "verified_by": "Permitted source search and all 70 gate-component tests after removal."
    }
  ],
  "alternatives_considered": [
    "Keep the duplicate blocks; rejected because the same bounded-history policy could drift.",
    "Introduce a generic projection framework; rejected as unnecessary."
  ],
  "pre_mortem": [
    "Reordering collections could change which malformed projection fails first; preserve stage links before stage states.",
    "Replacing upstream truncation with local length alone could hide omitted history; retain the existing boolean OR.",
    "Current-delivery status could overwrite historical failures; relabel the old stage and append verified delivery receipts instead.",
    "Cloud inventory could be mistaken for the unavailable saved Mac ledger; state observation scope and retain every unresolved source.",
    "An absent-worker backend pass can hide a web environment propagation defect until the worker component is installed; qualify re-entry with the installed worker present."
  ],
  "slices": [
    {
      "title": "Characterize existing projection contracts",
      "verify": "uv run pytest -q tests/unit/test_web_project_lineage.py",
      "expected": "Both collection tails, upstream truncation, exact CLI argv and malformed-history precedence are preserved.",
      "rollback": "Remove only the new characterization test module.",
      "status": "done"
    },
    {
      "title": "Consolidate the two ordered history blocks",
      "verify": "uv run pytest -q tests/unit/test_web_project_lineage.py tests/integration/test_web_api_development.py",
      "expected": "Existing projection and HTTP/CLI behavior are unchanged.",
      "rollback": "Restore the two original blocks in project_detail.",
      "status": "done"
    },
    {
      "title": "Remove the planned test-only wrapper",
      "verify": "uv run pytest -q tests/unit/test_gate_components.py",
      "expected": "Canonical comparison_context retains committed/untracked paths and conservative unavailable-base selection.",
      "rollback": "Restore only the wrapper and its three former assertions.",
      "status": "done"
    },
    {
      "title": "Reconcile delivered status and cloud preservation ledger",
      "verify": "Direct Git/GitHub PR, CI, refs and worktree metadata; byte-identical tracked patch and preserved metadata after the predecessor move.",
      "expected": "PR95/96 current routing reflects merged delivery; every observed cloud item has a retained disposition; physical Mac scope remains unverified.",
      "rollback": "Restore current-status edits; move the retained predecessor back using its recorded paths. Preserve all evidence.",
      "status": "done"
    },
    {
      "title": "Repair failures found by installed-worker aggregate re-entry",
      "verify": "uv run python scripts/run_owned_test.py -- uv run pytest -q tests/unit/test_native_fixture_journal_independence.py tests/unit/test_web_invoke.py tests/integration/test_openapi_safe_routes.py",
      "expected": "PID marker creation is not mistaken for published contents; configured ML uv cache crosses both existing process boundaries; provider credentials remain command-scoped; both actual capability aliases return HTTP 200.",
      "rollback": "Restore only the test PID reader and ML cache-forwarding clause; retain all failed evidence.",
      "status": "done"
    },
    {
      "title": "Qualify the assembled candidate",
      "verify": "uv run python scripts/gate.py full",
      "expected": "Fresh exact-tree gate and independent review; absent private-suite coverage remains UNVERIFIED and needs its own owner decision.",
      "rollback": "Retain the unqualified patch separately; do not publish or merge.",
      "status": "pending"
    }
  ],
  "tier_impact": [
    "protected"
  ],
  "docs_to_update": [
    "docs/ARCHITECTURE.md",
    "docs/governance/README.md",
    "docs/BUILD-STATUS.md",
    "docs/operations/mac-workstation-handover-2026-10-19.md",
    "docs/superpowers/plans/2026-10-08-repository-hygiene.md",
    "docs/superpowers/plans/2026-10-26-native-rule-authority.md",
    "docs/superpowers/plans/2026-10-29-pr93-recovery-reconciliation.md",
    "docs/superpowers/plans/2026-10-30-project-lineage-projection-refactor.md",
    "docs/superpowers/plans/2026-10-26-mac-portability-qualification.md",
    "docs/superpowers/plans/2026-10-26-qlib-tabular-wave1.md",
    "docs/superpowers/plans/2026-10-26-qlib-w11-refit.md",
    "docs/superpowers/plans/2026-10-26-w05-research-integration.md",
    "README.md"
  ],
  "out_of_scope": [
    "Product features and statistical algorithms",
    "Storage and research authority",
    "Other Software Team control changes",
    "Active P2 fixes",
    "Physical Mac inspection and original saved-ledger recovery",
    "Remote branch/PR retirement without disposition",
    "Publication or merge before authorization"
  ],
  "files": [
    "apps/alpha-web/src/alpha_web/_development.py",
    "scripts/gate_components.py",
    "tests/unit/test_web_project_lineage.py",
    "tests/unit/test_gate_components.py",
    "docs/ARCHITECTURE.md",
    "docs/governance/README.md",
    "docs/BUILD-STATUS.md",
    "docs/operations/mac-workstation-handover-2026-10-19.md",
    "docs/superpowers/plans/2026-10-08-repository-hygiene.md",
    "docs/superpowers/plans/2026-10-26-native-rule-authority.md",
    "docs/superpowers/plans/2026-10-29-pr93-recovery-reconciliation.md",
    "docs/superpowers/plans/2026-10-30-project-lineage-projection-refactor.md",
    "docs/superpowers/plans/2026-10-26-mac-portability-qualification.md",
    "docs/superpowers/plans/2026-10-26-qlib-tabular-wave1.md",
    "docs/superpowers/plans/2026-10-26-qlib-w11-refit.md",
    "docs/superpowers/plans/2026-10-26-w05-research-integration.md",
    "architecture/atlas/generated/",
    "README.md",
    "apps/alpha-web/src/alpha_web/_catalog.py",
    "tests/unit/test_web_invoke.py",
    "tests/unit/test_native_fixture_journal_independence.py"
  ]
}
```

The 17 characterization cases passed on the unmodified adapter before refactoring. They are
behavior-preservation evidence, not a red-to-green bug fix. Final checks and review must bind
the actual assembled candidate; no earlier cleanup/private-suite exception transfers.


## Preserved checkpoint and expanded successor

The original 12-path candidate passed all six public components/49 steps with a valid stamp on
`01bf937e26c482d6d8a0af59fe4f761eb166d7ea59f7e86b99b37d834c28154e`. Its staged Git tree is
`d7a60d95d43a157ec081f5e79ad82a8bfbb0545c`; exact source, patch, gate/review receipts and verified
manifests are retained privately under `.alpha/state/project-cleanup-20261030/`. Formal review
was BLOCK solely on the absent private suite. These receipts remain historical evidence and do
not certify the expanded successor.

The remaining implementation follows the existing [foundation backlog](2026-10-26-native-rule-authority.md#foundation-stage-contract-and-handoff-icm-aligned-alpha-adaptation)
and [hygiene plan](2026-10-08-repository-hygiene.md#cloud-visible-ledger-reconciliation-2026-10-30).
A task-scoped absence-only decision through cleanup/refactor delivery, including necessary fixes,
has been requested and remains pending. It is not an exact-tree approval or permission to publish.
Keep private coverage UNVERIFIED and every real failure, gate and review requirement intact.
Finish source/docs/generated outputs and focused review before one final assembled gate.


## Aggregate re-entry findings and bounded repairs

The expanded `f1550eca` full gate failed in backend pytest: 3 failed, 6,711 passed, 61 skipped,
two subtests passed; the unchanged 93% floor was met at 93.01%. Its source, review, component
receipt, complete log and coverage file are sealed under
`.alpha/state/project-cleanup-20261030/failed-backend-f1550eca/`. No downstream component ran.

One cancellation control observed an existing but empty synthetic `payload.pid`; the fixture
writes contents after creating the file. A deterministic real-file regression reproduced
`int('')`. The test-only reader now waits for contents inside its existing five-second bound;
nonempty malformed contents still fail loudly. Cancellation order, exact-once journal assertions,
production supervisor, fixture fingerprint, owner budgets and accounting are unchanged. This
observed race does not establish a cause for any historical UNKNOWN owner stall.

Both automatic ML capability aliases returned 422 after the Qlib worker became installed. The
web-to-CLI environment dropped configured `UV_CACHE_DIR`, although the CLI-to-worker contract
already permits it; uv then failed cache initialization. The earlier pass preceded worker
installation. A cache-only diagnostic changed 422 to 200; regressions failed before the fix.
Web ML commands now preserve that nonsecret runtime location through the existing boundary.
Provider credential/auth-home routing, locked/no-sync worker launch and isolation remain intact.
Both real installed-worker aliases return HTTP 200 after the source fix. No P2 API/router,
OpenAPI or client-generation source was changed.

The PID regression passed after repair. The properly owned focused selection passed all 102
cases; scoped typing, lint and formatting passed. A prior direct focused invocation omitted the
required ownership wrapper and failed two process-group reaping checks; its log is retained
separately, and neither test nor production cleanup was changed to suppress those failures.
All source/docs/generated outputs and fresh review precede the next assembled full gate. The
requested absence-only decision remains TASK-scoped through cleanup/refactor delivery, including
necessary fixes; no exact-tree-only reapproval is inferred or requested.

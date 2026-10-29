```json
{
  "schema_version": 1,
  "title": "Fail closed on empty component gate definitions",
  "context": "Accepted main 99f2d472 exposes a fail-open edge: run_component can record an empty step definition as passed, and the receipt matcher accepts an empty expected/recorded list. Refuse to claim component or full-gate success when no verification step ran.",
  "assumptions": [
    {"statement": "Every registered component must run at least one verification step to earn a pass.", "verified_by": "All six accepted-main component definitions are populated; the empty-list path is exercised only by a focused regression."},
    {"statement": "A gate component failure must keep the existing failed receipt and stamp-clearing behavior.", "verified_by": "Existing component failure and interruption tests assert these receipt/stamp invariants."}
  ],
  "alternatives_considered": ["Do not treat an empty definition as a successful no-op or change any test selection, threshold, or private-suite policy."],
  "pre_mortem": [
    "A future optional component may intentionally have no checks; fail closed and require an explicit non-empty check before it can join the registered full gate.",
    "A stale or externally written empty passed receipt may bypass component execution; reject empty expectations in the exact receipt matcher too."
  ],
  "slices": [
    {"title": "Reject empty component definitions and receipts", "verify": "pytest -q -p no:cacheprovider tests/unit/test_gate_components.py", "expected": "Empty component execution fails with a failed receipt, and empty receipts cannot validate or produce a full stamp; existing interruption and tree-stability protections remain unchanged.", "rollback": "Revert the gate component and focused unit-test changes.", "files": ["scripts/gate_components.py", "tests/unit/test_gate_components.py"], "status": "done"},
    {"title": "Document the fail-closed gate contract", "verify": "python scripts/gate.py plan-check docs/superpowers/plans/2026-10-22-empty-component-gate.md", "expected": "The operating manual and append-only build record describe the empty-definition failure; no aggregate gate or application-authority claim is implied.", "rollback": "Revert the manual and build-status additions with this candidate.", "files": ["CLAUDE.md", "docs/BUILD-STATUS.md"], "status": "done"}
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["CLAUDE.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["Quantification, architecture DAG, look-ahead, determinism, or application authority", "Private holdout contents or evaluator policy", "Installs, commits, publication, merges, or changes to existing worktrees"]
}
```

**Current status — 2026-10-22:** Implementation candidate on isolated task branch from exact accepted main `99f2d472dd4511b446e1198ae80201e7207d089d`.

**Delivery state:** Implementation and bounded checks complete; candidate is uncommitted; aggregate gate remains outstanding. An independent exact-tree review found no actionable issues and did not run tests.

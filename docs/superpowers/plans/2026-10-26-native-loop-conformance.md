```json
{
  "schema_version": 1,
  "title": "Pinned native loop conformance",
  "context": "Dev-only real LoopBase extension on the preserved lifecycle candidate; no production activation.",
  "assumptions": [
    {"statement": "The supplied complete source is pinned and trusted after hashing.", "verified_by": "source_pin.verify_source and imported-source receipts"},
    {"statement": "Resume is limited to the same live fixture owner.", "verified_by": "explicit native resume/cancellation probes"}
  ],
  "alternatives_considered": ["Stock RDLoop, copied scheduler fragments and production dispatch are excluded by the authorized scope."],
  "pre_mortem": ["Post-effect step_n could be mistaken for admission authority.", "Cancelled in-memory state could be mistaken for a successful checkpoint.", "A native import could inherit credentials or reach a provider backend."],
  "slices": [
    {"title": "Pinned isolated imports", "verify": "uv sync --locked --project workers/rdagent", "expected": "Only the isolated lock is installed; upstream imports execute in a sanitized subprocess.", "rollback": "Remove the development worker project.", "status": "done"},
    {"title": "Native stages and continuation", "verify": "ALPHA_RDAGENT_SOURCE=<pinned-source> pytest -q tests/unit/test_native_loop_conformance.py", "expected": "Explicit public native probes pass without provider or data effects.", "rollback": "Remove the worker and its public tests.", "status": "done"},
    {"title": "Exact evidence and independent review", "verify": "Scoped ruff/mypy, lint-imports, explicit foundation/native tests, fresh parent-commissioned review", "expected": "Evidence binds the exact candidate; remaining release limits are explicit.", "rollback": "Keep the preserved lifecycle candidate and reject this descendant.", "status": "in_progress"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["CLAUDE.md", "docs/BUILD-STATUS.md", "workers/rdagent/README.md"],
  "out_of_scope": ["Production native dispatch", "ControlStore accounting integration", "Cross-owner recovery", "Scientific admission", "Full gate and commits"],
  "files": ["workers/rdagent", "tests/unit/test_native_loop_conformance.py"]
}
```

# Pinned native loop conformance

Status: development implementation complete; fresh independent review pending.

Baseline: staged tree `9353241401d9e409d92accd7dd676c2c156186ed` on
`e635e6cb5bc7b9fa688dc524998d7fe1ff8eebdc`. Preserve the prior lifecycle candidate.

1. Establish an isolated Python 3.12 dependency lock for the pinned upstream LoopBase import
   closure. Verify source bytes before importing; sanitize HOME/environment and use an ephemeral
   signing key. Test actual imports in a separate fixture process.
2. Subclass actual LoopBase with LoopMeta and fixed Scenario/Experiment operators. Exercise the
   five native stage shapes and explicit synthetic feedback labels/metrics through native run,
   dump and load. Verify effects are bounded before operators execute.
3. Exercise same-live-owner checkpoint continuation, concurrent/stale rejection and cancellation
   with task quiescence. Preserve failure receipts, run explicit public tests and import checks,
   freeze exact diff and request fresh independent review through the parent.

No package DAG changes, real datasets, estimator changes or seed changes. This adds only a
development worker and tests; no production route imports or invokes it. No commits or full gate
are authorized. ALPHA retains admission, budgets, exposure, execution, economics, evidence and
approval authority. Native checkpoint state is never an authority record. Cross-owner recovery,
owner-death containment and hostile-code isolation remain unqualified.

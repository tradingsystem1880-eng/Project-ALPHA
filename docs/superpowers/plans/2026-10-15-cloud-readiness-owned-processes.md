```json
{
  "schema_version": 1,
  "title": "Make cloud test ownership and synthetic fixtures reliable",
  "context": "Unchanged main837e198 produced fourteen backend failures and one dialog teardown failure in this cloud runtime. Repair execution ownership and fixture lifecycle without changing production proxy/cancellation behavior or acceptance thresholds.",
  "assumptions": [{"statement": "A separate Linux subreaper may wait only for its own command and adopted descendants.", "verified_by": "Dedicated ancestor diagnostic actually reaped eight children; all eight cancellation tests plus menu control passed."}, {"statement": "Proxy isolation belongs in the synthetic urllib opener.", "verified_by": "All five redirect cases passed with test-only ProxyHandler({}); production code uses urllib."}],
  "alternatives_considered": ["Do not ignore zombies, unset global proxies, swallow warnings/dialog errors, install dependencies, or add a reaper inside application/pytest."],
  "pre_mortem": ["A global reaper steals unrelated child exit statuses: use a separate process owning one command subtree and verify unrelated sibling wait.", "A supervisor hides failed exits or leaks children on signals: verify exact exit propagation, signal forwarding and actual PID disappearance.", "A browser test observes challenge before confirm completes: await acceptance and performed action, preserving rejection."],
  "slices": [{"title": "Own Linux pytest descendants at the gate process boundary", "verify": "uv run pytest -q tests/unit/test_gate_process_supervisor.py tests/unit/test_gate_components.py", "expected": "Failing-first ownership, exit, signal, isolation and portable pass-through tests pass; original pytest argv and thresholds unchanged.", "rollback": "Remove supervisor and gate runner integration.", "status": "done"}, {"title": "Isolate synthetic transport and finish owned test resources", "verify": "Focused Tiingo/web finalizer tests; deterministic dialog acceptance/rejection tests; repeated browser test with unique output directory.", "expected": "Synthetic requests cannot inherit proxy routing; stdout is closed; dialog acceptance and action completion are awaited with errors propagated.", "rollback": "Revert fixture/helper edits.", "status": "done"}, {"title": "Document runtime contract, independently review and validate exact candidate", "verify": "plan-check, full gate on unchanged final tree, independent review bound to final tree/diff hashes", "expected": "All checks retain existing acceptance criteria; complete evidence indexed; no publication.", "rollback": "Revert candidate branch changes.", "status": "in_progress"}],
  "tier_impact": ["protected"],
  "docs_to_update": ["README.md", "CLAUDE.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["Production application cancellation and proxy semantics", "Quant/DAG/look-ahead/determinism behavior", "Private test inspection", "Dependencies and account/security settings", "Publication or merge"]
}
```

**Delivery state:** Implementation candidate; exact-tree review and full acceptance are recorded separately.

No quant source, architecture edges, look-ahead rules or research determinism changes. Original evidence: `.alpha/state/cloud-validation-837e198/index.json`. Candidate red/green logs and review receipts: `.alpha/state/cloud-readiness-candidate/`.

# Merge-triggered README maintenance

**Delivery state:** Implementation in progress; not published or active.

```json
{
  "schema_version": 1,
  "title": "Merge-triggered README maintenance",
  "context": "Keep a bounded plain-language reader guide grounded in merged code without changing setup or product authority.",
  "assumptions": [{"statement": "Existing CI and Git guards remain authoritative.", "verified_by": "AGENTS.md, CLAUDE.md, scripts/git_guard.py and .github/workflows/ci.yml"}],
  "alternatives_considered": ["Direct model edits to main rejected: use a guarded docs PR.", "Reuse advisory codex_bridge rejected: it intentionally tolerates inference failure."],
  "pre_mortem": ["Missing authentication must fail visibly, never appear current.", "Rapid merges must not publish stale explanations.", "Model output may invent capabilities: bounded evidence and normal review remain necessary."],
  "slices": [
    {"title": "Bounded context and output validation", "verify": "pytest tests/unit/test_readme_maintenance.py", "expected": "Only the owned README section can change; malformed output fails closed.", "rollback": "Remove the new helper and tests.", "status": "done"},
    {"title": "Read-only generation and guarded PR delivery", "verify": "Workflow contract tests and independent review", "expected": "No-op, duplicate, stale, failure and self-trigger cases remain bounded; existing CI runs explicitly.", "rollback": "Remove the README workflow and CI manual trigger.", "status": "done"},
    {"title": "Documentation and exact-tree qualification", "verify": "Full gate and tree-bound independent review", "expected": "Honest activation/authentication status and publication payload; no bypass.", "rollback": "Revert this feature through normal review.", "status": "pending"}
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["CLAUDE.md", "docs/BUILD-STATUS.md", "README.md", "docs/operations/readme-maintenance.md"],
  "out_of_scope": ["Trading", "Private test access", "Credentials or security setting changes", "Automatic approval or bypass merging", "Delivery-marker branch"],
  "files": ["scripts/readme_maintenance.py", "tests/unit/test_readme_maintenance.py", ".github/workflows/readme-maintenance.yml", ".github/readme/schema.json"]
}
```

No data/strategy/import DAG changes; no look-ahead or seed semantics change. Inference is advisory
and never establishes empirical or paper readiness. Existing technical material stays outside the
owned section; detected technical drift blocks publication for a normal human-authored correction.

Activation requires an authorized Actions API key and the existing repository policy allowing
workflow-created PRs. No settings or credentials are changed by this implementation. The absent
private review suite is a separate publication blocker for the protected workflow implementation;
prior delivery exceptions are outside this task's scope.

## Public implementation evidence

The focused README suite passes **28 tests**, including a real subprocess transfer-validation
smoke in a directory with no checkout. Ruff, strict mypy, actionlint 1.7.7 and FeaturePlan validation
pass. Independent review of the earlier candidate found no software defects and blocked on the
absent required private suite. A subsequent isolation improvement separates evidence preparation,
checkout-free inference, and guarded delivery into three jobs in the same workflow. The earlier
full-gate run was deliberately interrupted while backend coverage ran; its lint/type/import and
Semgrep scan/contract steps passed, but it is not aggregate evidence for this revised candidate.
The revised exact-tree gate and fresh independent review are required before any actual commit.
No workflow, key, security setting or hosted trigger has been activated.

Source baseline advanced to PR100 main `2a8aa50b5669f6645ecfb5c0e0e23fb8f932bf82`. Its five completion-marker documents are preserved; unfinished Mac, storage, cleanup and product acceptance scopes stay open. The pre-PR100 qualification was superseded when main advanced.

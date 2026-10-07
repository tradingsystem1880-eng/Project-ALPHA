# Workflow UI redesign and full-stack repair

**Delivery state:** Implemented and independently reviewed. Offline component checks passed;
current aggregate acceptance is checked with `uv run python scripts/gate.py check --tier full`.
Live-provider and physical-owner acceptance limits are recorded in the UI audit.

```json
{
  "schema_version": 1,
  "title": "Workflow UI redesign and full-stack repair",
  "context": "Replace crowded terminal navigation with workflow pages and test real browser-to-CLI journeys. Preserve unrelated benchmark work.",
  "assumptions": [
    {"statement": "Existing CLI authority and research safeguards remain authoritative", "verified_by": "API regression tests and import checks"},
    {"statement": "Mutating browser checks use an isolated disposable store", "verified_by": "test backend environment and process provenance"}
  ],
  "alternatives_considered": ["Retaining the terminal layout was rejected by the owner in favour of workflow pages"],
  "pre_mortem": ["Mocked API tests can hide integration defects; add real backend journeys", "Navigation migration can orphan capabilities; inventory every registered pane and dock", "Unavailable providers or Touch ID must be reported as unverified rather than simulated success"],
  "slices": [
    {"title": "Navigation model and capability inventory", "verify": "npm test -- workflowModel", "expected": "Every existing pane remains reachable", "rollback": "Revert workflow model", "status": "done"},
    {"title": "Workflow shell and persistent context", "verify": "npm run build and Playwright navigation checks", "expected": "Full-width pages, deep links and history work", "rollback": "Restore prior App shell", "status": "done"},
    {"title": "Shared asset selector and form repairs", "verify": "Playwright real asset and form journeys", "expected": "Inventory-backed selection and honest empty states", "rollback": "Revert selector changes", "status": "done"},
    {"title": "Real backend audit and regression repairs", "verify": "Browser journeys and targeted Python integration tests", "expected": "Recorded per-function results and reproducing regressions", "rollback": "Revert each isolated repair", "status": "done"},
    {"title": "Independent review, documentation and final gate", "verify": "uv run python scripts/gate.py full", "expected": "Exact-tree verification with unavailable checks explicitly recorded", "rollback": "Revert UI change only", "status": "done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["CLAUDE.md", "docs/BUILD-STATUS.md", "apps/alpha-web/frontend/README.md", "docs/audit/2026-09-29-workflow-ui.md"],
  "out_of_scope": ["New trading authority", "Numerical algorithm changes", "Owner record mutation during testing", "Benchmark changes"],
  "files": ["apps/alpha-web/", "tests/integration/", "tests/unit/test_web_ml.py", "scripts/run_playwright_backend.py", "docs/", "CLAUDE.md", ".claude/rules/alpha-web.md"]
}
```

Implementation uses small verified slices. No DAG, point-in-time, seed or numerical changes are
intended. Mutations remain behind existing CLI and owner-auth seams. Registry coverage, browser
navigation and actual persisted results are separate acceptance checks.

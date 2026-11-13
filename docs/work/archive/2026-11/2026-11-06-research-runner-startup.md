# Research runner startup boundary

**Delivery state:** Completed — merged via PRs #118/#119

**Historical delivery state (as first recorded):** Implemented; prior local full gate passed; merged-main delivery pending.

```json
{
  "schema_version": 1,
  "title": "Research runner startup boundary",
  "context": "Canonical covered parallel tests miss process readiness before SIGTERM. Fresh imports on unchanged qualified UI baseline load NumPy, SciPy, Polars and validation before the process-only run_child utility can start. Localize research-only dependencies without changing supervision, deadlines, formulas or receipt verification.",
  "assumptions": [{"statement": "The unchanged baseline shares this startup dependency graph.", "verified_by": "Identical research_execution.py bytes and five covered fresh-process baseline probes, each over the original five-second readiness budget."}],
  "alternatives_considered": ["Increasing readiness budgets weakens the regression and is excluded.", "Changing the stdlib-only owned-test wrapper has no demonstrated cause."],
  "pre_mortem": ["Moving imports could bypass a verification path or change monkeypatch targets.", "Other canonical failures may have independent causes."],
  "slices": [
    {"title": "Isolate process-only import boundary", "verify": "uv run pytest -q tests/unit/test_research_execution_import_boundary.py", "expected": "Fresh run_child import excludes unused analysis packages; original test fails first.", "rollback": "Restore research_execution.py imports.", "status": "done"},
    {"title": "Preserve research behavior and qualify", "verify": "Owned research execution and process supervisor tests; import contracts; canonical full gate", "expected": "Existing receipt, cleanup and fingerprint assertions pass unchanged, followed by exact-tree qualification and independent review.", "rollback": "Restore localized imports and the test patch target together.", "status": "in_progress"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["CLAUDE.md", "docs/BUILD-STATUS.md", "README.md"],
  "out_of_scope": ["Deadline increases", "Statistical changes", "Changing admission authority", "Unproven chart fixes"],
  "files": ["apps/alpha-cli/src/alpha_cli/research_execution.py", "tests/unit/test_research_execution.py", "tests/unit/test_research_execution_import_boundary.py"]
}
```

The import boundary test is structural, not a host-dependent timing assertion. Covered
parallel probes retain raw elapsed values outside the repository. A changed source file
legitimately changes existing execution fingerprints and controller hashes; their computation
and verification remain intact. No data, as-of, seed, strategy or statistical formula changes.
The separate detached UI baseline and original failure receipts remain preserved. A passing
focused test cannot establish that the independent half-second child marker or browser canvas
failure is fixed. Their investigation and aggregate qualification remain separate.

Focused covering checks passed: 71 research execution/import-boundary/process-supervisor cases
under the required process owner, Ruff check/format, and all 13 import contracts. No original
assertion or budget was relaxed. The rule-specification test patches its actual validation-module
function after localization; its original six acceptance/rejection cases remain intact. README
already describes the card, setup and limits accurately; this internal startup fix needs no
new user-facing claim. Independent final-tree review and full qualification remain pending.

The prior combined candidate tree `6379c8fbc5a12971d5024fd196b75ea231b130ee` subsequently
passed all six canonical components. The original five-second readiness assertion and separate
half-second supervisor test were unchanged. The half-second failure cause remains unresolved;
it did not reproduce in that successful backend run. UI PR118 is now merged on main
`8db344908f0530a03ed238c69bd9c1a40bf00afc` with the identical qualified base tree.
Source code transfers unchanged; current delivery bindings/checks and publication remain pending.

# W05 opt-in daily acquisition budget

**Delivery state:** Completed within the focused offline scope; full gate and publication not run.

```json
{
  "schema_version": 1,
  "title": "W05 opt-in daily acquisition budget",
  "context": "Bound a future separately approved keyless daily capture without changing PR92 or the reviewed timezone candidate.",
  "assumptions": [
    {"statement": "HTTP attempt and application-body budgets are enforceable through the existing transport.", "verified_by": "Synthetic real-handler tests; socket and hidden-buffer traffic explicitly excluded."}
  ],
  "alternatives_considered": ["Reuse the existing 100-page ceiling alone: insufficient for a two-attempt approval.", "Generic network framework: unnecessary scope expansion."],
  "pre_mortem": ["Redirects or retries silently exceed a page counter.", "An interrupted or partial capture is mislabeled complete."],
  "slices": [
    {"title": "Shared opt-in transport budget", "verify": "Explicit public test_crypto_request_budget.py tests", "expected": "Attempts and observed body reads stay within declared caps; defaults preserved", "rollback": "Do not enable strict mode; retain default path", "status": "done"},
    {"title": "Daily REST CLI propagation", "verify": "Synthetic CLI pagination and publication tests", "expected": "One budget spans pages; unsupported scopes fail before storage", "rollback": "Remove optional CLI exposure without changing stored artifacts", "status": "done"},
    {"title": "Focused qualification and independent review", "verify": "Public regressions, focused Ruff/mypy, import contracts, plan validation, independent source review", "expected": "Preserved exact candidate identity and honest qualification limits", "rollback": "Keep unpublished isolated candidate and receipts", "status": "done"}
  ],
  "tier_impact": [],
  "docs_to_update": ["CLAUDE.md", ".claude/rules/alpha-data.md", "docs/BUILD-STATUS.md", "docs/operations/bounded-research-workflow.md"],
  "out_of_scope": ["Market-data acquisition", "Credentials and storage changes", "Protected data", "Full gate", "Commit or publication", "Research acceptance"],
  "files": ["packages/alpha-data/src/alpha_data/crypto/providers/_wire.py", "packages/alpha-data/src/alpha_data/crypto/providers/binance.py", "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "tests/unit/test_crypto_request_budget.py"]
}
```

Scope: preserve PR92 and the independently reviewed UTC-cutoff fix in an isolated candidate.
No acquisition, installation, publication, full gate or changes to storage configuration.

1. Add one invocation budget at the existing transport boundary. Preserve ordinary defaults;
   strict mode charges attempts before open, refuses redirects, counts body reads and aborts
   unknown interrupted reads. Verify synthetic transport errors, retries, caps and cleanup.
2. Propagate the same budget through Binance daily REST pagination and the existing CLI.
   Reject unsupported scopes before storage. Verify real-handler synthetic CLI publication and
   nonpublication, repeated pages, partial responses and exhausted budgets.
3. Run explicit public regressions, focused typing/lint, independent review and fix/retest findings.
   Preserve patch, exact tree and receipts in the existing W05 container.

No numeric research semantics, dependencies, dataset schemas or import-layer permissions change.
Budgeting does not establish historical availability, full-window coverage or research authority.

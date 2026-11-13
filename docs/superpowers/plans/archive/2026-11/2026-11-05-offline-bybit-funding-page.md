# Offline request-bound Bybit funding page

**Delivery state:** Completed — merged via PR #117

**Historical delivery state (as first recorded):** Focused offline implementation and review complete; full qualification not run. No publication.

```json
{
  "schema_version": 1,
  "title": "Offline request-bound Bybit funding page",
  "context": "One W05 funding-page contract on main 5a0d64ae6e04dad1d7fb31cb02ee798a314c9bff, tree b795de4e9611035aa9c725a2604bf3bcf038f414; preserve existing native parser and acquisition surfaces.",
  "assumptions": [
    {"statement": "Funding identity must match the exact request and settlements cannot exceed its knowledge cutoff.", "verified_by": "Ordinary synthetic page and plan regressions."},
    {"statement": "The existing fetch path refuses full bounded funding pages.", "verified_by": "Mocked fetch full-page refusal regression."}
  ],
  "alternatives_considered": ["Modify legacy parser schema: rejected to preserve old readers.", "Add pagination, durable quotas or providers: separate slices."],
  "pre_mortem": ["A foreign instrument is admitted under the requested identity.", "A future settlement is silently filtered or labelled historically available.", "A short page is mistaken for complete history."],
  "slices": [
    {"title": "Pure page validation and existing plan binding", "verify": "Explicit ordinary synthetic funding unit cases", "expected": "Exact identity, inclusive bounds and future cutoff refusal with unchanged legacy frames", "rollback": "Restore legacy funding parser binding; retained receipts and reader schemas unchanged", "status": "done"},
    {"title": "Focused compatibility and independent review", "verify": "Bybit, backfill and native acquisition public regressions; Ruff, mypy and import contracts", "expected": "Report actual checks and limits without live or full-gate qualification claims", "rollback": "Keep isolated unpublished candidate and failure evidence", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["CLAUDE.md", "docs/operations/research-platform-contracts.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["Provider calls", "Credentials", "Protected test contents", "Dependencies", "Publication", "Historical coverage qualification", "Pagination", "Durable quota accounting", "Storage migrations", "Qlib defaults", "QuantPad"],
  "files": ["packages/alpha-data/src/alpha_data/crypto/providers/bybit.py", "apps/alpha-cli/src/alpha_cli/_crypto_acquisition.py", "tests/unit/test_bybit_funding_page.py"]
}
```

Add `parse_funding_page` around unchanged `parse_funding_history`; bind it through
the existing funding acquisition plan. The wrapper returns identical columns and
values, retains native signed rates and irregular settlement intervals, and adds
no availability timestamp. Its 8 MiB input ceiling and 200-row ceiling are finite
application bounds, not an OS memory limit. Empty or conflicting pages remain errors.
The existing fetch layer retains full bounded-page refusal; no pagination is added.

No import-DAG, receipt/hash, snapshot, catalog, calendar, label, seed or rights change.
Settlement time does not prove historical publication time. Neither a valid page
nor a short response establishes complete coverage, rights or research admission.
Providers remain unqualified; QuantPad remains excluded.

The future-poison check and deliberately leaky legacy-parser control live in an
ordinary unit file with the `bias_guard` marker. Existing protected test contents
were not accessed or changed. Full-gate/private-suite evidence is not inferred.

README review: no_change. This narrows validation within an already documented
native acquisition path, adds no user command or setup, and establishes no new
provider readiness; detailed semantics belong in the existing query contracts.

Focused evidence: the initial new test collection failed because the additive function
did not yet exist. After implementation, 21 new synthetic cases passed. The covering
Bybit/backfill/native-acquisition/ingestion/snapshot-query selection passed 143 cases.
Independent read-only source review found no blocking defect and suggested three
compatibility cases; all 24 final funding cases passed after adding them. Focused
Ruff check/format and strict mypy passed for the three Python files; all 13 import
contracts held. The initial mypy run reported 14 errors in new test helpers, which
were corrected without changing production behavior. Plan validation passed.

Verification reused the installed Python 3.12 environment at
`/workspace/Project-ALPHA/.venv` with isolated-checkout source directories prepended
to `sys.path`; no dependencies were installed or changed. Explicit public test paths
only were selected. The canonical full gate, aggregate coverage, protected-suite
checks, live provider qualification and publication were not run. No absence-only
exception is inherited from PR113/114. Rollback changes only the new wrapper/binding;
existing artifacts require no migration and their legacy readers remain available.

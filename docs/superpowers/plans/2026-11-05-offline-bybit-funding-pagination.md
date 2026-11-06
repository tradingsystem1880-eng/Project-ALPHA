# Offline Bybit funding backward progression

**Delivery state:** Focused offline implementation and source review complete. No live integration or publication.

```json
{
  "schema_version": 1,
  "title": "Offline Bybit funding backward progression",
  "context": "Successor to preserved single-page content 59abb43c5f8bfed2f66ceecd1d8b10f7fe59fca0adeeb0a1b366aa9acc826aa2 on main 5a0d64ae6e04dad1d7fb31cb02ee798a314c9bff.",
  "assumptions": [
    {"statement": "Inclusive upper bounds require oldest settlement minus one millisecond for backward progress.", "verified_by": "Synthetic request-bound page sequence tests."},
    {"statement": "A pure callback collector can be useful without enabling production acquisition.", "verified_by": "No transport, storage or CLI integration; existing full-page refusal regression retained."}
  ],
  "alternatives_considered": ["Replace production full-page refusal: rejected until raw retention and acquisition safeguards exist.", "Add a scheduler or durable cursor: out of scope."],
  "pre_mortem": ["A repeated boundary loops or duplicates observations.", "A short page is mislabelled complete.", "Callback allocation is mistaken for transport-budget enforcement."],
  "slices": [
    {"title": "Pure finite collector and synthetic failure cases", "verify": "Explicit test_bybit_funding_pagination.py", "expected": "Strict backward progress, identity and clock validation, bounded calls and accepted bytes", "rollback": "Remove unused collector; production acquisition unchanged", "status": "done"},
    {"title": "Compatibility checks and independent review", "verify": "Funding page, Bybit/backfill/native acquisition regressions; lint/types/import/plan checks", "expected": "Record fresh counts and preserve predecessor evidence separately", "rollback": "Retain predecessor without publication", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["CLAUDE.md", "docs/operations/research-platform-contracts.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["Provider calls", "Credentials", "Dependencies", "Protected contents", "Full/Atlas/preflight gates", "Persistence", "Raw retention", "Production integration", "Publication"],
  "files": ["packages/alpha-data/src/alpha_data/crypto/providers/bybit_funding.py", "tests/unit/test_bybit_funding_pagination.py"]
}
```

README no_change: no new user command, provider readiness or setup change. The
collector is an offline internal component, not a qualified acquisition route.

Predecessor files and evidence remain unchanged in `/workspace/alpha-funding`;
`/workspace/funding-evidence/single-page-predecessor.json` inventories their hashes
and labels the historical verification summary. The successor is separate at
`/workspace/alpha-funding-pagination`, base tree
`b795de4e9611035aa9c725a2604bf3bcf038f414`. No commit or publication was created.

The callback receives exact symbol/category, paired bounds and byte allowance;
no live supplier or CLI registration exists. Nonempty pages reuse the predecessor
validator. Empty success envelopes are recognized only in this collector, without
weakening the legacy parser. Original bounds remain fixed while each inclusive
upper boundary decreases; a final singleton page does not alter parser contracts.
Short pages continue. All stop reasons retain `coverage_complete=False`.

Fresh final focused verification: 145 tests passed across the new pagination file (38
cases), predecessor funding-page file (24 cases), existing Bybit/backfill unit files
and native acquisition integration file. Ruff check/format, strict mypy for the two
new Python files, all 13 import contracts and plan validation passed. The initial
red collection failed on the absent new module before implementation. No other test
or source failure was observed in this slice. The installed predecessor environment
was reused with successor source directories first on `sys.path`; no dependencies
were installed. Ordinary public tests only; full/Atlas/preflight gates and protected
test contents were not accessed. The future-poison case includes a leaky legacy
parser control in the ordinary unit test file.

Independent read-only source review found no blocking findings. Its two suggested
tests (shrinking allowance across accepted pages and a non-bytes callback payload)
were added before the final 145-case run. The earlier 143-case run is historical,
not an additional disjoint test count. Final content identity and review receipts
are recorded separately under `/workspace/funding-evidence/`.

Accepted-payload bytes and callback counts do not measure HTTP, cost or irreversible
provider consumption. An arbitrary callback can allocate or block outside these
limits; future transport must enforce the provided allowance and an elapsed deadline.
Raw evidence must be retained before normalization with bounded acquisition/recovery
controls before production integration. The current production full-page refusal
is unchanged. No durable state, schema, science defaults, cadence, publication timing,
complete history or provider qualification follows. QuantPad remains excluded.

# Offline funding raw-first retention

**Delivery state:** Focused offline implementation and source review complete. No production integration or publication.

```json
{
  "schema_version": 1,
  "title": "Offline funding raw-first retention",
  "context": "Preserve pagination content 3437646696187fd43242acf967ed18e2da3f07e258985f64d8792f571fa4e99e and integrate existing raw staging before offline funding decode, on main 5a0d64ae6e04dad1d7fb31cb02ee798a314c9bff.",
  "assumptions": [
    {"statement": "Current raw receipt and staging support zero-byte evidence without a schema change.", "verified_by": "Raw-only synthetic empty-body retention and legacy ingestion refusal tests."},
    {"statement": "Existing artifact-first/manifest-last publication can preserve rejected payloads.", "verified_by": "Actual temporary filesystem operations with injected interruption points."}
  ],
  "alternatives_considered": ["Arbitrary sink callback: rejected because it proves no filesystem retention.", "New acquisition ledger or raw schema: unnecessary; existing store and receipt suffice."],
  "pre_mortem": ["Decode precedes raw publication.", "A storage acknowledgement failure permits continued collection.", "Synthetic capacity injection is mistaken for production admission."],
  "slices": [
    {"title": "Raw-only retention and offline collector composition", "verify": "Explicit ordinary synthetic raw-retention tests", "expected": "Verified exact bytes before decode, including malformed/zero bodies; no normalization", "rollback": "Remove offline composition and raw-only entry; keep retained raw artifacts and readers", "status": "done"},
    {"title": "Failure boundaries and independent review", "verify": "Affected ingestion/storage/funding tests; lint/types/import/plan checks", "expected": "Fresh evidence and explicit filesystem/power-loss limits", "rollback": "Preserve isolated candidate without live integration", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["CLAUDE.md", "docs/operations/research-platform-contracts.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["Live routes", "Providers", "Credentials", "Owner data", "Dependencies", "Protected contents", "Full/Atlas/preflight gates", "Durable quota/resume", "Snapshot restore", "Publication"],
  "files": ["packages/alpha-data/src/alpha_data/crypto/ingestion.py", "packages/alpha-data/src/alpha_data/crypto/funding_ingestion.py", "tests/unit/test_funding_raw_retention.py"]
}
```

README no_change: no command/setup/provider-readiness change. Existing production
full-page refusal remains. Predecessor workspaces and receipts remain untouched.

Successor workspace: `/workspace/alpha-funding-raw`, based on main tree
`b795de4e9611035aa9c725a2604bf3bcf038f414`. No existing persisted schema changed:
raw receipts/staging already permit zero bytes. Only the new raw-only entry enables
that case; legacy ingestion remains nonempty. No generic sink is accepted as retention
evidence: real existing store staging, raw artifact publication, manifest publication
and verification precede collector decoding. Rejected bodies remain inspectable via
the existing inventory and embedded receipt. Failures return no collection.

Fresh final focused evidence: 115 tests passed across raw retention (19), existing ingestion
and storage (34), predecessor funding pagination (38) and page validation (24). An
earlier 113-case run and subsequent 17-case raw-only run are historical, not disjoint
additional counts. Ruff check/format,
strict mypy for all three changed Python files, and 13 import contracts passed.
The initial red collection lacked the new module; initial mypy reported six new
test-helper errors, corrected without changing production semantics. No predecessor
receipt is represented as a fresh test run. Final plan/diff checks and review are
recorded with the candidate identity under `/workspace/funding-evidence/`.

Independent read-only source review found no blocking findings. Its two suggested
tests (invalid dataset before supplier and post-publication readability failure
before decode) were added before the final run. No production source changed after
the initial source review. Final review binds the complete candidate separately.

Tests use actual temporary filesystem operations for content/prefix verification,
fsync of appended payload, hard links, atomic replacement, manifest verification and
reopen. Fault injection supplies partial-write and publication-acknowledgement errors;
volume UUID/capacity values are synthetic, while production reserve defaults and
validation remain unchanged. Neither these tests nor arbitrary callback completion
establish real root admission, power-loss durability or concurrency qualification.
Directory/metadata sync semantics are unchanged; no stronger durability is claimed.
Before the raw manifest commits, full receipt/request recovery requires exact original
caller replay inputs; staged/external bytes alone are not a durable resume journal.

Oversized/non-bytes output is rejected before storage/decoding, so the retention claim
applies only to bounded byte responses. Supplier read/allocation/deadline enforcement,
current access/rights, durable acquisition budgets and admitted retained storage remain
production prerequisites. The production full-page refusal remains. No quota/resume,
snapshot restore, normalized publication, coverage, scientific default or provider
qualification is added. Settlement and publication availability remain distinct;
QuantPad stays excluded. Full/Atlas/preflight gates and protected contents are excluded
from this slice; no provider/credential/dependency/install/commit/push/external action
was used. Existing installed Python environment is reused with successor sources first.

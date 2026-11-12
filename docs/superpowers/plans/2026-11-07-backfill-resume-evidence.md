# Verify retained backfill work before resume

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

Historical delivery state (as first recorded): focused implementation candidate. Exact-tree review/check receipts are separate;
release qualification and live/provider acceptance are NOT RUN.

```json
{
  "schema_version": 1,
  "title": "Verify retained backfill work before resume",
  "context": "W05/W02 slice C: v1 backfill currently skips done entries without evidence verification and reacquires split parents. Base main 3f7b23185c29b2542605bd41b9485016c2ef3e79.",
  "assumptions": [
    {"statement": "The existing ledger is progress only; manifests and exact raw/normalized bytes remain evidence.", "verified_by": "_crypto_backfill.py and CryptoBulkStore.verify_manifest source"},
    {"statement": "Verification can fail before any new acquisition without resetting prior progress.", "verified_by": "Ordinary synthetic resume and actual CLI/acquisition/storage composition cases"}
  ],
  "alternatives_considered": ["New resume ledger or quota database: rejected.", "Automatically reacquire missing completed evidence: rejected because it hides history loss and repeats effects."],
  "pre_mortem": ["A split child escapes preflight.", "A valid manifest belongs to another request.", "Dry-run probes storage or writes progress.", "A retry reacquires an already-split parent."],
  "slices": [
    {"title": "Preflight completed leaves and reopen split progress", "verify": "Scoped test_crypto_backfill_resume.py and existing backfill tests", "expected": "Verify before new effects; resume only unfinished leaves; interrupted progress remains reusable", "rollback": "Revert source; v1 progress and immutable evidence remain unchanged", "status": "done"},
    {"title": "Compose real evidence verification through CLI", "verify": "Synthetic CLI resume tests, scoped lint/types/import/plan checks and independent source review", "expected": "Reject wrong/missing/changed/inactive evidence without download or ledger mutation", "rollback": "Keep original receipts/readers; no migration", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/superpowers/plans/2026-11-07-backfill-resume-evidence.md"],
  "out_of_scope": ["Provider calls", "Real storage or store initialization", "Protected contents", "Full/protected gates", "Durable quota accounting", "New retry policy", "Provider qualification", "Shared README/manual/build/Atlas edits", "Publication"],
  "files": ["apps/alpha-cli/src/alpha_cli/_crypto_backfill.py", "apps/alpha-cli/src/alpha_cli/_crypto_backfill_evidence.py", "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "tests/unit/test_crypto_backfill.py", "tests/unit/test_crypto_backfill_resume.py", "tests/integration/test_crypto_backfill_resume_cli.py"]
}
```

Proposed delivery documentation: describe completed-window preflight, explicit dry-run verification
status and split-leaf resume in README/manual/build record at later integration. Shared documents
and Atlas are deliberately untouched under the coordinating owner's current isolation constraint.
No claim of changed HTTP limits, persisted usage, complete historical coverage, rights or research
admission follows. Ordinary old artifact readers and v1 window-entry serialization remain intact.

The existing CLI now supplies resume verification. Every requested retained `done` leaf, including
split descendants, is checked before any new acquisition. Root identity, retirement, manifest and
raw/normalized byte hashes, dataset identity, retained quality and request fields must agree.
Funding effective frequency remains `funding_interval`; no fixed historical interval is assumed.
Missing legacy verification metadata is a stop, not permission to erase or reacquire old work.
Existing warnings/quarantines are verified captures, never upgraded to qualified research inputs.

Retained splits reopen their children directly. Cancellation retains successful leaf entries;
only unfinished leaves retry. Dry-run opens no storage and writes no progress; its additive
`resume_verification=not_run_dry_run` and zero `verified_completed` fields make that limit explicit.
No snapshot is created by backfill. Partial acquisition/publication failures cannot be reported as
new completed windows; previously published raw evidence remains available for investigation.
Legacy failed/missing split parents with retained contained child windows stop on inconsistent
topology before any acquisition. The runner does not reconstruct a new tree, discard child
history or automatically reacquire a larger overlapping window. Reconciliation is separate.

This does not add durable HTTP/quota usage, cross-process fencing, a changed retry policy,
crash-uncertainty reconciliation, publication-time evidence or historical completeness. It reuses
the store's existing streaming verification; it introduces no global artifact-read byte budget.
Other v1 readers remain unchanged; reverting this code would restore the older unsafe skip
behavior, so rollback must not be represented as qualified resume evidence.

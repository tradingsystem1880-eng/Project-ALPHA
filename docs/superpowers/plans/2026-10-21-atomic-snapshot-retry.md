# Atomic snapshot and promotion retry audit

**Delivery state:** Implemented; final verification reported in task evidence

```json
{
  "schema_version": 1,
  "title": "Reproduce atomic snapshot and promotion retry gaps",
  "context": "Isolated branch from b2556c0ede016f99dba687187b6e9f501bedd5cb; hypotheses require deterministic reproduction before source fixes.",
  "assumptions": [{"statement": "Snapshot callers supply no shared promotion lock", "verified_by": "Read-only navigator and public source inspection"}],
  "alternatives_considered": ["Retain current behavior if hypotheses do not reproduce", "Reject changed snapshot input and reuse only byte-identical immutable retry artifacts"],
  "pre_mortem": ["A self-hashed snapshot can preserve mixed source generations", "Deleting retry evidence would break immutability", "Available gate success cannot attest an absent private suite"],
  "slices": [
    {"title": "Reproduce snapshot interleaving", "verify": ".venv/bin/python -m pytest -q tests/unit/test_ingest_pipeline.py -k snapshot", "expected": "Completed promotion immediately after bars copy yields coherent data or clean rejection", "rollback": "Leave source unchanged if hypothesis is false", "status": "done"},
    {"title": "Reproduce receipt retry after both rollback paths", "verify": ".venv/bin/python -m pytest -q tests/unit/test_ingest_pipeline.py -k 'failed_promotion or explicit_rollback'", "expected": "Same receipt retry succeeds without altering earlier evidence", "rollback": "Preserve original failure logs and exact diff", "status": "done"},
    {"title": "Minimal fixes, controls, documentation and independent review", "verify": "uv run python scripts/gate.py full", "expected": "Report actual gate outcome and absent-suite attestation separately", "rollback": "Retain reviewable uncommitted changes and every failure receipt", "status": "in_progress"}
  ],
  "tier_impact": ["protected", "dag", "bias", "determinism"],
  "docs_to_update": ["CLAUDE.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["Frozen Stooq candidate", "Live providers or trading", "Credentials", "Holdout contents", "Network/security/policy changes", "Commit, push, PR or merge"],
  "files": ["packages/alpha-data/src/alpha_data/snapshot.py", "packages/alpha-data/src/alpha_data/pipeline.py", "tests/unit/test_ingest_pipeline.py", "tests/integration/test_data_cli.py"]
}
```

The change remains in alpha-data with no new dependency edges. Snapshot copying and receipt
publication do not alter point-in-time filtering, estimator mathematics or seed derivation.
Synthetic fixtures and synchronous injection avoid provider calls and timing-dependent sleeps.
Retain red/green command logs, exit codes and exact candidate content receipts outside public docs.
No historical missing-suite exception applies to this change.

Both initial hypotheses reproduced against unchanged production source. The snapshot verifier
accepted A bars with B actions/provenance; both automatic and explicit rollback retries failed
at the retained candidate with Linux ENOTEMPTY. An independent counterexample additionally
reproduced a completed rollback during copying. Retaining open original peer descriptors until
post-copy identity checks rejects replacements even when rollback restores identical bytes.
Descriptors are scoped per symbol (at most three), preserving the per-symbol promotion contract.
This relies on ParquetStore atomic replacement, not arbitrary external in-place file mutation.

Candidate/backup publication reuses exact matching relative structure and bytes; conflicts remain
typed failures and existing evidence is preserved. Positive retry and conflicting-artifact controls,
synchronous copy-boundary injection, event-coordinated rollback, CLI exit-2/no-traceback and PIT
future-poison controls cover the changed behavior. No provider acceptance or trading authority follows.
Final exact-tree gate/review receipts are retained separately; an absent private suite cannot be
attested by an available-suite pass and no historical exception is extended.

The first corrected-tree full gate passed backend, frontend/browser, literature and Qlib, then
failed Atlas freshness after its tests passed. The required graph/input/unknowns outputs are
regenerated with the existing Atlas command; no curated definitions or authority are changed.
That failed exact-tree receipt remains separate from the final regenerated-tree verification.

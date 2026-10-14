# Isolate the public future-poison test helper

```json
{
  "schema_version": 1,
  "title": "Make the selected future-poison guard portable in isolated staging",
  "context": "The hosted public mutation adequacy diagnostics repeatedly failed collection because tests/bias_guards/test_verified_semantic_read_future_poison.py imported _invoke from tests.integration.test_research_cli, while the isolated staging layout includes tests/fixtures and selected tests but not tests/integration. The test is public and must remain selected and executable.",
  "assumptions": [
    {
      "statement": "The shared CliRunner helper is test support and can live in tests/fixtures without changing command semantics.",
      "verified_by": "The helper body is preserved byte-for-byte in the extracted fixture and the existing integration importer remains compatible."
    },
    {
      "statement": "The existing owner-approved validation activation can run the documented suite in a separate validation checkout without reading or changing test contents.",
      "verified_by": "The 2026-10-14 approval transcript and prior validation receipt document a path-only git mv from tests/holdout_seed to tests/holdout."
    }
  ],
  "alternatives_considered": [
    "Expand scripts/harness_quant.py to copy tests/integration: rejected for this ordinary candidate because it broadens protected staging scope; that repair remains a separate pending approval.",
    "Drop or reclassify the selected future-poison test: rejected because it would reduce public test coverage and mask the collection failure."
  ],
  "pre_mortem": [
    "The extracted helper changes behavior: preserve its implementation and assert existing integration coverage.",
    "The test passes only in the repository checkout but still fails in isolated mutation staging: exercise the actual staged layout and run its selected guard.",
    "Temporary suite activation leaks into the product change: keep activation in a separate disposable validation checkout and verify the product candidate paths remain unchanged."
  ],
  "slices": [
    {
      "title": "Extract shared CLI helper and preserve the integration import",
      "verify": "uv run pytest -q -n 0 tests/bias_guards/test_verified_semantic_read_future_poison.py tests/integration/test_research_cli.py; run the selected bias guard in actual isolated staging",
      "expected": "Focused public tests pass and the staged bias guard collects without importing tests.integration.",
      "rollback": "Restore the prior integration helper and its original bias-guard import.",
      "status": "done"
    },
    {
      "title": "Refresh and check generated Atlas inputs",
      "verify": "uv run python -m alpha_atlas.generate --refresh-cli; uv run python -m alpha_atlas.generate --check",
      "expected": "Generated Atlas outputs are fresh for the plan and changed test source hashes.",
      "rollback": "Restore only generated Atlas outputs and retain the prior recovery patch and receipts.",
      "status": "done"
    },
    {
      "title": "Run approved supplemental validation in an isolated checkout and obtain fresh review",
      "verify": "Run uv run python scripts/gate.py full on the exact product candidate. In a separate validation checkout, activate the existing seed suite using the owner-approved path-only git mv and run uv run pytest tests/holdout -q. Obtain fresh independent review bound to the exact product candidate and validation receipts.",
      "expected": "The exact product candidate full passes; the supplemental suite reports its aggregate result without source disclosure; private coverage remains honestly scoped; fresh review approves the candidate.",
      "rollback": "Remove only the disposable validation checkout after its receipts and product-source parity are verified; preserve the product candidate and historical evidence.",
      "status": "in_progress"
    }
  ],
  "tier_impact": [
    "protected"
  ],
  "docs_to_update": [
    "architecture/atlas/generated/graph.json",
    "architecture/atlas/generated/inputs.json",
    "architecture/atlas/generated/views/unknowns.json"
  ],
  "out_of_scope": [
    "Production behavior or public CLI semantics",
    "Mutation stager or gate implementation",
    "Mutant inventory, selected tests, floors, exclusions, timeout, concurrency or acceptance changes",
    "Theme CSS fixture staging (separate protected staging repair)",
    "Reading, creating, editing or disclosing private test contents",
    "Exhaustive mutation sweep or publication before fresh approval and normal CI"
  ]
}
```

The helper extraction keeps the existing test selected and portable in the public isolated layout; it does not repair the independent theme-CSS staging omission. The 2026-10-14 owner approval authorizes temporary suite activation and validation only. It is not a waiver or a claim of hidden private coverage. The activated validation tree must remain separate from the product candidate.

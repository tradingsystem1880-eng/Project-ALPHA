# ML response compatibility and atomic publication contract tests

**Delivery state:** The isolated validation copy passed the documented holdout tests (17/17), the canonical full gate (all six components), and independent review. Hosted head and post-merge results are tracked in PR acceptance evidence; private coverage is UNVERIFIED. The temporary holdout activation and its Atlas refresh are validation setup, not product changes.

```json
{
  "schema_version": 1,
  "title": "Align ML web responses and test atomic text publication",
  "context": "On accepted main fc6d3b90, FastAPI response validation rejected already-supported schema-v2 rank_ensemble_v1 exchange and two-fit diagnostics. The shared atomic text writer also lacked direct public contract tests. This combined candidate preserves the write helper and worker behavior while validating both contracts.",
  "assumptions": [
    {
      "statement": "CLI and isolated worker already support schema2 rank_ensemble_v1 and two fits.",
      "verified_by": "ml_contract.py recipe validation, real.py fold diagnostics and actual FastAPI response reproduction."
    },
    {
      "statement": "alpha_validation._atomic.write_text is the established public text publication seam.",
      "verified_by": "Existing module API and recovery-tested atomic-publication regression tests."
    }
  ],
  "alternatives_considered": [
    "Rejected changing numerical/worker behavior, adding ensemble UI fields or weakening response models to arbitrary values."
  ],
  "pre_mortem": [
    "A broad response relaxation could admit unsupported schema/model/fit values.",
    "Generated OpenAPI or TypeScript could stay stale even when Python tests pass."
  ],
  "slices": [
    {
      "title": "Reproduce and constrain response validation",
      "verify": "uv run pytest -q -p no:cacheprovider tests/unit/test_web_ml.py -k response",
      "expected": "v1 positive controls pass; v2 route cases fail before fix; unsupported values remain rejected.",
      "rollback": "Remove only new response regressions.",
      "status": "done"
    },
    {
      "title": "Exercise existing atomic text publication guarantees",
      "verify": "uv run pytest -q -p no:cacheprovider tests/unit/test_validation_atomic_publication.py",
      "expected": "Nested-parent creation, complete replacement and failure cleanup preserve the old file and leave no temporary file.",
      "rollback": "Remove only the focused public tests; leave the existing helper unchanged.",
      "status": "done"
    },
    {
      "title": "Align response contracts and generated API artifacts",
      "verify": "Focused ML tests; OpenAPI generation/check; frontend API generation and TypeScript build.",
      "expected": "Schema 1 accepts LightGBM, schema 2 accepts rank_ensemble_v1, and invalid pairings fail even when result.json is absent.",
      "rollback": "Restore the original response contract and regenerate OpenAPI and client types.",
      "status": "done"
    },
    {
      "title": "Complete combined acceptance",
      "verify": "Supported Atlas refresh/check and exact-tree local full/review; hosted head and post-merge results are tracked separately in PR acceptance evidence.",
      "expected": "The combined source and generated contracts pass local acceptance on one exact tree; private coverage remains explicitly unverified.",
      "rollback": "Revert only this combined delivery after preserving its recovery receipt.",
      "status": "local_verified"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "CHANGELOG.md",
    "architecture/atlas/generated/graph.json",
    "architecture/atlas/generated/inputs.json",
    "architecture/atlas/generated/views/unknowns.json"
  ],
  "out_of_scope": [
    "Numerical behavior",
    "Worker capabilities",
    "Artifact validation",
    "Protected gates",
    "Owner data/private tests",
    "Qlib training"
  ],
  "files": [
    "CLAUDE.md",
    "apps/alpha-web/src/alpha_web/api/ml.py",
    "apps/alpha-web/frontend/src/panels/MlDiagnostics.tsx",
    "tests/unit/test_web_ml.py",
    "tests/unit/test_validation_atomic_publication.py",
    "apps/alpha-web/frontend/openapi.json",
    "apps/alpha-web/frontend/src/api/generated.ts",
    "apps/alpha-web/src/alpha_web/static/app/",
    "architecture/atlas/generated/graph.json",
    "architecture/atlas/generated/inputs.json",
    "architecture/atlas/generated/views/unknowns.json",
    "CHANGELOG.md",
    "docs/BUILD-STATUS.md",
    "docs/superpowers/plans/2026-10-14-ml-response-ensemble.md"
  ]
}
```

Runtime reproduction uses synthetic exchange files, stubbed CLI completion/evaluation and real FastAPI response serialization. No Qlib training or owner data is involved. DAG, look-ahead timing, determinism and authority boundaries remain unchanged.

Focused verification passed 56 backend tests; OpenAPI, generated TypeScript and Atlas were refreshed. The API discriminates the supported schema/model pairs, and prepared-exchange regressions prove invalid cross-pairings fail even when result.json is absent. Atomic tests cover nested-parent creation, complete replacement and cleanup after write or replacement failure. The UI describes the actual fit count per fold. The isolated validation copy passed the documented holdout suite (17 tests), all six canonical full-gate components, and independent review. Hosted head and post-merge results are tracked separately in PR acceptance evidence; private coverage is UNVERIFIED.

# Native RD cumulative qualification correction

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

**Historical delivery state (as first recorded):** Scoped candidate; exact qualification outcome recorded in external receipts.

```json
{
  "schema_version": 1,
  "title": "Coherent native RD cumulative offline regression",
  "context": "Preserve1ef1bcfe and exports. Initial9file coherent run found receipt collisions; canonical changed-file type checking found181test diagnostics. No production feature change.",
  "assumptions": [
    {
      "statement": "Existing controller and worker dependencies suffice without setup",
      "verified_by": "Offline locked-controller check and compatible unchanged284-package upstream inventory"
    },
    {
      "statement": "Changing tests/helpers does not change worker/API/SPA runtime identity",
      "verified_by": "Exact parent/successor production-source and52staticfile identity comparison"
    }
  ],
  "alternatives_considered": [
    "Use namespaced evidence and concrete checked test types; reject existing-directory reuse, type ignores and broad/private-gate substitution."
  ],
  "pre_mortem": [
    "Receipt files can collide or overwrite across selected components; use fresh per-component namespaces.",
    "Untyped test helpers hide canonical typing failures; type changed apps/tests cumulatively with checked JSON narrowing and real SQLite connection fixtures."
  ],
  "slices": [
    {
      "title": "Reproduce coherent predecessor failures",
      "verify": "Explicit9file owned regression plus cumulativechanged-file typing",
      "expected": "Preserved initial failure receipts and exact source identity",
      "rollback": "No predecessor mutations; retain failures",
      "status": "done"
    },
    {
      "title": "Correct test-only isolation and typing",
      "verify": "Owned pureselection, strict22file subset, independent source review",
      "expected": "Assertions and production/runtime identity preserved; no ignores",
      "rollback": "Retain1ef candidate and remove test-only successor",
      "status": "done"
    },
    {
      "title": "Freeze and qualify asset-enabled cumulative successor",
      "verify": "Explicit9file owned regression plus cumulative lint/type/import contracts and scoped frontend tests",
      "expected": "Exact tree/selection/counts in external receipts; full/private qualification remains excluded",
      "rollback": "Retain predecessor/artifacts and report any remaining failure honestly",
      "status": "in_progress"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/operations/native-cumulative-regression.md"
  ],
  "out_of_scope": [
    "Production/worker/accounting/authority changes",
    "Protected/full/privategates",
    "Installs/transfers/publication",
    "Paper/data/Qlib owner work"
  ],
  "files": [
    "tests/unit/test_native_stock_dispatch.py",
    "tests/unit/test_native_stock_fixture.py",
    "tests/unit/test_native_stock_inspect.py",
    "tests/unit/test_native_stock_snapshot.py",
    "tests/unit/test_native_stock_profile.py",
    "tests/unit/test_native_stock_result.py",
    "tests/unit/test_native_stock_operator_cli.py",
    "tests/unit/test_native_result_api.py",
    "tests/unit/test_native_result_web.py",
    "tests/unit/_native_stock_test_support.py"
  ]
}
```

No claim of full/private or live inference qualification. Frozen source is checked as one
explicit selection; retained successful production/build receipts may be reused only
where exact dependency/byte identity proves applicability.

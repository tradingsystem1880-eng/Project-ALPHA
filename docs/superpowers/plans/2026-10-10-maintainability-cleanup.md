**Delivery state:** Completed implementation; target acceptance is bound to external verification receipts.

# Bounded maintainability cleanup

```json
{
  "schema_version": 1,
  "title": "Bounded maintainability cleanup",
  "context": "Owner authorized bounded cleanup, a one-time missing-private-engineering-suite exception for this cleanup only, and separate guarded publication/merge after fresh public tests, hosted CI and independent review. Transfer only the cleanup delta onto a clean target after PR54; preserve original unrelated staged work and exclude the unaccepted standing policy.",
  "assumptions": [
    {
      "statement": "The target includes accepted PR54 and the post-merge fixture/wheel repair PR57.",
      "verified_by": "Base d914be9f4df6cee6a5231229c2dfeda70037574a, verified origin/main and external final-acceptance.json."
    },
    {
      "statement": "Numerical, authority, transaction and historical evidence semantics are unchanged.",
      "verified_by": "Exact-byte/codec characterization, public integration/seam tests and independent review."
    }
  ],
  "alternatives_considered": [
    "Rejected broad rewrite, package merger, ORM and blanket dead-code deletion."
  ],
  "pre_mortem": [
    "Source relocation could weaken execution fingerprint coverage: inspect explicit fingerprint registries before moving execution logic.",
    "Uncommitted unrelated work could be omitted or mixed into cleanup: resolve baseline and retain separate cleanup diff."
  ],
  "slices": [
    {
      "title": "Immutable crypto persistence",
      "verify": "uv run pytest -q tests/unit/test_crypto_persistence.py tests/integration/test_crypto_data_cli.py tests/unit/test_crypto_profiles.py",
      "expected": "Exact bytes, repeated writes, errors and failure ordering preserved.",
      "rollback": "Revert only shared writer extraction.",
      "status": "done"
    },
    {
      "title": "Pure control serialization",
      "verify": "uv run pytest -q tests/unit/test_control_store.py tests/unit/test_control_schema.py tests/unit/test_research_control_store.py",
      "expected": "Pure helpers separated; facade imports, limits, errors and transactions unchanged.",
      "rollback": "Restore original helper definitions.",
      "status": "done"
    },
    {
      "title": "Development checks and navigation",
      "verify": "uv run pytest -q tests/unit/test_gate_components.py tests/unit/test_documentation_truth.py; uv run python scripts/gate.py full",
      "expected": "Single frontend TypeScript/build sequence; retain coverage, serial functional browser tests and API/SPA freshness. Final acceptance uses fresh target-bound full and independent evidence.",
      "rollback": "Restore command definitions and navigation links.",
      "status": "done"
    }
  ],
  "tier_impact": [
    "dag",
    "determinism"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "README.md",
    "docs/ARCHITECTURE.md"
  ],
  "out_of_scope": [
    "Unrelated staged chart/cash/source changes and the proposed standing private-suite policy",
    "Mutation workflow repairs already separately owned by PR54",
    "Private source access, research holdout data or waiver of an actual failure",
    "Quant algorithms, migrations, authority transactions and agent-framework redesign",
    "Dependency removal or test reductions without evidence"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/_control_json.py",
    "apps/alpha-cli/src/alpha_cli/_crypto_persistence.py",
    "apps/alpha-cli/src/alpha_cli/control_store.py",
    "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py",
    "apps/alpha-web/frontend/package.json",
    "scripts/gate_components.py",
    "tests/unit/test_control_json.py",
    "tests/unit/test_crypto_persistence.py",
    "tests/unit/test_gate_components.py",
    ".claude/agents/independent-reviewer.md",
    "CLAUDE.md",
    "README.md",
    "docs/ARCHITECTURE.md",
    "docs/BUILD-STATUS.md",
    "docs/operations/development-loop.md",
    "docs/superpowers/plans/2026-10-10-maintainability-cleanup.md",
    "architecture/atlas/generated/",
    "docs/atlas/"
  ]
}
```

The prototype passed all six canonical components and scoped independent review on preserved tree `6eb3c371181276121db5d9a210ce219b2f06394047a67ec664b5ca31fbf9f571`. That evidence does not transfer to the eventual target tree. Fresh focused/full checks and independent review are required after integration; final receipts stay outside the tested source tree.

## One-time cleanup exception

The owner explicitly approved proceeding without the absent private engineering suite for this bounded cleanup and authorized its separate push/merge after fresh public tests, hosted CI and review pass. Record private coverage UNVERIFIED; no private source access, actual failure waiver, standing availability policy, research exception or permission for later changes is granted. This exception is independent of PR54's mutation-only exception.

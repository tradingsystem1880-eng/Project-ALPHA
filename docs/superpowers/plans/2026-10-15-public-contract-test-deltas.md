# Add public contract regression tests

**Current status — 2026-10-17:** Accepted through [PR #64](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/64) with seven successful required checks. The five public regression-test deltas are integrated. Preserve the original payload/source caveat; current-main mutation adequacy remains UNMEASURED.

**Delivery state:** Completed (accepted five public regression-test deltas via PR #64 only; current mutation adequacy remains UNMEASURED).

Earlier dated status and incident entries are preserved as historical records.

**Historical delivery state (2026-10-15, before PR #64):** Completed; local implementation and focused public verification were complete, while exact-source and release acceptance remained separate.

```json
{
  "schema_version": 1,
  "title": "Add public contract regression tests",
  "context": "Add five public regression-test deltas supplied in the parent task, originally normalized against accepted base b2c43735 and now prepared on newly accepted base 0a3cdaef. The local five-file patch is recoverable, but it is not byte-identical to the original six-file cloud patch; the original plan content was not transferred.",
  "assumptions": [
    {
      "statement": "The tested contracts are already implemented on accepted base 0a3cdaef, so this candidate changes public test coverage only",
      "verified_by": "The five focused test files pass without production-source changes"
    }
  ],
  "alternatives_considered": [
    "Keep the five test files in one isolated candidate so their local verification and exact recovery remain bound together",
    "Do not reconstruct or claim parity with the unavailable original cloud plan/payload"
  ],
  "pre_mortem": [
    "Rendering assertions could bind to incidental artist details; keep them focused on supplied geometry, direction, bounds, category order and theme colors",
    "Boundary cases could accidentally imply a production behavior change; this candidate remains tests-only and must pass against the accepted source",
    "The task-provided normalized patch differs from the original full cloud patch; preserve both identities and report that limitation"
  ],
  "slices": [
    {
      "title": "Cover candle/error-bar value validation and rendered geometry",
      "verify": "uv run pytest -q tests/unit/test_figure_render.py tests/unit/test_figure_spec.py",
      "expected": "Public tests cover finite aligned candle/error-bar inputs and supplied renderer geometry, category order, interval bounds and directional colors",
      "rollback": "Restore the exact five-file candidate patch from its recovery receipt",
      "files": ["tests/unit/test_figure_render.py", "tests/unit/test_figure_spec.py"],
      "status": "done"
    },
    {
      "title": "Cover zero prop-firm and artifact-count boundaries",
      "verify": "uv run pytest -q tests/unit/test_propfirm.py tests/unit/test_research_artifacts.py",
      "expected": "Zero account/target values are rejected; zero artifact counts remain typed and booleans are rejected",
      "rollback": "Restore the exact five-file candidate patch from its recovery receipt",
      "files": ["tests/unit/test_propfirm.py", "tests/unit/test_research_artifacts.py"],
      "status": "done"
    },
    {
      "title": "Cover zero-horizon evidence-window boundaries",
      "verify": "uv run pytest -q tests/unit/test_research_topology.py",
      "expected": "A zero forward horizon accepts same-index outcomes across discovery, confirmation and final holdout windows, and rejects a nonzero interval",
      "rollback": "Restore the exact five-file candidate patch from its recovery receipt",
      "files": ["tests/unit/test_research_topology.py"],
      "status": "done"
    },
    {
      "title": "Regenerate and validate derived Atlas inputs",
      "verify": "cd tools/alpha-atlas && uv run python -m alpha_atlas.generate --check; uv run pytest -q",
      "expected": "All eight supported Atlas outputs are fresh and the public Atlas suite passes",
      "rollback": "Regenerate outputs from the reviewed source tree; do not hand-edit generated files",
      "files": ["architecture/atlas/generated/graph.json", "architecture/atlas/generated/inputs.json", "architecture/atlas/generated/views/unknowns.json"],
      "status": "done"
    }
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["docs/superpowers/plans/2026-10-15-public-contract-test-deltas.md"],
  "out_of_scope": [
    "Production source or behavior changes",
    "Changing mutation selection, inventory, floors, tolerances, timeouts, concurrency or acceptance rules",
    "Private-suite source/data access or a private-coverage pass claim",
    "Reconstructing the missing sixth cloud-patch file or claiming the local patch matches the cloud patch",
    "Hosted publication or merge before parent scope authorization"
  ],
  "files": [
    "docs/superpowers/plans/2026-10-15-public-contract-test-deltas.md",
    "architecture/atlas/generated/graph.json",
    "architecture/atlas/generated/inputs.json",
    "architecture/atlas/generated/views/unknowns.json",
    "tests/unit/test_figure_render.py",
    "tests/unit/test_figure_spec.py",
    "tests/unit/test_propfirm.py",
    "tests/unit/test_research_artifacts.py",
    "tests/unit/test_research_topology.py"
  ]
}
```

## Preparation verification

- The five focused files pass together: 144 tests. Ruff lint and formatting checks pass. The manual-size check passes, and the four-slice plan validates.
- All eight supported Atlas outputs are fresh, and the public Atlas suite passes 102 tests.
- The normalized supplied five-file patch is SHA-256 `40cca0b72fbb8381ac6d38dc97f91a9afb8790db69f784256c2b3d75d1416549`; this candidate adds a formatting correction, this scoped plan and regenerated Atlas outputs. It is not byte-identical to the original six-file cloud patch.
- This candidate starts from accepted base `0a3cdaef`, which includes PR #63; the five-file source patch was originally normalized against `b2c43735` and remains separately preserved in the reconciliation evidence directory.
- Production sources, mutation rules, private-suite materials and coverage floors are unchanged. Hosted acceptance and merge have not been performed.

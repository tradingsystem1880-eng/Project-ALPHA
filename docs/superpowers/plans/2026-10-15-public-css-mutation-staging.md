# Carry selected theme CSS into isolated mutation staging

**Delivery state:** Completed (2026-10-15; implementation and scoped public verification; release acceptance is outside this implementation plan).

```json
{
  "schema_version": 1,
  "title": "Carry selected theme CSS into isolated mutation staging",
  "context": "The retained public theme-drift preflights read tracked frontend CSS by repository-relative path. Isolated mutation staging must preserve the selected checked-out inputs in both the initial staging tree and mutmut's nested execution tree.",
  "assumptions": [
    {
      "statement": "The package selection continues to include tests/unit/test_theme_drift.py when its alpha_research imports are selected",
      "verified_by": "The focused staging regression asserts the selected test is present, exact copied fixture bytes, and nested-copy configuration"
    }
  ],
  "alternatives_considered": [
    "Copying the whole frontend tree is unnecessary; only the two committed CSS inputs are required",
    "Deselecting or ignoring the public theme tests would conceal a staging failure and reduce test coverage"
  ],
  "pre_mortem": [
    "The CSS may exist in the staging tree but not in mutmut's nested execution tree; the generated also_copy list must include the minimal apps subtree",
    "A missing stylesheet must fail loudly rather than be fabricated or silently omitted",
    "Restoring selected tests that previously failed staging preflight can change the effective executed population and measured denominators even though selection and exclusion rules remain unchanged"
  ],
  "slices": [
    {
      "title": "Copy exact CSS only when the theme-drift test is selected",
      "verify": "uv run pytest -q tests/unit/test_mutation_public_staging.py",
      "expected": "Selected staging contains byte-identical index.css and theme.generated.css and includes apps in the nested copy list",
      "rollback": "Revert the CSS-specific stage_mutation_tree hunk and its public regression",
      "files": ["scripts/harness_quant.py", "tests/unit/test_mutation_public_staging.py"],
      "status": "done"
    },
    {
      "title": "Reject either missing public CSS input",
      "verify": "uv run pytest -q tests/unit/test_mutation_public_staging.py",
      "expected": "Both missing-source negative controls raise FileNotFoundError",
      "rollback": "Revert the CSS-specific stage_mutation_tree hunk and its public regression",
      "files": ["tests/unit/test_mutation_public_staging.py"],
      "status": "done"
    },
    {
      "title": "Regenerate Atlas and verify its public outputs",
      "verify": "cd tools/alpha-atlas && uv run python -m alpha_atlas.generate && uv run python -m alpha_atlas.generate --check; uv run pytest -q",
      "expected": "All eight supported generated outputs are fresh and the Atlas public suite passes",
      "rollback": "Regenerate from the reviewed source tree; do not hand-edit generated outputs",
      "files": ["architecture/atlas/generated/graph.json", "architecture/atlas/generated/inputs.json", "architecture/atlas/generated/views/unknowns.json"],
      "status": "done"
    },
    {
      "title": "Reconcile concise instructions and current-state documentation",
      "verify": "uv run pytest -q tests/unit/test_claude_md_relocation.py::TestCurrentManual::test_core_is_small && uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-10-15-public-css-mutation-staging.md",
      "expected": "CLAUDE.md preserves the UI orientation within the existing manual-size limit; the harness guide and build status describe the current guard and distinguish unchanged rules from restored executed cases",
      "rollback": "Restore these documentation files from the exact candidate recovery patch",
      "files": ["CLAUDE.md", "docs/BUILD-STATUS.md", "docs/operations/claude-code-harness.md"],
      "status": "done"
    }
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["CLAUDE.md", "docs/BUILD-STATUS.md", "docs/operations/claude-code-harness.md"],
  "out_of_scope": [
    "The public CLI helper extraction and consumer import changes already integrated by PR #62",
    "Changing selector/exclusion rules, mutant inventory, thresholds, tolerance, timeouts, concurrency or acceptance semantics; restoring formerly deselected selected theme tests can change the effective executed case set and measured outcomes",
    "Private-suite source/data access or any private-coverage pass claim",
    "A new exhaustive mutation sweep or publication before exact-target acceptance"
  ],
  "files": ["CLAUDE.md", "architecture/atlas/generated/graph.json", "architecture/atlas/generated/inputs.json", "architecture/atlas/generated/views/unknowns.json", "docs/BUILD-STATUS.md", "docs/operations/claude-code-harness.md", "docs/superpowers/plans/2026-10-15-public-css-mutation-staging.md", "scripts/harness_quant.py", "tests/unit/test_mutation_public_staging.py"]
}
```

PR #62 already supplies the public CLI fixture helper and consumer imports; this plan records the selected CSS staging repair plus bounded current-state documentation and generated-Atlas upkeep. The harness copies the current checkout inputs, which matched accepted base `b2c43735` in this candidate. Selector/exclusion rules, identities, floors, tolerance, timeouts, concurrency and acceptance criteria are unchanged; restoring cases previously deselected by staging preflight can change the effective executed set and measured outcomes. Private coverage remains **UNVERIFIED**.

## Preparation verification

- The initial CSS regression was run without the staging change and failed on its three original cases; with the change restored, the expanded `uv run pytest -q tests/unit/test_mutation_public_staging.py` passes all 4 selected and unselected staging cases.
- Focused staging/sweep/fragment checks passed: 76 tests.
- A real staged tree for `alpha_research/data.py` contained `tests/unit/test_theme_drift.py`, byte-identical committed CSS, and `also_copy = ["packages", "apps"]`; the selected theme test passed all 54 tests from that tree.
- This plan covers implementation and scoped public verification only. The standard protected-path review, canonical full, required hosted CI, normal merge and post-merge CI follow the repository's separate release process. No exhaustive mutation sweep or private-suite access is part of this repair.

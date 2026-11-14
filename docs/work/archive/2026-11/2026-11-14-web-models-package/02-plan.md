# The web API models as a package

**Delivery state:** Completed — built and checked on branch `m6/models-package`; done when its pull request merges.
**Build class:** hard — a 3,407-line move across 19 new files, raised from small by the brief.

Filed straight into the archive, as `2026-11-14-shared-helpers` was: the work-in-progress ceiling
(34) admits no new live plan, and the work was finished in one sitting.

## For the owner

- The 3,407-line file of API models is now 18 files of 21 to 574 lines, one per area of the API.
- Nothing changes in the app: the API contract file generated from the code is byte-for-byte the
  same, and every model is the same code, only in a different file.
- The three identical copies of the base model class are now one.
- No research approval is touched.

```json
{
  "schema_version": 1,
  "title": "The web API models as a package",
  "context": "api/models.py was the fourth-largest product file (3,407 lines) and is read by most web changes.",
  "assumptions": [
    {"statement": "Pydantic names OpenAPI components by class name, qualifying by module only on a name collision, so moving classes without collisions leaves the document unchanged.", "verified_by": "the freshness check and the sha256 of the generated document before and after"},
    {"statement": "No approval binding covers alpha_web.", "verified_by": "DAILY_GUARD_FILES and _research_code_paths list only alpha_cli and alpha_research files"}
  ],
  "alternatives_considered": [
    "A re-export shim models.py plus a sibling package: rejected, the package __init__ is the same interface without a second file.",
    "Moving one router at a time over several pull requests (the old refactor plan): rejected, a single mechanical move proven by one hash comparison is smaller to review than many."
  ],
  "pre_mortem": [
    "A missing import in a new module leaves a forward reference unresolved and changes or breaks the schema: caught by the byte check and pydantic completeness.",
    "Fixture provenance names the deleted file: the capture script now names the new modules; the committed provenance records the earlier capture."
  ],
  "slices": [
    {"title": "Move the models into the package (Codex build)", "verify": "uv run python scripts/generate_web_openapi.py --check", "expected": "passes without regenerating", "rollback": "revert the move commit", "status": "done"},
    {"title": "One StrictModel; baseline, rule and refactor index (Claude)", "verify": "uv run python scripts/gate.py check --all", "expected": "All checks passed", "rollback": "revert the follow-up commit", "status": "done"}
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["docs/reference/invariants/web-api.md", "docs/roadmap/refactors/web-api-models-split.md"],
  "out_of_scope": ["apps/alpha-web/frontend/", "model fields and validators", "apps/alpha-cli"],
  "files": ["apps/alpha-web/src/alpha_web/api/models.py", "apps/alpha-web/src/alpha_web/api/models/", "apps/alpha-web/src/alpha_web/api/ml.py", "apps/alpha-web/src/alpha_web/api/v3.py", "scripts/capture_c04_risk_basis_fixture.py", ".claude/code-size-baseline.json", "docs/reference/invariants/web-api.md", "docs/roadmap/", "STATUS.md", "docs/work/archive/2026-11/2026-11-14-web-models-package/"]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [web API rules](../../../../reference/invariants/web-api.md) | API contract | always |
| [engineering rules](../../../../reference/invariants/engineering.md) | Code size | always |

## Slices

As in the JSON block.

## Test plan

The OpenAPI freshness check and a sha256 of the generated document before and after; an AST
comparison of every top-level definition's source text; the web, MCP and risk tests; smoke.

## Look-ahead, determinism and import impact

None: no data, clock, statistic or approval. Import contracts hold (alpha_web imports only alpha_core
and public alpha_cli seams, as before).

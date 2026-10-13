**Delivery state:** Completed implementation; release acceptance is bound to final verification receipts.

# Compatible frontend dependency patches

```json
{
  "schema_version": 1,
  "title": "Compatible frontend dependency security patches",
  "context": "Owner authorized triage and compatible fixes while PR54 hosted sweep runs. Separate recoverable branch from researchd3; frozen mutation, cleanup and preflight are untouched. Transfer only scoped delta after accepted target settles; no publication now.",
  "assumptions": [
    {
      "statement": "All pending branches retain the eight affected installed entries.",
      "verified_by": "Compare five live package-lock manifests, official advisories and installed npm dependency graph."
    },
    {
      "statement": "Bokeh/sprintf cannot be fixed through a currently published compatible package update.",
      "verified_by": "Official GHSA lists no patched sprintf-js version; npm latest is 1.1.3 and Bokeh latest 3.10.0 still depends on it."
    }
  ],
  "alternatives_considered": [
    "Rejected npm audit fix --force, Bokeh downgrade, new registries, blanket dependency refresh and check suppression."
  ],
  "pre_mortem": [
    "Updating Vitest alone could conflict with the exact coverage peer version; keep them aligned.",
    "Unrelated transitive updates could enlarge scope; inspect lock delta and preserve Chai 6.2.2."
  ],
  "slices": [
    {
      "title": "Aligned test-tool patch",
      "verify": "npm ci; npm run test:coverage",
      "expected": "Vitest and coverage 4.1.11, 393 existing tests and unchanged coverage thresholds pass.",
      "rollback": "Restore only package and lock diff.",
      "status": "done"
    },
    {
      "title": "YAML and parser patch versions",
      "verify": "npm run lint -- --deny-warnings; npm run generate:api; npm run build",
      "expected": "js-yaml 4.3.2, brace-expansion 2.1.7, source-map-js 1.2.2; API and all 41 built assets byte-identical; no unrelated version change. Fresh final integrated acceptance remains pending.",
      "rollback": "Restore only package and lock diff.",
      "status": "done"
    }
  ],
  "tier_impact": [],
  "docs_to_update": [
    "docs/BUILD-STATUS.md"
  ],
  "out_of_scope": [
    "Private suite/data or policy change",
    "Frozen 20-path cleanup and preflight",
    "Bokeh version downgrade or upstream sprintf fork",
    "Renderer behavior change without separate scoped correction",
    "Final publication before settled target"
  ],
  "files": [
    "apps/alpha-web/frontend/package.json",
    "apps/alpha-web/frontend/package-lock.json",
    "docs/BUILD-STATUS.md"
  ]
}
```

Six development-tool audit entries are addressed with compatible versions. The runtime Bokeh/sprintf advisory remains unpatched upstream. A separate reproduced extreme-range renderer precision issue requires its own correction; no renderer change is included here. This is not a claim of exploitable production vulnerabilities or final release acceptance.

## Accepted integration target

Integrated only this scoped followup on accepted main `31479cad` after PR56 exact-head and post-merge CI passed. Historical preparation remains recoverable. Final public full, independent review, hosted CI and post-merge receipts bind the actual target; preparation receipts do not establish acceptance. The four-followup absence-only decision is recorded in `docs/operations/2026-10-12-four-followup-private-suite-exception.md`; private coverage remains UNVERIFIED. Renderer/readiness stays separate, and no new exhaustive mutation sweep is included.

# Terminal workflow polish

```json
{
  "schema_version": 1,
  "title": "Terminal workflow polish",
  "context": "Owner requests Bloomberg-style workflow quality with grey Windows reference chrome. Improve fast task navigation and useful chart workspace area.",
  "assumptions": [
    {
      "statement": "Only existing registered UI destinations may be opened by function commands",
      "verified_by": "Profile-aware command mapping tests"
    }
  ],
  "alternatives_considered": [
    "Installing a second chart engine is unnecessary for navigation and layout fixes",
    "Preserve canonical versus archive identity; layout preferences do not grant data authority"
  ],
  "pre_mortem": [
    "Compact controls may become inaccessible",
    "Persisted settings may be malformed",
    "Comparison charts may fall below the viewport"
  ],
  "slices": [
    {
      "title": "Function commands and task navigation",
      "verify": "Vitest mapping and browser keyboard tests",
      "expected": "Every visible task is directly navigable without mutation",
      "rollback": "Revert this presentation slice",
      "status": "done"
    },
    {
      "title": "Persistent compact chart desk",
      "verify": "Preference tests and browser resize/reload checks",
      "expected": "Docks restore safely and chart comparisons share the workspace",
      "rollback": "Revert this presentation slice",
      "status": "done"
    },
    {
      "title": "Visual audit and independent review",
      "verify": "Browser screenshots, accessibility and component gate",
      "expected": "Reference chrome remains legible at supported sizes",
      "rollback": "Revert this presentation slice",
      "status": "done"
    },
    {
      "title": "Documentation and aggregate verification",
      "verify": "Full gate and documented limitations",
      "expected": "Current evidence and integration ownership remain explicit",
      "rollback": "Revert this presentation slice",
      "status": "done"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "apps/alpha-web/frontend/README.md",
    "docs/BUILD-STATUS.md",
    "docs/audit/2026-09-30-terminal-workflow-polish.md"
  ],
  "out_of_scope": [
    "New numerical formulas",
    "New provider subscriptions",
    "Research agent branch mutation",
    "Bloomberg product equivalence or certification"
  ],
  "files": [
    "apps/alpha-web/frontend/",
    "docs/"
  ]
}
```

Visual authority: Desktop/ALPHA-terminal-designs, especially 1-Terminal and 9-Option-E. Navigation inspiration: Bloomberg official Getting Started guide (https://data.bloomberglp.com/professional/sites/10/Getting-Started-Guide-for-Students-English.pdf). No new DAG edges, statistical calculations, research authority or data admission.

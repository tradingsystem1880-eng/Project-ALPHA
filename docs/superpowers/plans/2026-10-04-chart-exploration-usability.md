# Chart exploration and data readability

**Delivery state:** Completed

**Acceptance (2026-10-05):** the canonical full gate passed on the frozen shared tree (stamp tree `54b7f96e`, 2026-10-04 13:46 UTC, all six components, 969 s); see the 2026-10-05 record in `docs/BUILD-STATUS.md`. Earlier state: Completed implementation and scoped verification; aggregate acceptance requires the current passing canonical receipt.

Owner asks to make the scientific workstation easier to use, read and chart. Preserve the approved top bar, native source identity, recorded evidence, null gaps and independent panels. No estimators, API changes, data acquisition, source substitution or authority changes. UTC range controls change presentation only. No commits requested; preserve existing work and staging.

Acceptance requires focused unit/browser evidence, minimum/reference/wide visual inspection, independent review and a current frozen-tree canonical full receipt. Historical receipts do not authorize this changed tree.

```json
{
  "schema_version": 1,
  "title": "Chart exploration and data readability",
  "context": "Improve data understanding and scientific chart exploration without replacing the approved shell or modifying evidence.",
  "assumptions": [
    {
      "statement": "Existing immutable returned series can support explicit UTC display ranges and exact table exports",
      "verified_by": "Current scientific renderers, API types and recorded table contracts"
    }
  ],
  "alternatives_considered": [
    "Compact UTC range controls over existing Bokeh instances instead of adding another renderer or always-mounted overview plot"
  ],
  "pre_mortem": [
    "Range controls must not change source or refetch data",
    "Absent values must remain absent in summaries and exports",
    "Extra chrome must not make small panels unusable"
  ],
  "slices": [
    {
      "title": "Observed-value and UTC range contracts",
      "verify": "Focused model unit tests",
      "expected": "Exact extrema/counts, gaps and bounded UTC windows without resampling",
      "rollback": "Revert only this slice",
      "status": "done"
    },
    {
      "title": "Scientific chart exploration and exact values",
      "verify": "Types/lint and browser interactions including linked ranges and retained canvases",
      "expected": "Direct range controls, readable coverage and exact CSV/table navigation",
      "rollback": "Revert only this slice",
      "status": "done"
    },
    {
      "title": "Readable workspace labels and guided empty chart",
      "verify": "Minimum/reference/wide browser regressions and visual review",
      "expected": "Human-readable layouts/panels and actionable source selection",
      "rollback": "Revert only this slice",
      "status": "done"
    },
    {
      "title": "Documentation and scoped verification",
      "verify": "Coverage/build, viewport/browser evidence and independent review; frozen-tree canonical full is independently mandatory",
      "expected": "Evidence-backed implementation with explicit limitations; only a fresh canonical receipt determines aggregate acceptance",
      "rollback": "Revert only this task changes",
      "status": "done"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "apps/alpha-web/frontend/README.md"
  ],
  "out_of_scope": [
    "Backend/statistical changes",
    "Source acquisition",
    "New chart dependencies",
    "Live routing",
    "Publication"
  ]
}
```

# Scientific research and data workstation

**Delivery state:** Completed

**Acceptance (2026-10-05):** the canonical full gate passed on the frozen shared tree (stamp tree `54b7f96e`, 2026-10-04 13:46 UTC, all six components, 969 s); see the 2026-10-05 record in `docs/BUILD-STATUS.md`. Earlier state: Scientific rendering, source controls, research composition and scoped frontend verification are delivered. Aggregate acceptance is determined exclusively by a passing canonical receipt bound to the current frozen tree; see the correction report.

Owner correction supersedes the prior decision to limit Qbot to composition only. Keep the approved top bar. Qbot uses Bokeh HTML reports and Matplotlib scientific plotting; render live typed ALPHA responses directly, never reuse Qbot sample values. Scientific views must expose axes/units, linked ranges, exact values tables and existing backend figures. Market renderer remains optional.

DAG, statistical models, data artifacts and authority remain unchanged. Split implementation into small verified increments within these slices. Canonical final gate: `uv run python scripts/gate.py full`.

```json
{
  "schema_version": 1,
  "title": "Scientific research and data workstation",
  "context": "Owner correction: preserve classic top bar, make Qbot Bokeh/Matplotlib scientific research first class and default, retain optional market renderer, expose project-free browsing and hourly archives.",
  "assumptions": [
    {
      "statement": "Existing APIs supply recorded research data without new estimators",
      "verified_by": "Typed projections, real CLI journeys and explicit missing-snapshot tests"
    }
  ],
  "alternatives_considered": [
    "BokehJS client over existing typed data instead of generating report HTML or importing Python into web",
    "Keep optional existing market renderer rather than deleting chart evidence features"
  ],
  "pre_mortem": [
    "Pinned sources must not follow unrelated canonical changes",
    "Chart reconstruction must not lose pan and zoom",
    "Run snapshot absence must remain explicit"
  ],
  "slices": [
    {
      "title": "Scientific rendering primitives",
      "verify": "Types, unit contracts and real browser render",
      "expected": "Bokeh plots with axes, units, gaps, zoom, exports and UTC linking",
      "rollback": "Revert only this correction; preserve previous user work",
      "status": "done"
    },
    {
      "title": "Workspace and research integration",
      "verify": "Workspace and browser regressions",
      "expected": "Default scientific mode; existing market features remain selectable",
      "rollback": "Revert only this correction; preserve previous user work",
      "status": "done"
    },
    {
      "title": "Project-free browsing and source discoverability",
      "verify": "Context and archive browser journeys",
      "expected": "Visible project chooser and no-project browsing; exact hourly archives",
      "rollback": "Revert only this correction; preserve previous user work",
      "status": "done"
    },
    {
      "title": "Research composition and scoped verification",
      "verify": "Frontend coverage/build, browser journeys and independent review; canonical aggregate remains independently mandatory",
      "expected": "Dense plots and tables with truthful evidence and scoped verification; current canonical receipt determines aggregate acceptance",
      "rollback": "Revert only this correction; preserve previous user work",
      "status": "done"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    ".claude/rules/alpha-web.md",
    "docs/ARCHITECTURE.md",
    "docs/BUILD-STATUS.md",
    "apps/alpha-web/frontend/README.md"
  ],
  "out_of_scope": [
    "Backend endpoints and estimator changes",
    "Live capital routing",
    "Provider acquisition and user artifact modification",
    "Historical confirmation receipts"
  ]
}
```

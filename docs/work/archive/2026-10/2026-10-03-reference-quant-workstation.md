# Reference-matched quant workstation

**Delivery state:** Completed

**Acceptance (2026-10-05):** the canonical full gate passed on the frozen shared tree (stamp tree `54b7f96e`, 2026-10-04 13:46 UTC, all six components, 969 s); see the 2026-10-05 record in `docs/BUILD-STATUS.md`. Earlier state: Completed implementation; aggregate acceptance requires a current full-gate receipt.

Source: owner implementation plan, 2026-10-03. Branch: feat/crypto-terminal-ui.
Preserve the existing dirty tree. Primary visual authority: Desktop/ALPHA-terminal-designs
(1, 2, 3, 9). Qbot's pinned results panel informs plot/table composition only.
No backend endpoints, statistics or authority changes. Missing snapshots never fall back.

## Slices and verification
1. Typed workspace/source model, persistence and migration; pure Vitest tests.
2. Stable chart lifetime and panel controls; types and chart browser regressions.
3. ChartWorkspace, splitters, maximize and imperative UTC linking; Playwright.
4. Recorded interactive and scientific surfaces, report composition; types and browser tests.
5. Classic menus, toolbar, document tabs and consolidated CSS; viewport QA.
6. Docs, assets, independent review and full gate; coverage/build/e2e, real backend journeys
   and `uv run python scripts/gate.py full`.

Status: implementation and review corrections delivered. Acceptance is determined by fresh final-tree gate evidence. DAG unchanged; no metric calculations or RNG changes.

```json
{
  "schema_version": 1,
  "title": "Reference-matched quant workstation",
  "context": "Owner-authorised reference-style terminal with four independent analytical panels and backend-authored recorded evidence. Preserve existing dirty work.",
  "assumptions": [
    {
      "statement": "Existing APIs supply recorded research data without new estimators",
      "verified_by": "Typed projections, real CLI journeys and explicit missing-snapshot tests"
    }
  ],
  "alternatives_considered": [
    "Retain Lightweight Charts and local split layout rather than a new docking framework",
    "Use ALPHA mockups for appearance and Qbot only for plot/table organisation"
  ],
  "pre_mortem": [
    "Pinned sources must not follow unrelated canonical changes",
    "Chart reconstruction must not lose pan and zoom",
    "Run snapshot absence must remain explicit"
  ],
  "slices": [
    {
      "title": "Typed workspace and source model",
      "verify": "Vitest and source-isolation browser tests",
      "expected": "Validated four-panel presentation",
      "rollback": "Restore only workstation frontend changes; preserve backend and user work",
      "status": "done"
    },
    {
      "title": "Stable charts and linking",
      "verify": "Panned-range, maximize and asynchronous link regressions",
      "expected": "Mounted charts retain state",
      "rollback": "Restore only workstation frontend changes; preserve backend and user work",
      "status": "done"
    },
    {
      "title": "Recorded research and scientific surfaces",
      "verify": "Missing-price and backend projection browser tests",
      "expected": "Available evidence renders with gaps and provenance",
      "rollback": "Restore only workstation frontend changes; preserve backend and user work",
      "status": "done"
    },
    {
      "title": "Reference shell and review corrections",
      "verify": "Three viewport browser suites and independent review",
      "expected": "Compact chrome and functional routes",
      "rollback": "Restore only workstation frontend changes; preserve backend and user work",
      "status": "done"
    },
    {
      "title": "Final review and verification readiness",
      "verify": "Frontend lint, types, coverage, API generation, build, viewport regressions, performance and independent review; final acceptance uses uv run python scripts/gate.py full",
      "expected": "Current-tree acceptance requires successful aggregate receipt",
      "rollback": "Restore only workstation frontend changes; preserve backend and user work",
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

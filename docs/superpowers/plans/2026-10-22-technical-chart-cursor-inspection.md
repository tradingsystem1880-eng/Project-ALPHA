# Keyboard and tap inspection for the technical chart

**Delivery state:** Implementation and focused validation complete; independent review approved.

Selected scope: let users inspect the exact candle and already returned study values in the default Technical · Bokeh chart with keyboard navigation or a tap, using the chart's existing cursor/readout. Clear the active inspection when the chart is recomposed after a study change. Preserve Classic/Default chart grammar and the optional Market · Lightweight renderer. No backend/API change, new dependency, aggregation, or client-side study/P&L calculation.

Base: accepted commit `99f2d472dd4511b446e1198ae80201e7207d089d`; isolated checkout branch `work`, clean at start. No local `main` ref exists; `origin/main` is a different commit. Work is bound to the supplied accepted commit without switching refs.

```json
{
  "schema_version": 1,
  "title": "Keyboard and tap inspection for the technical chart",
  "context": "The default Bokeh renderer already updates the exact OHLCV header, backend study legends and linked UTC cursor on pointer hover. It has no keyboard path, a tap does not set the cursor, and overlay recomposition can leave the previous header value visible. Add a bounded inspection path over the same unaggregated candle and server-returned study arrays.",
  "assumptions": [
    {"statement": "Bokeh chart x values are native observation indexes; the renderer has exact index-to-UTC timestamps and candle rows.", "verified_by": "apps/alpha-web/frontend/src/components/technical/technicalRenderer.ts mountTechnicalChart: bars, times, indexOf, MouseMove cursor path and pointer tap coordinate inversion"},
    {"statement": "The overlay response aligns study values to exact candle UTC timestamps and represents warm-up/missing points as null.", "verified_by": "apps/alpha-web/frontend/src/components/technical/technicalRenderer.ts align; apps/alpha-web/frontend/e2e/support/technicalFixture.ts studySeries"},
    {"statement": "Existing page footer and chart source chip carry UTC, native quote/volume units, source/quality, as-of and snapshot/archive identity.", "verified_by": "apps/alpha-web/frontend/src/panels/PriceChart.tsx chart source chip and chart-foot"}
  ],
  "alternatives_considered": [
    "Add another chart library or compute study values in the browser: rejected because the current Bokeh cursor already renders exact backend values and no new renderer or calculation is needed.",
    "Change the optional Lightweight renderer or chart themes: rejected because this increment is specifically the missing keyboard/tap path in the existing default renderer."
  ],
  "pre_mortem": [
    "A tap could select an observation outside the current view; clamp the selected index to the visible ordinal range and exercise a real browser touch on the price panel.",
    "A stale readout could survive a study/style recomposition even if the old renderer is destroyed; assert that the cursor clears and the header returns to the last returned candle after changing the study selection.",
    "A keyboard listener could interfere with chart controls or change chart geometry; scope keys to the focusable chart host and capture both Classic and Default screenshots after exercising the interaction."
  ],
  "slices": [
    {
      "title": "Add bounded renderer cursor navigation and tap selection, with controller tests",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/components/technical/technicalRenderer.test.ts",
      "expected": "Controller selects exact visible observation indexes, clamps boundaries, clears on Escape, and reports the corresponding UTC timestamps; existing cross-chart linking still works.",
      "rollback": "Revert the cursor navigation and tap changes in technicalRenderer.ts and its renderer tests.",
      "files": ["apps/alpha-web/frontend/src/components/technical/technicalRenderer.ts", "apps/alpha-web/frontend/src/components/technical/technicalRenderer.test.ts"],
      "status": "done"
    },
    {
      "title": "Wire keyboard/tap inspection into TechnicalChart, clear on study recomposition, document and verify the running app",
      "verify": "cd apps/alpha-web/frontend && npx tsc -b && npm run lint -- --deny-warnings && npx playwright test e2e/technical-chart.spec.ts --project chromium-reference-only --no-deps",
      "expected": "Keyboard and touch select exact fixture candles/study values, null warm-up remains —, a study change clears selection, state/provenance labels remain visible, and Classic/Default screenshots retain the chart grammar.",
      "rollback": "Revert the TechnicalChart, workflow CSS, focused browser tests, user docs and generated static/app build changes.",
      "files": ["apps/alpha-web/frontend/src/components/technical/TechnicalChart.tsx", "apps/alpha-web/frontend/src/workflow.css", "apps/alpha-web/frontend/e2e/technical-chart.spec.ts", "apps/alpha-web/frontend/README.md", "CLAUDE.md", "docs/BUILD-STATUS.md", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    }
  ],
  "tier_impact": ["risk"],
  "docs_to_update": ["CLAUDE.md", "docs/BUILD-STATUS.md", "apps/alpha-web/frontend/README.md"],
  "out_of_scope": ["backend, API, CLI, data schema or scientific workflow changes", "new dependencies or renderer installation", "Lightweight Charts behavior or chart palette/theme changes", "live, private, holdout or externally sourced data"],
  "files": ["apps/alpha-web/src/alpha_web/static/app/**"]
}
```

## Deterministic acceptance fixture and checks

- Browser fixture: `walkBars(260, '2025-10-06', false)` from `e2e/support/technicalFixture.ts`, plus the existing `studySeries('sma:50', bars)` overlay stand-in. This is deterministic synthetic test data; it is not an executed research artifact.
- Exact identity/value checks: `End` shows the final fixture timestamp and OHLCV; `ArrowLeft` shows the preceding source candle and its matching `SMA(50)` value; `Home` shows the first timestamp and `—` for the SMA warm-up null. A browser touch tap over a candle selects that same source row and its aligned study value.
- Stale state: while an inspected bar is selected, uncheck the existing `MA 50` study in Indicators. After the replacement overlay response and chart recomposition, the cursor is cleared and the OHLC header is back on the final returned candle. No derived value is introduced.
- Provenance/state: assert visible UTC/native-unit footer and the source/quality chip; run deterministic loading, empty-bars, and candle-request failure cases and assert their existing truthful messages.
- Unit test: `cd apps/alpha-web/frontend && npx vitest run src/components/technical/technicalRenderer.test.ts`.
- Browser fixture and screenshot QA: `cd apps/alpha-web/frontend && ALPHA_TECHNICAL_SHOTS=/workspace/task-evidence/alpha-chart-inspection npx playwright test e2e/technical-chart.spec.ts --project chromium-reference-only --no-deps`. The screenshot run uses the local app with mocked deterministic API fixtures; it does not open or inspect research results.
- Build/type/lint: `cd apps/alpha-web/frontend && npm run build && npm run lint -- --deny-warnings`; rebuild updates the committed `static/app` package assets.

## Boundaries

The interaction only selects existing candle indexes and backend overlay indexes. It does not create price or study observations, join across missing times, aggregate bars, alter as-of semantics, or claim the synthetic test stand-in is research evidence. Existing chart source provenance and data-state behavior remain owned by `PriceChart`.

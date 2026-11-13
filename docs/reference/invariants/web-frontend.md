---
owner: web frontend
sources:
  - apps/alpha-web/frontend/src/**
  - apps/alpha-web/frontend/e2e/**
  - apps/alpha-web/frontend/package.json
  - apps/alpha-web/frontend/vite.config.ts
  - apps/alpha-web/frontend/vitest.config.ts
  - apps/alpha-web/frontend/playwright.config.ts
  - apps/alpha-web/frontend/scripts/normalize-build.mjs
  - scripts/run_frontend_browser_lanes.py
  - tests/integration/test_web_spa_assets.py
  - tests/unit/test_web_menu_groups.py
verified: 1ac86fc02443
---

# Web frontend invariants

Rules for the Workstation single-page app (SPA) in `apps/alpha-web/frontend/` (React, TypeScript, Vite, BokehJS,
Lightweight Charts). The backend it talks to is covered in [web-api.md](web-api.md).

## No authority in the browser

- The SPA computes no metric, verdict, signal, indicator value or rule result. It renders what the server returns,
  and shows server text (blocked reasons, watermarks, CLI errors) verbatim.
- Owner steps run only through `components/OwnerActionButton.tsx`, which calls the owner-auth challenge/perform
  routes. Steps an ADR keeps CLI-only get `components/CopyCommand.tsx` with the exact command (`CLI_ONLY` in
  `panels/researchCockpitModel.ts`). See [research-integrity § Owner authority](research-integrity.md#owner-authority).
- Never label local confirmation as verified physical presence.
  [ADR-0038](../../adr/0038-local-confirmation-and-terminal-archive-charts.md)
- The crypto/equities profile (`state/settings.ts`, `shell/profiles.ts`) is a display setting. It is never sent to the
  server and never grants anything. Selecting a project confers no research authority either.
- `explain/bands.ts` mirrors the grade bands in `packages/alpha-validation/src/alpha_validation/verdict.py` so the UI
  can explain a grade. The persisted manifest verdict is always authoritative; change both files together.
  Drift is caught by `src/explain/explain.test.ts`, which recomputes grades from real manifest fixtures.
- The Market Watch live ticker is display only: never stored, never read by anything else.

## Shell and navigation

- `App.tsx` renders workflow pages from `shell/workflowModel.ts`. URLs are `#page=...&pane=...` (plus `run=` for a
  run). Keep existing page and pane names stable — they are bookmarks and test targets.
- `shell/documents.ts` is the registry: one `DocumentDefinition` per `WindowId`, each holding panes.
  `workflowModel.DOCUMENT_PAGE` maps every `WindowId` to a page; `shell/profiles.ts` decides which windows a profile shows.
- Only the selected task panel mounts, so hidden panels do not poll. The exception is `ChartWorkspace`: once opened it
  stays mounted (hidden) so charts keep their captured context and range.
- `shell/menuModel.ts` `GROUP_MENU` must name every CLI command group the server's catalog serves, and no others. An
  unmapped group throws and blanks the menu bar. Enforced by `tests/unit/test_web_menu_groups.py`.
- Archive-chart identity belongs to `App`. Run, project, profile and stored-market navigation clear it.
- A control no capability backs renders disabled with the reason in its `title`; never a silent no-op.
- The toolbar status chip (`shell/statusModel.statusChip`) shows the strongest state: the selected run's research-gate
  watermark verbatim, else `Research gate open` for the linked project (reason in `title`), else `Paper only`.
- The project selector allows `No project — browse data`. A failed project inventory is shown as an error with retry,
  never as an empty list.

## Market data views

- Market Watch lists only profile-compatible symbols present in the stored inventory. Clicking one opens the canonical
  price chart and clears the date window, snapshot, run and archive context (`actions.openStoredMarket`).
- The venue comes from the stored `provenance.source`; a missing or `unknown` source shows `—`, never a guessed name.
  USD, USDT and USDC pairs are never merged ([data § Crypto identity and features](data.md#crypto-identity-and-features)).
- Every price is dated (Age column); rows older than two days are dimmed and a symbol without bars shows `—`. Daily %
  is a display change between the last two stored closes, not a metric.
- The opt-in live ticker polls only while the tab is visible. A failed, non-finite or mismatched quote leaves the stored
  close and its date in place.
- `components/AssetSelect.tsx` defaults to the canonical stored inventory; archive navigation is opt-in. A manually typed
  symbol is labelled `availability not verified` and is never treated as verified provider inventory.
- The Data Manager shows the Expansion SSD state honestly: not mounted is a named blocker, never a cached ready.
  `controlPlane.buildDataPullArgs` throws the date problem the CLI would reject.

## Charts

- Study values come only from `alpha chart overlays`. A study the CLI refuses (for example, longer than the window) is
  dropped by name; an overlay failure shows `overlays unavailable`. Never estimate a missing value.
- Never resample, aggregate or substitute bars in the browser. An interval needs a compatible recorded native source;
  there is no automatic venue or market substitution.
- Archive, run and snapshot contexts never silently fall back to canonical stored bars. A run without a recorded price
  snapshot cannot borrow current candles. Archive charts stay separate from strategy context.
- In `ChartWorkspace` (at most four panels) only the primary panel follows canonical market navigation. Comparison
  panels stay pinned, and changing a panel's source never changes canonical research context.
- Keep chart creation separate from option, evidence and selection updates; fit/reset happens only on request.
- Analytical panels default to the `scientific` (BokehJS) renderer; Lightweight Charts (`market`) is opt-in. The default
  `chartStyle` is `classic` (`components/technical/`).
- The technical chart spaces bars by observation. Where the series' own calendar (weekday or continuous) has no
  observation it draws a gap mark; it never interpolates a bar.
- Volume colouring uses exact native-index viewport intersections, including partly visible edge bars, and classifies
  up/down against the previous close (an unchanged close counts as up). Keep the full x/volume source.
- Price annotations keep unit isolation: only `unit: 'price'` annotations draw on the price pane.
- Bokeh views own standalone documents. Release the views and the document/model registries on cancel, failure and
  disposal.
- A canvas is invisible to a screen reader. Every canvas chart needs a real-markup alternative: `panels/ChartDataAlternative.tsx`
  for price bars, and `components/FigureCard.tsx` alt text, caveats and value tables for server figures.
- Never change timing budgets or aggregate bars to make a performance test pass. The `@perf-budget` specs run only with
  `ALPHA_PERF_BUDGETS=1` on an idle reference machine.
- Screenshot baselines are kept per platform (`*-darwin.png`, `*-linux.png`). Re-take Linux images in the Playwright
  Linux container; never copy macOS images over them.

## UTC and exact exports

- Show and export every timestamp in UTC. CSV exports use ISO-8601 UTC timestamps and the exact returned values —
  zero and negative kept, an empty cell for a missing value. Enforced by `src/panels/chartTableModel.test.ts` and
  `src/components/scientificPlotModel.test.ts`.
- Preserve backend null gaps; never join or fill them. Show a missing study value as `—`.
- Rounding is display-only (Market Watch shows 7 significant digits). Tables and exports keep exact values.
- Date windows (All / 30D / 90D / 1Y, custom) are display ranges over returned coverage. They never refetch or resample.

## Run detail binding

- `panels/rundetail/index.tsx` tags every async result with the `runId` and request id that asked for it, and renders
  only results for the currently selected run and its latest request. A previous run's summary, figures or trades
  must never show or export under the new run.
- States are explicit: no run selected → "Select a run"; error → the error; pending → "Loading run…". A trades request
  error stays distinct from a genuinely empty trades list.
  Enforced by `e2e/rundetail-trades-race.spec.ts`.
- `reportModel.summaryRows` shows recorded manifest values only (`not recorded` otherwise) — no client arithmetic.
- `reportModel.reportTree` keeps empty leaves visible with their reason. In the figure overlay a Copy the browser cannot
  do is disabled with the reason, and question, uncertainty and caveat prose stays in the DOM in both explain modes.
- The backtest result card is opt-in (`backtestResultCard` defaults to `false`). With malformed, legacy or failed evidence
  it renders as unavailable. Enforced by `e2e/backtest-result-card.spec.ts`.

## Generated API client

- `src/api/generated.ts` is generated from `openapi.json` by `npm run generate:api` (openapi-typescript). Never edit it
  by hand. `src/api/types.ts` gives readable aliases over its `components`.
- Change the backend first, regenerate `openapi.json` (see [web-api.md § API contract](web-api.md#api-contract)), then
  regenerate the client and commit both. The frontend gate fails if `generated.ts` differs after regeneration.
- The SPA owner-action union must match the server's closed action list minus `record_semantic_event`, which the
  browser never sends (`src/api/ownerActions.test.ts`, `tests/unit/test_web_owner_actions_drift.py`).

## Committed static bundle

- `apps/alpha-web/src/alpha_web/static/app/` is build output, committed so the Python wheel can serve it. Never edit it
  by hand.
- `npm run build` writes it (Vite `emptyOutDir`, base `/static/app/`) and `scripts/normalize-build.mjs` normalizes the
  text assets. Any change under `frontend/src` needs a rebuild committed in the same change; the frontend gate fails on
  a dirty `static/app` diff after its own build.
- Verify UI changes in the integrated app (`uv run alpha-web`). `npm run dev` serves assets only, with no API proxy.
- If `static/app/index.html` is missing the server answers 503 with a build hint
  (`tests/unit/test_web_port_config.py`); `tests/integration/test_web_spa_assets.py` checks the bundle is committed and served.

## Tests

- Vitest runs `src/**/*.test.ts` only, in the Node environment — no jsdom, no component tests. Put branch logic in pure
  `*Model.ts` modules next to their `*.test.ts`.
- Coverage is measured only over the pure-model files listed in `vitest.config.ts` (thresholds 85 % statements, lines and
  functions; 70 % branches). Add a new pure model to that list.
- Playwright specs live in `e2e/`. The default config starts its own real backend on port 8802
  (`ALPHA_PLAYWRIGHT_PORT`, never 8801) and refuses to reuse an unknown server. Its bars are labelled synthetic fixtures.
- Keep real-backend journeys separate from API-mocked scenarios. Mocked tests do not prove provider or owner acceptance.
- Three specs are excluded from default discovery and run only as their own lanes through
  `scripts/run_frontend_browser_lanes.py`: `risk-metric-basis`, `risk-live`, `native-result-real`. Do not run them under
  the default config or add filters to the lane command.
- Browser lanes run against a fresh build: `npm run build` before `npm run test:e2e:built` (the frontend gate's order).

## Adding a panel

1. Make the data a backend route first (see [web-api.md § Adding a route](web-api.md#adding-a-route)) and regenerate
   the client.
2. Write the component in `src/panels/`, with its logic in a pure `*Model.ts` plus tests.
3. Add it as a pane of a document in `shell/documents.ts`. A new `WindowId` also needs entries in `shell/profiles.ts`
   and `workflowModel.DOCUMENT_PAGE`.
4. Give canvas output an accessible table and exact UTC export; bind async data to the selected identity.
5. Run the frontend loop, rebuild, and commit `static/app` with the source.

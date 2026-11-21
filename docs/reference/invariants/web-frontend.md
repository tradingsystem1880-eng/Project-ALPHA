---
owner: web frontend
sources:
  - apps/alpha-web/frontend/index.html
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
verified: c8a2c1338d4a612d
---

# Web frontend invariants

Rules for the Workstation single-page app (SPA) in `apps/alpha-web/frontend/` (React, TypeScript, Vite, BokehJS,
Lightweight Charts). The backend it talks to is covered in [web-api.md](web-api.md).

On this page: [No authority in the browser](#no-authority-in-the-browser), [Shell and navigation](#shell-and-navigation), [Market data
views](#market-data-views), [Workstation themes](#workstation-themes-and-readability), [Charts](#charts), [UTC and exact
exports](#utc-and-exact-exports), [Run detail binding](#run-detail-binding), [Generated API client](#generated-api-client), [Built static
bundle](#built-static-bundle), [Tests](#tests), [Adding a panel](#adding-a-panel).

## No authority in the browser

- The SPA computes no metric, verdict, signal, indicator value or rule result. It renders what the server returns, and shows server text (blocked reasons,
  watermarks, CLI errors) verbatim.
- Owner steps run only through `components/OwnerActionButton.tsx`, which calls the owner-auth challenge/perform routes. Steps an ADR keeps CLI-only get
  `components/CopyCommand.tsx` with the exact command (`CLI_ONLY` in `panels/researchCockpitModel.ts`). See [research-integrity § Owner
  authority](research-integrity.md#owner-authority).
- Never label local confirmation as verified physical presence. [ADR-0038](../../adr/0038-local-confirmation-and-terminal-archive-charts.md)
- The crypto/equities profile (`state/settings.ts`, `shell/profiles.ts`) is a display setting. It is never sent to the server and never grants anything.
  Selecting a project confers no research authority either.
- No screen shows an A–F grade. The frontend holds no band table; the stored manifest `verdict` stays for old records and machines.
- The Market Watch live ticker is display only: never stored, never read by anything else.

## Shell and navigation

- `App.tsx` renders workflow pages from `shell/workflowModel.ts`. URLs are `#page=...&pane=...` (plus `run=` for a run). Keep existing page and pane names
  stable — they are bookmarks and test targets.
- `shell/documents.ts` is the registry: one `DocumentDefinition` per `WindowId`, each holding panes. `workflowModel.DOCUMENT_PAGE` maps every `WindowId` to a
  page; `shell/profiles.ts` decides which windows a profile shows.
- Only the selected task panel mounts, so hidden panels do not poll. The exception is `ChartWorkspace`: once opened it stays mounted (hidden) so charts keep
  their captured context and range.
- `shell/menuModel.ts` `GROUP_MENU` must name every CLI command group the server's catalog serves, and no others. An unmapped group throws and blanks the menu
  bar. Enforced by `tests/unit/test_web_menu_groups.py`.
- Archive-chart identity belongs to `App`. Run, project, profile and stored-market navigation clear it.
- A control no capability backs renders disabled with the reason in its `title`; never a silent no-op.
- The toolbar status chip (`shell/statusModel.statusChip`) shows the strongest state: the selected run's research-gate watermark verbatim, else `Research gate
  open` for the linked project (reason in `title`), else `Paper only`.
- The project selector allows `No project — browse data`. A failed project inventory is shown as an error with retry, never as an empty list. Loading settles
  after request or projection failure as well as an empty success; disposed reads cannot update the selector. Enforced by `src/shell/ContextBar.test.tsx`.

## Market data views

- Market Watch lists only profile-compatible symbols present in the stored inventory. Clicking one opens the canonical price chart and clears the date window,
  snapshot, run and archive context (`actions.openStoredMarket`).
- The venue comes from the stored `provenance.source`; a missing or `unknown` source shows `—`, never a guessed name. USD, USDT and USDC pairs are never
  merged ([data-crypto § Crypto identity and features](data-crypto.md#crypto-identity-and-features)).
- Every price is dated (Age column); rows older than two days are dimmed and a symbol without bars shows `—`. Daily % is a display change between the last two
  stored closes, not a metric.
- The opt-in live ticker polls only while the tab is visible. A failed, non-finite or mismatched quote leaves the stored close and its date in place.
- `components/AssetSelect.tsx` defaults to the canonical stored inventory; archive navigation is opt-in. A manually typed symbol is labelled `availability not
  verified` and is never treated as verified provider inventory.
- The Data Manager and status bar relay storage readiness without device names; blocked details remain visible. `controlPlane.buildDataPullArgs` throws the
  date problem the CLI would reject.
- The Market screen (Data & Assets › Market, pane `MarketOverview`, a workflow pane and not a document) shows stored bars from `GET
  /api/market/overview`. It is a display, not a research result: it says `Market view. Not a test result.` and prints `Data to:` with the last stored
  bar. It names its scan caps.
- Every Market tile and the all-lines chart share one scale by default (100 at the window start).
  A `Scale` selector lets the owner give each tile its own range; the page states the active scale in one line.
  Change numbers carry a direction mark and a direction colour, and the mark stays. `Differs most` marks the asset furthest from the group median
  (`panels/marketModel.differsMost`); it is neutral, never a good or bad colour. Tiles and rows are buttons that open the single-asset chart
  (`actions.openStoredMarket`). Colour is never the only signal. Enforced by `src/panels/MarketOverview.test.tsx`, `marketModel.test.ts`,
  `e2e/market-overview.spec.ts`.

## Today screen

- The Today screen (Research › Today, pane `FollowToday`, a workflow pane) shows `alpha follow today --json` from `GET /api/follow/today`.
  A selected card loads `GET /api/follow/{id}`. It computes nothing: decisions, readings, paper figures and the replay check
  are shown as the command gives them.
- It says `Paper only. Forward use; not research. Not advice.` Groups run NEW SIGNAL, OPEN PAPER POSITION, NOTHING TODAY,
  LATE OR MISSED, then WAITING. An empty group is one muted line. A behind or late card carries an icon and words,
  never colour alone. Up and down use ▲▼ as the Market view does.
- It has no buy or sell button and starts, updates or stops no follow. An empty list shows
  `alpha follow start --test <run id>` and `alpha results list`.
- The equity chart plots the entries `follow show` returns (newest 5): percent since the start, a dashed zero line,
  and a table below. Enforced by `src/panels/FollowToday.test.tsx`, `followTodayModel.test.ts`, `e2e/follow-today.spec.ts`.

## Workstation themes and readability

- Owner request, 2026-11-18: not all black; charts may stay dark. Top-bar Theme: Light (default), Dim, Dark (old terminal), applied before first paint.
- Owner decision, 2026-11-18 (later that day): UI design is deferred again. No restructure of the Workstation and no unprompted design proposals; only
  the RD-Agent view is reshaped, to the journey layout, which later result views reuse. When UI work resumes, ask the owner for reference screenshots
  ([log](../project/owner-decisions-5.md#2026-11-18-the-workstation-must-not-be-all-black-ui-design-waits)).
- Colours come from three palettes in `index.css`; type at least 14 px, prose line height 1.45, tabular monospace numbers. Body ink 7:1, other text 4.5:1.
- Browser charts read scoped chart tokens (`util/tokens.ts`): light in Light and Dim, each with a remembered **Dark chart** box. Stored images keep their
  recorded colours.
- No literal colours outside the palette declarations: `util/themeContract.test.ts` scans; `theme/theme.test.ts` checks contrast in all three themes.

## Charts

- Study values come only from `alpha chart overlays`. A study the CLI refuses (for example, longer than the window) is dropped by name; an overlay failure
  shows `overlays unavailable`. Never estimate a missing value.
- Never resample, aggregate or substitute bars in the browser. An interval needs a compatible recorded native source; there is no automatic venue or market
  substitution.
- Archive, run and snapshot contexts never silently fall back to canonical stored bars. A run without a recorded price snapshot cannot borrow current candles.
  The one exception is the small walk-forward chart on the Gates tab: it draws the bars stored now, cut at the run's last date,
  and its legend says the run's own bars were not saved.
  A rule test records no snapshot, so its price comes from the same exception: the bars stored now, cut at the research cut-off and the run's
  last date, drawn only when their source fingerprint equals the one the run recorded. Otherwise the pane says why (`bars_changed_since_run`,
  `price_not_saved_with_run`) and draws nothing. A bar at or after the cut-off is never read.
  Archive charts stay separate from strategy context.
- `components/tearsheet/TearSheetStack.tsx` draws one BokehJS grid from `GET /api/runs/{id}/series`: price with entry and exit markers,
  equity against buy and hold (Log toggle), and drawdown, on one x-range with one crosshair and one readout. Tested periods and
  walk-forward tests are shaded and named. It draws stored values only; the model (`tearSheetModel.ts`) computes no statistic. Colours come from the theme.
- In `ChartWorkspace` (at most four panels) only the primary panel follows canonical market navigation. Comparison panels stay pinned, and changing a panel's
  source never changes canonical research context.
- Keep chart creation separate from option, evidence and selection updates; fit/reset happens only on request.
- Analytical panels default to the `scientific` (BokehJS) renderer; Lightweight Charts (`market`) is opt-in. The default `chartStyle` is `classic`
  (`components/technical/`).
- The technical chart spaces bars by observation. Where the series' own calendar (weekday or continuous) has no observation it draws a gap mark; it never
  interpolates a bar.
- Volume colouring uses exact native-index viewport intersections, including partly visible edge bars, and classifies up/down against the previous close (an
  unchanged close counts as up). Keep the full x/volume source.
- Price annotations keep unit isolation: only `unit: 'price'` annotations draw on the price pane.
- Bokeh views own standalone documents. Release the views and the document/model registries on cancel, failure and disposal.
- A canvas is invisible to a screen reader. Every canvas chart needs a real-markup alternative: `panels/ChartDataAlternative.tsx` for price bars, and
  `components/FigureCard.tsx` alt text, caveats and value tables for server figures.
- Never change timing budgets or aggregate bars to make a performance test pass. The `@perf-budget` specs run only with `ALPHA_PERF_BUDGETS=1` on an idle
  reference machine.
- Screenshot baselines are kept per platform (`*-darwin.png`, `*-linux.png`). Re-take Linux images in the Playwright Linux container; never copy macOS images
  over them.

## UTC and exact exports

- Display timestamps through `util/formatTime.ts`: `17 Nov 2026, 14:33 UTC`, with raw ISO in the element title.
  Recorded durations use whole minutes/hours (`<1 min` below a minute). CSV exports keep ISO-8601 UTC and exact values —
  zero and negative kept, an empty cell for a missing value. Enforced by `src/panels/chartTableModel.test.ts` and
  `src/components/scientificPlotModel.test.ts`.
- Preserve backend null gaps; never join or fill them. Show a missing study value as `—`.
- Rounding is display-only (Market Watch shows 7 significant digits). Tables and exports keep exact values.
- Date windows (All / 30D / 90D / 1Y, custom) are display ranges over returned coverage. They never refetch or resample.

## Run detail binding
Moved to [web-run-detail.md § Run detail binding](web-run-detail.md#run-detail-binding).

## Generated API client

- `src/api/generated.ts` is generated from `openapi.json` by `npm run generate:api` (openapi-typescript). Never edit it
  by hand. `src/api/types.ts` gives readable aliases over its `components`.
- Change the backend first, regenerate `openapi.json` (see [web-api.md § API contract](web-api.md#api-contract)), then
  regenerate the client and commit both. The frontend gate fails if `generated.ts` differs after regeneration.
- The SPA owner-action union must match the server's closed action list minus `record_semantic_event`, which the
  browser never sends (`src/api/ownerActions.test.ts`, `tests/unit/test_web_owner_actions_drift.py`).

## Built static bundle

- `apps/alpha-web/src/alpha_web/static/app/` is build output and is not committed (git-ignored). Never edit it by hand.
  After a pull that changes `frontend/`, run `npm ci && npm run build` in `apps/alpha-web/frontend` before `alpha-web`.
- `npm run build` writes it (Vite `emptyOutDir`, base `/static/app/`) and `scripts/normalize-build.mjs` normalizes the
  text assets. CI builds it in every job that needs it; the alpha-web wheel ships it (hatch `artifacts`) and
  `scripts/wheel_smoke.py` fails a wheel built without it.
- Verify UI changes in the integrated app (`uv run alpha-web`). `npm run dev` serves assets only, with no API proxy.
- The API starts without a frontend build. The server mounts `/static` when the asset directory exists at startup.
  If `static/app/index.html` is missing, the SPA entry points answer 503 with a build hint
  (`tests/unit/test_web_port_config.py`); `tests/integration/test_web_spa_assets.py` checks the bundle is built and served.

## Tests

- Vitest runs `src/**/*.test.{ts,tsx}` in Node — no jsdom. Rendering/effect checks use Node and mocked hooks;
  put branch logic in pure `*Model.ts` modules next to their `*.test.ts`.
- Coverage is measured only over the pure-model files listed in `vitest.config.ts` (thresholds 85 % statements, lines and
  functions; 70 % branches). Add a new pure model to that list.
- Playwright specs live in `e2e/`. The default config starts its own real backend on port 8802
  (`ALPHA_PLAYWRIGHT_PORT`, never 8801) and refuses to reuse an unknown server. Its bars are labelled synthetic fixtures.
- Keep real-backend journeys separate from API-mocked scenarios. Mocked tests do not prove provider or owner acceptance.
- Three specs are excluded from default discovery and run only as their own lanes through
  `scripts/run_frontend_browser_lanes.py`: `risk-metric-basis`, `risk-live`, `native-result-real`. Do not run them under
  the default config or add filters to the lane command.
- Browser lanes run against a fresh build: `npm run build` before `npm run test:e2e:built` (the frontend gate's order).
  `--viewports reference` runs the default lane at the reference viewport only (pull-request CI, `gate.py component
  frontend`); `--viewports all`, the default, runs all four (nightly, `component frontend-full`).

## Adding a panel

1. Make the data a backend route first (see [web-api.md § Adding a route](web-api.md#adding-a-route)) and regenerate
   the client.
2. Write the component in `src/panels/`, with its logic in a pure `*Model.ts` plus tests.
3. Add it as a pane of a document in `shell/documents.ts`. A new `WindowId` also needs entries in `shell/profiles.ts`
   and `workflowModel.DOCUMENT_PAGE`.
4. Give canvas output an accessible table and exact UTC export; bind async data to the selected identity.
5. Run the frontend loop and rebuild; commit the source only (`static/app` is build output).

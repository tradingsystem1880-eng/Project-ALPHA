---
owner: web workstation
sources:
  - apps/alpha-web/src/alpha_web/*.py
  - apps/alpha-web/src/alpha_web/api/**
  - apps/alpha-web/frontend/index.html
  - apps/alpha-web/frontend/src/**
  - apps/alpha-web/frontend/package.json
verified: c2dcf32acfe529b5
---

# alpha-web: code map and change loop

Where things are in the Workstation, and how a change to it is checked. The routing page is [CONTEXT.md](CONTEXT.md).

## Code map

The ALPHA Workstation: a local FastAPI backend (JSON and server-sent events) in
`apps/alpha-web/src/alpha_web/` and a React single-page app in `apps/alpha-web/frontend/`. It sits
on top of the import graph: it imports only `alpha_core` and public `alpha_cli` seams (import-linter
contracts "alpha_web imports only public platform surfaces" and "alpha_web sits atop the DAG"), and
runs `alpha` as a subprocess for every action. It never runs the engine, reads SQLite itself, or
grants authority.

- Backend code: `apps/alpha-web/src/alpha_web/` (routes in `api/`; copy a sibling such as `api/native_results.py` with its adapter
  `_native_results.py`; response models are one module per area in `api/models/`, not one big file). Frontend: `frontend/src/` (`panels/`, `shell/`,
  `components/`, `api/`). The built bundle `src/alpha_web/static/app` is
  build output, not committed; `npm ci && npm run build` writes it, and must run before serving or building the wheel. Never edit it by hand.
- Backend tests: `tests/unit/test_web_*.py`, `tests/integration/test_web_api_*.py`,
  `tests/integration/test_openapi_safe_routes.py`. Frontend unit tests sit next to the code as
  `frontend/src/**/*.test.{ts,tsx}` (vitest, Node, no jsdom); browser tests in `frontend/e2e/` (Playwright).
- RD-Agent's read-only panel is `panels/RdAgentPanel.tsx`, registered in `shell/documents.ts`,
  `profiles.ts` and `workflowModel.ts`; the registry supplies View and the command palette.
  Run and step times use `util/formatTime.ts` (UTC text, original ISO on hover).
  The run reader and its journey/PNG routes share the read-only router in `api/rdagent.py`.
  `panels/RdAgentJourney.tsx` renders the selected idea's seven stored steps and wraps code excerpts.
  The run summary shows recorded values. Unit tests sit beside both panels.
  The browser interaction spec is `e2e/rdagent-journey.spec.ts`.
  Field sources and limits: [API](../../docs/reference/invariants/web-api-reads.md#reads-and-writes),
  [journey view](../../docs/reference/invariants/web-run-detail.md#run-detail-binding).
- The rule-test Summary uses `panels/ruleTestModel.ts` and `panels/rundetail/RuleTestReport.tsx`. Its "Checks run on this test" section reads `GET /api/runs/{id}/checks` (`_checks.py`, which relays `alpha results show`).
- The reading block (`components/ReadingBlock.tsx`, model `panels/readingModel.ts`) is used by `RuleTestReport.tsx` and `SetupLabPanel.tsx`. The rule-test reading
  and the declared or exploratory word come with `GET /api/runs/{id}/checks` (`_checks.py`); Setup Lab's come from `alpha setup show` (`_setup_runs.py`). Browser spec: `e2e/reading-block.spec.ts`.
- The other places that show a run's reading (Navigator run list `panels/navigatorModel.ts`, Pipeline, activity feed, toasts, command palette, Gates tab
  `explain/gates.ts`, Summary and edge review rows) use the helpers in `panels/readingModel.ts`. Rules: [readings in the remaining places](../../docs/reference/invariants/web-run-detail.md#readings-in-the-remaining-places). Specs: `panels/readingEverywhere.test.tsx`, `e2e/readings-everywhere.spec.ts`.
- The Gates tab charts (`panels/rundetail/WalkForward.tsx`, `CheckCharts.tsx`, `NullChart.tsx`; pure models `walkForwardModel.ts`, `checkChartModel.ts`, `nullChartModel.ts`; reads in `useCheckChartData.ts`) use `GET /api/candles` and `GET /api/runs/{id}/nulls`, no new route. Browser spec: `e2e/check-charts.spec.ts`.
- The Market screen (Data & Assets › Market) is `panels/MarketOverview.tsx` with pure helpers in `panels/marketModel.ts`. It reads `GET /api/market/overview`
  (`api/market.py`, `api/models/market.py`), which relays `alpha data market-overview` (`apps/alpha-cli/src/alpha_cli/market_overview_cmds.py`). Browser spec: `e2e/market-overview.spec.ts`.
  Rules: [Market data views](../../docs/reference/invariants/web-frontend.md#market-data-views), [reads](../../docs/reference/invariants/web-api-reads.md#market-overview-read).
- The Today screen (Research › Today) is `panels/FollowToday.tsx` with helpers in `panels/followTodayModel.ts`. It reads `GET /api/follow/today` and
  `GET /api/follow/{id}` (`api/follow.py`, `api/models/follow.py`), which relay `alpha follow today|show`. Browser spec: `e2e/follow-today.spec.ts`.
  Rules: [Today screen](../../docs/reference/invariants/web-frontend.md#today-screen), [reads](../../docs/reference/invariants/web-api-reads.md#follow-today-read).
- Setup Lab ([component page](../../docs/reference/project/components/setup-lab.md); Research → Setup Lab), Kronos Studio (View → Forecast): [fields](../../docs/reference/invariants/web-api-reads.md#reads-and-writes).
- Tests: a backend test for every route (including the CLI-failure path), a vitest model test for
  new panel logic, and a browser spec when a page's behaviour changes.

## Change loop

- After a backend route change, from the repository root:
  1. `uv run python scripts/generate_web_openapi.py` (rewrites `frontend/openapi.json`);
  2. `uv run python scripts/check_openapi_operations.py --write` (operation classification and
     `docs/governance/capability-authority-matrix.md`);
  3. `uv run python scripts/gate.py check`.
- Frontend loop, in `apps/alpha-web/frontend`: `npm ci`; `npm run generate:api`;
  `npm run lint -- --deny-warnings`; `npm run build` (also rebuilds the served bundle);
  `npm run test:coverage`; browser lanes `npm run test:e2e:built`. Commit `src/api/generated.ts`
  with the source. For appearance changes, follow the [theme contract](../../docs/reference/invariants/web-frontend.md#workstation-themes-and-readability).
- CI runs the whole loop as `uv run python scripts/gate.py component frontend`; it fails if the
  generated client differs from what is committed.
- Regenerated `frontend/openapi.json`, `src/api/generated.ts`, the static bundle and the governance
  classification, as above.

## Also read
| Read | Section | When |
|---|---|---|
| [command reference](../../docs/reference/commands.md) | — | finding the `alpha` command a route should call |
| [Setup Lab](../../docs/reference/project/components/setup-lab.md) | To change this screen | any Setup Lab screen work: files, loop, tests, screenshots |
| [frontend README](frontend/README.md) | — | taking or checking screenshots of any other screen (2% tolerance, Linux container, test backend port 8802) |

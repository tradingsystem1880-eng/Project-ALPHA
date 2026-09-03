**Delivery state:** In progress (2026-09-03; P1–P5 on `feat/trader-terminal-phase1-work`, PR #47).

# Trader Terminal — Phase 4 "Pixel": artboard-exact chrome, honest live Market Watch, one-click owner actions

```json
{
  "schema_version": 1,
  "title": "Trader Terminal Phase 4 (Pixel): artboard-exact chrome, Market Watch with venue/age and an opt-in public ticker, owner-action buttons wherever the UI says owner approval is needed, full real-backend acceptance",
  "context": "Phase 3 (docs/superpowers/plans/2026-09-03-trader-terminal-phase3-terminal.md) shipped the terminal shell; the owner opened it on 2026-09-03 and rejected it on three grounds: Market Watch reads as duplicated assets with a stale price shown as current (BTC/USDT Binance and BTC/USD Coinbase are two stored pairs; 93,354 is the 2026-06-30 stored close), the chrome does not match the approved artboards in /Users/hunternovotny/Desktop/ALPHA-terminal-designs (1-Terminal, 2-Strategy-Performance-Report, 3-Chart-maximised, 4-Governance-window, Option E palette), and every 'needs owner approval / Touch ID / trusted CLI' notice is a dead end although the owner-auth REST vocabulary already carries launch_d1, launch_d2, revise_exploration and record_final_disposition. Owner decisions (2026-09-03): one row per stored pair with the venue shown; live public ticker, opt-in, stored close plus its date as the fallback; reproduce every artboard element, disabled with a reason where no capability backs it; every blocked state gets a button that completes the step (Touch ID) or, where an ADR keeps it CLI-only, a Copy-command button. No statistic, point-in-time reader, DAG edge, MCP tool or authority changes.",
  "assumptions": [
    {
      "statement": "The candles projection already carries the venue: `provenance.source` is `ccxt:<exchange>` for ccxt pulls and the provider id otherwise, so Market Watch can label each stored pair's venue from the `?tail=2` read it already makes, without a new symbols projection.",
      "verified_by": "curl of GET /api/candles/XRP%2FUSDT on 2026-09-03 (source `ccxt:binance`, knowledge_cutoff 2026-06-30) and apps/alpha-web/src/alpha_web/api/candles.py."
    },
    {
      "statement": "A public ccxt ticker read needs no key and no ADR: it is comparison-only, never stored, never a data authority, and follows the read-only network pattern of `alpha data first-bar` (CCXTAdapter.first_bar, data_cmds.py:163, catalog.py:37).",
      "verified_by": "read of packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py:136-240 and apps/alpha-cli/src/alpha_cli/data_cmds.py:163-180 on 2026-09-03; P2 adds `@pytest.mark.network` live tests and offline fake-exchange tests."
    },
    {
      "statement": "Chrome fonts and colours are hand-written CSS (index.css); the canvas tokens and terminal_classic.json (quant tier) stay untouched, so Phase 4 carries no /verify-quant or /review-gate obligation.",
      "verified_by": "read of apps/alpha-web/frontend/src/theme.generated.css, src/util/theme.drift.test.ts and tests/unit/test_theme_drift.py on 2026-09-03."
    },
    {
      "statement": "The owner-auth challenge/perform routes dispatch launch_d1 → `alpha research run deep`, launch_d2 → `alpha research run confirm`, record_final_disposition → `alpha research decide`, revise_exploration → `alpha research propose --answer …` under one Touch ID receipt; the SPA only lacks buttons for them. Holdout reveal and the reviewed-asset master stay CLI-only by ADR-0021/0026/0032.",
      "verified_by": "read of apps/alpha-web/src/alpha_web/api/owner_auth.py:38-52,183-200 and apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx:344-437 on 2026-09-03; P4 adds a drift test between the SPA action list and OWNER_ACTION_TYPES."
    }
  ],
  "alternatives_considered": [
    "One Market Watch row per base asset (hide the Coinbase USD pair): rejected by the owner and by the crypto rule that USD and USDT pairs are never merged; the artboard itself lists BTCUSDT and BTCUSD.",
    "Show the stored close only with its date and no live quote: rejected by the owner — a trader's Market Watch must be able to read a current price; the ticker is opt-in and clearly labelled `live`.",
    "Omit artboard controls that have no capability (window glyphs, Alerts, Favorites): rejected by the owner — they are drawn disabled with the reason in the tooltip.",
    "Move the profile/symbol invariant into the settings store: rejected — the store knows nothing of the linked context; the App effect is the one home of the rule (simplify pass 09a9ea7)."
  ],
  "pre_mortem": [
    "The ticker poll runs behind a hidden tab or after the toggle is off: the pure `shouldPoll(live, visible)` gate is unit-tested and the interval is cleared on toggle-off/visibilitychange; e2e asserts no `/api/data/ticker` request when the toggle is off.",
    "A ticker from Binance is shown for a Coinbase pair: the venue comes from the pair's own provenance, the ticker request carries that exchange, and the response symbol/exchange must echo the request or the row falls back to the stored close.",
    "The chrome rewrite breaks axe (icon-only buttons, dock close/pin targets): every icon button carries an aria-label and 24px min target; chromium-minimum runs in every slice.",
    "The twenty screenshot baselines churn twice: P3a and P3b re-baseline once, at the end of P3b, then a clean run proves stability.",
    "Owner-action buttons could imply authority the browser does not have: buttons only call the existing challenge/perform routes; blocked reasons are relayed verbatim; CLI-only steps copy the exact argv and name the ADR.",
    "static/app or openapi.json forgotten: every slice ends with the build and `git status --short` of both.",
    "The real-backend walkthrough needs network (pull, ticker): it runs on the owner's machine with the network marker and reports failures verbatim; the offline gate never depends on it."
  ],
  "slices": [
    {
      "title": "P1 Market Watch tells the truth: venue, age, artboard row anatomy",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/panels/marketWatchModel.test.ts && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "watchRow reads bars + provenance: label without the slash (BTCUSDT), venue (Binance/Coinbase/Tiingo…), last, daily %, asOf date and a stale flag (older than two days); rows render ▲/▼ by tone, a blue selection row, a venue cell and an Age cell showing the bar date; Details lists every stored quote of the selected base asset with venue and date; a `+ click to add…` row opens the Data Manager and focuses its symbol field. No price is ever invented.",
      "rollback": "Revert the slice commit.",
      "files": ["apps/alpha-web/frontend/src/panels/marketWatchModel.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.test.ts", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/src/panels/actions.ts", "apps/alpha-web/frontend/src/App.tsx", "apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "P2 live public ticker, opt-in: CCXTAdapter.fetch_ticker → alpha data ticker → GET /api/data/ticker → Market Watch Live toggle",
      "verify": "uv run pytest -q tests/unit/test_ccxt_adapter_ticker.py tests/unit/test_cli_data_ticker.py tests/integration/test_web_api_catalog.py -m \"not network\" && uv run python scripts/generate_web_openapi.py --check && uv run python scripts/check_openapi_operations.py && cd apps/alpha-web/frontend && npm run generate:api && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "A read-only public quote seam that fails loud (unknown market, missing last, non-ccxt source → typed error/422/404); the Market Watch header reads `Market Watch: HH:MM:SS`, a persisted Live toggle polls every 10 s only while on and the tab is visible, rows show `live` in the Age cell with the ticker's last and fall back to the stored close and date when the read fails; equities tickers keep the stored close.",
      "rollback": "Revert the slice commit; the route is additive.",
      "files": ["packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py", "tests/unit/test_ccxt_adapter_ticker.py", "apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/test_cli_data_ticker.py", "apps/alpha-web/src/alpha_web/_catalog.py", "apps/alpha-web/src/alpha_web/api/catalog.py", "apps/alpha-web/src/alpha_web/api/models.py", "tests/integration/test_web_api_catalog.py", "apps/alpha-web/frontend/openapi.json", "apps/alpha-web/frontend/src/api/generated.ts", "apps/alpha-web/frontend/src/api/client.ts", "apps/alpha-web/frontend/src/api/types.ts", "apps/alpha-web/frontend/src/state/settings.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.test.ts", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/src/alpha_web/static/app/**", "docs/governance/openapi-operation-classification.json", "docs/governance/capability-authority-matrix.md"],
      "status": "done"
    },
    {
      "title": "P3a artboard-exact shell: fonts, title bar, icon toolbar, dock headers with bottom tabs, Navigator glyphs and counts, document header, Toolbox table, status bar wording",
      "verify": "cd apps/alpha-web/frontend && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "Chrome matches 1-Terminal.png: system UI 12px tabular numerals; title `ALPHA Terminal — Crypto — [BTCUSDT,D1]` with disabled window glyphs; toolbar of chart-type/timeframe/zoom/crosshair/grid/action icon buttons (chart controls applied in PriceChartCanvas), `Profile` combo, symbol combo, `Search Ctrl+K` field, lock `Paper only` chip, shield `Governance`; New Idea in the Research menu and palette; Guided/Advanced and Settings in the View menu; dock headers with pin (disabled) and close (hides; View › Docks restores) and tabs at the bottom (Market Watch Symbols·Details·Data, Navigator Common·Favorites, Data Manager Pull·Snapshots·Quality·Storage, Toolbox Jobs N·Trades·Backtests·Data pulls·Log·Alerts); Navigator folder/document glyphs and `Binance (N pairs)` counts; document header bar with minimise/maximise/close; Toolbox `Time | Job | Status | Detail | ✓` table; status bar `For Help, press F1 | Profile: … | <venues ✓> | Expansion SSD … | Paper only · no live routing | <UTC> | O: H: L: C: V: | n / n bars`. axe clean at 1280/1440/wide.",
      "rollback": "Revert the slice commit.",
      "files": ["apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/src/App.tsx", "apps/alpha-web/frontend/src/shell/**", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/src/panels/Navigator.tsx", "apps/alpha-web/frontend/src/panels/navigatorModel.ts", "apps/alpha-web/frontend/src/panels/navigatorModel.test.ts", "apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/panels/JobMonitor.tsx", "apps/alpha-web/frontend/src/panels/jobTableModel.ts", "apps/alpha-web/frontend/src/panels/jobTableModel.test.ts", "apps/alpha-web/frontend/src/components/PriceChartCanvas.tsx", "apps/alpha-web/frontend/src/components/ContextBar.tsx", "apps/alpha-web/frontend/src/context/chartControls.ts", "apps/alpha-web/frontend/src/components/CommandPalette.tsx", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/frontend/e2e/real-backend.spec.ts", "apps/alpha-web/frontend/e2e/crypto-data.spec.ts", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "P3b artboard-exact documents: report toolbar and tree, Governance table, figure maximise header; re-baseline",
      "verify": "cd apps/alpha-web/frontend && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --update-snapshots=all && npm run test:e2e && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "Report matches 2-Strategy-Performance-Report.png (toolbar Export CSV · Save PNG · Compare… · Run again · Notes; tree with glyphs and counts; summary table left, figures right); Governance matches 4-Governance-window.png (page list with counts, Item·State·Detail table, glossary filter); the figure overlay matches 3-Chart-maximised.png; twenty document baselines replaced and a clean four-project run is green.",
      "rollback": "Revert the slice commit and restore the previous baselines.",
      "files": ["apps/alpha-web/frontend/src/panels/rundetail/**", "apps/alpha-web/frontend/src/panels/reportModel.ts", "apps/alpha-web/frontend/src/panels/reportModel.test.ts", "apps/alpha-web/frontend/src/panels/Governance.tsx", "apps/alpha-web/frontend/src/panels/governanceModel.ts", "apps/alpha-web/frontend/src/panels/governanceModel.test.ts", "apps/alpha-web/frontend/src/components/FigureOverlay.tsx", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/frontend/e2e/workstation.spec.ts-snapshots/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "P4 every blocked state has a button: OwnerActionButton, launch_d1/launch_d2/revise/disposition wired, gate-lock next step, Copy command for CLI-only steps, Enroll Touch ID",
      "verify": "uv run pytest -q tests/unit/test_web_owner_actions_drift.py -m \"not network\" && cd apps/alpha-web/frontend && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "Wherever the SPA prints an owner/Touch ID/blocked notice there is a button: Touch ID · launch D1 / launch D2 / record decision / revise answers (challenge → WebAuthn → perform, relayed errors verbatim), the research-gate lock offers the case's current owner step beside `Open research case`, CLI-only steps (holdout reveal, reviewed-asset master, credential recovery) offer `Copy command` naming the ADR, and an unenrolled owner is sent to /owner-auth/enroll. A unit test pins the SPA's action list to OWNER_ACTION_TYPES.",
      "rollback": "Revert the slice commit; the backend is unchanged.",
      "files": ["apps/alpha-web/frontend/src/components/OwnerActionButton.tsx", "apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx", "apps/alpha-web/frontend/src/panels/researchCockpitModel.ts", "apps/alpha-web/frontend/src/panels/researchCockpitModel.test.ts", "apps/alpha-web/frontend/src/panels/V3Workbenches.tsx", "apps/alpha-web/frontend/src/panels/useLinkedProjectGate.ts", "apps/alpha-web/frontend/src/panels/StrategyLab.tsx", "apps/alpha-web/frontend/src/panels/Governance.tsx", "apps/alpha-web/frontend/src/panels/governanceModel.ts", "apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/panels/EvidenceHub.tsx", "apps/alpha-web/frontend/src/auth/ownerAuth.ts", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "tests/unit/test_web_owner_actions_drift.py", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "P5 prove everything and ship: full gates, real-backend acceptance in both profiles, docs, PR #47 green and merged",
      "verify": "uv run python scripts/gate.py full && cd apps/alpha-web/frontend && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npm run build && npm run test:e2e && cd ../../.. && uv run pytest -q tests/unit/test_documentation_truth.py tests/unit/test_claude_md_relocation.py -m \"not network\" && uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-09-04-trader-terminal-phase4-pixel.md && gh pr checks 47",
      "expected": "Every gate green; the scripted real-backend walkthrough (both profiles, every document and dock tab, Market Watch venue/age/live, an XRP/USDT Binance pull landing in the Toolbox, a validate run opening its report) exits 0 with its screenshots beside the artboards; rule rows, BUILD-STATUS, spec addendum and findings #14–#16 updated; PR #47 CI green and merged with a merge commit; the terminal launched for the owner.",
      "rollback": "Docs-only revert; the merge is the owner's decision.",
      "files": [".claude/rules/alpha-web.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md", "docs/superpowers/plans/2026-09-04-trader-terminal-phase4-pixel.md"],
      "status": "pending"
    }
  ],
  "tier_impact": ["protected", "dag"],
  "docs_to_update": [".claude/rules/alpha-web.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md"],
  "out_of_scope": [
    "Live trading, broker readiness, order routing; the ticker is a displayed quote, never an execution price or a stored series.",
    "New statistics, new providers beyond the public ccxt ticker, new MCP tools (pinned at 62), new ADRs.",
    "Intraday timeframes (buttons stay disabled with the reason).",
    "Making holdout reveal, the reviewed-asset master or credential recovery browser actions (ADR-bound CLI steps; the UI copies the command).",
    "Automating Touch ID itself in tests (WebAuthn is stubbed in e2e; the owner presses the sensor once)."
  ],
  "files": ["apps/alpha-web/**", "packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py", "apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/**", "tests/integration/test_web_api_catalog.py", ".claude/rules/alpha-web.md", "docs/**"]
}
```

## Context

The owner's second walkthrough (2026-09-03) rejected Phase 3 on truthfulness (Market Watch),
fidelity (artboards) and usability (dead-end owner notices). Phase 4 fixes all three without
moving any statistic, reader, DAG edge, MCP tool or authority.

## Deviations
* **P1** — the Market Watch table gained a `Venue` and an `Age` column (the artboard has only
  Symbol · Last · Daily %) because the owner's two complaints — "duplicates" and "that is not
  today's price" — are answered by exactly those two cells; the artboard's three-column look is
  kept for the row anatomy (▲/▼ glyph, blue selection, `+ click to add…`). Rows are keyed by the
  stored symbol and spelled without the slash. `symbolFitsProfile` stays the only market filter.
* **P2** — `alpha data ticker` is ccxt-only like `first-bar`; equities tickers keep the stored
  close. The Live toggle lives in `alpha.settings` (`liveTicker`, default off) and the poll clears
  its overlay the moment it is switched off, so a stale live price can never linger. The generated
  `docs/governance/openapi-operation-classification.json` and `capability-authority-matrix.md`
  were rewritten by `check_openapi_operations.py --write` for the one new read-only GET.
* **P3a** — the chrome typeface is the platform UI face at 12px (`--chrome-font-size`; 11px at the
  1280px minimum so every material question still fits the 720px viewport) — the generated canvas
  tokens are untouched. Docks are 300px/345px (artboard 278/345) so the five Market Watch columns
  fit; the `Age` cell prints days since the bar (`65d`, `live`) with the exact bar date in its
  title and in the Details tab, because a full ISO date did not fit the dock. Guided/Advanced,
  New Idea, Settings and the dock toggles live in the View/Research menus as the artboard has no
  toolbar buttons for them; the ⚙ settings popover stays as the last toolbar glyph. Market Watch
  row buttons keep a 24px hit target (axe target-size) so rows are ~26px, not the artboard's 21px.
  The Data Manager's `Snapshots` tab, the Navigator's `Favorites`, the Toolbox `Alerts` tab, the
  toolbar `Stop`, the dock pin and the title-bar window glyphs are rendered disabled with the
  reason in their tooltip — nothing behind them exists yet.
* **P3b** — the report toolbar is `Export CSV · Save PNG · Compare… · Run again · Notes` plus a
  disabled save glyph (a run directory is already immutable on disk) and a print glyph: Export CSV
  writes the trades projection verbatim (`tradesCsv`), Save PNG hands over the first drawable figure
  of the current view through the bare `…/image?fmt=png` endpoint, Compare… opens the Compare
  document (the run is ticked there — Compare keeps its own selection), Notes toggles the existing
  narrative/terse explanation setting. The Governance table is `Item | State | Detail`; providers
  and storage rows split state from detail while the five hazard sentences stay verbatim in State.
  Page labels carry the artboard counts (`Research gates (1 open)`, `Overrides (N)`,
  `Glossary (N)`). The figure overlay fills the window with a `<figure> — <run> (maximised)`
  header, zoom in/out/fit that scales the served SVG in the browser (nothing is redrawn) and
  `Esc restores · run <8> · UTC`; the focus trap now walks Save PNG → Save SVG → Copy → Close →
  Zoom in. The Toolbox opens by default only on windows ≥960px tall (the artboard is 991px) so the
  1440×900 reference keeps every material research question in view. Twenty document baselines
  re-taken."status": "done"* In progress (2026-09-03; P1–P5 on `feat/trader-terminal-phase1-work`, PR #47).

# Trader Terminal — Phase 4 "Pixel": artboard-exact chrome, honest live Market Watch, one-click owner actions

```json
{
  "schema_version": 1,
  "title": "Trader Terminal Phase 4 (Pixel): artboard-exact chrome, Market Watch with venue/age and an opt-in public ticker, owner-action buttons wherever the UI says owner approval is needed, full real-backend acceptance",
  "context": "Phase 3 (docs/superpowers/plans/2026-09-03-trader-terminal-phase3-terminal.md) shipped the terminal shell; the owner opened it on 2026-09-03 and rejected it on three grounds: Market Watch reads as duplicated assets with a stale price shown as current (BTC/USDT Binance and BTC/USD Coinbase are two stored pairs; 93,354 is the 2026-06-30 stored close), the chrome does not match the approved artboards in /Users/hunternovotny/Desktop/ALPHA-terminal-designs (1-Terminal, 2-Strategy-Performance-Report, 3-Chart-maximised, 4-Governance-window, Option E palette), and every 'needs owner approval / Touch ID / trusted CLI' notice is a dead end although the owner-auth REST vocabulary already carries launch_d1, launch_d2, revise_exploration and record_final_disposition. Owner decisions (2026-09-03): one row per stored pair with the venue shown; live public ticker, opt-in, stored close plus its date as the fallback; reproduce every artboard element, disabled with a reason where no capability backs it; every blocked state gets a button that completes the step (Touch ID) or, where an ADR keeps it CLI-only, a Copy-command button. No statistic, point-in-time reader, DAG edge, MCP tool or authority changes.",
  "assumptions": [
    {
      "statement": "The candles projection already carries the venue: `provenance.source` is `ccxt:<exchange>` for ccxt pulls and the provider id otherwise, so Market Watch can label each stored pair's venue from the `?tail=2` read it already makes, without a new symbols projection.",
      "verified_by": "curl of GET /api/candles/XRP%2FUSDT on 2026-09-03 (source `ccxt:binance`, knowledge_cutoff 2026-06-30) and apps/alpha-web/src/alpha_web/api/candles.py."
    },
    {
      "statement": "A public ccxt ticker read needs no key and no ADR: it is comparison-only, never stored, never a data authority, and follows the read-only network pattern of `alpha data first-bar` (CCXTAdapter.first_bar, data_cmds.py:163, catalog.py:37).",
      "verified_by": "read of packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py:136-240 and apps/alpha-cli/src/alpha_cli/data_cmds.py:163-180 on 2026-09-03; P2 adds `@pytest.mark.network` live tests and offline fake-exchange tests."
    },
    {
      "statement": "Chrome fonts and colours are hand-written CSS (index.css); the canvas tokens and terminal_classic.json (quant tier) stay untouched, so Phase 4 carries no /verify-quant or /review-gate obligation.",
      "verified_by": "read of apps/alpha-web/frontend/src/theme.generated.css, src/util/theme.drift.test.ts and tests/unit/test_theme_drift.py on 2026-09-03."
    },
    {
      "statement": "The owner-auth challenge/perform routes dispatch launch_d1 → `alpha research run deep`, launch_d2 → `alpha research run confirm`, record_final_disposition → `alpha research decide`, revise_exploration → `alpha research propose --answer …` under one Touch ID receipt; the SPA only lacks buttons for them. Holdout reveal and the reviewed-asset master stay CLI-only by ADR-0021/0026/0032.",
      "verified_by": "read of apps/alpha-web/src/alpha_web/api/owner_auth.py:38-52,183-200 and apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx:344-437 on 2026-09-03; P4 adds a drift test between the SPA action list and OWNER_ACTION_TYPES."
    }
  ],
  "alternatives_considered": [
    "One Market Watch row per base asset (hide the Coinbase USD pair): rejected by the owner and by the crypto rule that USD and USDT pairs are never merged; the artboard itself lists BTCUSDT and BTCUSD.",
    "Show the stored close only with its date and no live quote: rejected by the owner — a trader's Market Watch must be able to read a current price; the ticker is opt-in and clearly labelled `live`.",
    "Omit artboard controls that have no capability (window glyphs, Alerts, Favorites): rejected by the owner — they are drawn disabled with the reason in the tooltip.",
    "Move the profile/symbol invariant into the settings store: rejected — the store knows nothing of the linked context; the App effect is the one home of the rule (simplify pass 09a9ea7)."
  ],
  "pre_mortem": [
    "The ticker poll runs behind a hidden tab or after the toggle is off: the pure `shouldPoll(live, visible)` gate is unit-tested and the interval is cleared on toggle-off/visibilitychange; e2e asserts no `/api/data/ticker` request when the toggle is off.",
    "A ticker from Binance is shown for a Coinbase pair: the venue comes from the pair's own provenance, the ticker request carries that exchange, and the response symbol/exchange must echo the request or the row falls back to the stored close.",
    "The chrome rewrite breaks axe (icon-only buttons, dock close/pin targets): every icon button carries an aria-label and 24px min target; chromium-minimum runs in every slice.",
    "The twenty screenshot baselines churn twice: P3a and P3b re-baseline once, at the end of P3b, then a clean run proves stability.",
    "Owner-action buttons could imply authority the browser does not have: buttons only call the existing challenge/perform routes; blocked reasons are relayed verbatim; CLI-only steps copy the exact argv and name the ADR.",
    "static/app or openapi.json forgotten: every slice ends with the build and `git status --short` of both.",
    "The real-backend walkthrough needs network (pull, ticker): it runs on the owner's machine with the network marker and reports failures verbatim; the offline gate never depends on it."
  ],
  "slices": [
    {
      "title": "P1 Market Watch tells the truth: venue, age, artboard row anatomy",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/panels/marketWatchModel.test.ts && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "watchRow reads bars + provenance: label without the slash (BTCUSDT), venue (Binance/Coinbase/Tiingo…), last, daily %, asOf date and a stale flag (older than two days); rows render ▲/▼ by tone, a blue selection row, a venue cell and an Age cell showing the bar date; Details lists every stored quote of the selected base asset with venue and date; a `+ click to add…` row opens the Data Manager and focuses its symbol field. No price is ever invented.",
      "rollback": "Revert the slice commit.",
      "files": ["apps/alpha-web/frontend/src/panels/marketWatchModel.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.test.ts", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/src/panels/actions.ts", "apps/alpha-web/frontend/src/App.tsx", "apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "P2 live public ticker, opt-in: CCXTAdapter.fetch_ticker → alpha data ticker → GET /api/data/ticker → Market Watch Live toggle",
      "verify": "uv run pytest -q tests/unit/test_ccxt_adapter_ticker.py tests/unit/test_cli_data_ticker.py tests/integration/test_web_api_catalog.py -m \"not network\" && uv run python scripts/generate_web_openapi.py --check && uv run python scripts/check_openapi_operations.py && cd apps/alpha-web/frontend && npm run generate:api && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "A read-only public quote seam that fails loud (unknown market, missing last, non-ccxt source → typed error/422/404); the Market Watch header reads `Market Watch: HH:MM:SS`, a persisted Live toggle polls every 10 s only while on and the tab is visible, rows show `live` in the Age cell with the ticker's last and fall back to the stored close and date when the read fails; equities tickers keep the stored close.",
      "rollback": "Revert the slice commit; the route is additive.",
      "files": ["packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py", "tests/unit/test_ccxt_adapter_ticker.py", "apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/test_cli_data_ticker.py", "apps/alpha-web/src/alpha_web/_catalog.py", "apps/alpha-web/src/alpha_web/api/catalog.py", "apps/alpha-web/src/alpha_web/api/models.py", "tests/integration/test_web_api_catalog.py", "apps/alpha-web/frontend/openapi.json", "apps/alpha-web/frontend/src/api/generated.ts", "apps/alpha-web/frontend/src/api/client.ts", "apps/alpha-web/frontend/src/api/types.ts", "apps/alpha-web/frontend/src/state/settings.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.test.ts", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/src/alpha_web/static/app/**", "docs/governance/openapi-operation-classification.json", "docs/governance/capability-authority-matrix.md"],
      "status": "done"
    },
    {
      "title": "P3a artboard-exact shell: fonts, title bar, icon toolbar, dock headers with bottom tabs, Navigator glyphs and counts, document header, Toolbox table, status bar wording",
      "verify": "cd apps/alpha-web/frontend && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "Chrome matches 1-Terminal.png: system UI 12px tabular numerals; title `ALPHA Terminal — Crypto — [BTCUSDT,D1]` with disabled window glyphs; toolbar of chart-type/timeframe/zoom/crosshair/grid/action icon buttons (chart controls applied in PriceChartCanvas), `Profile` combo, symbol combo, `Search Ctrl+K` field, lock `Paper only` chip, shield `Governance`; New Idea in the Research menu and palette; Guided/Advanced and Settings in the View menu; dock headers with pin (disabled) and close (hides; View › Docks restores) and tabs at the bottom (Market Watch Symbols·Details·Data, Navigator Common·Favorites, Data Manager Pull·Snapshots·Quality·Storage, Toolbox Jobs N·Trades·Backtests·Data pulls·Log·Alerts); Navigator folder/document glyphs and `Binance (N pairs)` counts; document header bar with minimise/maximise/close; Toolbox `Time | Job | Status | Detail | ✓` table; status bar `For Help, press F1 | Profile: … | <venues ✓> | Expansion SSD … | Paper only · no live routing | <UTC> | O: H: L: C: V: | n / n bars`. axe clean at 1280/1440/wide.",
      "rollback": "Revert the slice commit.",
      "files": ["apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/src/App.tsx", "apps/alpha-web/frontend/src/shell/**", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/src/panels/Navigator.tsx", "apps/alpha-web/frontend/src/panels/navigatorModel.ts", "apps/alpha-web/frontend/src/panels/navigatorModel.test.ts", "apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/panels/JobMonitor.tsx", "apps/alpha-web/frontend/src/panels/jobTableModel.ts", "apps/alpha-web/frontend/src/panels/jobTableModel.test.ts", "apps/alpha-web/frontend/src/components/PriceChartCanvas.tsx", "apps/alpha-web/frontend/src/components/ContextBar.tsx", "apps/alpha-web/frontend/src/context/chartControls.ts", "apps/alpha-web/frontend/src/components/CommandPalette.tsx", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/frontend/e2e/real-backend.spec.ts", "apps/alpha-web/frontend/e2e/crypto-data.spec.ts", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "P3b artboard-exact documents: report toolbar and tree, Governance table, figure maximise header; re-baseline",
      "verify": "cd apps/alpha-web/frontend && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --update-snapshots=all && npm run test:e2e && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "Report matches 2-Strategy-Performance-Report.png (toolbar Export CSV · Save PNG · Compare… · Run again · Notes; tree with glyphs and counts; summary table left, figures right); Governance matches 4-Governance-window.png (page list with counts, Item·State·Detail table, glossary filter); the figure overlay matches 3-Chart-maximised.png; twenty document baselines replaced and a clean four-project run is green.",
      "rollback": "Revert the slice commit and restore the previous baselines.",
      "files": ["apps/alpha-web/frontend/src/panels/rundetail/**", "apps/alpha-web/frontend/src/panels/reportModel.ts", "apps/alpha-web/frontend/src/panels/reportModel.test.ts", "apps/alpha-web/frontend/src/panels/Governance.tsx", "apps/alpha-web/frontend/src/panels/governanceModel.ts", "apps/alpha-web/frontend/src/panels/governanceModel.test.ts", "apps/alpha-web/frontend/src/components/FigureOverlay.tsx", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/frontend/e2e/workstation.spec.ts-snapshots/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "P4 every blocked state has a button: OwnerActionButton, launch_d1/launch_d2/revise/disposition wired, gate-lock next step, Copy command for CLI-only steps, Enroll Touch ID",
      "verify": "uv run pytest -q tests/unit/test_web_owner_actions_drift.py -m \"not network\" && cd apps/alpha-web/frontend && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "Wherever the SPA prints an owner/Touch ID/blocked notice there is a button: Touch ID · launch D1 / launch D2 / record decision / revise answers (challenge → WebAuthn → perform, relayed errors verbatim), the research-gate lock offers the case's current owner step beside `Open research case`, CLI-only steps (holdout reveal, reviewed-asset master, credential recovery) offer `Copy command` naming the ADR, and an unenrolled owner is sent to /owner-auth/enroll. A unit test pins the SPA's action list to OWNER_ACTION_TYPES.",
      "rollback": "Revert the slice commit; the backend is unchanged.",
      "files": ["apps/alpha-web/frontend/src/components/OwnerActionButton.tsx", "apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx", "apps/alpha-web/frontend/src/panels/researchCockpitModel.ts", "apps/alpha-web/frontend/src/panels/researchCockpitModel.test.ts", "apps/alpha-web/frontend/src/panels/V3Workbenches.tsx", "apps/alpha-web/frontend/src/panels/useLinkedProjectGate.ts", "apps/alpha-web/frontend/src/panels/StrategyLab.tsx", "apps/alpha-web/frontend/src/panels/Governance.tsx", "apps/alpha-web/frontend/src/panels/governanceModel.ts", "apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/panels/EvidenceHub.tsx", "apps/alpha-web/frontend/src/auth/ownerAuth.ts", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "tests/unit/test_web_owner_actions_drift.py", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "P5 prove everything and ship: full gates, real-backend acceptance in both profiles, docs, PR #47 green and merged",
      "verify": "uv run python scripts/gate.py full && cd apps/alpha-web/frontend && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npm run build && npm run test:e2e && cd ../../.. && uv run pytest -q tests/unit/test_documentation_truth.py tests/unit/test_claude_md_relocation.py -m \"not network\" && uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-09-04-trader-terminal-phase4-pixel.md && gh pr checks 47",
      "expected": "Every gate green; the scripted real-backend walkthrough (both profiles, every document and dock tab, Market Watch venue/age/live, an XRP/USDT Binance pull landing in the Toolbox, a validate run opening its report) exits 0 with its screenshots beside the artboards; rule rows, BUILD-STATUS, spec addendum and findings #14–#16 updated; PR #47 CI green and merged with a merge commit; the terminal launched for the owner.",
      "rollback": "Docs-only revert; the merge is the owner's decision.",
      "files": [".claude/rules/alpha-web.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md", "docs/superpowers/plans/2026-09-04-trader-terminal-phase4-pixel.md"],
      "status": "pending"
    }
  ],
  "tier_impact": ["protected", "dag"],
  "docs_to_update": [".claude/rules/alpha-web.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md"],
  "out_of_scope": [
    "Live trading, broker readiness, order routing; the ticker is a displayed quote, never an execution price or a stored series.",
    "New statistics, new providers beyond the public ccxt ticker, new MCP tools (pinned at 62), new ADRs.",
    "Intraday timeframes (buttons stay disabled with the reason).",
    "Making holdout reveal, the reviewed-asset master or credential recovery browser actions (ADR-bound CLI steps; the UI copies the command).",
    "Automating Touch ID itself in tests (WebAuthn is stubbed in e2e; the owner presses the sensor once)."
  ],
  "files": ["apps/alpha-web/**", "packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py", "apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/**", "tests/integration/test_web_api_catalog.py", ".claude/rules/alpha-web.md", "docs/**"]
}
```

## Context

The owner's second walkthrough (2026-09-03) rejected Phase 3 on truthfulness (Market Watch),
fidelity (artboards) and usability (dead-end owner notices). Phase 4 fixes all three without
moving any statistic, reader, DAG edge, MCP tool or authority.

## Deviations
* **P1** — the Market Watch table gained a `Venue` and an `Age` column (the artboard has only
  Symbol · Last · Daily %) because the owner's two complaints — "duplicates" and "that is not
  today's price" — are answered by exactly those two cells; the artboard's three-column look is
  kept for the row anatomy (▲/▼ glyph, blue selection, `+ click to add…`). Rows are keyed by the
  stored symbol and spelled without the slash. `symbolFitsProfile` stays the only market filter.
* **P2** — `alpha data ticker` is ccxt-only like `first-bar`; equities tickers keep the stored
  close. The Live toggle lives in `alpha.settings` (`liveTicker`, default off) and the poll clears
  its overlay the moment it is switched off, so a stale live price can never linger. The generated
  `docs/governance/openapi-operation-classification.json` and `capability-authority-matrix.md`
  were rewritten by `check_openapi_operations.py --write` for the one new read-only GET.
* **P3a** — the chrome typeface is the platform UI face at 12px (`--chrome-font-size`; 11px at the
  1280px minimum so every material question still fits the 720px viewport) — the generated canvas
  tokens are untouched. Docks are 300px/345px (artboard 278/345) so the five Market Watch columns
  fit; the `Age` cell prints days since the bar (`65d`, `live`) with the exact bar date in its
  title and in the Details tab, because a full ISO date did not fit the dock. Guided/Advanced,
  New Idea, Settings and the dock toggles live in the View/Research menus as the artboard has no
  toolbar buttons for them; the ⚙ settings popover stays as the last toolbar glyph. Market Watch
  row buttons keep a 24px hit target (axe target-size) so rows are ~26px, not the artboard's 21px.
  The Data Manager's `Snapshots` tab, the Navigator's `Favorites`, the Toolbox `Alerts` tab, the
  toolbar `Stop`, the dock pin and the title-bar window glyphs are rendered disabled with the
  reason in their tooltip — nothing behind them exists yet.
* **P3b** — the report toolbar is `Export CSV · Save PNG · Compare… · Run again · Notes` plus a
  disabled save glyph (a run directory is already immutable on disk) and a print glyph: Export CSV
  writes the trades projection verbatim (`tradesCsv`), Save PNG hands over the first drawable figure
  of the current view through the bare `…/image?fmt=png` endpoint, Compare… opens the Compare
  document (the run is ticked there — Compare keeps its own selection), Notes toggles the existing
  narrative/terse explanation setting. The Governance table is `Item | State | Detail`; providers
  and storage rows split state from detail while the five hazard sentences stay verbatim in State.
  Page labels carry the artboard counts (`Research gates (1 open)`, `Overrides (N)`,
  `Glossary (N)`). The figure overlay fills the window with a `<figure> — <run> (maximised)`
  header, zoom in/out/fit that scales the served SVG in the browser (nothing is redrawn) and
  `Esc restores · run <8> · UTC`; the focus trap now walks Save PNG → Save SVG → Copy → Close →
  Zoom in. The Toolbox opens by default only on windows ≥960px tall (the artboard is 991px) so the
  1440×900 reference keeps every material research question in view. Twenty document baselines
  re-taken."status": "done"* In progress (2026-09-03; P1–P5 on `feat/trader-terminal-phase1-work`, PR #47).

# Trader Terminal — Phase 4 "Pixel": artboard-exact chrome, honest live Market Watch, one-click owner actions

```json
{
  "schema_version": 1,
  "title": "Trader Terminal Phase 4 (Pixel): artboard-exact chrome, Market Watch with venue/age and an opt-in public ticker, owner-action buttons wherever the UI says owner approval is needed, full real-backend acceptance",
  "context": "Phase 3 (docs/superpowers/plans/2026-09-03-trader-terminal-phase3-terminal.md) shipped the terminal shell; the owner opened it on 2026-09-03 and rejected it on three grounds: Market Watch reads as duplicated assets with a stale price shown as current (BTC/USDT Binance and BTC/USD Coinbase are two stored pairs; 93,354 is the 2026-06-30 stored close), the chrome does not match the approved artboards in /Users/hunternovotny/Desktop/ALPHA-terminal-designs (1-Terminal, 2-Strategy-Performance-Report, 3-Chart-maximised, 4-Governance-window, Option E palette), and every 'needs owner approval / Touch ID / trusted CLI' notice is a dead end although the owner-auth REST vocabulary already carries launch_d1, launch_d2, revise_exploration and record_final_disposition. Owner decisions (2026-09-03): one row per stored pair with the venue shown; live public ticker, opt-in, stored close plus its date as the fallback; reproduce every artboard element, disabled with a reason where no capability backs it; every blocked state gets a button that completes the step (Touch ID) or, where an ADR keeps it CLI-only, a Copy-command button. No statistic, point-in-time reader, DAG edge, MCP tool or authority changes.",
  "assumptions": [
    {
      "statement": "The candles projection already carries the venue: `provenance.source` is `ccxt:<exchange>` for ccxt pulls and the provider id otherwise, so Market Watch can label each stored pair's venue from the `?tail=2` read it already makes, without a new symbols projection.",
      "verified_by": "curl of GET /api/candles/XRP%2FUSDT on 2026-09-03 (source `ccxt:binance`, knowledge_cutoff 2026-06-30) and apps/alpha-web/src/alpha_web/api/candles.py."
    },
    {
      "statement": "A public ccxt ticker read needs no key and no ADR: it is comparison-only, never stored, never a data authority, and follows the read-only network pattern of `alpha data first-bar` (CCXTAdapter.first_bar, data_cmds.py:163, catalog.py:37).",
      "verified_by": "read of packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py:136-240 and apps/alpha-cli/src/alpha_cli/data_cmds.py:163-180 on 2026-09-03; P2 adds `@pytest.mark.network` live tests and offline fake-exchange tests."
    },
    {
      "statement": "Chrome fonts and colours are hand-written CSS (index.css); the canvas tokens and terminal_classic.json (quant tier) stay untouched, so Phase 4 carries no /verify-quant or /review-gate obligation.",
      "verified_by": "read of apps/alpha-web/frontend/src/theme.generated.css, src/util/theme.drift.test.ts and tests/unit/test_theme_drift.py on 2026-09-03."
    },
    {
      "statement": "The owner-auth challenge/perform routes dispatch launch_d1 → `alpha research run deep`, launch_d2 → `alpha research run confirm`, record_final_disposition → `alpha research decide`, revise_exploration → `alpha research propose --answer …` under one Touch ID receipt; the SPA only lacks buttons for them. Holdout reveal and the reviewed-asset master stay CLI-only by ADR-0021/0026/0032.",
      "verified_by": "read of apps/alpha-web/src/alpha_web/api/owner_auth.py:38-52,183-200 and apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx:344-437 on 2026-09-03; P4 adds a drift test between the SPA action list and OWNER_ACTION_TYPES."
    }
  ],
  "alternatives_considered": [
    "One Market Watch row per base asset (hide the Coinbase USD pair): rejected by the owner and by the crypto rule that USD and USDT pairs are never merged; the artboard itself lists BTCUSDT and BTCUSD.",
    "Show the stored close only with its date and no live quote: rejected by the owner — a trader's Market Watch must be able to read a current price; the ticker is opt-in and clearly labelled `live`.",
    "Omit artboard controls that have no capability (window glyphs, Alerts, Favorites): rejected by the owner — they are drawn disabled with the reason in the tooltip.",
    "Move the profile/symbol invariant into the settings store: rejected — the store knows nothing of the linked context; the App effect is the one home of the rule (simplify pass 09a9ea7)."
  ],
  "pre_mortem": [
    "The ticker poll runs behind a hidden tab or after the toggle is off: the pure `shouldPoll(live, visible)` gate is unit-tested and the interval is cleared on toggle-off/visibilitychange; e2e asserts no `/api/data/ticker` request when the toggle is off.",
    "A ticker from Binance is shown for a Coinbase pair: the venue comes from the pair's own provenance, the ticker request carries that exchange, and the response symbol/exchange must echo the request or the row falls back to the stored close.",
    "The chrome rewrite breaks axe (icon-only buttons, dock close/pin targets): every icon button carries an aria-label and 24px min target; chromium-minimum runs in every slice.",
    "The twenty screenshot baselines churn twice: P3a and P3b re-baseline once, at the end of P3b, then a clean run proves stability.",
    "Owner-action buttons could imply authority the browser does not have: buttons only call the existing challenge/perform routes; blocked reasons are relayed verbatim; CLI-only steps copy the exact argv and name the ADR.",
    "static/app or openapi.json forgotten: every slice ends with the build and `git status --short` of both.",
    "The real-backend walkthrough needs network (pull, ticker): it runs on the owner's machine with the network marker and reports failures verbatim; the offline gate never depends on it."
  ],
  "slices": [
    {
      "title": "P1 Market Watch tells the truth: venue, age, artboard row anatomy",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/panels/marketWatchModel.test.ts && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "watchRow reads bars + provenance: label without the slash (BTCUSDT), venue (Binance/Coinbase/Tiingo…), last, daily %, asOf date and a stale flag (older than two days); rows render ▲/▼ by tone, a blue selection row, a venue cell and an Age cell showing the bar date; Details lists every stored quote of the selected base asset with venue and date; a `+ click to add…` row opens the Data Manager and focuses its symbol field. No price is ever invented.",
      "rollback": "Revert the slice commit.",
      "files": ["apps/alpha-web/frontend/src/panels/marketWatchModel.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.test.ts", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/src/panels/actions.ts", "apps/alpha-web/frontend/src/App.tsx", "apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "P2 live public ticker, opt-in: CCXTAdapter.fetch_ticker → alpha data ticker → GET /api/data/ticker → Market Watch Live toggle",
      "verify": "uv run pytest -q tests/unit/test_ccxt_adapter_ticker.py tests/unit/test_cli_data_ticker.py tests/integration/test_web_api_catalog.py -m \"not network\" && uv run python scripts/generate_web_openapi.py --check && uv run python scripts/check_openapi_operations.py && cd apps/alpha-web/frontend && npm run generate:api && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "A read-only public quote seam that fails loud (unknown market, missing last, non-ccxt source → typed error/422/404); the Market Watch header reads `Market Watch: HH:MM:SS`, a persisted Live toggle polls every 10 s only while on and the tab is visible, rows show `live` in the Age cell with the ticker's last and fall back to the stored close and date when the read fails; equities tickers keep the stored close.",
      "rollback": "Revert the slice commit; the route is additive.",
      "files": ["packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py", "tests/unit/test_ccxt_adapter_ticker.py", "apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/test_cli_data_ticker.py", "apps/alpha-web/src/alpha_web/_catalog.py", "apps/alpha-web/src/alpha_web/api/catalog.py", "apps/alpha-web/src/alpha_web/api/models.py", "tests/integration/test_web_api_catalog.py", "apps/alpha-web/frontend/openapi.json", "apps/alpha-web/frontend/src/api/generated.ts", "apps/alpha-web/frontend/src/api/client.ts", "apps/alpha-web/frontend/src/api/types.ts", "apps/alpha-web/frontend/src/state/settings.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.test.ts", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/src/alpha_web/static/app/**", "docs/governance/openapi-operation-classification.json", "docs/governance/capability-authority-matrix.md"],
      "status": "done"
    },
    {
      "title": "P3a artboard-exact shell: fonts, title bar, icon toolbar, dock headers with bottom tabs, Navigator glyphs and counts, document header, Toolbox table, status bar wording",
      "verify": "cd apps/alpha-web/frontend && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "Chrome matches 1-Terminal.png: system UI 12px tabular numerals; title `ALPHA Terminal — Crypto — [BTCUSDT,D1]` with disabled window glyphs; toolbar of chart-type/timeframe/zoom/crosshair/grid/action icon buttons (chart controls applied in PriceChartCanvas), `Profile` combo, symbol combo, `Search Ctrl+K` field, lock `Paper only` chip, shield `Governance`; New Idea in the Research menu and palette; Guided/Advanced and Settings in the View menu; dock headers with pin (disabled) and close (hides; View › Docks restores) and tabs at the bottom (Market Watch Symbols·Details·Data, Navigator Common·Favorites, Data Manager Pull·Snapshots·Quality·Storage, Toolbox Jobs N·Trades·Backtests·Data pulls·Log·Alerts); Navigator folder/document glyphs and `Binance (N pairs)` counts; document header bar with minimise/maximise/close; Toolbox `Time | Job | Status | Detail | ✓` table; status bar `For Help, press F1 | Profile: … | <venues ✓> | Expansion SSD … | Paper only · no live routing | <UTC> | O: H: L: C: V: | n / n bars`. axe clean at 1280/1440/wide.",
      "rollback": "Revert the slice commit.",
      "files": ["apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/src/App.tsx", "apps/alpha-web/frontend/src/shell/**", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/src/panels/Navigator.tsx", "apps/alpha-web/frontend/src/panels/navigatorModel.ts", "apps/alpha-web/frontend/src/panels/navigatorModel.test.ts", "apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/panels/JobMonitor.tsx", "apps/alpha-web/frontend/src/panels/jobTableModel.ts", "apps/alpha-web/frontend/src/panels/jobTableModel.test.ts", "apps/alpha-web/frontend/src/components/PriceChartCanvas.tsx", "apps/alpha-web/frontend/src/components/ContextBar.tsx", "apps/alpha-web/frontend/src/context/chartControls.ts", "apps/alpha-web/frontend/src/components/CommandPalette.tsx", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/frontend/e2e/real-backend.spec.ts", "apps/alpha-web/frontend/e2e/crypto-data.spec.ts", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "P3b artboard-exact documents: report toolbar and tree, Governance table, figure maximise header; re-baseline",
      "verify": "cd apps/alpha-web/frontend && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --update-snapshots=all && npm run test:e2e && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "Report matches 2-Strategy-Performance-Report.png (toolbar Export CSV · Save PNG · Compare… · Run again · Notes; tree with glyphs and counts; summary table left, figures right); Governance matches 4-Governance-window.png (page list with counts, Item·State·Detail table, glossary filter); the figure overlay matches 3-Chart-maximised.png; twenty document baselines replaced and a clean four-project run is green.",
      "rollback": "Revert the slice commit and restore the previous baselines.",
      "files": ["apps/alpha-web/frontend/src/panels/rundetail/**", "apps/alpha-web/frontend/src/panels/reportModel.ts", "apps/alpha-web/frontend/src/panels/reportModel.test.ts", "apps/alpha-web/frontend/src/panels/Governance.tsx", "apps/alpha-web/frontend/src/panels/governanceModel.ts", "apps/alpha-web/frontend/src/panels/governanceModel.test.ts", "apps/alpha-web/frontend/src/components/FigureOverlay.tsx", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/frontend/e2e/workstation.spec.ts-snapshots/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "P4 every blocked state has a button: OwnerActionButton, launch_d1/launch_d2/revise/disposition wired, gate-lock next step, Copy command for CLI-only steps, Enroll Touch ID",
      "verify": "uv run pytest -q tests/unit/test_web_owner_actions_drift.py -m \"not network\" && cd apps/alpha-web/frontend && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "Wherever the SPA prints an owner/Touch ID/blocked notice there is a button: Touch ID · launch D1 / launch D2 / record decision / revise answers (challenge → WebAuthn → perform, relayed errors verbatim), the research-gate lock offers the case's current owner step beside `Open research case`, CLI-only steps (holdout reveal, reviewed-asset master, credential recovery) offer `Copy command` naming the ADR, and an unenrolled owner is sent to /owner-auth/enroll. A unit test pins the SPA's action list to OWNER_ACTION_TYPES.",
      "rollback": "Revert the slice commit; the backend is unchanged.",
      "files": ["apps/alpha-web/frontend/src/components/OwnerActionButton.tsx", "apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx", "apps/alpha-web/frontend/src/panels/researchCockpitModel.ts", "apps/alpha-web/frontend/src/panels/researchCockpitModel.test.ts", "apps/alpha-web/frontend/src/panels/V3Workbenches.tsx", "apps/alpha-web/frontend/src/panels/useLinkedProjectGate.ts", "apps/alpha-web/frontend/src/panels/StrategyLab.tsx", "apps/alpha-web/frontend/src/panels/Governance.tsx", "apps/alpha-web/frontend/src/panels/governanceModel.ts", "apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/panels/EvidenceHub.tsx", "apps/alpha-web/frontend/src/auth/ownerAuth.ts", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "tests/unit/test_web_owner_actions_drift.py", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "P5 prove everything and ship: full gates, real-backend acceptance in both profiles, docs, PR #47 green and merged",
      "verify": "uv run python scripts/gate.py full && cd apps/alpha-web/frontend && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npm run build && npm run test:e2e && cd ../../.. && uv run pytest -q tests/unit/test_documentation_truth.py tests/unit/test_claude_md_relocation.py -m \"not network\" && uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-09-04-trader-terminal-phase4-pixel.md && gh pr checks 47",
      "expected": "Every gate green; the scripted real-backend walkthrough (both profiles, every document and dock tab, Market Watch venue/age/live, an XRP/USDT Binance pull landing in the Toolbox, a validate run opening its report) exits 0 with its screenshots beside the artboards; rule rows, BUILD-STATUS, spec addendum and findings #14–#16 updated; PR #47 CI green and merged with a merge commit; the terminal launched for the owner.",
      "rollback": "Docs-only revert; the merge is the owner's decision.",
      "files": [".claude/rules/alpha-web.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md", "docs/superpowers/plans/2026-09-04-trader-terminal-phase4-pixel.md"],
      "status": "pending"
    }
  ],
  "tier_impact": ["protected", "dag"],
  "docs_to_update": [".claude/rules/alpha-web.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md"],
  "out_of_scope": [
    "Live trading, broker readiness, order routing; the ticker is a displayed quote, never an execution price or a stored series.",
    "New statistics, new providers beyond the public ccxt ticker, new MCP tools (pinned at 62), new ADRs.",
    "Intraday timeframes (buttons stay disabled with the reason).",
    "Making holdout reveal, the reviewed-asset master or credential recovery browser actions (ADR-bound CLI steps; the UI copies the command).",
    "Automating Touch ID itself in tests (WebAuthn is stubbed in e2e; the owner presses the sensor once)."
  ],
  "files": ["apps/alpha-web/**", "packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py", "apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/**", "tests/integration/test_web_api_catalog.py", ".claude/rules/alpha-web.md", "docs/**"]
}
```

## Context

The owner's second walkthrough (2026-09-03) rejected Phase 3 on truthfulness (Market Watch),
fidelity (artboards) and usability (dead-end owner notices). Phase 4 fixes all three without
moving any statistic, reader, DAG edge, MCP tool or authority.

## Deviations
* **P1** — the Market Watch table gained a `Venue` and an `Age` column (the artboard has only
  Symbol · Last · Daily %) because the owner's two complaints — "duplicates" and "that is not
  today's price" — are answered by exactly those two cells; the artboard's three-column look is
  kept for the row anatomy (▲/▼ glyph, blue selection, `+ click to add…`). Rows are keyed by the
  stored symbol and spelled without the slash. `symbolFitsProfile` stays the only market filter.
* **P2** — `alpha data ticker` is ccxt-only like `first-bar`; equities tickers keep the stored
  close. The Live toggle lives in `alpha.settings` (`liveTicker`, default off) and the poll clears
  its overlay the moment it is switched off, so a stale live price can never linger. The generated
  `docs/governance/openapi-operation-classification.json` and `capability-authority-matrix.md`
  were rewritten by `check_openapi_operations.py --write` for the one new read-only GET.
* **P3a** — the chrome typeface is the platform UI face at 12px (`--chrome-font-size`; 11px at the
  1280px minimum so every material question still fits the 720px viewport) — the generated canvas
  tokens are untouched. Docks are 300px/345px (artboard 278/345) so the five Market Watch columns
  fit; the `Age` cell prints days since the bar (`65d`, `live`) with the exact bar date in its
  title and in the Details tab, because a full ISO date did not fit the dock. Guided/Advanced,
  New Idea, Settings and the dock toggles live in the View/Research menus as the artboard has no
  toolbar buttons for them; the ⚙ settings popover stays as the last toolbar glyph. Market Watch
  row buttons keep a 24px hit target (axe target-size) so rows are ~26px, not the artboard's 21px.
  The Data Manager's `Snapshots` tab, the Navigator's `Favorites`, the Toolbox `Alerts` tab, the
  toolbar `Stop`, the dock pin and the title-bar window glyphs are rendered disabled with the
  reason in their tooltip — nothing behind them exists yet.
* **P3b** — the report toolbar is `Export CSV · Save PNG · Compare… · Run again · Notes` plus a
  disabled save glyph (a run directory is already immutable on disk) and a print glyph: Export CSV
  writes the trades projection verbatim (`tradesCsv`), Save PNG hands over the first drawable figure
  of the current view through the bare `…/image?fmt=png` endpoint, Compare… opens the Compare
  document (the run is ticked there — Compare keeps its own selection), Notes toggles the existing
  narrative/terse explanation setting. The Governance table is `Item | State | Detail`; providers
  and storage rows split state from detail while the five hazard sentences stay verbatim in State.
  Page labels carry the artboard counts (`Research gates (1 open)`, `Overrides (N)`,
  `Glossary (N)`). The figure overlay fills the window with a `<figure> — <run> (maximised)`
  header, zoom in/out/fit that scales the served SVG in the browser (nothing is redrawn) and
  `Esc restores · run <8> · UTC`; the focus trap now walks Save PNG → Save SVG → Copy → Close →
  Zoom in. The Toolbox opens by default only on windows ≥960px tall (the artboard is 991px) so the
  1440×900 reference keeps every material research question in view. Twenty document baselines
  re-taken."status": "done"* In progress (2026-09-03; P1–P5 on `feat/trader-terminal-phase1-work`, PR #47).

# Trader Terminal — Phase 4 "Pixel": artboard-exact chrome, honest live Market Watch, one-click owner actions

```json
{
  "schema_version": 1,
  "title": "Trader Terminal Phase 4 (Pixel): artboard-exact chrome, Market Watch with venue/age and an opt-in public ticker, owner-action buttons wherever the UI says owner approval is needed, full real-backend acceptance",
  "context": "Phase 3 (docs/superpowers/plans/2026-09-03-trader-terminal-phase3-terminal.md) shipped the terminal shell; the owner opened it on 2026-09-03 and rejected it on three grounds: Market Watch reads as duplicated assets with a stale price shown as current (BTC/USDT Binance and BTC/USD Coinbase are two stored pairs; 93,354 is the 2026-06-30 stored close), the chrome does not match the approved artboards in /Users/hunternovotny/Desktop/ALPHA-terminal-designs (1-Terminal, 2-Strategy-Performance-Report, 3-Chart-maximised, 4-Governance-window, Option E palette), and every 'needs owner approval / Touch ID / trusted CLI' notice is a dead end although the owner-auth REST vocabulary already carries launch_d1, launch_d2, revise_exploration and record_final_disposition. Owner decisions (2026-09-03): one row per stored pair with the venue shown; live public ticker, opt-in, stored close plus its date as the fallback; reproduce every artboard element, disabled with a reason where no capability backs it; every blocked state gets a button that completes the step (Touch ID) or, where an ADR keeps it CLI-only, a Copy-command button. No statistic, point-in-time reader, DAG edge, MCP tool or authority changes.",
  "assumptions": [
    {
      "statement": "The candles projection already carries the venue: `provenance.source` is `ccxt:<exchange>` for ccxt pulls and the provider id otherwise, so Market Watch can label each stored pair's venue from the `?tail=2` read it already makes, without a new symbols projection.",
      "verified_by": "curl of GET /api/candles/XRP%2FUSDT on 2026-09-03 (source `ccxt:binance`, knowledge_cutoff 2026-06-30) and apps/alpha-web/src/alpha_web/api/candles.py."
    },
    {
      "statement": "A public ccxt ticker read needs no key and no ADR: it is comparison-only, never stored, never a data authority, and follows the read-only network pattern of `alpha data first-bar` (CCXTAdapter.first_bar, data_cmds.py:163, catalog.py:37).",
      "verified_by": "read of packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py:136-240 and apps/alpha-cli/src/alpha_cli/data_cmds.py:163-180 on 2026-09-03; P2 adds `@pytest.mark.network` live tests and offline fake-exchange tests."
    },
    {
      "statement": "Chrome fonts and colours are hand-written CSS (index.css); the canvas tokens and terminal_classic.json (quant tier) stay untouched, so Phase 4 carries no /verify-quant or /review-gate obligation.",
      "verified_by": "read of apps/alpha-web/frontend/src/theme.generated.css, src/util/theme.drift.test.ts and tests/unit/test_theme_drift.py on 2026-09-03."
    },
    {
      "statement": "The owner-auth challenge/perform routes dispatch launch_d1 → `alpha research run deep`, launch_d2 → `alpha research run confirm`, record_final_disposition → `alpha research decide`, revise_exploration → `alpha research propose --answer …` under one Touch ID receipt; the SPA only lacks buttons for them. Holdout reveal and the reviewed-asset master stay CLI-only by ADR-0021/0026/0032.",
      "verified_by": "read of apps/alpha-web/src/alpha_web/api/owner_auth.py:38-52,183-200 and apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx:344-437 on 2026-09-03; P4 adds a drift test between the SPA action list and OWNER_ACTION_TYPES."
    }
  ],
  "alternatives_considered": [
    "One Market Watch row per base asset (hide the Coinbase USD pair): rejected by the owner and by the crypto rule that USD and USDT pairs are never merged; the artboard itself lists BTCUSDT and BTCUSD.",
    "Show the stored close only with its date and no live quote: rejected by the owner — a trader's Market Watch must be able to read a current price; the ticker is opt-in and clearly labelled `live`.",
    "Omit artboard controls that have no capability (window glyphs, Alerts, Favorites): rejected by the owner — they are drawn disabled with the reason in the tooltip.",
    "Move the profile/symbol invariant into the settings store: rejected — the store knows nothing of the linked context; the App effect is the one home of the rule (simplify pass 09a9ea7)."
  ],
  "pre_mortem": [
    "The ticker poll runs behind a hidden tab or after the toggle is off: the pure `shouldPoll(live, visible)` gate is unit-tested and the interval is cleared on toggle-off/visibilitychange; e2e asserts no `/api/data/ticker` request when the toggle is off.",
    "A ticker from Binance is shown for a Coinbase pair: the venue comes from the pair's own provenance, the ticker request carries that exchange, and the response symbol/exchange must echo the request or the row falls back to the stored close.",
    "The chrome rewrite breaks axe (icon-only buttons, dock close/pin targets): every icon button carries an aria-label and 24px min target; chromium-minimum runs in every slice.",
    "The twenty screenshot baselines churn twice: P3a and P3b re-baseline once, at the end of P3b, then a clean run proves stability.",
    "Owner-action buttons could imply authority the browser does not have: buttons only call the existing challenge/perform routes; blocked reasons are relayed verbatim; CLI-only steps copy the exact argv and name the ADR.",
    "static/app or openapi.json forgotten: every slice ends with the build and `git status --short` of both.",
    "The real-backend walkthrough needs network (pull, ticker): it runs on the owner's machine with the network marker and reports failures verbatim; the offline gate never depends on it."
  ],
  "slices": [
    {
      "title": "P1 Market Watch tells the truth: venue, age, artboard row anatomy",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/panels/marketWatchModel.test.ts && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "watchRow reads bars + provenance: label without the slash (BTCUSDT), venue (Binance/Coinbase/Tiingo…), last, daily %, asOf date and a stale flag (older than two days); rows render ▲/▼ by tone, a blue selection row, a venue cell and an Age cell showing the bar date; Details lists every stored quote of the selected base asset with venue and date; a `+ click to add…` row opens the Data Manager and focuses its symbol field. No price is ever invented.",
      "rollback": "Revert the slice commit.",
      "files": ["apps/alpha-web/frontend/src/panels/marketWatchModel.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.test.ts", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/src/panels/actions.ts", "apps/alpha-web/frontend/src/App.tsx", "apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "P2 live public ticker, opt-in: CCXTAdapter.fetch_ticker → alpha data ticker → GET /api/data/ticker → Market Watch Live toggle",
      "verify": "uv run pytest -q tests/unit/test_ccxt_adapter_ticker.py tests/unit/test_cli_data_ticker.py tests/integration/test_web_api_catalog.py -m \"not network\" && uv run python scripts/generate_web_openapi.py --check && uv run python scripts/check_openapi_operations.py && cd apps/alpha-web/frontend && npm run generate:api && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "A read-only public quote seam that fails loud (unknown market, missing last, non-ccxt source → typed error/422/404); the Market Watch header reads `Market Watch: HH:MM:SS`, a persisted Live toggle polls every 10 s only while on and the tab is visible, rows show `live` in the Age cell with the ticker's last and fall back to the stored close and date when the read fails; equities tickers keep the stored close.",
      "rollback": "Revert the slice commit; the route is additive.",
      "files": ["packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py", "tests/unit/test_ccxt_adapter_ticker.py", "apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/test_cli_data_ticker.py", "apps/alpha-web/src/alpha_web/_catalog.py", "apps/alpha-web/src/alpha_web/api/catalog.py", "apps/alpha-web/src/alpha_web/api/models.py", "tests/integration/test_web_api_catalog.py", "apps/alpha-web/frontend/openapi.json", "apps/alpha-web/frontend/src/api/generated.ts", "apps/alpha-web/frontend/src/api/client.ts", "apps/alpha-web/frontend/src/api/types.ts", "apps/alpha-web/frontend/src/state/settings.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.test.ts", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/src/alpha_web/static/app/**", "docs/governance/openapi-operation-classification.json", "docs/governance/capability-authority-matrix.md"],
      "status": "done"
    },
    {
      "title": "P3a artboard-exact shell: fonts, title bar, icon toolbar, dock headers with bottom tabs, Navigator glyphs and counts, document header, Toolbox table, status bar wording",
      "verify": "cd apps/alpha-web/frontend && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "Chrome matches 1-Terminal.png: system UI 12px tabular numerals; title `ALPHA Terminal — Crypto — [BTCUSDT,D1]` with disabled window glyphs; toolbar of chart-type/timeframe/zoom/crosshair/grid/action icon buttons (chart controls applied in PriceChartCanvas), `Profile` combo, symbol combo, `Search Ctrl+K` field, lock `Paper only` chip, shield `Governance`; New Idea in the Research menu and palette; Guided/Advanced and Settings in the View menu; dock headers with pin (disabled) and close (hides; View › Docks restores) and tabs at the bottom (Market Watch Symbols·Details·Data, Navigator Common·Favorites, Data Manager Pull·Snapshots·Quality·Storage, Toolbox Jobs N·Trades·Backtests·Data pulls·Log·Alerts); Navigator folder/document glyphs and `Binance (N pairs)` counts; document header bar with minimise/maximise/close; Toolbox `Time | Job | Status | Detail | ✓` table; status bar `For Help, press F1 | Profile: … | <venues ✓> | Expansion SSD … | Paper only · no live routing | <UTC> | O: H: L: C: V: | n / n bars`. axe clean at 1280/1440/wide.",
      "rollback": "Revert the slice commit.",
      "files": ["apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/src/App.tsx", "apps/alpha-web/frontend/src/shell/**", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/src/panels/Navigator.tsx", "apps/alpha-web/frontend/src/panels/navigatorModel.ts", "apps/alpha-web/frontend/src/panels/navigatorModel.test.ts", "apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/panels/JobMonitor.tsx", "apps/alpha-web/frontend/src/panels/jobTableModel.ts", "apps/alpha-web/frontend/src/panels/jobTableModel.test.ts", "apps/alpha-web/frontend/src/components/PriceChartCanvas.tsx", "apps/alpha-web/frontend/src/components/ContextBar.tsx", "apps/alpha-web/frontend/src/context/chartControls.ts", "apps/alpha-web/frontend/src/components/CommandPalette.tsx", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/frontend/e2e/real-backend.spec.ts", "apps/alpha-web/frontend/e2e/crypto-data.spec.ts", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "P3b artboard-exact documents: report toolbar and tree, Governance table, figure maximise header; re-baseline",
      "verify": "cd apps/alpha-web/frontend && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --update-snapshots=all && npm run test:e2e && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "Report matches 2-Strategy-Performance-Report.png (toolbar Export CSV · Save PNG · Compare… · Run again · Notes; tree with glyphs and counts; summary table left, figures right); Governance matches 4-Governance-window.png (page list with counts, Item·State·Detail table, glossary filter); the figure overlay matches 3-Chart-maximised.png; twenty document baselines replaced and a clean four-project run is green.",
      "rollback": "Revert the slice commit and restore the previous baselines.",
      "files": ["apps/alpha-web/frontend/src/panels/rundetail/**", "apps/alpha-web/frontend/src/panels/reportModel.ts", "apps/alpha-web/frontend/src/panels/reportModel.test.ts", "apps/alpha-web/frontend/src/panels/Governance.tsx", "apps/alpha-web/frontend/src/panels/governanceModel.ts", "apps/alpha-web/frontend/src/panels/governanceModel.test.ts", "apps/alpha-web/frontend/src/components/FigureOverlay.tsx", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "apps/alpha-web/frontend/e2e/workstation.spec.ts-snapshots/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "P4 every blocked state has a button: OwnerActionButton, launch_d1/launch_d2/revise/disposition wired, gate-lock next step, Copy command for CLI-only steps, Enroll Touch ID",
      "verify": "uv run pytest -q tests/unit/test_web_owner_actions_drift.py -m \"not network\" && cd apps/alpha-web/frontend && npx vitest run && npm run lint -- --deny-warnings && npx tsc -b && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "Wherever the SPA prints an owner/Touch ID/blocked notice there is a button: Touch ID · launch D1 / launch D2 / record decision / revise answers (challenge → WebAuthn → perform, relayed errors verbatim), the research-gate lock offers the case's current owner step beside `Open research case`, CLI-only steps (holdout reveal, reviewed-asset master, credential recovery) offer `Copy command` naming the ADR, and an unenrolled owner is sent to /owner-auth/enroll. A unit test pins the SPA's action list to OWNER_ACTION_TYPES.",
      "rollback": "Revert the slice commit; the backend is unchanged.",
      "files": ["apps/alpha-web/frontend/src/components/OwnerActionButton.tsx", "apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx", "apps/alpha-web/frontend/src/panels/researchCockpitModel.ts", "apps/alpha-web/frontend/src/panels/researchCockpitModel.test.ts", "apps/alpha-web/frontend/src/panels/V3Workbenches.tsx", "apps/alpha-web/frontend/src/panels/useLinkedProjectGate.ts", "apps/alpha-web/frontend/src/panels/StrategyLab.tsx", "apps/alpha-web/frontend/src/panels/Governance.tsx", "apps/alpha-web/frontend/src/panels/governanceModel.ts", "apps/alpha-web/frontend/src/panels/DataManager.tsx", "apps/alpha-web/frontend/src/panels/EvidenceHub.tsx", "apps/alpha-web/frontend/src/auth/ownerAuth.ts", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "tests/unit/test_web_owner_actions_drift.py", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "pending"
    },
    {
      "title": "P5 prove everything and ship: full gates, real-backend acceptance in both profiles, docs, PR #47 green and merged",
      "verify": "uv run python scripts/gate.py full && cd apps/alpha-web/frontend && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npm run build && npm run test:e2e && cd ../../.. && uv run pytest -q tests/unit/test_documentation_truth.py tests/unit/test_claude_md_relocation.py -m \"not network\" && uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-09-04-trader-terminal-phase4-pixel.md && gh pr checks 47",
      "expected": "Every gate green; the scripted real-backend walkthrough (both profiles, every document and dock tab, Market Watch venue/age/live, an XRP/USDT Binance pull landing in the Toolbox, a validate run opening its report) exits 0 with its screenshots beside the artboards; rule rows, BUILD-STATUS, spec addendum and findings #14–#16 updated; PR #47 CI green and merged with a merge commit; the terminal launched for the owner.",
      "rollback": "Docs-only revert; the merge is the owner's decision.",
      "files": [".claude/rules/alpha-web.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md", "docs/superpowers/plans/2026-09-04-trader-terminal-phase4-pixel.md"],
      "status": "pending"
    }
  ],
  "tier_impact": ["protected", "dag"],
  "docs_to_update": [".claude/rules/alpha-web.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md"],
  "out_of_scope": [
    "Live trading, broker readiness, order routing; the ticker is a displayed quote, never an execution price or a stored series.",
    "New statistics, new providers beyond the public ccxt ticker, new MCP tools (pinned at 62), new ADRs.",
    "Intraday timeframes (buttons stay disabled with the reason).",
    "Making holdout reveal, the reviewed-asset master or credential recovery browser actions (ADR-bound CLI steps; the UI copies the command).",
    "Automating Touch ID itself in tests (WebAuthn is stubbed in e2e; the owner presses the sensor once)."
  ],
  "files": ["apps/alpha-web/**", "packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py", "apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/**", "tests/integration/test_web_api_catalog.py", ".claude/rules/alpha-web.md", "docs/**"]
}
```

## Context

The owner's second walkthrough (2026-09-03) rejected Phase 3 on truthfulness (Market Watch),
fidelity (artboards) and usability (dead-end owner notices). Phase 4 fixes all three without
moving any statistic, reader, DAG edge, MCP tool or authority.

## Deviations
* **P1** — the Market Watch table gained a `Venue` and an `Age` column (the artboard has only
  Symbol · Last · Daily %) because the owner's two complaints — "duplicates" and "that is not
  today's price" — are answered by exactly those two cells; the artboard's three-column look is
  kept for the row anatomy (▲/▼ glyph, blue selection, `+ click to add…`). Rows are keyed by the
  stored symbol and spelled without the slash. `symbolFitsProfile` stays the only market filter.
* **P2** — `alpha data ticker` is ccxt-only like `first-bar`; equities tickers keep the stored
  close. The Live toggle lives in `alpha.settings` (`liveTicker`, default off) and the poll clears
  its overlay the moment it is switched off, so a stale live price can never linger. The generated
  `docs/governance/openapi-operation-classification.json` and `capability-authority-matrix.md`
  were rewritten by `check_openapi_operations.py --write` for the one new read-only GET.
* **P3a** — the chrome typeface is the platform UI face at 12px (`--chrome-font-size`; 11px at the
  1280px minimum so every material question still fits the 720px viewport) — the generated canvas
  tokens are untouched. Docks are 300px/345px (artboard 278/345) so the five Market Watch columns
  fit; the `Age` cell prints days since the bar (`65d`, `live`) with the exact bar date in its
  title and in the Details tab, because a full ISO date did not fit the dock. Guided/Advanced,
  New Idea, Settings and the dock toggles live in the View/Research menus as the artboard has no
  toolbar buttons for them; the ⚙ settings popover stays as the last toolbar glyph. Market Watch
  row buttons keep a 24px hit target (axe target-size) so rows are ~26px, not the artboard's 21px.
  The Data Manager's `Snapshots` tab, the Navigator's `Favorites`, the Toolbox `Alerts` tab, the
  toolbar `Stop`, the dock pin and the title-bar window glyphs are rendered disabled with the
  reason in their tooltip — nothing behind them exists yet.
* **P3b** — the report toolbar is `Export CSV · Save PNG · Compare… · Run again · Notes` plus a
  disabled save glyph (a run directory is already immutable on disk) and a print glyph: Export CSV
  writes the trades projection verbatim (`tradesCsv`), Save PNG hands over the first drawable figure
  of the current view through the bare `…/image?fmt=png` endpoint, Compare… opens the Compare
  document (the run is ticked there — Compare keeps its own selection), Notes toggles the existing
  narrative/terse explanation setting. The Governance table is `Item | State | Detail`; providers
  and storage rows split state from detail while the five hazard sentences stay verbatim in State.
  Page labels carry the artboard counts (`Research gates (1 open)`, `Overrides (N)`,
  `Glossary (N)`). The figure overlay fills the window with a `<figure> — <run> (maximised)`
  header, zoom in/out/fit that scales the served SVG in the browser (nothing is redrawn) and
  `Esc restores · run <8> · UTC`; the focus trap now walks Save PNG → Save SVG → Copy → Close →
  Zoom in. The Toolbox opens by default only on windows ≥960px tall (the artboard is 991px) so the
  1440×900 reference keeps every material research question in view. Twenty document baselines
  re-taken.

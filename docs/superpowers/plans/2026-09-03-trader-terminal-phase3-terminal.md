# Trader Terminal — Phase 3 "Terminal": Option E theme, terminal shell, profiles

```json
{
  "schema_version": 1,
  "title": "Trader Terminal Phase 3 (Terminal): Option E theme document + generated CSS tokens, server-side market field, profile manifests, document/dock registry with menu bar, toolbar, Market Watch, Navigator, MDI documents, Toolbox and status bar",
  "context": "Phases 1 (docs/superpowers/plans/2026-09-01-trader-terminal-phase1-work.md) and 2 (docs/superpowers/plans/2026-09-02-trader-terminal-phase2-clean.md) are complete on feat/trader-terminal-phase1-work. Spec docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md sections 4.1, 4.2, 4.6 and 7 define Phase 3: the Option E visual system (light chrome, black canvases, square corners, 11px UI) as a theme document loaded by alpha_research/figures/theme.py with the SPA's CSS tokens generated from it and drift-tested; a server-side additive `market` field on run and project projections; static crypto/equities profile manifests that gate windows, docks and provider lists in the browser without ever becoming a permission; and the classic terminal shell — title bar, eleven-entry menu bar, toolbar with the symbol/venue/timeframe combo + status chip + Governance, left Market Watch and Navigator docks, an MDI document area with bottom tabs (only the active document mounts), a bottom Toolbox (Jobs · Trades · Backtests · Data pulls · Log) and a right Data Manager dock, and a status bar. The six-screen tab strip, LibraryRail and ContextBar are replaced; the Phase 2 Governance dialog becomes a Governance document. Nothing here changes a statistic, a point-in-time reader, the DAG, MCP, or any authority; figure bytes change deliberately (RENDERER_VERSION 3 -> 4) and the twelve screenshot baselines are replaced by document baselines. Finding #12 (workflow-centric navigation) closes here.",
  "assumptions": [
    {
      "statement": "There is one hardcoded default theme: load_theme(theme_id='alpha-dark') in theme.py:119, called with no argument at the five figures_cmds.py sites; the cache key already carries theme_id + theme_digest + renderer_version (figure_cache.py:53-85, _figures.py:119-137), so switching the default to `terminal-classic` invalidates every cached figure without a new route or flag, and alpha_web keeps importing no alpha_research.",
      "verified_by": "navigator read of theme.py:119-127, figures_cmds.py:67,192,362,400,430, alpha_cli/figure_cache.py:53-85, alpha_web/_figures.py:119-137 on 2026-09-03; T3 pins the default with tests/unit/test_figure_theme.py::test_default_theme_is_terminal_classic and lint-imports."
    },
    {
      "statement": "tests/unit/test_theme_drift.py:22 forces the CSS --bg/--panel tokens to equal the figure theme's bg/panel, which Option E (light chrome around black canvases) cannot satisfy; the resolution is a token split: figure-theme roles mirror into generated `--canvas-*` tokens, chrome tokens live in a hand-written CSS block whose text/surface pairs are AA-tested from the CSS values, and the Theme dataclass gains no field.",
      "verified_by": "navigator read of tests/unit/test_theme_drift.py:22-72 and theme.py:35-74 (frozen slots dataclass) on 2026-09-03; T3 rewrites the drift test to the split and keeps the --faint never-text rule."
    },
    {
      "statement": "Figure fonts stay `DejaVu Sans`/`DejaVu Sans Mono` in the theme JSON because render.py:189-199 fails loud on a font matplotlib cannot find and CI has no Verdana/Tahoma; the 11px Verdana/Tahoma face is CSS-only with a system fallback stack, so figure determinism (two-process byte identity) is unchanged.",
      "verified_by": "navigator read of render.py:189-199 and tests/integration/test_figure_determinism.py:82-137 on 2026-09-03; T3 pins font_family with test_figure_font_is_the_pinned_dejavu_face."
    },
    {
      "statement": "Only theme.py (one default-id line), version.py (bump + changelog line) and any render.py styling change are quant-tier (.py under packages/alpha-research/src; scripts/gate.py:95,255-272); the JSON theme, CSS, TS, figures_cmds.py, _figures.py, models.py and _runs.py are neither quant nor risk tier. T3 therefore carries /verify-quant PASS and /review-gate APPROVE; no other slice does.",
      "verified_by": "navigator read of scripts/gate.py:91-128,255-272 on 2026-09-03; the T3 verify line runs both gates."
    },
    {
      "statement": "Run manifests carry `source` (e.g. `ccxt:binance`, `tiingo`) and `symbol`/`symbols`; `market` is derived server-side in _runs.run_record next to display_name — source wins (ccxt/binance/bybit/coinbase -> crypto; tiingo/yfinance/stooq/quantpad -> equities), else a `/`-pair symbol -> crypto, else `unknown` (never guessed). ProjectSummary carries no symbol or source and alpha_web only relays `alpha project list --json`, so every project is `market: unknown` until the CLI projection is extended (out of scope); the Navigator always shows `unknown` rows under a labelled leaf.",
      "verified_by": "navigator read of _runs.py:402-455, api/models.py:187-224,1427-1437, _development.py:45-61 on 2026-09-03; T1 pins every branch in tests/integration/test_web_api_runs.py and the project case in test_web_api_development.py."
    },
    {
      "statement": "`profile` remains a display setting (settings.ts, html[data-profile]) and a static manifest in shell/profiles.ts; the browser filters providers by ProviderDefinition.asset_classes and lists by the server `market` field; no request ever carries `profile`.",
      "verified_by": "navigator read of settings.ts:6,13,66-69, api/control.py:14, models.py:680-696, DataManager.tsx:79-123 on 2026-09-03; T1 walks openapi.json for any `profile` parameter/property and T7 collects every request during a profile switch."
    },
    {
      "statement": "The `.claude/rules/alpha-web.md` row describing six fixed screens is a v1 line that tests/unit/test_claude_md_relocation.py requires verbatim in CLAUDE.md ∪ rules ∪ docs/BUILD-STATUS.md; T8 moves that exact line into the dated BUILD-STATUS record (allowed by .claude/rules/docs.md) and writes the document/dock row in its place under gate.py ack; tests/fixtures/claude_md_v1.md is never edited.",
      "verified_by": "navigator read of .claude/rules/alpha-web.md:32, tests/unit/test_claude_md_relocation.py:28-56, tests/fixtures/claude_md_v1.md:327 on 2026-09-03; T8 runs the relocation test."
    },
    {
      "statement": "No committed figure byte goldens exist (tests/fixtures has none); the figure byte contract is the two-process determinism suite plus render assertions, so 'goldens re-baseline' means the Playwright screenshot baselines, which are replaced (12 `*-screen-*.png` -> 12 `*-document-*.png`) in T7.",
      "verified_by": "navigator and test-architect globs of tests/fixtures and e2e/workstation.spec.ts-snapshots on 2026-09-03."
    }
  ],
  "alternatives_considered": [
    "Add a `chrome` mapping to the Theme dataclass and JSON so Python owns the chrome palette too: rejected — the Theme is a frozen slots dataclass consumed only by the figure renderer; chrome colours never reach Python, and adding fields there widens a quant-tier edit and the theme digest for no consumer. The CSS block is AA-tested directly.",
    "Keep alpha-dark as default and pass `--theme terminal-classic` through the CLI and a web query parameter: rejected — the web cannot pick a theme per request without a new route and cache-key dimension; one default keeps every figure and the SPA on the same palette.",
    "Ship Verdana/Tahoma to matplotlib for figure text: rejected — render.py fails loud on unknown fonts and CI machines differ; determinism would depend on installed fonts.",
    "Keep the six screens and add docks around them: rejected — the spec's document/dock model is the Phase 3 deliverable and finding #12; layering docks on the tab strip would keep two navigation systems.",
    "Add a docking library (dockview/react-mosaic) for MDI: rejected — a new runtime dependency (license matrix, bundle, a11y unknowns) for a fixed layout of three dock sides and one document area that CSS grid plus a small MDI reducer covers."
  ],
  "pre_mortem": [
    "The mockup palette fails the repo's WCAG maths (chrome label #8a6d00 on #f2f2f2 = 4.38:1, up-text #1a8f47 = 3.7:1, down-text #c8312f on #e6e6e6 = 4.27:1; canvas accent #316ac5 on black = 3.8:1 forces the substrate lower; cyan #00e5ff is outside the categorical lightness band): T3 writes those tests first and darkens the values until they pass — the spec says the mockup values are a starting point, not exempt.",
    "Flipping the default theme without bumping RENDERER_VERSION leaves stale cached SVGs reachable: T3 bumps to 4 with a changelog line and asserts it; the cache key also carries the new theme digest.",
    "theme.py/version.py edits trip the quant attestation and mutation gate: T3 keeps the Python diff to the default id, the version bump and any render.py styling, runs /verify-quant (colour/data contract checks listed in the test plan) and /review-gate before commit.",
    "The document/dock refactor breaks every e2e navigation site at once (≥25 getByRole('tab') sites, library rail locators, Governance dialog locators): T7 introduces an openDocument(page, id) helper and dock locators in one slice and is kept under the 1000-non-docs-line commit guard by splitting the harness rewrite (T7a) from the baseline replacement (T7b).",
    "The topbar was already full at 1280px in Phase 2 (axe target-size): the toolbar/status bar are laid out with explicit widths and the chromium-minimum project runs in every slice's e2e gate, not only in T7.",
    "Only the active document may mount (no polling behind a hidden tab): the MDI reducer keeps inactive documents unmounted and T7 asserts an inactive document's endpoint is not requested.",
    "The `market` field lands in RunListItem/RunDetail/ProjectSummary (StrictModel) and every typed harness fixture must gain it or tsc fails: T1 regenerates openapi.json, generated.ts and the fixtures in the same slice.",
    "Screenshot baselines are replaced, not updated, so a flaky render would be baked in: T7b re-snapshots with --update-snapshots=all and repeats the run once without the flag on both screenshot projects.",
    "static/app is forgotten after a frontend slice: every frontend slice ends with npm run build and git status --short apps/alpha-web/src/alpha_web/static/app."
  ],
  "slices": [
    {
      "title": "T1 server-side `market` on run and project projections; `profile` provably never an API parameter",
      "verify": "uv run pytest -q tests/integration/test_web_api_runs.py tests/integration/test_web_api_development.py tests/unit/test_web_contracts.py -m \"not network\" && uv run python scripts/generate_web_openapi.py --check && uv run python scripts/check_openapi_operations.py && uv run lint-imports && cd apps/alpha-web/frontend && npm run generate:api && npx tsc -b && npm run lint -- --deny-warnings && npm run build && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app apps/alpha-web/frontend/src/api/generated.ts && uv run python scripts/gate.py fast",
      "expected": "RunListItem, RunDetail, the run_added/run_updated activity payload and ProjectSummary carry `market: 'crypto' | 'equities' | 'unknown'` derived in _runs.run_record (source wins; pair convention; else unknown; projects unknown until the CLI projection carries a source); a `profile` query parameter is rejected (422) and openapi.json contains no `profile` parameter or property; typed harness fixtures gain the field.",
      "rollback": "Remove the field from _runs.py, models.py and the fixtures; regenerate contracts.",
      "files": ["apps/alpha-web/src/alpha_web/_runs.py", "apps/alpha-web/src/alpha_web/api/models.py", "apps/alpha-web/src/alpha_web/api/runs.py", "apps/alpha-web/frontend/openapi.json", "apps/alpha-web/frontend/src/api/generated.ts", "apps/alpha-web/frontend/src/api/types.ts", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "tests/integration/test_web_api_runs.py", "tests/integration/test_web_api_development.py", "tests/unit/test_web_contracts.py", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "T2 static profile manifests (crypto / equities) and Data Manager defaults derived from them",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/shell/profiles.test.ts src/panels/dataManagerModel.test.ts && npm run lint -- --deny-warnings && npx tsc -b && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "shell/profiles.ts exports a deep-frozen PROFILES record (id, label, windows, docks, providers, defaultSource, defaultVenue, symbolStyle, starterWatchlist, paperVenues, glossaryTags) for crypto (ccxt + crypto-house families; hides options, screener, corporate actions, IBKR paper) and equities (tiingo default, yfinance, stooq, quantpad; hides funding/OI/on-chain/DEX, Binance sandbox, crowding); market-neutral windows (kronos, ml-lab, jobs, governance) in both; dataManagerModel.pullDefaults/starterSymbols read the manifest; the registry cross-check test is written red and turns green in T4.",
      "rollback": "Delete profiles.ts and restore dataManagerModel's inline defaults.",
      "files": ["apps/alpha-web/frontend/src/shell/profiles.ts", "apps/alpha-web/frontend/src/shell/profiles.test.ts", "apps/alpha-web/frontend/src/panels/dataManagerModel.ts", "apps/alpha-web/frontend/vitest.config.ts"],
      "status": "done"
    },
    {
      "title": "T3 Option E theme document `terminal_classic.json` as default, generated `--canvas-*` CSS tokens, chrome token block with AA tests, RENDERER_VERSION 4 (quant tier)",
      "verify": "uv run pytest -q tests/unit/test_figure_theme.py tests/unit/test_theme_drift.py tests/unit/test_figure_render.py tests/unit/test_figure_cache.py tests/unit/test_figures_cli_commands.py tests/integration/test_figure_determinism.py -m \"not network\" && uv run alpha figures theme-css --out apps/alpha-web/frontend/src/theme.generated.css --check && uv run lint-imports && cd apps/alpha-web/frontend && npx vitest run src/util/theme.drift.test.ts && npm run lint -- --deny-warnings && npm run build && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "themes/terminal_classic.json (black canvas: bg #000000, frame/line #e0e0e0, grid #2a2a2a, axis ink #c8c8c8, up #2fc36a, down #e5484d, accent #316ac5, a verified four-slot categorical ramp, DejaVu fonts) passes every existing palette test parametrised over both themes; load_theme() defaults to terminal-classic; RENDERER_VERSION == 4 with a changelog line; `alpha figures theme-css --out … [--check]` writes frontend/src/theme.generated.css (`--canvas-*` roles, `--r: 0`, `--r-lg: 0`, `--font-size: 11px`) from the importable `theme_css` function and --check is byte-exact; index.css gains the hand-written light chrome block (window #e6e6e6, panel #f2f2f2, title #dcdcdc, controls #e0e0e0, bevels #ffffff/#8a8a8a, ink #111111, secondary #555555, rule #d4d4d4, input #ffffff, selection #316ac5 on white, label/up/down darkened until AA) whose text×surface pairs test_theme_drift proves ≥ 4.5:1; tokens.ts FALLBACK mirrors the canvas roles with an 11px font; /verify-quant PASS and /review-gate APPROVE recorded.",
      "rollback": "Delete terminal_classic.json and the generated CSS, restore the default id, version 3 and index.css tokens.",
      "files": ["packages/alpha-research/src/alpha_research/figures/theme.py", "packages/alpha-research/src/alpha_research/figures/version.py", "packages/alpha-research/src/alpha_research/figures/render.py", "packages/alpha-research/src/alpha_research/figures/themes/terminal_classic.json", "apps/alpha-web/frontend/src/theme.generated.css", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/src/main.tsx", "apps/alpha-web/frontend/src/util/tokens.ts", "apps/alpha-web/frontend/src/util/theme.drift.test.ts", "tests/unit/test_figure_theme.py", "tests/unit/test_theme_drift.py", "tests/unit/test_figure_render.py", "tests/unit/test_figures_cli_commands.py", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "T4 document and dock registries replace screens.tsx",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/shell/documents.test.ts src/shell/profiles.test.ts && npm run lint -- --deny-warnings && npx tsc -b && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "shell/documents.ts exports DOCUMENTS (chart, report, compare, build, research, governance, forecast, ml, jobs kinds with title/component/params), REPORT_DOCUMENT, document(id) that throws on an unknown id, and DOCKS (left: MarketWatch, Navigator; right: DataManager + Research/Strategy tools; bottom: Toolbox with tabs Jobs · Trades · Backtests · Data pulls · Log); the carried-over invariants (Standalone Sandbox separate from ResearchCockpit, no Glossary pane, no hazard stripe) hold; screens.test.ts is deleted; every profile window/dock id resolves.",
      "rollback": "Restore screens.tsx and screens.test.ts; delete documents.ts.",
      "files": ["apps/alpha-web/frontend/src/shell/documents.ts", "apps/alpha-web/frontend/src/shell/documents.test.ts", "apps/alpha-web/frontend/src/shell/screens.tsx", "apps/alpha-web/frontend/src/shell/screens.test.ts", "apps/alpha-web/frontend/vitest.config.ts"],
      "status": "done"
    },
    {
      "title": "T5 pure shell models: MDI reducer, menu assignment, toolbar/title bar, status bar",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/shell && npm run lint -- --deny-warnings && npx tsc -b && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "mdiModel (open/activate/close with stable insertion order, keyed documents such as report:<run_id>, closing the last leaves active null, unknown close throws, deterministic), menuModel (the eleven menus in spec order; every /api/commands entry assigned to exactly one menu, unmapped group throws; Window lists open documents; Governance under View), toolbarModel (M15 H1 H4 D1 W1 with disabled + reason for unavailable timeframes; windowTitle 'ALPHA Terminal — <Profile> — [<symbol · venue · tf>]'), statusBarModel (segments in spec order; injected clock; SSD segment from storageRow, never a cached ready; hovered bar null -> '—', NaN throws) — all in the vitest allow-list.",
      "rollback": "Delete the four model files and tests.",
      "files": ["apps/alpha-web/frontend/src/shell/mdiModel.ts", "apps/alpha-web/frontend/src/shell/mdiModel.test.ts", "apps/alpha-web/frontend/src/shell/menuModel.ts", "apps/alpha-web/frontend/src/shell/menuModel.test.ts", "apps/alpha-web/frontend/src/shell/toolbarModel.ts", "apps/alpha-web/frontend/src/shell/toolbarModel.test.ts", "apps/alpha-web/frontend/src/shell/statusBarModel.ts", "apps/alpha-web/frontend/src/shell/statusBarModel.test.ts", "apps/alpha-web/frontend/vitest.config.ts"],
      "status": "done"
    },
    {
      "title": "T6 Market Watch and Navigator models and panels; Governance glossary filtered by profile tags",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/panels/marketWatchModel.test.ts src/panels/navigatorModel.test.ts src/panels/governanceModel.test.ts && npm run lint -- --deny-warnings && npx tsc -b && cd ../../.. && uv run python scripts/gate.py fast",
      "expected": "marketWatchModel rows = profile watchlist ∪ stored pairs (de-duplicated, watchlist first) with last/daily% from the candles projection (up/down/flat tones; missing or non-finite -> '—', never 0.00), tabs Symbols · Details · Data; navigatorModel builds the six groups (Strategies · Backtests · Research cases · Data · Scripts · Paper sandbox), files runs by the server `market` field only, always shows `unknown` under a labelled leaf, honours showAll, lists venues + Expansion SSD from storageRow; governanceModel's Glossary page filters by PROFILES[profile].glossaryTags with untagged entries in both; MarketWatch.tsx and Navigator.tsx render them.",
      "rollback": "Delete the two models/panels and restore the Glossary page.",
      "files": ["apps/alpha-web/frontend/src/panels/marketWatchModel.ts", "apps/alpha-web/frontend/src/panels/marketWatchModel.test.ts", "apps/alpha-web/frontend/src/panels/MarketWatch.tsx", "apps/alpha-web/frontend/src/panels/navigatorModel.ts", "apps/alpha-web/frontend/src/panels/navigatorModel.test.ts", "apps/alpha-web/frontend/src/panels/Navigator.tsx", "apps/alpha-web/frontend/src/panels/governanceModel.ts", "apps/alpha-web/frontend/src/panels/governanceModel.test.ts", "apps/alpha-web/frontend/src/explain/glossary.ts", "apps/alpha-web/frontend/vitest.config.ts"],
      "status": "done"
    },
    {
      "title": "T7a terminal shell in App.tsx + Playwright harness rewritten to documents and docks",
      "verify": "cd apps/alpha-web/frontend && npm run lint -- --deny-warnings && npm run test:coverage && npm run build && npx playwright test --project=chromium-minimum && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "App.tsx renders title bar, role=menubar (eleven menus, ArrowLeft/Right, Enter, Escape), toolbar (chart type, timeframes, Data/Research/Run/Stop/Report, Profile combo, symbol/venue/timeframe combo replacing ContextBar, search, status chip, Governance), left docks Market Watch + Navigator (replacing LibraryRail), the MDI document area with bottom tablist (only the active document mounts; #run= deep link opens a report document), bottom Toolbox tabs, right Data Manager dock, and the status bar; Governance opens as a document; the harness `SCREENS` loop becomes a `DOCUMENTS` loop with an openDocument(page, id) helper, dock locators replace every screen-tab/library-rail/Governance-dialog site, the watermark test asserts report chip → toolbar chip → Governance document (2 then 3, exact), the profile-switch test asserts no request carries `profile`, the inactive-document test asserts no polling, and the Phase 3 acceptance test walks every document at all viewports; chromium-minimum (no screenshots) is green.",
      "rollback": "Restore App.tsx, LibraryRail, ContextBar and the harness from the T6 commit.",
      "files": ["apps/alpha-web/frontend/src/App.tsx", "apps/alpha-web/frontend/src/shell/**", "apps/alpha-web/frontend/src/components/CommandPalette.tsx", "apps/alpha-web/frontend/src/panels/actions.ts", "apps/alpha-web/frontend/src/panels/Governance.tsx", "apps/alpha-web/frontend/src/panels/JobMonitor.tsx", "apps/alpha-web/frontend/src/panels/PriceChart.tsx", "apps/alpha-web/frontend/src/components/PriceChartCanvas.tsx", "apps/alpha-web/frontend/src/components/KronosKlineCanvas.tsx", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "T7b document screenshot baselines replace the screen baselines; full frontend gate",
      "verify": "cd apps/alpha-web/frontend && npx playwright test --update-snapshots=all && npm run test:e2e && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "The twelve `*-screen-{chromium-reference,chromium-wide}.png` baselines are deleted and twelve `*-document-*.png` baselines committed; a second run without the flag is green on all four projects; static/app clean.",
      "rollback": "Restore the previous baselines.",
      "files": ["apps/alpha-web/frontend/e2e/workstation.spec.ts-snapshots/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "T8 rule rewrite under ack, docs honesty, full gate",
      "verify": "uv run python scripts/gate.py full && uv run pytest -q tests/unit/test_documentation_truth.py tests/unit/test_claude_md_relocation.py -m \"not network\" && uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-09-03-trader-terminal-phase3-terminal.md",
      "expected": "The six-fixed-screens row of .claude/rules/alpha-web.md is moved verbatim into the dated docs/BUILD-STATUS.md record and replaced by the document/dock registry row (Edit tool after gate.py ack); CLAUDE.md 'New Workstation panel' pointer names documents.ts; docs/BUILD-STATUS.md gains the Phase 3 record; the spec marks Phase 3 implemented; finding #12 carries its fixing commits; every slice is done; the full gate is green including the 14-wheel smoke.",
      "rollback": "Docs-only; revert the doc commit.",
      "files": [".claude/rules/alpha-web.md", "CLAUDE.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md", "docs/superpowers/plans/2026-09-03-trader-terminal-phase3-terminal.md"],
      "status": "pending"
    }
  ],
  "tier_impact": ["quant", "risk", "protected", "dag", "determinism"],
  "docs_to_update": [".claude/rules/alpha-web.md", "CLAUDE.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md"],
  "out_of_scope": [
    "Live trading, broker readiness, new statistics, new providers, new MCP tools (pinned at 62).",
    "Extending `alpha project list --json` with a source/universe field so projects can carry a real market (projects stay `unknown`; a follow-up CLI plan).",
    "Intraday timeframes: M15/H1/H4/W1 toolbar buttons are present but disabled with the reason 'daily data only' because every engine run is daily.",
    "Shipping Verdana/Tahoma to matplotlib; figure text stays DejaVu.",
    "A docking library or user-rearrangeable layouts; the dock sides are fixed by the registry.",
    "Mobile layouts; the three desktop viewports remain the gate.",
    "An Alerts tab (dropped by the owner; no alert engine exists)."
  ],
  "files": ["apps/alpha-web/**", "packages/alpha-research/src/alpha_research/figures/**", "apps/alpha-cli/src/alpha_cli/figures_cmds.py", "tests/unit/**", "tests/integration/test_web_api_runs.py", "tests/integration/test_web_api_development.py", "tests/integration/test_figure_determinism.py", "docs/**", ".claude/rules/alpha-web.md", "CLAUDE.md"]
}
```

## Context

Phase 3 turns the Workstation into the approved classic desktop terminal (spec §4.2, artboards at
1440×900, Option E palette §4.6) and makes the crypto/equities profile a first-class manifest
(§4.1). Everything a trader sees changes; nothing an auditor relies on does: no statistic, PIT
reader, DAG edge, MCP tool or authority path moves. Figure bytes change deliberately behind a
renderer version bump; screenshot baselines are replaced.

## Slices (order, each behind its own gate)

T1 `market` (backend) → T2 profiles (pure TS) → T3 theme + generated tokens + renderer bump
(quant tier: `/verify-quant` + `/review-gate`) → T4 registries → T5 shell models → T6 Market
Watch / Navigator → T7a shell + harness rewrite → T7b baselines + full frontend gate → T8 rule
rewrite under `gate.py ack`, docs, full gate.

## Test plan (test-architect items, 2026-09-03)

* T1 → #1–#7 (`test_web_api_runs.py`: market from source before symbol; pair-convention fallback
  only; never defaults, `profile` query rejected; source wins a conflict; `test_web_api_development.py`
  project summary `unknown`; `test_web_contracts.py` no `profile` parameter/property in openapi.json;
  contract regeneration + typed fixtures).
* T2 → #8–#14 (`profiles.test.ts`: exactly two frozen data-only manifests; crypto/equities
  windows, providers, defaults, watchlists; market-neutral windows in both; `pullDefaults`/
  `starterSymbols` derived; registry cross-check written red until T4).
* T3 → #15–#32 (`test_figure_theme.py` parametrised over both themes; default is
  terminal-classic; canvas text AA on black; canvas marks ≥ 3:1; categorical/CVD/substrate for the
  new ramp; DejaVu pinned; `test_theme_drift.py` rewritten: generated CSS byte-current, `--canvas-*`
  mirror, chrome text × chrome surface AA matrix, `--faint` never text, square corners + 11px;
  `theme.drift.test.ts` on the canvas roles; `test_figure_render.py` black canvas with light frame,
  two themes render different bytes, `RENDERER_VERSION == 4` with changelog). Deviation from the
  architect's #18–#21/#26: chrome lives in CSS, not in the Theme dataclass (see alternatives), so the
  chrome AA matrix reads CSS values and the digest test is not needed.
  **Quant-verifier scope for T3:** diff confined to `theme.py` (default id), `version.py`,
  `render.py` styling and `themes/*.json`; independently recompute WCAG 2.1 contrast and OKLab ΔE
  under the three Machado (2009) severity-1.0 matrices for every asserted pair with the thresholds
  in `test_figure_theme.py` unchanged; both JSON files canonical, lowercase hex, exactly four unique
  categorical slots disjoint from semantic colours; `RENDERER_VERSION` +1 with changelog and
  `FIGURES_CACHE_VERSION` untouched and equal to `alpha_cli.figure_cache`; `render.py` pure
  (two-process determinism suite green); `font_family` DejaVu; `lint-imports` green.
* T4 → #33–#35 (`documents.test.ts`); T5 → #36–#40; T6 → #41–#43; T7 → #45–#54 (documents loop,
  menubar/MDI keyboard, profile gating with request capture, active-only mounting, Navigator opens a
  report, status bar truth, Market Watch never invents a price, watermark three surfaces, Phase 3
  acceptance); T8 → #55.
* Rewritten because the shell changes: `screens.test.ts` → `documents.test.ts`; every
  `getByRole('tab', { name: <screen> })`, `.library-row`, Governance `role=dialog` and
  Escape/focus-return site in the harness; the `@reference-only` cold-shell budget test ("screen
  switch" → document switch); `cryptoDataCenterJourney` and its callers in `crypto-data.spec.ts` /
  `real-backend.spec.ts` navigate to the right Data Manager dock. Unchanged regression gates:
  `statusModel`, `reportModel`, `figureExport`, `jobTableModel`, `dataManagerModel` tests.
* Markers: none new; **no `bias_guard`** (no PIT reader), no `network`.

## DAG / look-ahead / determinism impact

* **DAG:** `alpha_web` keeps importing only `alpha_core` + public CLI seams; the theme is selected in
  `alpha_research` (default) and published through the existing `figures catalog` key environment;
  `uv run lint-imports` in T1, T3 and T8.
* **Look-ahead:** none — `market` and every shell model are projections of completed manifests and
  static manifests; no `as_of` path is touched.
* **Determinism:** figure bytes change once, behind `RENDERER_VERSION` 4 and the new theme digest;
  the two-process determinism suite must stay green in T3; the MDI reducer and every model are pure
  and clock-injected.

## Deviations recorded during /implement

* **T1** — `profile` on `/api/runs` is ignored (the response equals the unfiltered one) rather than
  rejected with 422: FastAPI drops unknown query parameters and adding a rejection dependency for one
  parameter is speculative; the openapi walk proves no route or schema names `profile`.
  `ProjectSummary.market` is a defaulted field (`"unknown"`), so the relay does not touch CLI rows.
* **T3** — figure titles stay above the frame (matplotlib figure chrome), not inside it; the
  independent review found `faint` text illegible on black (raised to #767676, now AA-tested as
  canvas text), the zero baseline repurposing the frame colour (now muted and dashed), heatmap
  "absent" cells vanishing when panel == bg (panel #141414), and the rc changes untested (the render
  test now asserts four framed spines, a dotted grid and a framed legend); the `scripts/` shim was
  removed in favour of `alpha figures theme-css`; `.claude/rules/alpha-research.md` names both theme
  documents (one ack).
  Committed as d8a04c5 with both attestations bound. Low review findings carried as follow-ups:
  a transparent export keeps `legend.facecolor` at the theme background rather than mirroring
  `face`; the frozen v1 alpha_dark row and the new terminal_classic row sit side by side in the
  rule (the v1 line is verbatim by test, the new row states the current default).
* **T2** — the registry cross-check (architect #13) is written in T4, not T2: a test importing a
  module that does not exist yet fails `tsc -b`, which every slice's build gate runs.
* **T4** — the lookup is `documentOf(id)` / `dockOf(id)` rather than `document(id)`: a module
  export named `document` shadows the DOM global that Governance.tsx already uses. `screens.tsx`
  stays until T7a because App.tsx and the command palette still render it; only `screens.test.ts`
  is replaced. Docks are declarative (id, side, title, tabs) — Market Watch and Navigator have no
  component until T6. Every profile window id resolves: the crypto-only ids open the governed
  Crypto Data Center on their section/family through document params (`initialSection`,
  `initialFamily`), crowding opens the research cockpit, and the Governance document is the dialog's
  page tree without the modal (`GovernanceDocument`), which moved that Governance.tsx split from
  T7a into T4.
* **T5** — a command's group is the first word of its catalog id (`backtest run` → `backtest`);
  `GROUP_MENU` maps the twenty-three served groups and `tests/unit/test_web_menu_groups.py`
  (added, not in the plan's file list) reads that table out of the TypeScript source and fails
  when the served catalog gains or loses a group, so the runtime throw can never be reached by a
  CLI change alone. The venue in the title bar comes from the profile manifest (`venueLabel`)
  because the linked context carries symbol and timeframe but no venue.
* **T6** — stored symbols (`/api/symbols`) carry no server `market`, so Market Watch keeps the
  other market out by the profile's symbol style (pair vs ticker), the same pair convention the
  server's own fallback uses; runs and projects are still filed by the server field only. The
  glossary had no market-specific term to filter, so three tagged entries were added (funding rate,
  open interest — crypto; ex-dividend date — equities) and `glossaryEntries(profile)` lives in
  `governanceModel`; the Glossary panel reads it. `MarketWatch.tsx` and `Navigator.tsx` exist but
  are not mounted until T7a. The post-edit hook's ESLint lint of `.tsx` files reports a missing
  `eslint.config.*` (the frontend lints with oxlint, which passes) — noted for the retrospective.
* **T7a** — the shell is `App.tsx` plus `shell/{MenuBar,Toolbar,SettingsMenu,DocumentArea,Toolbox,
  StatusBar}.tsx`; `screens.tsx` and `LibraryRail.tsx` are deleted and the Governance modal became
  the document only. Documents may declare `side` panes (Build keeps Strategy Development beside
  Development Next Step / Standalone Sandbox; Research keeps Backlog, Literature and Codex beside the
  cockpit) so the gate-lock count of two stays honest; document titles never equal a pane title
  (`Research`, `Machine learning`). The MDI strip has one close button for the active document
  (axe forbids non-tab children inside a tablist; Delete on a tab also closes it). The Toolbox is
  collapsible and starts collapsed below an 800px-high window so the cockpit's material questions
  stay in view at 1280×720; its Data pulls tab shows provider readiness. There is no Stop button:
  the terminal owns no running process (jobs cancel from the Jobs table). The watermark's three
  surfaces are proven sequentially (report chip + toolbar chip, then toolbar chip + Governance row,
  then the report chip again) because Governance is a document and only the active document
  mounts. A fresh terminal charts the profile's default symbol. Chromium-minimum: 42 green; the
  screenshot projects are re-baselined in T7b (twenty `*-document-*.png`, ten documents × two
  projects, rather than twelve). The intended two-part commit landed as one (5771447, 1421
  changed lines; the guard did not block) because zsh does not word-split an unquoted variable of
  paths — the "part 2" in its subject is a misnomer.
* **T7b** — `--update-snapshots=all` wrote the twenty `*-document-*.png` baselines; the `25k bars`
  budget test then failed once because the status bar repeats the bar count, so the harness scopes
  both bar-count assertions to the Price pane. The unflagged `npm run test:e2e` is green on all
  four projects (128 passed) and `static/app` is clean. Two pre-existing
  `research-desk-chromium-{reference,wide}.png` files are referenced by no test and are left in
  place (not this slice's mess).

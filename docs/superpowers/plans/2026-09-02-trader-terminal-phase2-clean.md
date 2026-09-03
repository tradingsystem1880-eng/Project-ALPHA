**Delivery state:** Completed (2026-09-02; C1–C8 committed on `feat/trader-terminal-phase1-work`).

# Trader Terminal — Phase 2 "Clean": a report a trader can read, governance out of the way

```json
{
  "schema_version": 1,
  "title": "Trader Terminal Phase 2 (Clean): run display names, Strategy Performance Report, figure maximise/export, Governance window, status chip + Notes, jobs table",
  "context": "Phase 1 (docs/superpowers/plans/2026-09-01-trader-terminal-phase1-work.md, commits ab2d55c..21030b4) made crypto data pulling work. The owner's remaining findings #8-#12 (docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md) are about reading results and not being shouted at: run rows show 8-hex ids, the run report is a LEGACY_CONTEXT banner plus a five-column outcome band plus three tabs plus an inner tree plus per-figure prose, figures cannot be maximised or saved comfortably, and governance text (hazard stripes, authority notes, the Operate glossary footer) sits on every working screen. Spec docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md sections 4.4, 4.5 and 7 (Phase 2) define the fix: a server-computed additive `display_name` on the run projection, a Strategy Performance Report with a left tree and a Summary table, figure maximise with Save PNG / Save SVG / Copy and Esc, one Governance pane on Operate reached from a topbar Governance button, a status chip, the existing explain toggle acting as Notes, and one dense jobs table. Nothing here changes authority, statistics, figure bytes, the DAG, MCP, or any point-in-time reader; the research-gate watermark stays visible on at least three surfaces (report title-bar chip, status-bar segment, Governance pane).",
  "assumptions": [
    {
      "statement": "Run manifests carry no timeframe or start/end fields (RunSpec has strategy_name, params, periods_per_year; every engine run is daily), so the display name uses the constant `D1` and takes its date range from the run's equity_curve.parquet `ts` min/max through the existing bounded Polars projection; runs without a curve (optim, propfirm) omit the range.",
      "verified_by": "navigator read of alpha_cli/_runner.py:45-81, backtest_cmds.py:453-469, alpha_web/_runs.py:388-426 and :501-513 on 2026-09-02; slice C1's Python test pins both the with-curve and no-curve forms."
    },
    {
      "statement": "`alpha_web/_runs.run_record` is the single builder for /api/runs items and run_added/run_updated activity events (mtime-cached), and RunListItem/RunDetail are StrictModel (extra=forbid), so `display_name` is added in run_record + run_detail, the models, openapi.json, generated.ts and every typed e2e RunListItem fixture together.",
      "verified_by": "navigator read of alpha_web/_runs.py:388-426,471-498, api/models.py:13-14,187-230, e2e/support/workstationHarness.ts:1118-1160,1558-1574,2019 on 2026-09-02."
    },
    {
      "statement": "The venue in a display name comes only from fields the run manifest already carries (`source`, e.g. `ccxt:binance`, or the snapshot id); alpha_web never resolves snapshots through `_runner.verified_snapshot_hash` (risk-tier) and imports no alpha_data.",
      "verified_by": "navigator tier check on 2026-09-02 (scripts/gate.py:91-94 risk list; import-linter contract `alpha_web imports only public platform surfaces`); `uv run lint-imports` in C1 and C8."
    },
    {
      "statement": "Figure question/uncertainty/caveat texts are Python-authored (alpha_research FigureDefinition, non-empty enforced) and delivered in the figure sidecar; Phase 2 keeps them in the DOM (visually hidden when explain=terse) and never edits alpha_research, so no quant attestation is owed.",
      "verified_by": "navigator read of alpha_research/figures/catalog.py:36-61, alpha_web/_figures.py:204-218, FigureCard.tsx:126-143 on 2026-09-02; C8 greps the diff for packages/alpha-research."
    },
    {
      "statement": "No modal/dialog component exists in the SPA (only role=dialog popovers; @radix-ui/react-dialog is not a dependency), so the figure maximise is a fixed-position overlay div with role=dialog, aria-modal, a focus trap on its three buttons and an Esc keydown handler, following the App.tsx palette precedent; Copy uses navigator.clipboard.write on the existing PNG endpoint and needs no new route.",
      "verified_by": "navigator grep of src/ for dialog|modal|requestFullscreen|clipboard on 2026-09-02 (App.tsx:263-274, V3Workbenches.tsx:470-473, ChartDataAlternative.tsx:38-39, api/figures.py:58-97)."
    },
    {
      "statement": "The research-gate watermark e2e test asserts only the Results watermark text and the Operate providers override text today; rewriting it to assert the report title-bar chip, the status-bar segment and the Governance pane keeps the R6g rule of three surfaces and removes nothing.",
      "verified_by": "navigator read of e2e/support/workstationHarness.ts:2912-2931 and tests/integration/test_web_api_runs.py:197 on 2026-09-02; the rewritten test in C5 asserts three distinct surfaces."
    },
    {
      "statement": "Phase 2 keeps the six fixed screens; the Governance pane replaces the Glossary foot on Operate and the topbar Governance button is showPane('operate','Governance'), so `.claude/rules/alpha-web.md` needs only a module-table row (protected, one ack) and no shell-model rewrite (Phase 3).",
      "verified_by": "navigator read of shell/screens.tsx:129-141, App.tsx:211-226,279-315 on 2026-09-02; C8 edits the rule through the Edit tool after gate.py ack."
    }
  ],
  "alternatives_considered": [
    "Persist display_name into each run's manifest.json from the CLI: rejected — completed run directories are immutable and identity-hashed; a derived, additive projection field costs nothing and cannot drift.",
    "Build the Phase 3 MDI/document shell first and hang the report and Governance window on it: rejected — the spec phases Clean before Terminal so every owner-visible fix lands behind its own gate; Phase 3 can re-home these panels.",
    "Add @radix-ui/react-dialog for the figure overlay: rejected — one new runtime dependency (license matrix, bundle) for one overlay that a 40-line component covers.",
    "Delete the hazard banners outright: rejected — their content is governance-required; it is relocated to the Governance pane and the status chip, never removed."
  ],
  "pre_mortem": [
    "StrictModel forbids extra fields, so a `display_name` that reaches the client before the models/OpenAPI/e2e fixtures are updated fails every typed fixture; C1 regenerates contracts in the same slice and greps the harness for RunListItem literals.",
    "Reading equity_curve.parquet for every run on /api/runs slows the library rail on large stores; the record is mtime-cached and the read is bounded to the ts column min/max, and C1's test asserts the no-curve path does no parquet read.",
    "The figure overlay traps focus badly or leaves the caveat text hidden from assistive tech, failing axe serious/critical: C3 keeps question/uncertainty/caveat in the DOM with `.sr-only` in terse mode and the Playwright test tabs through the three buttons and closes with Esc.",
    "Clipboard writes are unavailable in headless Chromium without permissions: the e2e asserts the Copy button and stubs navigator.clipboard via addInitScript rather than reading the system clipboard.",
    "Removing ResearchGateLockNotice from Operate changes the e2e count assertions (1 on Operate, 2 on Build): C4 rewrites them to the new placement (0 on Operate, 2 on Build, 1 in Governance) rather than deleting the check.",
    "Screenshot baselines for results, operate, build and explore change by design; each is re-snapshotted with --update-snapshots=all in the slice that changes it, and the run is repeated once without the flag to prove stability.",
    "The jobs table drops the `title={currentStep}` or the progressbar accessible name and the running/failed e2e tests break silently in a rewrite: C6 keeps both attributes on the row and runs those two tests before touching styling.",
    "static/app is forgotten after a frontend slice and the CI diff check fails: every frontend slice ends with `npm run build` and `git status --short apps/alpha-web/src/alpha_web/static/app` before the gate."
  ],
  "slices": [
    {
      "title": "C1 server-side run display_name and the library rail that uses it",
      "verify": "uv run pytest -q tests/integration/test_web_api_runs.py tests/unit/test_web_contracts.py -m \"not network\" && uv run python scripts/generate_web_openapi.py --check && uv run python scripts/check_openapi_operations.py && cd apps/alpha-web/frontend && npx vitest run src/panels/RunBrowser.test.ts src/panels/v3Models.test.ts && npm run lint -- --deny-warnings && npm run build && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "GET /api/runs items and GET /api/runs/{id} carry `display_name` = `<strategy> D1 — <symbol> · <venue> · <start> → <end> · run <8 hex>` built in _runs.run_record from manifest fields plus the equity curve's ts range (venue and range omitted when absent; symbols joined with ', '); the activity events reuse the same record; LibraryRail rows and the run-detail toolbar show display_name with the 8-hex id demoted to a mono suffix; filter matches display_name; OpenAPI + generated.ts regenerated; e2e fixtures typed as RunListItem gain the field.",
      "rollback": "Revert _runs.py, models.py, LibraryRail.tsx, rundetail/index.tsx, regenerated contracts and fixtures; run directories are untouched.",
      "files": ["apps/alpha-web/src/alpha_web/_runs.py", "apps/alpha-web/src/alpha_web/api/models.py", "apps/alpha-web/frontend/src/shell/LibraryRail.tsx", "apps/alpha-web/frontend/src/panels/rundetail/index.tsx", "apps/alpha-web/frontend/src/panels/runBrowserModel.ts", "apps/alpha-web/frontend/src/panels/runBrowserModel.test.ts", "apps/alpha-web/frontend/src/api/types.ts", "apps/alpha-web/frontend/src/api/generated.ts", "apps/alpha-web/frontend/openapi.json", "apps/alpha-web/frontend/e2e/support/workstationHarness.ts", "tests/integration/test_web_api_runs.py", "docs/governance/openapi-operation-classification.json", "docs/governance/capability-authority-matrix.md", "apps/alpha-web/src/alpha_web/static/app/**", "apps/alpha-web/frontend/src/panels/v3Models.test.ts"],
      "status": "done"
    },
    {
      "title": "C2 Strategy Performance Report: Summary table and the left tree replace tabs, band and inner tree",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/panels/reportModel.test.ts src/panels/rundetail && npm run lint -- --deny-warnings && npm run test:coverage && npm run build && npx playwright test e2e/workstation.spec.ts -g \"library rail|Results screen|watermark\" && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "The Results screen shows one report window titled by display_name with a left tree (Strategy Analysis: Summary · Ratios · Equity & drawdown; Trade Analysis: List of trades · P&L distribution · Run-up/drawdown; Periodical Analysis; Robustness: Walk-forward · Shuffled-return null · Deflated Sharpe · Monte Carlo paths; Settings & data) mapped 1:1 onto the existing figure sections, gates, trades and stress-test views by a pure reportModel (sections that have no artifacts are shown disabled with the reason, never hidden); Summary is a key/value table from the manifest (net profit, CAGR, Sharpe, deflated Sharpe when present, max drawdown, volatility, trades, win rate/profit factor from the native tearsheet when available, snapshot, period, verdict); the five-column outcome band is gone and both watermark banners collapse into one compact chip in the report title bar with the full text as its title; the results-screen baseline is re-snapshotted deliberately.",
      "rollback": "Restore rundetail/index.tsx, FigureReport.tsx and the previous baselines; the API is untouched by this slice.",
      "files": ["apps/alpha-web/frontend/src/panels/rundetail/**", "apps/alpha-web/frontend/src/panels/FigureReport.tsx", "apps/alpha-web/frontend/src/panels/reportModel.ts", "apps/alpha-web/frontend/src/panels/reportModel.test.ts", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/vitest.config.ts", "apps/alpha-web/frontend/e2e/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "C3 figure maximise with Save PNG / Save SVG / Copy, Esc restore, prose behind Notes",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/components/figureExport.test.ts && npm run lint -- --deny-warnings && npm run build && npx playwright test e2e/workstation.spec.ts -g \"figure\" && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "Double-clicking a figure or pressing its expand button opens a role=dialog overlay with the figure at full size, buttons Save PNG (existing download URL), Save SVG, Copy (Clipboard API on the PNG blob; disabled with a reason when the API is unavailable) and Close; Esc and Close restore the report with focus returned to the card; the figure's question/uncertainty/caveat stay in the DOM in both modes and are visually shown only when explain=narrative (Notes); a Playwright test drives open → Tab through the buttons → Esc and asserts the axe gate; a pure figureExport model owns file names and the copy-capability decision.",
      "rollback": "Restore FigureCard.tsx and remove FigureOverlay.tsx and the model; the image endpoints are untouched.",
      "files": ["apps/alpha-web/frontend/src/components/FigureCard.tsx", "apps/alpha-web/frontend/src/components/FigureOverlay.tsx", "apps/alpha-web/frontend/src/components/figureExport.ts", "apps/alpha-web/frontend/src/components/figureExport.test.ts", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/vitest.config.ts", "apps/alpha-web/frontend/e2e/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "C4 Governance pane on Operate composed from existing projections; hazard banners and the glossary footer relocate into it",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/panels/governanceModel.test.ts src/shell/screens.test.ts && npm run lint -- --deny-warnings && npm run build && npx playwright test -g \"Operate screen|Research Cockpit captures|research-gate override|paper\" && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "A Governance pane (tree: Authority & status · Touch ID · Research gates · Overrides · Providers · Storage · Glossary) renders from existing client reads only (system/providers projection, research-gate model, paper sessions state, crypto storage, the GLOSSARY table filtered by profile) with every sandbox/paper/Touch ID/standalone sentence that used to be a hazard stripe listed verbatim under Authority & status; the `.sandbox-banner` stripes on ResearchCockpit, PaperMonitor, AiConsole and StrategyLab, the ResearchGateLockNotice on Operate, and the Glossary foot are removed from working screens; research-gate locks on Build affordances are unchanged; screens.test asserts the Operate foot is the Governance pane; e2e assertions on the relocated texts are rewritten to look inside the Governance pane; the operate and explore baselines are re-snapshotted deliberately.",
      "rollback": "Restore screens.tsx, the four banner sites and Glossary placement; the pane file can stay unmounted.",
      "files": ["apps/alpha-web/frontend/src/panels/Governance.tsx", "apps/alpha-web/frontend/src/panels/governanceModel.ts", "apps/alpha-web/frontend/src/panels/governanceModel.test.ts", "apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx", "apps/alpha-web/frontend/src/panels/PaperMonitor.tsx", "apps/alpha-web/frontend/src/panels/AiConsole.tsx", "apps/alpha-web/frontend/src/panels/StrategyLab.tsx", "apps/alpha-web/frontend/src/panels/Glossary.tsx", "apps/alpha-web/frontend/src/components/ResearchGateLockNotice.tsx", "apps/alpha-web/frontend/src/shell/screens.tsx", "apps/alpha-web/frontend/src/shell/screens.test.ts", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/vitest.config.ts", "apps/alpha-web/frontend/e2e/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "C5 status chip and Governance button in the topbar; watermark on three surfaces",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/shell/statusModel.test.ts && npm run lint -- --deny-warnings && npm run build && npx playwright test -g \"research-gate override|renders and clears\" && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "The topbar gains one status chip (`Paper only` by default; the research-gate override watermark text when the selected run carries one) and a Governance button that opens the Operate Governance pane; the research-gate e2e test asserts the watermark on the report title-bar chip, the topbar status segment and the Governance pane (three surfaces) and still asserts the Providers override reason; a pure statusModel decides the chip text; all six screens keep clearing the accessibility gate.",
      "rollback": "Restore App.tsx and the e2e test; the chip and model are removed.",
      "files": ["apps/alpha-web/frontend/src/App.tsx", "apps/alpha-web/frontend/src/shell/statusModel.ts", "apps/alpha-web/frontend/src/shell/statusModel.test.ts", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/vitest.config.ts", "apps/alpha-web/frontend/e2e/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "C6 one dense jobs table replaces the JobMonitor cards",
      "verify": "cd apps/alpha-web/frontend && npx vitest run src/panels/jobProgress.test.ts && npm run lint -- --deny-warnings && npm run build && npx playwright test -g \"running jobs|failed job|Build screen\" && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "JobMonitor renders one `.blotter` table (status · command · started · elapsed · ETA · progress · now/failure · actions) with the failure message as the `now` cell text and `title`, the progressbar keeping its accessible name, live log and cancel as row actions, and the console expanding beneath the row; the running-job and failed-job e2e tests pass against the table; the build baseline is re-snapshotted deliberately.",
      "rollback": "Restore JobMonitor.tsx and the build baseline.",
      "files": ["apps/alpha-web/frontend/src/panels/JobMonitor.tsx", "apps/alpha-web/frontend/src/panels/jobProgress.ts", "apps/alpha-web/frontend/src/panels/jobProgress.test.ts", "apps/alpha-web/frontend/src/index.css", "apps/alpha-web/frontend/e2e/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "C7 full frontend gate and Phase 2 acceptance e2e",
      "verify": "cd apps/alpha-web/frontend && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npm run test:e2e && cd ../../.. && git status --short apps/alpha-web/src/alpha_web/static/app && uv run python scripts/gate.py fast",
      "expected": "One Playwright acceptance test proves the Phase 2 acceptance sentence: no `.sandbox-banner` and no `.workbench-notice[role=note]` on any of the six working screens, every figure card opens the overlay, and a library row reads strategy · D1 · symbol · dates; the full frontend gate (lint, coverage thresholds, generated contracts clean, build, every e2e across three viewports) passes and static/app is clean.",
      "rollback": "Remove the acceptance test; nothing else changes in this slice.",
      "files": ["apps/alpha-web/frontend/e2e/**", "apps/alpha-web/src/alpha_web/static/app/**"],
      "status": "done"
    },
    {
      "title": "C8 docs honesty, rule update, full gate",
      "verify": "uv run python scripts/gate.py full && uv run pytest -q tests/unit/test_documentation_truth.py tests/unit/test_claude_md_relocation.py -m \"not network\" && uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-09-02-trader-terminal-phase2-clean.md",
      "expected": ".claude/rules/alpha-web.md gains rows for display_name, the report tree, FigureOverlay, Governance pane, status chip and jobs table (Edit tool after gate.py ack, v1 lines verbatim); docs/BUILD-STATUS.md gains the dated Phase 2 record; the spec marks Phase 2 implemented; findings #8-#12 carry their fixing commits; every slice is done; the full gate is green including the 14-wheel smoke.",
      "rollback": "Docs-only; revert the doc commit.",
      "files": [".claude/rules/alpha-web.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md", "docs/superpowers/plans/2026-09-02-trader-terminal-phase2-clean.md"],
      "status": "done"
    }
  ],
  "tier_impact": ["protected", "dag"],
  "docs_to_update": [".claude/rules/alpha-web.md", "docs/BUILD-STATUS.md", "docs/superpowers/specs/2026-09-01-trader-terminal-ui-design.md", "docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md"],
  "out_of_scope": [
    "Phase 3 Terminal: the MDI/document shell, menu bar, Market Watch, Navigator tree, Option E theme (`terminal_classic.json`) and the six-screen rewrite of .claude/rules/alpha-web.md.",
    "Any new statistic, figure, or figure byte change (alpha_research is untouched); any CLI command, MCP tool (pinned at 62), or authority change.",
    "Persisting display names or notes into run directories; export CSV of trades/equity (already available through the parquet projections; wiring a toolbar button is Phase 3).",
    "Removing role=alert/role=status live feedback notices; only informational hazard stripes, notes and the glossary footer relocate."
  ],
  "files": ["apps/alpha-web/**", "tests/integration/test_web_api_runs.py", "tests/unit/**", "docs/**", ".claude/rules/alpha-web.md"]
}
```

## Context

Phase 1 fixed *getting data in*; the owner's remaining walkthrough findings are about *reading
results* (#8 cluttered run report, #9 no full-screen/PNG, #10 hex-id run rows) and *not being
shouted at* (#11 governance text everywhere, #12 layer-organised navigation — the last is Phase 3).
Spec §4.4/§4.5/§7 (Phase 2) are the contract; the navigator map (2026-09-02) fixed the seams:

* `/api/runs` items are built once in `alpha_web/_runs.run_record` (mtime-cached) and reused by the
  activity stream; models are StrictModel, so an additive field must move model + OpenAPI +
  generated.ts + typed e2e fixtures together.
* Manifests have `params.strategy_name`, `symbol|symbols`, sometimes `source`; no timeframe or
  dates — the equity curve's `ts` range is the honest period.
* The report today: `rundetail/index.tsx` tabs (Report/Gates/Trades/Stress test/Artifacts), two
  SPA-authored watermark banners, an SPA-authored five-column band, `FigureReport.tsx` rail
  keyed by Python `FigureDefinition.section`, per-figure prose from the Python sidecar shown by
  `explain === 'narrative'`.
* No modal component; download/clipboard precedents exist (`ChartDataAlternative`,
  `V3Workbenches`).
* Governance texts: four `.sandbox-banner` stripes, ~13 informational `.workbench-notice`s, the
  `ResearchGateLockNotice` (e2e count-asserted), the Operate `Glossary` foot.
* Jobs: `JobMonitor.tsx` cards with `title={currentStep}` and a named progressbar that two e2e
  tests depend on.

## Slices

C1 (server display_name + rail) → C2 (report tree + summary, band/banners → chip) → C3 (figure
overlay + export) → C4 (Governance pane, banners relocate) → C5 (status chip + button, watermark
on three surfaces) → C6 (jobs table) → C7 (acceptance e2e + full frontend gate) → C8 (docs,
rule, full gate). Each slice: failing test → minimal code → its verify → fast gate → full gate →
one conventional commit.

## Test plan

Test-architect specification (2026-09-02, 40 items; the numbers below are its items).

* C1 → #1–#9 (backend display_name, contracts, typed fixtures, rail). Deviation accepted: the
  period comes from the equity curve's first/last bar (lazy min/max, mtime-cached) because
  backtest manifests carry no dates; validate manifests' `metadata.first_ts/last_ts` are a
  cheaper source to prefer when present (follow-up noted in C8).
* C2 → #10–#15 (`reportModel.test.ts`: five spec groups in order, every catalogue figure in exactly
  one leaf, empty leaves present and marked, Summary rows only from recorded manifest values —
  win rate / profit factor / exposure / max-DD date are `not recorded`, never client arithmetic —
  one watermark chip; Playwright tree + summary + no band/banner/tabs).
* C3 → #16–#19 (`figureMaximiseModel.test.ts`: open/escape reducer, content-addressed export urls
  and filenames, notes verbatim in both explain modes; Playwright dblclick → dialog → Copy stub →
  Escape restores focus; prose attached before/after, visible only with Notes).
* C4/C5 → #20–#32 (settings `notes` per panel; `statusChipModel`; `governanceModel` seven pages,
  overrides verbatim, storage via storageRow, glossary profile tags, authority rows ⊆ projection
  keys; `screens.test` no Glossary pane/foot; Playwright Governance dialog, no stripes/locks/footer
  on working screens, watermark on three surfaces rewritten stronger (count 2 then 3, never
  `.first()`), gate-lock test rewritten with the chip as the deep link, Notes persists).
  Adjustment to the plan block: Governance is a shell-level role=dialog opened from the topbar
  button (Esc closes), not an Operate pane; the Operate Glossary foot is removed.
* C6 → #33–#36 (`jobTableModel.test.ts`: running-first ordering, exact relay of current_step;
  running/failed e2e rewritten with row/cell locators, `getByTitle` + box-glyph checks kept).
* C7 → #37 re-snapshot all twelve baselines once the shell chip lands; acceptance test.
* Markers: **no `bias_guard`**, no `network` (#38); vitest allow-list gains the five models (#39).

* C1 → Python: `tests/integration/test_web_api_runs.py` — display_name with curve, without curve,
  with `symbols` list, activity event carries it; contract test regenerated. TS: `runBrowserModel`
  filter matches display_name.
* C2 → `reportModel.test.ts` — tree from available artifacts (disabled entries carry reasons),
  Summary rows from a manifest with/without native tearsheet; Playwright: report title = display
  name, watermark chip visible, no outcome band.
* C3 → `figureExport.test.ts` — file names, copy capability decision; Playwright: open by
  double-click and by button, Tab order, Esc restores focus, axe.
* C4 → `governanceModel.test.ts` — tree from projections, profile-filtered glossary, verbatim
  hazard sentences; `screens.test.ts` Operate foot; Playwright: relocated texts found inside the
  Governance pane, `.sandbox-banner` count 0 on working screens, ResearchGateLockNotice counts.
* C5 → `statusModel.test.ts` — chip text; Playwright watermark test on three surfaces.
* C6 → `jobProgress.test.ts` unchanged semantics; Playwright running/failed job tests against the
  table.
* C7 → Phase 2 acceptance test; full frontend gate.
* Markers: none new; **no `bias_guard`** (no PIT reader in scope).

## Deviations recorded during /implement

* **C2** — the Evidence Hub keeps a flat `RunFigures` list (the old self-fetching `FigureReport` rail is gone); the Summary rows are `not recorded` for win rate / profit factor / exposure / max-DD date because no manifest carries them.
* **C3** — the model is `figureExport.ts` (names, copy capability, `notesVisible`), not a reducer; terse mode is toggled through the settings menu in the e2e because `preparePage` clears localStorage after any earlier init script.
* **C4** — Governance is a shell-level `role=dialog` opened from the topbar ⚖ button (Esc closes, focus returns); the Operate Glossary foot is removed and the unchanged `Glossary` panel renders inside the dialog **unfiltered** (no `GLOSSARY` entry carries a profile tag; adding tags is out of scope). Only the four `.sandbox-banner` stripes, the Development Center `ResearchGateLockNotice` and the Glossary foot moved; the Strategy Lab and Pipeline lock notices (Build affordances) and contextual `role=note` notices that name a next action stay. Two cockpit e2e assertions on the research-sandbox sentence now look inside the dialog.
* **C5** — the status chip is the deep link from a locked Development Center to the holding case (`Research gate open` → Governance → Open research case); `RESEARCH GATE OPEN` counts use `exact: true` because `getByText` is a case-insensitive substring match; at ≤1280px the brand sub-line and the Governance label hide so no topbar control is obscured (axe target-size).
* **C6** — the model is `jobTableModel.ts` (`jobRows`), `jobProgress.ts` unchanged; the running/failed e2e use row/cell locators.
* **C7** — the acceptance test also asserts no `.research-gate-lock` and no `.glossary` on any screen; `role=note` is not asserted (see C4). All twelve baselines were re-snapshotted byte-identical after C6.
* **C1** — the rail filter matches `display_name` inline (no new model function; `runBrowserModel.test.ts` does not exist, the existing `RunBrowser.test.ts` covers the model). `v3Models.test.ts` builds typed `RunDetail` fixtures and gained the field.

## DAG / look-ahead / determinism impact

* **DAG:** `alpha_web/_runs.py` keeps importing only `alpha_cli.run_store` / `artifact_contract`
  and reads parquet through the existing bounded projection; no alpha_data/alpha_research import;
  `uv run lint-imports` in C1 and C8.
* **Look-ahead:** none — display_name and the Summary table are projections of completed,
  immutable run artifacts; no `as_of` path is touched.
* **Determinism:** display_name is a pure function of manifest + curve bytes; figure bytes and
  endpoints are unchanged (Copy fetches the existing PNG); watermark texts remain server strings.
* **Protected:** `.claude/rules/alpha-web.md` (C8) via the Edit tool after `gate.py ack`.

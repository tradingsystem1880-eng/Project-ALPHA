# Trader Terminal UI — design spec

Status: APPROVED by owner 2026-09-01 (design + palette + open items) · Phase 1 "Work" IMPLEMENTED 2026-09-02 (plan `docs/superpowers/plans/2026-09-01-trader-terminal-phase1-work.md`; owner acceptance walkthrough and asset-master regeneration pending) · Phase 2 "Clean" IMPLEMENTED 2026-09-02 (plan `docs/superpowers/plans/2026-09-02-trader-terminal-phase2-clean.md`; owner walkthrough pending) · supersedes nothing (extends the Workstation program)
Owner decisions and evidence: `docs/audit/2026-09-01-owner-crypto-walkthrough-findings.md` (findings #1–#13, decisions D1–D7)
Approved mockups: Claude Design canvas "ALPHA Crypto Terminal" (four artboards: Terminal, Strategy
Performance Report, Maximised chart, Governance window)

## 1. Goal

Turn the ALPHA Workstation into a **classic desktop trading terminal** for a trader who is not a
programmer: a chart-centred workspace with docked panels, a Market Watch, a Navigator tree, a tabbed
Toolbox, a Data Manager, MultiCharts-style Strategy Performance Reports, and pure-black figure
canvases — split into a **Crypto profile** and an **Equities profile** so each market only shows the
data, functions and vocabulary that apply to it. Governance text leaves the working screens and
lives in one Governance window. Crypto data pulling must simply work.

Nothing in this program adds, removes or relocates **authority**. Touch ID, research gates,
owner-CLI-only D1, one-shot D2, paper-only execution, the 62-tool MCP pin, the import-linter DAG and
"never draw an analytical chart in the SPA" are unchanged.

## 2. Owner decisions (binding)

| # | Decision |
|---|----------|
| D1 | Two market profiles, equal split: **Crypto** and **Equities**; each shows only what is relevant to that market. |
| D2 | **Hybrid layout**: chart is the home; dense work (reports, compare, build) opens as full document windows. |
| D3 | Governance/explanatory text → one status segment + per-panel "Notes" + one **Governance window**. Never deleted, only relocated. |
| D4 | Phasing **Work → Clean → Terminal** (§7). |
| D5 | **Approach A**: evolve the existing SPA in place; keep the tested panel models; no side-by-side v2, no rewrite. |
| D6 | Crypto starter watchlist BTC/ETH/XRP/SOL-USDT; default venue Binance (Coinbase selectable). The 2 TB Expansion SSD datasets are first-class in the Data Manager, with honest state when unmounted. |
| D7 | Aesthetic: **classic desktop terminal** (menu bar, icon toolbars, bevelled docked panels, tree navigator, dense 11px tables, tabbed toolbox, status bar) with **black chart canvases, white frames, corner legends** (matplotlib style). **Owner chose Option E on 2026-09-01: light-grey window chrome around black chart canvases, green/red candles.** |

## 3. Findings this design resolves

#1 hidden job error text · #2 no date validation · #3 pre-listing start aborts pull · #4 symbol
format/defaults · #5 two data systems in two tabs · #6/#7 only 13 reviewed crypto assets incl.
catalog junk · #8 cluttered run report · #9 no figure fullscreen/PNG · #10 hex-id run list ·
#11 governance text everywhere · #12 layer-based navigation · #13 equities sources as crypto defaults.

## 4. Design

### 4.1 Market profiles

* `profile: 'crypto' | 'equities'` is a **display setting** in `frontend/src/state/settings.ts`
  (localStorage, like `density`/`explain`/`projectModes`), mirrored to `html[data-profile]`.
  It carries no authority and is never sent to the backend as a permission.
* A profile is a **static manifest** in `frontend/src/shell/profiles.ts`:
  `{ id, label, windows[], dockedPanels[], providers[], defaultSource, defaultVenue, symbolStyle,
  starterWatchlist[], paperVenues[], glossaryTags[] }`. Crypto: providers `ccxt` (OHLC for
  backtests) + the crypto-house families (funding, OI, order books, on-chain, DEX pools);
  hides options calculator, screener, corporate actions, IBKR paper. Equities: `tiingo` (default),
  `yfinance`, `stooq`, `quantpad`; hides funding/OI/on-chain/DEX, Binance sandbox, crowding studies.
* **Market of a run/project/strategy** is derived server-side from the existing manifest
  (`source`/`exchange`/symbol convention) and exposed as one string field `market` on the existing
  run-list and project-list projections (`alpha_web/api/models.py`, additive). Lists filter by
  profile with a "show all" toggle. Never derived in the browser from symbol text.
* Windows that belong to neither market (Kronos forecast, ML lab, Jobs, Governance) appear in both.

### 4.2 Terminal shell (Phase 3)

Window anatomy, top to bottom (all values from the approved mockup; exact px live in the theme):

1. **Title bar** — `ALPHA Terminal — <Profile> — [<active document>]`, window buttons.
2. **Menu bar** — File · Edit · View · Insert · Charts · Data · Research · Strategy · Backtest ·
   Window · Help. Menus are the discoverable index of every command the CLI-backed API exposes
   (`alpha info --json` commands catalog); ⌘K search stays.
3. **Toolbar** — chart type, timeframes (M15 H1 H4 D1 W1), zoom/crosshair/grid, Data, Research,
   Run, Stop, Report; **Profile** combo; **symbol/venue/timeframe** combo (replaces `ContextBar`);
   search; one **status chip** (`Paper only`) and the **Governance** button.
4. **Docked panels** (left): **Market Watch** (symbol · last · daily %, red/green, tabs Symbols ·
   Details · Data), **Navigator** tree (Strategies · Backtests · Research cases · Data (venues +
   Expansion SSD) · Scripts · Paper sandbox) — replaces `LibraryRail`.
5. **Document area** (centre): MDI documents with bottom **MDI tabs** — chart windows
   (`PriceChart` + layer pills: Funding · Open interest · Signals · Trades), **Strategy
   Performance Report** windows (§4.4), Compare, Build, Research case, Governance (§4.5).
   Only the active document mounts (keeps the existing "nothing polls behind a hidden tab" rule).
6. **Toolbox** (bottom, tabbed): Jobs · Trades · Backtests · Data pulls · Log — `JobMonitor`
   rows become one dense table with the **real** failure text (§4.3).
7. **Docked panel** (right): **Data Manager** (§4.3); other tools (Research, Strategy) dock here too.
8. **Status bar** — help hint · profile · provider ticks · Expansion SSD free space · `Paper only ·
   no live routing` · UTC clock · OHLCV of the hovered bar · bars loaded.

Implementation shape (Approach A): `screens.tsx`'s `SCREENS` becomes a **document registry** plus a
**docked-panel registry**; `PanelHost`/`ErrorBoundary` are kept; the six-screen tab strip becomes
menu + MDI tabs. `.claude/rules/alpha-web.md` line "six fixed screens" is rewritten to describe the
document/dock model (control-plane edit → `gate.py ack`). The Playwright harness's `SCREENS` loop
becomes a documents loop with the same axe/keyboard/viewport coverage.

### 4.3 Data Manager (Phase 1 — "Work")

One panel replaces the two data tabs (`DataExplorer` + `ResearchDataExplorer` entry points):

* **Pull OHLC (backtest data)** — Symbol combobox (stored pairs + profile starter list, free text
  accepted), Venue combobox (profile providers/exchanges), From/To as native `<input type=date>`
  (fixes #2), hint line `listed <date> · ~N bars · ~t s`, buttons **Pull** and **Estimate**.
  * **Symbol normalisation** (CLI, `alpha_cli/data_cmds.py`): `xrp-usdt`, `XRPUSDT`, `xrp/usdt` →
    `XRP/USDT` for ccxt; equities upper-cased. Ambiguous input fails loud with the accepted forms.
  * **First-listed detection** (new read-only CLI projection `alpha data first-bar SYMBOL --source
    ccxt --exchange … --json`, network-marked): the Estimate button and the hint use it; a pull whose
    start precedes the first bar fails with `No data before <date> (first listed). Start there?`
    and the UI offers a one-click retry from that date (fixes #3). No silent clamping.
  * **Real error text** (`alpha_web/_invoke.py`): a failed job's `current_step`/summary carries
    the Typer/Rich error *message*, never a box-border line; the message is also the Toolbox row
    detail (fixes #1). Rich box glyphs are stripped in one place.
  * Profile defaults: Crypto → `XRP/USDT`-style symbol, `ccxt` + Binance; Equities → `AAPL`,
    Tiingo (fixes #4/#13).
* **Stored pairs** table (pair · venue · bars · to) from the existing symbols/snapshots projections.
* **Expansion SSD — research datasets** table (family · source · state) from `alpha crypto-data
  coverage/storage --json`; header shows free space and last verify; when the volume is not
  mounted the panel shows `Expansion SSD not mounted` in the same row and the status bar segment
  turns amber — never a cached "ready".
* **Reviewed assets** — BTC ETH XRP SOL. Adding XRP and SOL is a governed change under ADR-0032:
  extend `alpha_data.crypto.asset_master.with_reviewed_native_assets` and `_NATIVE_NETWORKS`, then
  the owner regenerates the asset master with the existing receipted `asset-master-create`. The
  "+" button in the UI opens the recipe (CLI command + receipt requirement); it does not mutate.
  The five catalog-junk ids (#7) are explained in the Governance window's Storage page; removing
  them is a separate ADR-0032 decision, not part of this program.

### 4.4 Strategy Performance Report (Phase 2 → 3)

* Run windows are titled like a trader would: `<strategy> <timeframe> — <symbol> · <venue> ·
  <start> → <end> · run <8 hex>` — the name is computed server-side into the run projection
  (`display_name`, additive) from the manifest; the Navigator and MDI tabs use it (fixes #10).
* Window toolbar: Save · Print · **Export CSV** (trades and equity, via the existing bounded
  parquet projections) · **Save PNG** · Compare… · Run again · **Notes**.
* **Left tree** (replaces Report/Trades/Stress-test tabs + inner tree, fixes #8): Strategy Analysis
  (Summary · Ratios · Equity & drawdown) · Trade Analysis (List of trades · P&L distribution ·
  Run-up/drawdown) · Periodical Analysis · Robustness (Walk-forward · Shuffled-return null ·
  Deflated Sharpe · Monte Carlo paths) · Settings & data. Sections map 1:1 onto the existing figure
  catalog groups and manifest sections; no new statistics.
* **Summary** = key/value table from the manifest (net profit, Sharpe, deflated Sharpe, max DD +
  date, vol, trades, win rate, profit factor, exposure, costs, data snapshot, period, verdict).
* Figures render as today (server SVG/PNG) inside sunken black frames. **Double-click or the
  expand button maximises** the figure into its own document window with Save PNG / Save SVG /
  Copy and Esc to restore (fixes #9). The figure's question / certainty / caveat copy stays in
  the DOM for assistive tech and is shown by **Notes**, not inline.
* The 5-column outcome band and the `LEGACY_CONTEXT_UNKNOWN` watermark become: one compact
  watermark chip in the report title bar, one status-bar segment, and the full text in the
  Governance window — three surfaces, satisfying the R6g "≥3 surfaces" rule.

### 4.5 Governance window (Phase 2)

Tree: Authority & status · Touch ID · Research gates · Overrides · Providers · Storage · Glossary.
Content is the existing projections (`ProviderSystem`, overrides list, research-gate model, paper
state, storage inventory) and the existing glossary (filtered by profile tags). The hazard-stripe
banners (`.sandbox-banner`), `ResearchGateLockNotice`, and the Operate glossary footer are removed
from working screens once their content is reachable here and via the status chip + Notes.
Research-gate **locks** on Build affordances remain exactly as today (relay-only).

### 4.6 Visual system

* One new theme document `alpha_research/figures/themes/terminal_classic.json` (the existing
  `theme.py` loader; frontend CSS tokens are generated from it, drift is CI-tested) — **Option E**:
  * chrome (light): window `#e6e6e6`, panel `#f2f2f2`, title/header `#dcdcdc`, controls `#e0e0e0`,
    bevels light `#ffffff` / dark `#8a8a8a`, ink `#111111`, secondary `#555555`, table rules
    `#d4d4d4`, inputs `#ffffff`, selection `#316ac5` on white text, chrome label `#8a6d00`;
    semantic text on light surfaces up `#1a8f47` / down `#c8312f` (darker than the canvas pair so
    they pass AA on `#f2f2f2`).
  * canvas (black): bg `#000000`, frame `#e0e0e0`, grid `#2a2a2a`, axis text `#c8c8c8`, up
    `#2fc36a` (hollow), down `#e5484d` (filled), last-price tag `#316ac5`, primary series
    `#d4d4d4`, drawdown `#e5484d`, label yellow `#ffd400`, signal accents cyan `#00e5ff` /
    magenta `#ff33cc`.
  All text colours must pass the existing WCAG AA theme tests against the lightest surface they
  sit on; the mockup values above are the starting point, not exempt from that test.
* Type: Verdana/Tahoma 11px UI, tabular numerals; figures use the same face at 10–11px.
* Figures: black background, white 1px frame, dotted grey grid, legend box in a corner, title in
  the frame — `figures/version.py` bumps (any visual change) and figure goldens re-baseline.
* Square corners; `--r`/`--r-lg` → 0; raised/sunken bevel utilities; 20px panel title bars;
  22px toolbar buttons; 19px tab strips; 26px table rows at comfortable density, 21px compact.
* The interactive price chart stays Lightweight Charts (it is a chart *surface*, not an analytical
  figure) restyled from the same tokens; analytical figures stay Python-rendered.

## 5. Out of scope

Live trading, broker readiness changes, new statistics, new providers, new MCP tools, changing
the reviewed-asset policy beyond adding XRP/SOL, mobile layouts (three desktop viewports remain
the gate), the Equities profile's starter watchlist beyond what is already stored.

## 6. Constraints honoured (with the test that proves each)

| Constraint | Proof |
|---|---|
| DAG: `alpha_web` imports only `alpha_core` + public CLI seams | `uv run lint-imports` |
| MCP pinned at 62 | `tests/integration/test_research_mcp.py` |
| No browser-derived authority/masking | existing mutation-denial + relay tests; new profile tests assert no request carries `profile` as a permission |
| Research-gate watermark on ≥3 surfaces | `e2e/support/workstationHarness.ts` watermark test, rewritten for report title bar + status bar + Governance |
| Accessibility: axe serious/critical, keyboard, 3 viewports | same harness over the document registry |
| Figures byte-stable, theme drift | `tests/unit/test_figure_theme.py`, figure goldens, `figures/version.py` bump |
| Generated API + committed `static/app` clean | `npm run generate:api`, `scripts/generate_web_openapi.py --check`, CI asset diff |
| Six-fixed-screens rule | `.claude/rules/alpha-web.md` rewritten under `gate.py ack`; `screens.test.ts` updated |

## 7. Phasing (each phase ships alone and passes the full gate)

**Phase 1 — Work (crypto data pulling works).** Real job error text · native date inputs +
validation · symbol normalisation · `alpha data first-bar` + pre-listing error with "start there" ·
`profile` setting with data defaults only · one Data Manager panel (pull, stored pairs, SSD
datasets, reviewed assets recipe) · XRP/SOL reviewed natives + regenerated asset master (owner-run,
receipted).
Acceptance: owner pulls XRP/USDT on Binance from the UI with no prior knowledge of formats or
listing dates, sees a stored pair, and every failure message names the fix.
**Status (2026-09-02): implemented (W1–W8, commits `ab2d55c`…`1097fc2`); the owner walkthrough of this
acceptance and the receipted asset-master regeneration are still to be run by the owner.**

**Phase 2 — Clean.** `display_name` for runs · Strategy Performance Report tree + summary table ·
figure maximise + Save PNG/SVG/Copy · Governance window · status chip + Notes replace banners,
band and glossary footer · Toolbox table for jobs.
Acceptance: no hazard stripe or governance paragraph on a working screen; every figure opens
full-screen; the run list reads as strategy · timeframe · symbol · dates.
**Status (2026-09-02): implemented (C1–C8, commits `bfda12a`…`a2569a0`); the Governance window is a
shell-level dialog reached from the topbar ⚖ button and the status chip rather than an Operate pane;
the acceptance sentence is proven by the Playwright test "Phase 2 acceptance"; the owner walkthrough
is still to be run.**

**Phase 3 — Terminal.** `terminal_black.json` theme + fonts + bevels · title/menu/toolbar/status
anatomy · Market Watch + Navigator + Toolbox + Data Manager docks · MDI documents + tabs · profile
manifests gating windows/panels/providers · Equities profile · rule + e2e + screenshot rebaselines.
Acceptance: the app matches the approved artboards at 1440×900 within the theme's tokens; all
gates green; owner walkthrough in both profiles.

## 8. Risks

* **Governed-surface churn** (rule edit, e2e rewrite, screenshot baselines) — mitigated by doing it
  once, in Phase 3, behind a single plan slice with `gate.py ack`.
* **11px text and accessibility** — contrast is gated, size is not; keep the density knob and
  browser zoom working; no fixed-height text clipping.
* **Lightweight Charts vs. figure look** — the interactive chart cannot be pixel-identical to
  matplotlib; the shared theme keeps colours identical, frames/grid are approximated.
* **Two data paths remain two** (backtests read legacy snapshots; research reads the crypto house)
  — the Data Manager explains which is which in one line each; merging them is out of scope.

## 9. Open items for the owner

1. ~~Dark or light chrome~~ — resolved: Option E (light chrome, black canvases).
2. ~~Equities starter watchlist~~ — resolved: the already-stored SPY/AAPL/… set.
3. ~~Toolbox "Alerts" tab~~ — resolved: dropped; no alert engine exists, so no placeholder tab.

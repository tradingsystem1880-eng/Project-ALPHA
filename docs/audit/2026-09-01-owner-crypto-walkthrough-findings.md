# Owner crypto walkthrough — findings log

Started 2026-09-01. Owner (trader, non-programmer) + Claude walk through Project ALPHA
focused on crypto. Every bug, error, confusing UX, inefficiency, or "I want it to do X instead"
gets one entry here. Later this log feeds a change plan.

Severity: **BUG** (wrong/broken) · **UX** (works but confusing/clunky) · **GAP** (feature missing
or owner wants different behaviour) · **PERF** (slow/inefficient) · **Q** (open question)

| # | Sev | Area | What happened / what was expected | Repro / evidence | Status |
|---|-----|------|-----------------------------------|------------------|--------|
| 1 | BUG | Web · Jobs | A failed `data pull` job shows a Rich box-border line (`╰────╯`) as its "current step"/reason instead of the real error text. Owner saw "job failed" with no usable message. | `_invoke.Job._current_step` returns the last non-empty stdout line; Typer/Rich errors end with a border line. Jobs `08ef0b08…`, `e4bf2a21…`, `040480e7…` on 2026-09-01. | fixed `ab2d55c` (W1: CLI `Error:` line is the job reason; `TYPER_USE_RICH=0`) |
| 2 | UX | Web · Market Data | Start/End are free-text fields with no date picker or validation; `2026-06-31` (invalid — June has 30 days) was accepted by the form and only rejected by the CLI. | `data pull xrp-usd --source ccxt --exchange coinbase --start 2015-01-01 --end 2026-06-31` → exit 2 "day is out of range for month". | fixed `751d6c3` (CLI rejects reversed ranges) + `2079239`/`921c6ae` (native date inputs, `validateDates` names the impossible date) |
| 3 | UX | CLI/Data · ccxt | A start date before the pair's listing aborts the whole pull ("ccxt returned no data for XRP/USD 2015-01-01…"). Owner has to know Coinbase listed XRP in 2019 (and relisted 2023). Expected: either start from first available bar (with a clear notice) or tell the owner the first available date. | Same command with valid dates fails; `--start 2023-08-01` succeeds (1065 bars); Binance `XRP/USDT --start 2019-01-01` succeeds (2738 bars). | fixed `c2c398d` (`first-bar` probe; pre-listing pull fails with the retry start) + `4d1a902`/`921c6ae` (Estimate + one-click `Start there`) |
| 4 | UX | Web · Market Data | Symbol format is undocumented in the form: owner typed `xrp-usd`, `xrp-usdt`, `arp`; CLI expects `XRP/USD` (Coinbase) / `XRP/USDT` (Binance). Defaults are `AAPL` + Yahoo Finance — wrong for a crypto-first owner. | `DataExplorer.tsx` defaults `sym='AAPL'`, source = first historical provider (yfinance). | fixed `751d6c3` (symbol normalisation) + `2079239`/`921c6ae` (crypto profile defaults XRP/USDT · ccxt · Binance; symbol combobox with the watchlist) |
| 5 | UX | Web · Data | Two parallel data systems in two different side tabs: "Market Data" (legacy `alpha data pull`: Yahoo/Tiingo/CCXT, equities-flavoured) and "Research Data" (governed Crypto Data Center: Binance/Bybit/CoinGecko/…, 8 sub-tabs). Owner cannot tell which one to use for basic crypto OHLC. | Research screen side rail: `Market Data` vs `Research Data` tabs. | fixed `921c6ae` (one Data Manager panel; Research Data embedded as its second tab) |
| 6 | GAP | Crypto data house | Only 13 reviewed native assets exist (bitcoin, ethereum, wbtc, weth, tether, usd-coin, usds, uniswap + 5 odd CoinGecko ids: fake-world-assets, helix-ai, humanity, kekius-maximus, nesa). XRP lookup → 422 "asset has no reviewed native mapping". A crypto trader needs a straightforward way to add majors (XRP, SOL, …). | `GET /api/crypto-data/assets/XRP` → 422; `data/crypto/asset-masters/b3e1f27….json`. | fixed `1097fc2` (`reviewed-native-v2` adds XRP/SOL; v1 bytes pinned) — owner still regenerates the cross-provider master with the receipted `asset-master-create` |
| 7 | Q | Crypto data house | Why are `fake-world-assets`, `helix-ai`, `humanity`, `kekius-maximus`, `nesa` in the reviewed asset master? Looks like a test/catalog artefact, not an owner choice. | same file as #6 | answered: those ids come from the qualified CoinGecko `asset_metadata` catalog that `build_cross_provider_asset_master` maps by network+contract, not from an owner choice; removing them is a separate ADR-0032 decision (Governance window → Storage page, Phase 2) |
| 8 | UX | Web · Run detail | Run report is cluttered: LEGACY_CONTEXT banner + 5-column "What changed / Evidence / Contradictory / Uncertainty / Valid next action" band + Report/Trades/Stress-test tabs + left tree (Performance/Signals/Trades/Risk) + per-figure "What this answers / How sure / Read with care" prose. Owner: hard to navigate, labels not human. | Screenshot `#run=499445caf2e20f54` (AMZN). | fixed `bfda12a` (display_name) + `c6e5397` (Strategy Performance Report: tree + Summary table, band/tabs/banners → one watermark chip) + `fecc14d` (prose behind Notes) |
| 9 | GAP | Web · Figures | Owner wants any chart to open full-screen (double-click) and to save as PNG easily. Today: tiny "SVG PNG" text links + "Details" button per figure. | FigureCard.tsx | fixed `fecc14d` (Expand / double-click → dialog with Save PNG · Save SVG · Copy · Close, Esc restores focus) |
| 10 | UX | Web · Library rail | Runs list shows 8-char hex ids + "HISTORICAL" badge + symbol. A trader wants strategy name, symbol, date range, result at a glance. | LibraryRail | fixed `bfda12a` (server `display_name`: strategy D1 — symbol · source · dates · run id; rail filters on it) |
| 11 | UX | Web · Global | Backend/governance explanation text is everywhere (hazard-stripe banners "RESEARCH SANDBOX…", "PAPER ONLY…", "TOUCH ID REQUIRED · NO OVERRIDE · NO TRADING", authority footnotes, Glossary footer taking ~1/3 of Operate). Owner wants it moved to its own tab / collapsible so the workspace is trader-focused. NOTE: some of this is governance-required (watermarks on ≥3 surfaces; figure question/uncertainty/caveat must exist for accessibility) — it can be collapsed/relocated, not deleted. | All screens | fixed `364e655` (Governance dialog absorbs the five hazard sentences, the Development Center lock notice and the Glossary foot) + `d3e424c` (status chip; watermark asserted on three surfaces) |
| 12 | UX | Web · Navigation | Six fixed screens (Research/Build/Results/Compare/Studios/Operate) are organised by *system layer*, not by *trader workflow*. Reference terminals (TrendSpider, MultiCharts) are chart-centric with tools opening beside the chart. | screens.tsx | fixed `fc8f577` (document/dock registries) + `c8321f0` (MDI/menu/toolbar/status-bar models) + `21dd1b7` (Market Watch, Navigator) + `5771447` (terminal shell: menu bar, toolbar, docks, MDI documents, Toolbox; `screens.tsx` deleted) + `f109f90` (document baselines) |
| 13 | UX | Web · Market Data | "Retired"/non-crypto sources (Yahoo, Tiingo, equities) still presented as first-class defaults for a crypto-focused owner. | DataExplorer provider select | fixed `2079239` (profile-driven defaults; equities profile keeps Tiingo/AAPL) |

## Session notes

### 2026-09-01 — orientation
- Repo clean on `main`, full gate stamp valid.
- Local data: 97 normalized crypto artifacts (Binance spot/futures, Bybit, CoinGecko, …),
  14 frozen crypto snapshots, 372 manifests, 24 run directories, 4 non-crypto snapshots
  (SPY/AAPL/US-equity yfinance + tiingo).
- Two existing projects: "UI research-to-strategy trial — test only" (gate open) and
  "Workstation v3 research demo" (US equities momentum).
- Open plan: `docs/superpowers/plans/2026-08-30-crypto-operational-readiness.md`
  (Expansion external volume was not writable on 2026-08-30 — storage acceptance blocked).

### 2026-09-01 — XRP data pull diagnosis (#1–#4)
- Owner's UI pull failed twice over: invalid date `2026-06-31`, then (with valid dates) a pre-listing
  start date. Working pulls executed by Claude and now stored: `XRP/USD` coinbase 2023-08-01→2026-06-30
  (1065 bars) and `XRP/USDT` binance 2019-01-01→2026-06-30 (2738 bars).
- Reference-terminal research (TrendSpider, MultiCharts, Brighter Data) summarised in the UI plan
  discussion; Brighter Data is an event-statistics overlay product, not a terminal.

### 2026-09-01 — UI redesign decisions (owner)
- **D1. Market profiles, equal split.** The workstation gets a Crypto profile and an Equities profile
  the owner switches between. Each profile shows only the data sources, functions, panels, and
  defaults relevant to that market (crypto has funding/OI/on-chain/DEX data equities lack; equities
  have corporate actions/options/screener data crypto lacks). Goal: a much cleaner per-market view.
- **D2. Hybrid layout.** Chart is the home screen (watchlist rail left, layer pills on the chart,
  tool drawers right: Data / Research / Strategy / Runs; collapsible bottom dock for trades/jobs/log).
  Dense work keeps full-screen desks: Results (left tree + figure grid, double-click = fullscreen),
  Compare, Build. Rejected: pure single-screen overlay (reports too cramped) and plain workflow
  tabs (least terminal-like).
- **D3. Explanatory/governance text placement.** One compact status-chip row in the top bar
  (e.g. "Sandbox · no trading"), an "i" toggle on each chart/panel revealing its notes on demand,
  and one Governance/System desk holding the full text, glossary, authority state, and overrides.
  Rejected: tooltips-only (easy to miss) and collapsed-in-place (still noisy).
- **Map facts for the design (navigator, 2026-09-01):** backtest/validate/optim/paper consume ONLY
  legacy `alpha data pull` → `alpha data snapshot` snapshots (crypto via `ccxt`); the governed crypto
  house (`alpha crypto-data`, CryptoSnapshotV1) feeds research D1/D2 and strategy-candidate only.
  Reviewed native assets are hard-coded to bitcoin+ethereum (`asset_master.py:173-207`); the odd
  ids are whatever tokens sat in the frozen GeckoTerminal top-pool page. No fullscreen/lightbox
  exists for figures. "Six fixed screens" is a protected rule (`.claude/rules/alpha-web.md`) and an
  e2e assertion — changing the shell is a governed change (rule edit needs `gate.py ack`).
- **D4. Phasing: Work → Clean → Terminal.** Phase 1 make crypto data pulling work (pair picker with
  listing dates, date picker, real error text, XRP/SOL reviewed assets). Phase 2 declutter existing
  screens (status chips, "i" toggles, Governance desk, figure fullscreen/PNG, human run names).
  Phase 3 Crypto/Equities profile switch + chart-home shell (drawers, dock) + Results desk restructure.
- **D5. Approach A — evolve the existing workstation in place.** Keep the screen/pane registry and
  existing panels; add a profile setting modelled on Guided/Advanced; add a Chart home screen from
  existing panels; restyle; retire per-profile irrelevant screens. Rejected: side-by-side v2 shell
  (double maintenance) and full rewrite (highest governed-surface risk).
- **D6. §1 Profiles approved** (crypto starter watchlist BTC/ETH/XRP/SOL-USDT; Binance default venue,
  Coinbase selectable). Owner reminder: datasets also live on the 2 TB external SSD ("Expansion"
  volume — governed crypto immutable store + QuantPad archive); the Data drawer must inventory the
  external volume alongside internal `data/`, and show honestly when the volume is not mounted.
- **D7. Aesthetic direction (owner, after mockup v1).** v1 "modern dark dashboard" rejected as
  AI-generated-looking. Owner wants a classic desktop trading terminal (MultiCharts / older Windows
  terminals; refs in `~/Desktop/Dashboard-Inspo`): menu bar + icon toolbars, docked panels with title
  bars, tree navigator, Market Watch table with red/green numerics, tabbed bottom toolbox, status
  bar, small dense text, bevelled square borders — and pure-black chart canvases with white frames,
  thin lines and corner legend boxes (matplotlib style). Implication for the plan: the SPA shell
  restyle AND the Python figure theme (`alpha_research/figures`) should adopt the black/white-frame
  matplotlib look so on-screen and exported figures match.
- **D8. Colour palette: Option E** (light-grey window chrome around black chart canvases; green/red
  hollow/filled candles; blue selection). Chosen from six rendered options on 2026-09-01. Theme
  document name in the spec: `terminal_classic.json`. PNGs: `~/Desktop/ALPHA-terminal-designs/`.
- **D9. Spec open items closed.** Equities starter watchlist = the stored SPY/AAPL/… set; Toolbox
  "Alerts" tab dropped (no alert engine). Spec `2026-09-01-trader-terminal-ui-design.md` marked
  APPROVED; next step is the Phase 1 ("Work") plan via `/plan-feature`.

### Session note 2026-09-02 — Phase 1 implemented

W1–W8 of `docs/superpowers/plans/2026-09-01-trader-terminal-phase1-work.md` are committed behind the full gate. Invariants-auditor on W7: look-ahead, determinism, architecture PASS; one low finding — no `@pytest.mark.bias_guard` test covers `AssetMaster.resolve_native`'s pre-genesis refusal (the unmarked unit assertion exists). `tests/bias_guards/` is protected and not agent-ackable, so adding that guard (with its must-fail leaky twin) is an owner-gated follow-up. Next: owner walkthrough of the Phase 1 acceptance, then Phase 2 "Clean".

### Session note 2026-09-02 — Phase 2 implemented

C1–C8 of `docs/superpowers/plans/2026-09-02-trader-terminal-phase2-clean.md` are committed behind the full gate on `feat/trader-terminal-phase1-work` (`bfda12a`, `c6e5397`, `fecc14d`, `364e655`, `d3e424c`, `13f2a30`, `a2569a0`, plus the docs commit). Findings #8–#11 are closed; #12 (workflow-centric navigation) is Phase 3 work. Deviations recorded in the plan: Governance is a shell-level dialog (topbar ⚖ button + status chip deep link), the glossary is unfiltered because no entry carries a profile tag, and contextual `role=note` notices that name a next action stay on working screens. Two harness lessons: at 1280px the topbar was full, so the brand sub-line and the Governance label hide under the existing `@media (max-width: 1280px)` block (axe target-size); Playwright `getByText` is a case-insensitive substring match, so counts of `RESEARCH GATE OPEN` now use `exact: true`. Next: owner walkthrough of the Phase 1 and Phase 2 acceptance sentences, then Phase 3 "Terminal" (own plan).

### 2026-09-03 — Phase 3 "Terminal" delivered

T1–T8 of `docs/superpowers/plans/2026-09-03-trader-terminal-phase3-terminal.md` are committed behind the full gate on `feat/trader-terminal-phase1-work` (`8d49fc9`, `eab1a94`, `d8a04c5`, `fc8f577`, `c8321f0`, `21dd1b7`, `5771447`, `f109f90`, plus the docs commit). Finding #12 is closed: the six screens are replaced by the terminal shell (menu bar, toolbar, Market Watch and Navigator docks, MDI documents with bottom tabs, Toolbox, Data Manager dock, status bar), gated per crypto/equities profile in the browser only. Deviations and harness lessons are recorded in the plan. Every finding in this log is now closed in code; still owner-run: the acceptance walkthroughs in both profiles, the receipted asset-master regeneration, and the `tests/bias_guards/` guard for `AssetMaster.resolve_native`.

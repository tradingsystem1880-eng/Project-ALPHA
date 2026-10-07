# ALPHA quant workstation

The local React application is served by FastAPI, with actions and engine-backed reads routed
through the existing public `alpha` CLI. Launch the integrated application from the repository:

```bash
uv run alpha-web
```

Open **http://localhost:8801**. This is the canonical origin for local action confirmation.

## Navigation

The classic menu bar and one compact toolbar expose the existing workflow routes through
**View** and Search (Cmd/Ctrl+K). Market Watch and Navigator occupy the left dock; Data Manager
or Research tools are optional right docks. Document tabs and Toolbox sit beneath the analytical
workspace, followed by the segmented status bar. Arrow keys, Home and End activate document tabs.
Closing a document retains other documents in the same profile. URLs remain `#page=...&pane=...`.

ChartWorkspace stores validated presentation settings per market profile. Its four-panel limit
supports single, side-by-side, stacked, three-row and 2×2 layouts. Splitters accept pointer drags
and arrow keys. Each panel has source, replace, duplicate, close and maximize controls; Escape
restores an individual maximized panel and its focused control. Chart instances survive layout,
grid, crosshair and series-type changes. Fit/reset is explicit. Narrow screens stack panels.

**Research · Bokeh** is the default renderer for market observations and recorded series. **Market · Lightweight** remains an optional per-panel mode. Genuine backend Matplotlib figures remain available under figures and the research report preset. Bokeh uses paper-like plotting surfaces with labeled axes, native OHLC, evidence markers, UTC readouts, pan/zoom/box zoom and PNG export. Volume and backend indicator series have separate expandable plots; their ranges are explicitly independent. Bokeh display LOD during movement is disclosed; full recorded values and tables stay intact. Splitter resizing preserves canvases/ranges and coalesces axis layout after an 80 ms quiet period. Scientific relayouts share the frame budget with four paint frames between plots; cursor overlays use Bokeh UTC scales without canvas uploads. Large-series timing tests measure initialized interaction after preflight/native LOD/font completion and include genuinely changed settled dimensions within their 60 measured intervals, retain DOM/action traces, and capture screenshots after timing instead of continuously recording JPEG frames.

**Performance budgets are an opt-in lane** (owner decision 2026-10-05). The four `@perf-budget` browser specs measure the host machine's frame timing, so the gate and CI skip them. Run them on an idle reference machine with `ALPHA_PERF_BUDGETS=1 npx playwright test --project chromium-reference-only`; the budgets themselves are unchanged.

**Document screenshots keep one baseline per platform** (owner decision 2026-10-07): `*-darwin.png` for macOS and `*-linux.png` for CI's Linux runners, both at the same 2% pixel tolerance. Re-take Linux baselines in the `mcr.microsoft.com/playwright:v<version>-noble` container (`--platform linux/amd64`) against a locally started backend, never by copying macOS images.

The toolbar controls the active panel. Native timeframe buttons select exact compatible archive
sources. From stored markets, interval buttons open a venue/market source chooser; unavailable intervals explain why and never resample in the browser. Price series types
are unavailable for recorded line plots; static scientific surfaces disable interactive controls.
Panels offers chart/table, chart/diagnostics and recorded price/equity/drawdown/rolling-Sharpe
presets, plus a research report arrangement of equity, drawdown, diagnostics and figures. Only the primary context panel follows active market navigation; comparisons pin their
market window/snapshot, archive manifest or recorded run. Changing a panel source cannot change
canonical research context. Hidden chart documents retain their captured context and range.

Optional UTC range and cursor linking uses a local animation-frame registry outside React state. Latest ranges reach one peer per available axis-work frame; pending resizing or other live documents can add convergence frames. Cursors reach peers together. Both renderers share cancellable axis work: resize dispatches are separated by four paint frames, and peer range dispatch never shares a resize frame. Current views and mounted charts are preserved.
Absent timestamps clear linked cursors. Recorded plots display backend values and null gaps;
backend histogram bins and QQ points use interactive Bokeh plots; monthly returns and portfolio correlations retain scientific SVG axes. All preserve exact accessible tables. Backend scientific figures remain explicitly static and retain exports,
metadata and sampling disclosures. Missing run price snapshots cannot use current candles.
The equity contract does not identify currency/normalization, which is disclosed in plot units.

The visible Project selector lists real projects/cases and includes **No project — browse data**. Clearing a project retains the viewed market/archive and window while clearing its version/run/snapshot identity. Project selection confers no research authority. Inventory failures remain visible and retryable.

Old comparison-symbol and dock preferences migrate; obsolete window-manager preferences remain
ignored. Named research workspace files keep their existing schema. Presentation storage confers
no research or execution authority.

The Strategy Development form retains the CLI catalogue.

The context button selects an available pair and date window. Crypto choices combine `/api/symbols`
with external-drive chart discovery. Alias labels such as BTC-USD and BTC/USD share one BTC/USD
row; expand it to select the exact stored feed or archive source/native interval. Quotes and
contracts remain distinct, and source labels include the native instrument and manifest identifier.
Selecting an archive opens Price with its exact manifest; failures remain explicit without a
canonical fallback. Canonical strategy context is preserved separately. Market Watch also offers
this picker through Browse all available markets. Browse all crypto datasets opens the typed
non-price inventory. Metadata is not proof of integrity or research eligibility. Downloads accept
typed symbols without claiming verified availability.

Page/task links use `#page=...&pane=...`. Legacy `#run=<id>` links remain supported. Context and
existing display preferences survive reload. Named workspace files remain unchanged; obsolete
terminal window preferences are ignored.

Price → External archive discovers compatible datasets on the configured external drive. Select an exact instrument, venue, market type, interval and acquisition window. Opening verifies the artifact and raw parents; metadata discovery alone is not verification. Archive charts label their own context and volume units, exclude incomplete bars and remain separate from strategy snapshots. Return to stored chart restores the canonical strategy symbol.

Research actions use a server-bound click confirmation; no Touch ID enrollment is required. Receipts identify local confirmation honestly. Optional legacy WebAuthn remains available. See ADR-0038 for the trusted-local security model.

## Connected edge workspace

On Price, **Research tools** opens Assistant, Conditions, Indicators and Notes. **Workspace results**
opens Scan results, Trades, Results and Run library beneath the chart. Dock selections and widths
persist per market profile; arrow keys navigate dock tabs. Data Manager and Research tools share
the right-hand space. Individual panel maximize fills the viewport while preserving the dock layout for restoration.

Market Watch in **Data & Assets → Watchlist** includes only markets present in the stored inventory.
Stored quote variants remain separate and are shown with their exact symbols; selecting a row opens
the canonical Price chart with its date window, snapshot and run selection cleared.

Select saved Conditions to see CLI-evaluated operands, pass/fail/unavailable status, signal, cutoff
and rule hash. A scan row opens its symbol and evaluated date, clearing prior archive/run/snapshot
context. Changed rule hashes are flagged. Exact archive and run charts remain explicitly labelled;
canonical rule evaluation is unavailable for these alternate datasets.

Assistant uses the installed, authenticated local Codex CLI; model inference is remote. It sends
only bounded, server-assembled context to that service. Readiness verifies isolation. Sessions and
source hashes persist locally; cancellation and a five-minute watchdog bound inference. Answers
cite attached sources and identify missing evidence. Changing context makes old drafts unavailable. Scan-linked sessions pin the exact rule hash;
editing that saved rule requires a rescan or explicitly selecting current rules. Saved running turns
continue to be checked after a web restart even if their job handle was lost; failed turns show
the backend error and a recovery action.
**Open draft in rule builder** rechecks context and validates the proposed RuleSpec; you still
review, name, save and test it through the existing workflow. No draft grants research approval,
executes arbitrary code or places an order. Legacy runs without verified snapshots and cutoffs
cannot be attached as verified evidence.

Notes require a selected Research Case and remain observations. Results show recorded return,
drawdown, fee/slippage assumptions, trades, baseline availability and validation; unavailable
cost totals or metrics are labelled. A matching screen or model explanation is not proof of edge.

## Development and checks

From this directory:

```bash
npm ci
npm run lint -- --deny-warnings
npm run test:coverage
npm run generate:api
npm run build
npm run test:e2e
```

The build writes the committed production SPA to `../src/alpha_web/static/app`. Use the integrated
FastAPI application for UI/backend verification. `npm run dev` is an assets-only Vite server;
it has no API proxy and is not the integrated application.

Playwright launches its own real backend at localhost:8802 and refuses to reuse an unknown server.
Set `ALPHA_PLAYWRIGHT_PORT=8803` (or another free port) when another checkout is testing concurrently. The app store, bulk store and working directory are temporary; bars for SPY and BTC/USDT are
labelled synthetic test fixtures, not market evidence. Paper routing is disabled. Mocked tests
remain useful for deterministic owner-auth, failure, latency and artifact cases; they do not prove
live provider or physical Touch ID acceptance. Real-backend tests exercise persisted research,
workspace, rule, scan, chart and job workflows separately.

Screenshots and accessibility checks cover 1280×720, 1440×900 and 1920×1080. The aggregate gate is
`uv run python scripts/gate.py full` from the repository root. Record blocked external dependencies
and unverified owner actions explicitly.

[Reference workstation delivery report](../../../docs/operations/2026-10-03-reference-quant-workstation.md).

[Scientific renderer correction](../../../docs/operations/2026-10-03-scientific-research-workstation.md).

Chart exploration: each scientific series has All data / 30D / 90D / 1Y and inclusive UTC-date windows anchored to returned coverage. These are display ranges; sources, native intervals and returned tables do not change. Linked UTC ranges apply through the existing imperative registry. Coverage expands to full-returned-series counts, null gaps, observed extrema and final timestamp value. Cursor data expands to native OHLCV for prices; numerical updates use refs, without workspace renders. Recorded tables expose row/page counts and exact full-returned-series CSV with empty cells for unavailable values. Sampling bounds have a readable table plus raw provenance. Empty charts offer direct source/archive actions; panel/layout captions retain stable stored enum identities. Small scientific panels scroll/contain plot content, preserving adjacent table controls.

Scientific resizing uses Bokeh’s native interaction/level-of-detail signal and returns to full-detail idle after settling. Observations and exact table/export values remain unchanged.

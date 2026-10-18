# ALPHA technical chart language (StockCharts Classic/Default grammar)

**Current status — 2026-10-17:** Accepted through [PR #55](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/55) with seven successful required checks. The separate wheel-order follow-up remains under its own status and is not closed by this annotation.

Earlier dated status and incident entries are preserved as historical records.

**Historical delivery state before PR #55:** Local implementation and corrected-tree full verification complete; authorized scoped PR delivery in progress.

Owner request 2026-10-07: make the primary analytical charts read as market-analysis software,
close to StockCharts Classic and Default, by reproducing their visual grammar rather than their layout.
Owner decisions: Classic is the default with Default as an alternate style; the time axis is gapless
with marks for missing expected observations; the Classic studies template (SMA 50/200, RSI 14,
MACD 12/26/9, volume) is on by default; scope is the price chart plus every BokehJS plot. The
Lightweight renderer and the matplotlib figure theme are follow-ups.

```json
{
  "schema_version": 1,
  "title": "StockCharts-grade technical chart language for the default BokehJS renderer",
  "context": "The default scientific price renderer shows one Bokeh plot with a toolbar, axis titles, sparse ticks and ~20px per bar; volume and backend indicators are hidden in a collapsed details element as independent plots. The owner wants the StockCharts Classic/Default grammar: observation-indexed bars at high density, a shared-border panel stack (RSI / price+volume / MACD), dense right-hand value axes, a bold month/year date axis, coloured legends with values, axis value tags and a dense OHLC header.",
  "assumptions": [
    {"statement": "Every study value can come from alpha chart overlays; sma, ema, bbands, rsi and macd (with histogram) already exist with panes price/rsi/macd.", "verified_by": "apps/alpha-cli/src/alpha_cli/chart_cmds.py indicator_series"},
    {"statement": "The CLI fails the whole overlay request when the window is shorter than the longest study.", "verified_by": "chart_cmds.py indicator_series raises DataError when _bars_needed >= n"},
    {"statement": "Bokeh 3.10 is the default price renderer and owns standalone documents released by bokehLifecycle.", "verified_by": "PriceChart.tsx renderer switch; chartWorkspaceModel default 'scientific'; bokehLifecycle.ts"},
    {"statement": "Header change from two recorded closes is display arithmetic with precedent.", "verified_by": "marketWatchModel.ts Daily % from the two stored closes"}
  ],
  "alternatives_considered": [
    "Restyle Lightweight Charts: rejected; owner made scientific (Bokeh) rendering the default and Lightweight cannot draw bold calendar labels or shared-border panels.",
    "Proportional datetime x axis: rejected by owner in favour of gapless observation spacing with gap marks.",
    "Client-computed indicators: forbidden; the SPA never computes a study value."
  ],
  "pre_mortem": [
    "Four 25k-bar panels with several Bokeh figures each exceed the existing perf budgets; keep LOD, one document per chart and RAF-throttled autoscale.",
    "Ordinal x breaks UTC range/cursor linking; convert through bar timestamps and test linking across two panels.",
    "Template studies longer than the loaded window fail every overlay; filter by a drift-tested barsNeeded mirror and name skipped studies.",
    "Canvas fonts differ by platform; baselines stay per platform and Linux baselines are re-taken in the Playwright container."
  ],
  "slices": [
    {"title": "Tokens and pure technical model (ordinal, date ticks, gaps, candle/volume colours, extents, labels, panel layout, header) with Vitest", "verify": "cd apps/alpha-web/frontend && npx vitest run src/components/technical", "expected": "all model tests pass", "rollback": "delete src/components/technical", "status": "done"},
    {"title": "Bokeh technical renderer and React wrapper wired into PriceChart; settings chartStyle, Classic template default, barsNeeded drift test, View menu style", "verify": "cd apps/alpha-web/frontend && npm run lint -- --deny-warnings && npx tsc -b && npm run test:coverage", "expected": "lint, types and unit tests pass", "rollback": "revert PriceChart renderer switch", "status": "done"},
    {"title": "Shared technical chrome for recorded series and cartesian Bokeh plots", "verify": "cd apps/alpha-web/frontend && npm run test:coverage", "expected": "pass", "rollback": "revert bokehPlot/bokehCartesian", "status": "done"},
    {"title": "Visual comparison loop against the StockCharts references, e2e updates, new technical-chart spec and baselines, perf budgets", "verify": "cd apps/alpha-web/frontend && npm run test:e2e && ALPHA_PERF_BUDGETS=1 npx playwright test --project chromium-reference-only", "expected": "functional e2e pass; opt-in timing measured and failures retained", "rollback": "restore previous baselines", "status": "done"},
    {"title": "Docs, committed static/app, full gate", "verify": "uv run python scripts/gate.py full", "expected": "all components pass", "rollback": "n/a", "status": "done"}
  ],
  "tier_impact": [],
  "docs_to_update": ["docs/BUILD-STATUS.md", "CLAUDE.md", ".claude/rules/alpha-web.md", "apps/alpha-web/frontend/README.md"],
  "out_of_scope": [
    "Lightweight renderer restyle",
    "matplotlib figure theme and figure goldens",
    "Backend, API or CLI changes",
    "Client-side indicator computation"
  ]
}
```

## Analysis: why StockCharts reads as "analysis" and TradingView/ALPHA read as "app"

| Area | StockCharts Classic/Default | TradingView / current ALPHA |
|---|---|---|
| Density | About 250 bars at about 5px per bar. The bars nearly touch: 4–6px bodies with 1px gaps. | About 20px per bar, with a lot of empty space between candles. |
| Geometry | 1px wicks and 1px body outlines. Classic: colour comes from close vs *prior close* (black/red) and fill from close vs open (hollow up). Default: OHLC ticks. | Solid filled green/red bodies with no outline. The palette encodes only one bit of information. |
| Plot fill | Price spans the full panel height. Volume is an overlay in the bottom quarter of the price panel. | 8% padding, no volume, and the price is centred with empty space around it. |
| Axes | Price is on the right only, with dense ticks (every 2.5, roughly one label per 17px). Volume ticks sit in the left gutter (25M…). There are no axis titles. | Sparse ticks, rotated axis titles ("Price (native quote units)", "Time (UTC)"), labels on both sides. |
| Date axis | Weekly day-of-month labels, **bold month names**, a bold year at the boundary, and darker gridlines at month starts. It is drawn between the price and MACD panels and again at the bottom. | Four `11/15`-style labels. |
| Grid | Light 1px lines (`#e8e8e8`) on every tick, with month gridlines slightly darker. | Faint and sparse. |
| Panels | RSI : price : MACD at about 1 : 2.9 : 1, separated by shared 1px borders (`#c0c0c0`), with no gaps or cards. | Separate plots inside a collapsed details element, each with an independent range. |
| Labels | Legend at the top left of each panel, in the series colour, with values ("MA(50) 322.30", "MACD(12,26,9) 3.261, 4.308, -1.047"). Value tags on the axis at the last value of every series; the price tag is bold with a black box. | Series names only, in a footer strip. No current values. |
| Header | A dense text block: symbol, date, Open/High/Low/Close/Volume, Chg with absolute and %. | Several rows of buttons and chips, and a crosshair readout row. |
| Typography | Small sans-serif, about 10–11px, hinted. Numbers are dominant. | Mixed monospace, larger chrome. |
| Colour | Black and red on white. Studies use saturated navy, red and green lines. Volume is desaturated grey/pink so it never competes with price. | Muted green/red with no hierarchy. |
| Interaction | Static image, with no toolbar or floating UI. | A floating Bokeh toolbar, box-zoom, and zoom on both axes. |

**Principles that become reusable tokens and primitives:**
- Observation-indexed x.
- Full-height autoscale on the y axis.
- Right-hand value axis with dense ticks.
- Calendar date ticks with a bold month and year hierarchy.
- 1px geometry.
- Shared-border panel stack.
- Coloured in-panel legends that show values.
- Axis value tags.
- Volume as an underlay.
- No toolbar. Interaction is x-only pan and zoom, plus a crosshair that updates the legends and header.

## Design

- `technicalTokens.ts`: Classic/Default palettes (measured hex values), font, body/tick geometry,
  study colour assignment and the `--tc-*` CSS variables every chart host sets.
- `technicalModel.ts` (pure, unit-tested): calendar inference, date ticks, observation gaps,
  candle classes, visible extents, nice ticks, labels, panel layout and header values.
- `technicalRenderer.ts`: one BokehJS `Column` of figures sharing an x `Range1d` over the
  observation index; canvas glyphs for series, pooled DOM layers for legends, tags, date strip,
  gap marks and the crosshair.
- `TechnicalChart.tsx`: header line, range links, Save PNG, skipped-study disclosure; recorded
  series and histogram/QQ plots use `technicalChrome.ts` with the same tokens.

## Implementation notes (2026-10-07)

- Deviation: `barsNeeded` was not mirrored; the SPA reads the CLI's own short-window refusal
  (`shortStudy`) and retries without that study, which stays exact when the overlay window is longer
  than the displayed bars. The CLI sentence is pinned by `tests/unit/test_chart_overlays.py`.
- Deviation: the chart style switch is a workspace-toolbar select beside the renderer select rather
  than a View-menu entry.
- `data-visible-range` on the technical host reports the first/last displayed observation (UTC),
  not the requested calendar bounds.
- Opt-in perf budget (`@perf-budget`, not in the gate or CI): four 25k-bar technical panels measure
  median ~10ms and p99 28–47ms on the owner's darwin machine, so the 34ms p99 budget fails
  intermittently. Unmodified `main` on the same machine measured p99 27–35ms and also fails at times.
- Linux baselines (`technical-chart.spec.ts` Classic/Default and the reference/wide chart documents)
  were rendered in `mcr.microsoft.com/playwright:v1.61.1-noble` (linux/amd64) against a host
  backend and inspected: identical geometry, DejaVu Sans in place of Verdana.
- Gap marks use the series' own calendar (`inferCalendar`: any weekend observation means 24/7),
  not the settings profile, and say "N weekdays/intervals without an observation" because
  exchange holidays are not known to the SPA.
- The Market · Lightweight renderer discloses CLI-refused studies as a `studies skipped` status
  chip; histogram/QQ plots keep reset and PNG save on an inner toolbar shown only on hover.
- Final review: recorded-series, cartesian, readout and price-footnote CSS read `--tc-*` variables
  set from the tokens on each chart host (no hard-coded colours or fonts), and value tags share
  `technicalChrome.tagStyle`.

## Cleanup review (2026-10-08)

Independent review found the original PNG export omitted DOM date labels, legends, gap marks and value tags. The export now composites those visible layers and the OHLC/title header over Bokeh canvases. A downloaded-PNG browser regression reproduced the original omission. The first focused invocation inadvertently ran dependency projects; it was interrupted deliberately after 48 passes, and its interrupted scanner journey is not treated as a defect result. Focused export verification and a fresh full gate are required for the corrected tree. Intermittent opt-in p99 timing remains unresolved; no budget was weakened. Hidden holdout coverage is UNVERIFIED because the directory is absent.


**2026-10-09 — Exact volume color views (unmerged).** Post-mask profiling exposed full-source CSS color materialization on every view update. Complementary up/down views now share the full native x/volume source with scalar style colors, retaining previous-close classification, equal-close bars, partial viewport intersections, width, scales, cursor and exports. Three failing-first partition tests are covered by 26 passing model tests; seven focused browser tests pass with unchanged screenshots and PNG export. The new profile recorded zero `_from_css_array` samples, versus about 165.5 ms directly before the change. Profiled/ordinary p99 passed at 27.2/27.3 ms; a fixed three-repeat run passed at 27.2/27.3/27.2 ms against the unchanged 34 ms limit. This evidence improves the previously intermittent timing lane without promising every future machine/run will pass. Fresh final aggregate and independent acceptance remain required; hidden-suite execution stays UNVERIFIED/BLOCK. [Cleanup plan](2026-10-08-repository-hygiene.md).


## Local reconciliation (2026-10-10)

Recovered onto `reconcile/preserved-features` from the verified preservation snapshot. Original receipts remain historical. Standing private-suite policy and mutation/maintainability changes are excluded. Focused checks and a fresh exact-tree aggregate are pending; no release acceptance or publication is claimed.

Fresh focused checks:69 backend regressions and eight chart browser tests pass on the recovered candidate. Two additional PNG omissions were reproduced and corrected: annotation-outside-window disclosure and the volume legend swatch. Final aggregate and independent acceptance remain pending.

## Authorized delivery checkpoint, 2026-10-11

The recovered chart/CASH/PIT/hygiene candidate passed all six canonical components on
unchanged tree f54af6df, including browser exports and preserved Darwin/Linux baselines.
The owner then approved the [one-time scoped private-suite exception](../../operations/2026-10-11-recovered-work-private-suite-exception.md)
and separate PRs/merges after all available checks. Private coverage remains UNVERIFIED.
This documentation update requires refreshed Atlas, full verification and fresh independent
review before guarded commit; hosted exact-target CI and dependency integration precede merge.
Historical receipts above remain historical and are not rewritten as current acceptance.

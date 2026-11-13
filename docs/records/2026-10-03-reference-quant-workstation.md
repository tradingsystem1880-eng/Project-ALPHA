# Reference-matched quant workstation delivery

> **Superseded acceptance note (2026-10-05):** pending or failed aggregate results below are historical. The canonical full gate later passed on the frozen shared tree (stamp tree `54b7f96e`, 2026-10-04 13:46 UTC); see `docs/BUILD-STATUS.md`.

Implementation branch: `feat/crypto-terminal-ui`. Existing shared-tree changes were preserved.
This report concerns the workstation additions; it does not attribute earlier backend, archive,
provider or authentication changes to this implementation. Engineering evidence confers no
research approval or execution authority.

## Audit and design choices

The prior shell stacked workflow navigation rows; chart composition lived inside App, comparison
charts inherited shared run/window inputs, and a single canvas effect rebuilt/fitted the chart on
options, evidence and selection updates. Existing APIs already supplied chart bundles, equity,
native tear sheets, portfolio projections and backend figures, so no endpoint or estimator was
needed.

The four images in `/Users/hunternovotny/Desktop/ALPHA-terminal-designs` are visual authority:
1 determines dock and tab placement; 2 determines report tree/metrics/plots; 3 determines individual
maximize/restore; 9 determines grey chrome and black plotting surfaces. Reference dimensions are
1585×991, with 1280×720 and 1920×1080 supported browser projects. The implementation uses existing
tokens, square controls, thin borders, compact rows, 11–12px text and JetBrains Mono numbers.
Mockup prices, provider states and diagnostics were not used as application data.

[Qbot's pinned results panel](https://github.com/UFund-Me/Qbot/blob/f0425ae4ae8bd02b79656b8f7039f4cd6874095e/qbot/gui/panels/panel_results.py)
informs adjacent plot/table composition and research/trading separation. Its wxPython widgets and
embedded HTML were not copied. ALPHA remains React with Lightweight Charts and backend figures.

## Architecture and behavior

App now provides classic menus, one active-panel toolbar, existing route/search destinations,
profile-specific open document tabs and the segmented status bar. ChartWorkspace composes existing
MarketDesk docks. Its validated local model limits analytical panels to four with stable IDs,
explicit sources, active panel, split ratios, layout and maximize state. Saved comparison symbols
migrate to pinned market descriptors; dock preferences and named research workspace schemas remain.

Single, side-by-side, stacked, three-row and 2×2 layouts have pointer/keyboard splitters. Presets
include chart/table, chart/diagnostics and recorded price/equity/drawdown/rolling Sharpe. Duplicate
copies configuration into independent identity. Replace/source/close/maximize act on one panel.
Individual maximize retains chart instances; Escape restores layout and focus. Narrow screens stack
panels. Market Watch/Navigator remain left; optional data/research docks remain right; document tabs
and Toolbox occupy the center footer.

Only primary market navigation follows canonical context. Comparisons retain their own market
window/snapshot, exact archive manifest or run. Hidden chart documents retain captured context.
Recorded run price errors remain explicit; current market candles never replace unavailable frozen
snapshots. Native timeframe buttons select compatible exact archives; unsupported intervals explain
absence and never resample client-side.

PriceChartCanvas separates chart lifetime from composition, options, markers and selection effects.
It saves the panned range before replacing a series and fits only on initial data or explicit reset.
UTC range/cursor linking uses a workspace-local animation-frame registry outside React state.
Remote range callbacks remain suppressed until captured local gestures; absent timestamps clear
cursors. UTC endpoints map directly to logical coordinates by binary search over backend timestamps; no queued chart state is read for remote ranges. Inclusive endpoint guards prevent an outward one-bar floating-point error.

RecordedSeries renders line/area equity, drawdown, benchmark, Sharpe, volatility, exposure and turnover
from backend points, preserving null gaps. Controls apply to active interactive plots; unsupported
series types/static-figure controls are disabled. ScientificPlots maps backend histogram bins, QQ
scatter, monthly returns and portfolio correlations to SVG axes/legends and exact accessible tables.
FigureSurface reuses backend Monte Carlo, robustness, regime and parameter-sweep figures with
exports, metadata and explicit noninteractive labels. Run report metrics remain recorded values;
the report tree now places aligned metrics beside equity/drawdown and available figures.

No backend/API schema or statistical-model additions were made. Immutable run responses and exact
archive/snapshot candle responses share the existing cache by complete request identity. Current
market reads remain fresh. API errors and stale source responses cannot overwrite a newer panel.

## Review corrections

Read-only independent review produced these normalized findings. Sources: workstation_review agent.
All patches are scoped to frontend presentation and interaction.

| ID | Severity | Area/location | Issue and impact | Patch/status |
| --- | --- | --- | --- | --- |
| RW-01 | Required | ChartWorkspace presets | Pinning primary severed canonical navigation | Preserve primary in two-panel presets; explicit canonical commands restore primary; addressed |
| RW-02 | Required | PriceChartCanvas composition | Reading range after series removal lost pan/zoom | Capture range before cleanup and restore after composition; addressed |
| RW-03 | Required | PriceChartCanvas/RecordedSeries linking | Async range notifications could echo | Remote suppression until captured local gestures; RAF throttle and rounding guard; addressed |
| RW-04 | Required | App workspace actions | Menu commands dispatched before mount were lost | Profile-scoped React command queue with one-time consumption; addressed |
| RW-05 | Required | App document closure | Neighbor could belong to another profile | Select remaining visible-profile neighbor; addressed |
| RW-06 | Required | PriceChart/PanelHost visibility | Lagged visibility could capture hidden run context | Pass captured workspace context, ignore hidden context transitions; addressed |
| RW-07 | Required | Linked range endpoints | Reading queued scale state could overwrite remote target | Compute target logical indices directly from backend timestamps; independently reproduced and corrected; addressed |
| RW-08 | Optional | Recorded controls | Toolbar actions were enabled without effects | Apply grid/crosshair/zoom/reset to recorded series; disable unsupported controls; addressed |

## Verification and evidence

Commands used include frontend lint with denied warnings, TypeScript build, Vitest coverage,
production build, deterministic API generation, Playwright reference/viewport scenarios and the
canonical aggregate `uv run python scripts/gate.py full`. Acceptance requires the exact current
working-tree receipt in `.alpha/state/gate-stamp.json`; historical receipts and this narrative are
not substitutes. The first aggregate attempt failed because a temporary Git-index environment leaked into isolated Git tests and the expanded manual exceeded its 6,000-byte combined limit. The environment was removed and the manual condensed without weakening requirements. Generated assets are temporarily staged for freshness checks; the original index is restored afterward. The final response reports the actual aggregate outcome. The three-viewport preparatory run had
280 passing tests and two minimum-size report scroll-focus failures; those were corrected and the
54 final focused viewport/accessibility regressions passed. All five reference-only performance and
real-workflow tests passed separately. The full gate reruns the entire 287-test browser suite.

Frontend unit evidence: 61 files / 340 tests passed; coverage 92.73% statements, 82.76% branches,
96.17% functions and 94.79% lines. Lint with denied warnings, types and build passed.

Read-only live browser validation opened local run `5ca68199f7241db4`: chart-bundle returned
`bars_status=snapshot_unavailable` with zero bars, while equity returned 2,808 timestamps and
native tear sheet supplied a backend rolling window of 126. The four-panel workspace displayed
three real recorded plots and the explicit price absence, with all three API reads returning 200.
No owner artifact or run was modified by this check.

Regression coverage includes mounted canvas identity across controls/layout/maximize; actual panned
range preservation; independent canonical/comparison sources; asynchronous bidirectional linking;
hidden-document retention; a run with missing price and available equity/drawdown/backend rolling
Sharpe; null-gap tables and scientific plots; archive failure/integrity behavior; scan navigation;
menu/search/report routes; accessibility; and real browser-to-API-to-CLI persisted research journeys.
The large-series scenarios use 25,000 bars and 200 annotations, including a four-panel case with
resize/cursor/range interaction against the existing median ≤18ms, p99 ≤34ms and over-budget ratio
≤adjacent baseline+0.05 thresholds. These deterministic fixtures are labelled test inputs, not
production evidence.

## Limitations and next improvements

A frozen price snapshot absent from a legacy or audited run cannot be recovered by presentation
code; its price panel reports absence while recorded diagnostics remain useful. Static backend
figures have no interactive cursor. The equity API does not identify currency/normalization, so the
unit readout explicitly discloses that rather than inventing USD. Native diagnostics retain backend
window/sampling/provenance; the browser computes geometry only. External provider credentials,
network acquisitions and live-capital routing are outside this frontend change.

The local layout supports four fixed analytical panels, not floating windows. Future work could add
an explicit backend equity-unit contract and richer recorded-run source discovery; each requires
separate scope and evidence. No new statistical computation is implied by this delivery.

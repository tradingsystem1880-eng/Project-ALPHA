# Design — Workstation v3 shell and causal chart artifacts

**Status:** Implemented; offline release gate passed
**Date:** 2026-07-19
**Implementation reviewed:** 2026-07-19
**Authority:** `CLAUDE.md`, ADR-0002, ADR-0003, ADR-0005, ADR-0013

## Goal

Turn the shipped Workstation v2 into a chart-first professional terminal without adding a second
analytics or execution authority. Dockview remains the layout system, Lightweight Charts remains
the market-chart renderer, uPlot remains the dense analytic renderer, and Python artifacts remain
authoritative.

## Workspaces

The frontend ships six curated presets while retaining user-defined layouts:

1. Market Desk — watchlist, large price chart, instrument/evidence inspector, activity/jobs.
2. Development Center — project/version/stage navigation, evidence, resolved spec, jobs.
3. Kronos Forecast Studio — actual candles, forecast modes, inspector, rolling evaluation.
4. ML Research — universe/folds, recipe, training history, IC and signal tear sheet.
5. Portfolio & Risk — real allocation, correlation, exposure, drawdown, and stress artifacts.
6. Operations — providers, snapshots, jobs, paper sessions, and workspaces.

The linked context is versioned and contains link group `A|B|C|D`, project/version, symbol or
universe, timeframe, date range/as-of, snapshot, and active run. A v2 context is migrated by filling
new fields with safe defaults; a saved user layout is never overwritten.

## Visual contract

- Flat cool-black surfaces, one-pixel separators, small radii, tabular numerics, compact hit areas.
- No glass, bloom, decorative gradients, hero cards, or AI-themed decoration.
- Red/green encode observed sign or failure/pass only; blue encodes selection.
- Every chart exposes axes, units, timezone, as-of, provenance, legend/crosshair values, and a
  textual table/download alternative.
- React renders typed projections. It never recomputes Sharpe, validation gates, verdicts, ML
  claims, trades, patterns, or forecast probabilities.

## Causal trace contract

New observed backtest/validation runs may publish these additive deterministic sidecars before the
manifest completion marker:

- `decision_trace.parquet`
- `orders.parquet`
- `fills.parquet`
- `indicator_series.parquet`
- `chart_annotations.parquet`
- existing `trades.parquet`

Decision, order, fill, and closed-trade timestamps remain distinct. All records have canonical
sequence identifiers derived from stable ordering, not engine UUIDs. Indicator and pattern values
must be emitted from the trailing prefix at the decision time. Missing information stays missing;
the CLI, web, and frontend never infer it after the run.

Historical v1/v2 runs remain readable and return `trace_unavailable`. They are never augmented in
place. An explicit rerun is required to generate a v3 trace.

## Chart behavior

- A decision at close `t` and fill at open `t+1` use distinct markers connected on the chart.
- Entry, exit, holding interval, stop/target interval, realized outcome, and source artifact are
  inspectable when the corresponding causal fields exist.
- Pattern geometry is typed vector data: level, line, zone, polyline, or swing point with exact
  timestamp/price anchors and detector provenance.
- Run annotations are immutable. User drawings remain workspace/project state until promoted into
  a new strategy version.
- Selecting a table record selects and zooms the matching chart record, and vice versa.

## Native tear sheet

The primary terminal view renders Python-authored equity/drawdown, monthly/yearly returns,
distribution/Q-Q, rolling statistics, trade statistics, and benchmark data in the dark theme.
QuantStats-Lumi HTML remains an export/audit artifact and its metrics are namespaced when their
definitions differ from ALPHA's.

## Kronos studio

Expose existing OHLCV samples rather than close-only projections. The default view combines actual
candles, a forecast-origin boundary, median close, q25-q75 and q05-q95 bands, and up to 20 visible
sample paths (hard cap 40). A sampled K-line is one complete model sample and is labeled as such;
independent OHLC quantiles are never combined into a synthetic median candle.

Modes are cone, sampled K-lines, terminal distribution, and rolling evaluation. Provenance,
sampling parameters, deterministic status, pretraining-overlap warnings, and replay-vs-model Tier-2
policy remain visible. `Use as signal` is disabled until a rolling evaluation exists.

## Acceptance

- v2 layout/context migration and all six presets are covered by tests.
- Trace rows reconcile exactly with canonical result objects and close-`t`/open-`t+1` behavior.
- Future-poison tests prove earlier trace prefixes do not change when future bars change.
- Visual regressions cover 1440x900 and 1920x1080; 1280x720 remains usable.
- Charts remain responsive at 25,000 bars and 200 annotations, and accessible alternatives exist.

## Current implementation note — 2026-07-19

The contract is implemented. `alpha_backtest.results.BacktestResult` carries decisions, indicators,
annotations, orders, fills, portfolio state, benchmark, trades, and equity from the engine;
`alpha_cli._artifacts.write_run_sidecars` publishes them through the v3 artifact contract; and
`alpha_cli.run_projection.chart_bundle` verifies, windows, and bounds the bundle. OOS and holdout
charts use `alpha_cli._runner.fresh_oos_execution` / `fresh_scored_execution`, so their metrics and
causal records come from the same primed-but-positionless fresh portfolio. No discovery-period
event is copied into scored evidence.

The frontend implementation anchors are
`frontend/src/components/PriceChartCanvas.tsx`, `frontend/src/panels/PriceChart.tsx`,
`frontend/src/panels/KronosStudio.tsx`, `frontend/src/panels/NativeTearSheet.tsx`, and
`frontend/src/layouts/presets.ts`. Date windows filter bars and every event/indicator/annotation
series together. Native tear-sheet projections use deterministic endpoint-preserving bounds and
return original/returned/truncated metadata. The v2 layout migrator preserves its legacy source,
validates every panel alias, and writes v3 only after Dockview accepts the complete document.

Primary checks live in `tests/integration/test_backtest_oos_cli.py`,
`tests/integration/test_backtest_holdout_cli.py`, `tests/integration/test_web_api_runs.py`,
`frontend/src/layouts/presets.test.ts`, `frontend/src/panels/v3Models.test.ts`, and
`frontend/e2e/workstation.spec.ts`. The offline release gate and generated-asset checks passed;
six-desk pixel baselines cover 1440x900 and 1920x1080, 1280x720 remains the minimum supported desk,
and the target M4/16 GB 25,000-bar/200-annotation probe passed. Exact counts live in the audit
closeout rather than being duplicated here.

import { describe, expect, it } from 'vitest'

import type {
  ChartBundle,
  ChartTraceEvent,
  ForecastPaths,
  NativeTearSheetProjection,
  ProjectDetail,
  RunDetail,
} from '../api/types'
import {
  DEVELOPMENT_STAGES,
  buildCalendarRows,
  buildEvidenceMarkers,
  evidenceForDecision,
  matchesRunScope,
  projectStageRows,
  sandboxCandidateSummary,
  visibleEvidenceMarkers,
  terminalReturns,
  type EvidenceMarker,
} from './v3Models'

function event(overrides: Partial<ChartTraceEvent>): ChartTraceEvent {
  return {
    sequence_id: 1,
    event_type: 'decision',
    ts: Date.UTC(2026, 0, 2, 23) / 1000,
    parent_sequence_id: null,
    instrument_id: 'AAPL.SIM',
    side: 'BUY',
    quantity: 5,
    filled_quantity: null,
    price: 100,
    status: null,
    signal: 1,
    decision_reason: 'causal rule',
    entry_ts: null,
    exit_ts: null,
    entry_price: null,
    exit_price: null,
    realized_pnl: null,
    realized_return: null,
    ...overrides,
  }
}

describe('causal chart evidence', () => {
  it('maps only backend trace records to displayed markers and preserves exact timestamps', () => {
    const bundle: ChartBundle = {
      run_id: '0123456789abcdef',
      trace_status: 'available',
      bars_status: 'snapshot_unavailable',
      provenance: { command: 'backtest_run', symbol: 'AAPL', symbols: null, snapshot_id: null, snapshot_hash: null, timezone: 'UTC', price_unit: 'native_quote', artifact_contract_version: 3, as_of: null, artifact_sha256: {} },
      bars: [],
      equity: { ts: [], equity: [], drawdown: [] },
      trades: [],
      trace: [
        event({ sequence_id: 7 }),
        event({ sequence_id: 8, event_type: 'fill', ts: Date.UTC(2026, 0, 5) / 1000 }),
        event({
          sequence_id: 9,
          event_type: 'trade',
          ts: Date.UTC(2026, 0, 8) / 1000,
          entry_ts: Date.UTC(2026, 0, 5) / 1000,
          exit_ts: Date.UTC(2026, 0, 8) / 1000,
          realized_return: 0.03,
        }),
      ],
      decisions: [],
      orders: [],
      fills: [],
      indicators: [],
      annotations: [],
      folds: [],
      forecast: null,
      truncated: { bars: false, equity: false, trades: false, trace: false, indicators: false, annotations: false },
    }
    const bars = [
      Date.UTC(2026, 0, 2) / 1000,
      Date.UTC(2026, 0, 5) / 1000,
      Date.UTC(2026, 0, 8) / 1000,
    ]

    const markers = buildEvidenceMarkers(bundle, bars)

    expect(markers.map((marker) => marker.kind)).toEqual(['decision', 'fill', 'entry', 'exit'])
    expect(markers[0]).toMatchObject({ sequenceId: 7, exactTs: bundle.trace[0].ts })
    expect(markers[3]).toMatchObject({ sequenceId: 9, barTs: bars[2], tone: 'positive' })
  })

  it('does not invent markers when a legacy run has no trace', () => {
    const bundle: ChartBundle = {
      run_id: '0123456789abcdef',
      trace_status: 'trace_unavailable',
      bars_status: 'snapshot_unavailable',
      provenance: { command: 'backtest_run', symbol: 'AAPL', symbols: null, snapshot_id: null, snapshot_hash: null, timezone: 'UTC', price_unit: 'native_quote', artifact_contract_version: null, as_of: null, artifact_sha256: {} },
      bars: [],
      equity: { ts: [], equity: [], drawdown: [] },
      trades: [],
      trace: [],
      decisions: [],
      orders: [],
      fills: [],
      indicators: [],
      annotations: [],
      folds: [],
      forecast: null,
      truncated: { bars: false, equity: false, trades: false, trace: false, indicators: false, annotations: false },
    }
    expect(buildEvidenceMarkers(bundle, [1, 2, 3])).toEqual([])
  })

  it('selects indicators and annotations by the decision global trace id after interleaving', () => {
    const bundle = {
      trace: [
        event({ sequence_id: 1 }),
        event({ sequence_id: 2, event_type: 'order', parent_sequence_id: 1 }),
        event({ sequence_id: 3, event_type: 'fill', parent_sequence_id: 2 }),
        event({ sequence_id: 4, decision_reason: 'second decision' }),
      ],
      indicators: [
        { sequence_id: 1, decision_sequence_id: 1, ts: 1, instrument_id: 'AAPL.SIM', name: 'close', value: 100, unit: 'price' },
        { sequence_id: 2, decision_sequence_id: 4, ts: 2, instrument_id: 'AAPL.SIM', name: 'close', value: 101, unit: 'price' },
      ],
      annotations: [
        {
          annotation_id: 1,
          decision_sequence_id: 4,
          kind: 'line',
          label: 'second channel',
          unit: 'price',
          reason: 'second decision evidence',
          anchors: [
            { anchor_index: 0, ts: 1, value: 99 },
            { anchor_index: 1, ts: 2, value: 101 },
          ],
        },
      ],
    } as ChartBundle

    const selected = evidenceForDecision(bundle, 4)

    expect(selected.indicators.map((row) => row.value)).toEqual([101])
    expect(selected.annotations.map((row) => row.label)).toEqual(['second channel'])
    expect(evidenceForDecision(bundle, 2)).toEqual({ indicators: [], annotations: [] })
  })

  it('discards trace endpoints outside the visible daily-bar window', () => {
    const jan1 = Date.UTC(2026, 0, 1) / 1000
    const jan2 = Date.UTC(2026, 0, 2) / 1000
    const jan3 = Date.UTC(2026, 0, 3) / 1000
    const jan4 = Date.UTC(2026, 0, 4) / 1000
    const bundle: ChartBundle = {
      run_id: '0123456789abcdef',
      trace_status: 'available',
      bars_status: 'available',
      provenance: { command: 'backtest_run', symbol: 'AAPL', symbols: null, snapshot_id: 'snapshot', snapshot_hash: null, timezone: 'UTC', price_unit: 'native_quote', artifact_contract_version: 3, as_of: jan3, artifact_sha256: {} },
      bars: [],
      equity: { ts: [], equity: [], drawdown: [] },
      trades: [],
      trace: [
        event({ sequence_id: 1, ts: jan1 + 23 * 60 * 60 }),
        event({ sequence_id: 2, ts: jan2 + 23 * 60 * 60 }),
        event({ sequence_id: 3, event_type: 'fill', ts: jan3 }),
        event({ sequence_id: 4, ts: jan4 + 23 * 60 * 60 }),
        event({ sequence_id: 5, event_type: 'trade', ts: jan3, entry_ts: jan1, exit_ts: jan3 }),
      ],
      decisions: [],
      orders: [],
      fills: [],
      indicators: [],
      annotations: [],
      folds: [],
      forecast: null,
      truncated: { bars: false, equity: false, trades: false, trace: false, indicators: false, annotations: false },
    }

    const markers = buildEvidenceMarkers(bundle, [jan2, jan3])

    expect(markers.map((marker) => [marker.sequenceId, marker.kind])).toEqual([
      [2, 'decision'],
      [3, 'fill'],
      [5, 'exit'],
    ])
  })

  it('uses a bounded visual marker projection while retaining selected evidence', () => {
    const markers: EvidenceMarker[] = Array.from({ length: 30 }, (_, index) => ({
      id: `${index}:decision`,
      sequenceId: index,
      kind: 'decision' as const,
      barTs: index,
      exactTs: index,
      label: 'D',
      tone: 'selection' as const,
    }))
    markers.push({
      id: '99:fill',
      sequenceId: 99,
      kind: 'fill',
      barTs: 99,
      exactTs: 99,
      label: 'F BUY',
      tone: 'positive',
    })

    const decisions = visibleEvidenceMarkers(markers, 'decisions', null, 5)
    expect(decisions).toHaveLength(5)
    expect(decisions[0].sequenceId).toBe(0)
    expect(decisions.at(-1)?.sequenceId).toBe(29)
    expect(visibleEvidenceMarkers(markers, 'executions', 17, 5).map((row) => row.sequenceId))
      .toEqual([17, 99])
  })
})

describe('run workspace capabilities', () => {
  function detail(kind: string, command: string, hasEquity = false): RunDetail {
    return {
      run_id: '0123456789abcdef',
      kind,
      mtime: 0,
      display_name: `${command} D1 — run 01234567`,
      market: 'unknown',
      manifest: { command },
      has_equity: hasEquity,
      has_trades: false,
      has_tearsheet: false,
      has_forecast: false,
      has_nulls: false,
      has_trials: false,
      has_forecast_paths: false,
      has_propfirm_paths: false,
      has_origins: false,
      has_portfolio_analytics: false,
      research_gate_watermark: null,
      run_context_kind: 'legacy_context_unknown',
      run_context_project_id: null,
      run_context_watermark: 'LEGACY_CONTEXT_UNKNOWN',
    }
  }

  it('keeps portfolio, forecast, and ML replay evidence in their declared desks', () => {
    expect(matchesRunScope(detail('portfolio', 'backtest_portfolio'), 'portfolio')).toBe(true)
    expect(matchesRunScope(detail('cross_sectional', 'cross_sectional'), 'portfolio')).toBe(true)
    expect(matchesRunScope(detail('forecast', 'forecast_run'), 'portfolio')).toBe(false)
    expect(matchesRunScope(detail('forecast', 'forecast_eval'), 'forecast')).toBe(true)
    expect(matchesRunScope(detail('runs', 'ml_replay'), 'ml-replay')).toBe(true)
    expect(matchesRunScope(detail('runs', 'backtest_run'), 'ml-replay')).toBe(false)
  })
})

describe('Kronos sample projections', () => {
  it('derives terminal returns from complete backend sample K-lines', () => {
    const paths: ForecastPaths = {
      ts: [2, 3],
      samples: [
        { sample: 0, opens: [100, 101], highs: [102, 103], lows: [99, 100], closes: [101, 102], volumes: [10, 11] },
        { sample: 1, opens: [100, 99], highs: [101, 100], lows: [98, 97], closes: [99, 98], volumes: [12, 13] },
      ],
    }
    const values = terminalReturns(paths, 100)
    expect(values.map((row) => row.sample)).toEqual([0, 1])
    expect(values[0].value).toBeCloseTo(0.02)
    expect(values[1].value).toBeCloseTo(-0.02)
  })
})

describe('native tear-sheet projection', () => {
  it('builds a sparse year/month matrix without recomputing return values', () => {
    const projection: NativeTearSheetProjection = {
      available: true,
      calendar_returns: [
        { year: 2025, month: 1, return_value: 0.03 },
        { year: 2026, month: 2, return_value: -0.02 },
      ],
      yearly_returns: [{ year: 2025, return_value: 0.03 }],
      histogram: [],
      qq: [],
      rolling: [],
      exposure_turnover: [],
      benchmark: [],
      trade_statistics: [],
      exposure_available: false,
      turnover_available: false,
      benchmark_available: false,
      trade_statistics_available: false,
      bounds: {
        point_limit: 2_000,
        qq: { original: 0, returned: 0, truncated: false, sampling: 'all' },
        rolling: { original: 0, returned: 0, truncated: false, sampling: 'all' },
        exposure_turnover: { original: 0, returned: 0, truncated: false, sampling: 'all' },
        benchmark: { original: 0, returned: 0, truncated: false, sampling: 'all' },
      },
      provenance: {
        run_id: '0123456789abcdef',
        metric_namespace: 'alpha_validation',
        artifact_contract_version: 3,
        artifact_sha256: { 'calendar_returns.parquet': 'a'.repeat(64) },
      },
    }
    const rows = buildCalendarRows(projection.calendar_returns)
    expect(rows).toHaveLength(2)
    expect(rows[0].months[0]).toBe(0.03)
    expect(rows[0].months[1]).toBeNull()
    expect(rows[1].months[1]).toBe(-0.02)
  })
})

describe('development lifecycle projection', () => {
  it('uses the latest backend state for each canonical stage', () => {
    const project = {
      project_id: 'project-1',
      name: 'Mean reversion',
      hypothesis: 'x',
      falsification_criterion: 'y',
      status: 'active',
      current_version_id: 'sv_1',
      current_experiment_id: 'ex_1',
      created_at: '2026-01-01T00:00:00+00:00',
      updated_at: '2026-01-01T00:00:00+00:00',
      versions: [],
      experiments: [],
      stage_states: [
        {
          project_id: 'project-1',
          experiment_id: 'ex_1',
          stage: 'baseline',
          state: 'pass',
          state_history: [],
          state_history_truncated: false,
        },
      ],
      stage_run_links: [
        {
          link_id: 'link-1',
          project_id: 'project-1',
          experiment_id: 'ex_1',
          stage: 'baseline',
          run_id: '0123456789abcdef',
          linked_at: '2026-01-01T00:00:00+00:00',
          state: 'pass',
          state_history: [],
          state_history_truncated: false,
        },
      ],
      attempts: [],
      holdouts: [],
      holdout_audit: [],
      decision_packets: [],
      monte_carlo_reviews: [],
      research_gate_state: 'not_required',
      research_gate_overrides: [],
      truncated: {
        versions: false,
        experiments: false,
        stage_states: false,
        stage_run_links: false,
        attempts: false,
        holdouts: false,
        holdout_audit: false,
        decision_packets: false,
        monte_carlo_reviews: false,
        research_gate_overrides: false,
      },
      market: 'unknown',
    } satisfies ProjectDetail

    const stages = projectStageRows(project)
    expect(stages).toHaveLength(DEVELOPMENT_STAGES.length)
    expect(stages.find((row) => row.id === 'baseline')).toMatchObject({
      state: 'pass',
      runId: '0123456789abcdef',
    })
    expect(stages.find((row) => row.id === 'oos')?.state).toBe('not_started')

    const definition = {
      schema_version: 1,
      strategy_name: 'hedged_basis_crowding_v1',
      required_instrument: 'BTCUSDT',
      required_quote_asset: 'USDT',
      required_venues: ['bybit', 'binance'],
      total_round_trip_cost_bps: 40,
      periods_per_year: 1095,
      execution_model: 'two_leg_return_replay',
      deployment_scope: 'sandbox_only',
      paper_blocker: 'UNSUPPORTED_MULTI_VENUE_PAPER',
      places_orders: false,
    }
    const candidate = {
      ...project,
      versions: [{
        version_id: 'sv_1',
        strategy_name: 'hedged_basis_crowding_v1',
        source_fingerprint: 'git:fixture',
        definition,
        parameter_space: {},
        created_at: '2026-01-01T00:00:00+00:00',
      }],
      market: 'unknown',
    } satisfies ProjectDetail
    expect(sandboxCandidateSummary(candidate)).toMatchObject({
      perpLeg: 'SHORT BYBIT LINEAR PERPETUAL',
      spotLeg: 'LONG BINANCE SPOT',
      totalRoundTripCostBps: 40,
      paperBlocker: 'UNSUPPORTED_MULTI_VENUE_PAPER',
    })
    expect(sandboxCandidateSummary({
      ...candidate,
      versions: [{ ...candidate.versions[0], definition: { ...definition, required_quote_asset: 'USD' } }],
    })).toBeNull()
  })
})

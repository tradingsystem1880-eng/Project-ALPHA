import { describe, expect, it } from 'vitest'
import type { RunDetail } from '../../api/types'
import { backtestResult, backtestSource, isBacktestRun } from './backtestResultModel'

const runId = 'a'.repeat(16)
const hash = 'b'.repeat(64)
const detail: RunDetail = {
  run_id: runId, kind: 'runs', has_equity: true,
  display_name: 'Fixture', market: 'unknown', mtime: 0, research_gate_watermark: null,
  run_context_kind: 'standalone_sandbox', run_context_project_id: null, run_context_watermark: null,
  has_trades: false, has_tearsheet: false, has_forecast: false, has_nulls: false,
  has_trials: false, has_forecast_paths: false, has_propfirm_paths: false, has_origins: false, has_portfolio_analytics: false,
  manifest: { run_id: runId, command: 'backtest_run', schema_version: 3,
    run_identity_version: 3, artifact_contract_version: 3,
    artifacts: { 'equity_curve.parquet': { sha256: hash } } },
}
const series = { ts: [0, 60], equity: [100, 75], drawdown: [0, -0.25] }

describe('backtest result evidence', () => {
  it('binds the source to the selected v3 backtest and existing equity artifact', () => {
    expect(backtestSource(detail, runId)).toEqual({ runId, sha256: hash })
    expect(backtestSource(detail, 'other')).toBeNull()
    for (const patch of [{ command: 'forecast' }, { run_id: 'other' }, { schema_version: 1 },
      { run_identity_version: 1 }, { artifact_contract_version: null }, { artifacts: {} },
      { artifacts: { 'equity_curve.parquet': { sha256: 'bogus' } } }]) {
      expect(backtestSource({ ...detail, manifest: { ...detail.manifest, ...patch } }, runId)).toBeNull()
    }
    expect(backtestSource({ ...detail, has_equity: false }, runId)).toBeNull()
    expect(backtestSource({ ...detail, kind: 'forecast' }, runId)).toBeNull()
  })
  it('preserves sign, fraction and epoch units deterministically without rounding', () => {
    const expected = { observations: '2', timestampUnixSeconds: '60', timestampUtc: '1970-01-01 00:01:00 UTC', drawdown: '-0.25' }
    expect(backtestResult(series)).toEqual(expected)
    expect(backtestResult(series)).toEqual(expected)
    expect(backtestResult({ ...series, drawdown: [0, -0] })?.drawdown).toBe('-0')
    expect(backtestResult({ ...series, drawdown: [0, -Number.MIN_VALUE] })?.drawdown).toBe('-5e-324')
    expect(backtestResult({ ...series, equity: [1, -Number.MAX_VALUE], drawdown: [0, -Number.MAX_VALUE] })?.drawdown).toBe(String(-Number.MAX_VALUE))
  })
  it.each([null, {}, { ...series, ts: [] }, { ...series, equity: [1] },
    { ...series, ts: [60, 0] }, { ...series, ts: [0, 0] }, { ...series, ts: [0, Infinity] },
    { ...series, equity: [0, 1] }, { ...series, equity: [NaN, 1] },
    { ...series, drawdown: [0, -Infinity] }, { ...series, drawdown: [0, 0.01] },
    { ...series, drawdown: [0, '-0.25'] }, { ...series, drawdown: [0, null] },
    { ...series, drawdown: [0, false] }, { ...series, drawdown: [0, { low: -0.3, high: -0.2 }] },
  ])('rejects malformed or unavailable evidence %j', input => {
    expect(backtestResult(input)).toBeNull()
  })
})


describe('backtest-only scope and readable UTC time', () => {
  it('leaves unrelated run families alone, including their legacy summaries', () => {
    expect(isBacktestRun(detail)).toBe(true)
    expect(isBacktestRun({ ...detail, manifest: {} })).toBe(true)
    expect(isBacktestRun({ ...detail, manifest: { command: 'backtest_unsupported' } })).toBe(true)
    for (const command of ['forecast', 'validate', 'research_daily_rule_native_v1']) {
      expect(isBacktestRun({ ...detail, manifest: { command } })).toBe(false)
    }
    expect(isBacktestRun({ ...detail, kind: 'forecast', manifest: {} })).toBe(false)
    expect(isBacktestRun({ ...detail, manifest: { verdict: {} } })).toBe(false)
  })
  it('displays the containing UTC second and preserves exact raw fractional seconds', () => {
    const result = backtestResult({ ...series, ts: [-1, 60.123456] })
    expect(result?.timestampUtc).toBe('1970-01-01 00:01:00 UTC')
    expect(result?.timestampUnixSeconds).toBe('60.123456')
    expect(backtestResult({ ts: [-0.1], equity: [1], drawdown: [0] })?.timestampUtc).toBe('1969-12-31 23:59:59 UTC')
    expect(backtestResult({ ts: [0], equity: [1], drawdown: [0] })?.drawdown).toBe('0')
  })
  it('bounds the supported UTC display range before constructing dates', () => {
    for (const timestamp of [-62167219201, 253402300800, Number.MAX_VALUE]) {
      expect(backtestResult({ ts: [timestamp], equity: [1], drawdown: [0] })).toBeNull()
    }
    expect(backtestResult({ ts: [-62167219200], equity: [1], drawdown: [0] })?.timestampUtc).toBe('0000-01-01 00:00:00 UTC')
    expect(backtestResult({ ts: [253402300799], equity: [1], drawdown: [0] })?.timestampUtc).toBe('9999-12-31 23:59:59 UTC')
  })
})

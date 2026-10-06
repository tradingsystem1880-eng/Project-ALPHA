import { describe, expect, it } from 'vitest'
import { DEFAULT_LINKED } from '../context/linked'
import { contextKey, evaluationUnavailable, scanChartContext } from './edgeWorkspace'

describe('edge workspace identity', () => {
  it('binds context to dataset, run and cutoff rather than ticker alone', () => {
    const context = { ...DEFAULT_LINKED, symbol: 'BTC/USDT' }
    expect(contextKey(context, null)).not.toBe(contextKey({ ...context, end: '2025-01-01' }, null))
    expect(contextKey(context, null)).not.toBe(contextKey({ ...context, snapshotId: 'frozen' }, null))
    expect(evaluationUnavailable(context, null)).toBeNull()
    expect(evaluationUnavailable({ ...context, snapshotId: 'frozen' }, null)).toContain('snapshot')
    expect(evaluationUnavailable({ ...context, runId: 'run' }, null)).toContain('run')
  })
  it('opens a scanned bar without retaining an unrelated run or snapshot', () => {
    expect(scanChartContext('BTC/USDT', '2025-01-03')).toEqual({ symbol: 'BTC/USDT', start: null, end: '2025-01-03', snapshotId: null, runId: null })
  })
})

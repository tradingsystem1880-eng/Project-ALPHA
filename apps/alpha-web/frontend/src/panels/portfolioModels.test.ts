import { describe, expect, it } from 'vitest'

import { buildCorrelationMatrix, latestAllocationRows } from './portfolioModels'

describe('portfolio artifact models', () => {
  it('builds a canonical dense correlation matrix without recomputing coefficients', () => {
    const rows = [
      { asset_a: 'SPY', asset_b: 'QQQ', correlation: 0.42 },
      { asset_a: 'QQQ', asset_b: 'SPY', correlation: 0.42 },
      { asset_a: 'SPY', asset_b: 'SPY', correlation: 1 },
      { asset_a: 'QQQ', asset_b: 'QQQ', correlation: 1 },
    ]
    const matrix = buildCorrelationMatrix(rows)
    expect(matrix.symbols).toEqual(['QQQ', 'SPY'])
    expect(matrix.values).toEqual([
      [1, 0.42],
      [0.42, 1],
    ])
  })

  it('selects only the latest immutable allocation timestamp in symbol order', () => {
    const rows = [
      { ts: 10, symbol: 'SPY', weight: 0.5 },
      { ts: 20, symbol: 'SPY', weight: 0.6 },
      { ts: 10, symbol: 'QQQ', weight: 0.5 },
      { ts: 20, symbol: 'QQQ', weight: 0.4 },
    ]
    expect(latestAllocationRows(rows)).toEqual([
      { ts: 20, symbol: 'QQQ', weight: 0.4 },
      { ts: 20, symbol: 'SPY', weight: 0.6 },
    ])
  })
})

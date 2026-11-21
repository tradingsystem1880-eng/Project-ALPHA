import { describe, expect, it } from 'vitest'

import { compareColumn, compareNotice, uniqueComparisonMaximum } from './compareRunsModel'
import { metricLabel } from '../explain/glossary'

describe('comparison winner semantics', () => {
  it('returns no winner for ties, missing metrics, or a single comparable run', () => {
    expect(uniqueComparisonMaximum([0, 0])).toBeNull()
    expect(uniqueComparisonMaximum([null, null])).toBeNull()
    expect(uniqueComparisonMaximum([0.2, null])).toBeNull()
  })

  it('returns the unique maximum only when two or more runs are comparable', () => {
    expect(uniqueComparisonMaximum([0.1, 0.3, 0.2])).toBe(0.3)
  })
})

const row = (symbol: string | null, command: string | null = 'validate') => ({ symbol, symbols: null, command })

describe('compare column headers', () => {
  it('reads short id, plain kind and asset', () => {
    expect(compareColumn('ae4ae2baf933749f', row('SPY'), { rule_test_labels: ['rule'], kind: 'validate' })).toEqual({
      id: 'ae4ae2baf9', kind: 'rule test', asset: 'SPY',
    })
    expect(compareColumn('76a0df75eb12', row('QQQ'), undefined)).toEqual({ id: '76a0df75eb', kind: 'validate', asset: 'QQQ' })
    expect(compareColumn('aaaa', { symbol: null, symbols: ['SPY', 'QQQ'], command: 'backtest run' }, undefined).kind).toBe('backtest run')
  })
})

describe('metric names', () => {
  it('uses the glossary name, else plain words for snake_case', () => {
    expect(metricLabel('annualized_vol')).toBe('Annualized volatility')
    expect(metricLabel('risk_of_ruin')).toBe('Risk of ruin')
    expect(metricLabel('sortino_ratio')).toBe('Sortino ratio')
  })
})

describe('compare notice', () => {
  it('says different assets for two assets, the snapshot note for one asset', () => {
    expect(compareNotice([row('SPY'), row('QQQ')], false)).toBe('different assets')
    expect(compareNotice([row('SPY'), row('SPY')], false)).toBe('different snapshots')
    expect(compareNotice([row('SPY'), row('SPY')], true)).toBeNull()
    expect(compareNotice([row('SPY'), row('QQQ')], true)).toBe('different assets')
  })
})

import { describe, expect, it } from 'vitest'

import type { ScanAlert, ScanRow } from '../api/types'
import {
  alertTransition,
  formatValue,
  newestFirst,
  orderRows,
  parseUniverse,
  signalLabel,
  signalTone,
  universeText,
  valueColumns,
} from './scannerModel'

const row = (symbol: string, signal: number, values: Record<string, number> = {}): ScanRow => ({
  symbol,
  signal,
  bar_ts: 1,
  bar_date: '2026-06-30',
  close: 1,
  values,
})

describe('scanner model', () => {
  it('labels signals and their tone', () => {
    expect([signalLabel(1), signalLabel(-1), signalLabel(0)]).toEqual(['LONG', 'SHORT', 'flat'])
    expect([signalTone(1), signalTone(-1), signalTone(0)]).toEqual(['up', 'down', 'flat'])
  })
  it('describes the universe honestly', () => {
    expect(universeText({ universe: { kind: 'stored', symbols: null } })).toBe('every stored symbol')
    expect(universeText({ universe: { kind: 'list', symbols: ['A', 'B'] } })).toBe('A, B')
    expect(universeText({ universe: { kind: 'list', symbols: ['A', 'B', 'C', 'D', 'E', 'F'] } })).toBe('A, B, C, D +2')
    expect(universeText({ universe: null })).toBe('—')
  })
  it('puts matches first and keeps value columns stable', () => {
    const rows = [row('C', 0, { 'sma:5': 1 }), row('B', -1, { 'sma:20': 2 }), row('A', 0), row('D', 1, { 'sma:5': 3 })]
    expect(orderRows(rows).map((item) => item.symbol)).toEqual(['B', 'D', 'A', 'C'])
    expect(valueColumns(rows)).toEqual(['sma:5', 'sma:20'])
    expect(formatValue(1234.56789012)).toBe('1,234.57')
    expect(formatValue(undefined)).toBe('—')
    expect(formatValue(Number.NaN)).toBe('—')
  })
  it('renders alert transitions newest first', () => {
    const alerts: ScanAlert[] = [
      { ts: 't1', scan: 's', symbol: 'A', previous: null, signal: 1, bar_date: 'd', close: 1 },
      { ts: 't2', scan: 's', symbol: 'B', previous: 1, signal: -1, bar_date: 'd', close: 1 },
    ]
    expect(alertTransition(alerts[0])).toBe('→ LONG')
    expect(alertTransition(alerts[1])).toBe('LONG → SHORT')
    expect(newestFirst(alerts).map((item) => item.symbol)).toEqual(['B', 'A'])
  })
  it('parses a universe field', () => {
    expect(parseUniverse('')).toBeNull()
    expect(parseUniverse(' BTC/USDT, ETH/USDT  SOL/USDT ')).toEqual(['BTC/USDT', 'ETH/USDT', 'SOL/USDT'])
  })
})

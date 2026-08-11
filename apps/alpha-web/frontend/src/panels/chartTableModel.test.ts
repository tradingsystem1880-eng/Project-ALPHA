import { describe, expect, it } from 'vitest'

import type { Candle, ChartTraceEvent } from '../api/types'
import { candlesCsv, chartTablePage, chartTracePage } from './chartTableModel'

const bars = Array.from({ length: 205 }, (_, index): Candle => ({
  t: 1_767_225_600 + index * 86_400,
  o: 100 + index,
  h: 102 + index,
  l: 99 + index,
  c: 101 + index,
  v: 1_000 + index,
}))

describe('price-chart data alternatives', () => {
  it('paginates without silently dropping the tail', () => {
    expect(chartTablePage(bars, 0)).toMatchObject({ page: 0, pages: 3, start: 1, end: 100, total: 205 })
    expect(chartTablePage(bars, 2)).toMatchObject({ start: 201, end: 205 })
    expect(chartTablePage(bars, 99)).toMatchObject({ page: 2, pages: 3 })
    expect(chartTablePage(bars, Number.NaN)).toMatchObject({ page: 0, start: 1 })
  })

  it('paginates the complete returned trace beyond the first 80 events', () => {
    const trace = Array.from(
      { length: 161 },
      (_, index) => ({ sequence_id: index + 1 }) as ChartTraceEvent,
    )

    expect(chartTracePage(trace, 0)).toMatchObject({ start: 1, end: 80, total: 161, pages: 3 })
    expect(chartTracePage(trace, 1).rows[0]?.sequence_id).toBe(81)
    expect(chartTracePage(trace, 2)).toMatchObject({ start: 161, end: 161 })
  })

  it('exports exact UTC OHLCV rows', () => {
    const csv = candlesCsv(bars.slice(0, 1))
    expect(csv).toContain('timestamp_utc,open,high,low,close,volume')
    expect(csv).toContain('2026-01-01T00:00:00.000Z,100,102,99,101,1000')
  })
})

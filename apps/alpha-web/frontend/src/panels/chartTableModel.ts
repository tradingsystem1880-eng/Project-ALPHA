import type { Candle, ChartTraceEvent } from '../api/types'

export const CHART_TABLE_PAGE_SIZE = 100
export const CHART_TRACE_PAGE_SIZE = 80

interface BoundedPage<T> {
  rows: T[]
  page: number
  pages: number
  start: number
  end: number
  total: number
}

function boundedPage<T>(values: T[], page: number, pageSize: number): BoundedPage<T> {
  const pages = Math.max(1, Math.ceil(values.length / pageSize))
  const requested = Number.isFinite(page) ? Math.trunc(page) : 0
  const bounded = Math.max(0, Math.min(requested, pages - 1))
  const offset = bounded * pageSize
  const rows = values.slice(offset, offset + pageSize)
  return {
    rows,
    page: bounded,
    pages,
    start: rows.length === 0 ? 0 : offset + 1,
    end: offset + rows.length,
    total: values.length,
  }
}

export function chartTablePage(bars: Candle[], page: number): BoundedPage<Candle> {
  return boundedPage(bars, page, CHART_TABLE_PAGE_SIZE)
}

export function chartTracePage(
  trace: ChartTraceEvent[],
  page: number,
): BoundedPage<ChartTraceEvent> {
  return boundedPage(trace, page, CHART_TRACE_PAGE_SIZE)
}

export function candlesCsv(bars: Candle[]): string {
  const rows = bars.map((bar) =>
    [new Date(bar.t * 1_000).toISOString(), bar.o, bar.h, bar.l, bar.c, bar.v].join(','),
  )
  return ['timestamp_utc,open,high,low,close,volume', ...rows].join('\n') + '\n'
}

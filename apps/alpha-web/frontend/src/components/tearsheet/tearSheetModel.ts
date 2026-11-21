import type { RunSeries } from '../../api/types'

/** Pure model of the tear-sheet stack: stored values re-shaped for drawing; no statistic is computed. */

export interface XY { x: number[]; y: number[] }
export interface Span { from: number; to: number }
export interface Band extends Span { kind: 'tradable' | 'scored' | 'fold'; label: string }
export interface Stack {
  price: { x: number[]; close: number[] } | null
  equity: XY
  benchmark: XY | null
  drawdown: XY
  entries: XY
  exits: XY
  held: Span[]
  bands: Band[]
  logScale: boolean
}
export interface Readout {
  date: string
  close: number | null
  equity: number | null
  benchmark: number | null
  drawdown: number | null
  inMarket: boolean
}
type Trade = RunSeries['trades'][number]

const ms = (seconds: number) => seconds * 1000

/** True from the entry day up to, not including, the exit day. */
export function inMarket(trades: readonly Trade[], t: number): boolean {
  return trades.some(trade => trade.entry_ts <= t && t < trade.exit_ts)
}

export function heldSpans(trades: readonly Trade[]): Span[] {
  return trades.map(trade => ({ from: ms(trade.entry_ts), to: ms(trade.exit_ts) }))
}

/** Index of the sample nearest to `t` in a sorted array; -1 when empty. */
function nearest(times: readonly number[], t: number): number {
  if (!times.length) return -1
  let lo = 0, hi = times.length - 1
  while (lo < hi) { const mid = (lo + hi) >>> 1; if (times[mid] < t) lo = mid + 1; else hi = mid }
  return lo > 0 && t - times[lo - 1] <= times[lo] - t ? lo - 1 : lo
}

/** The stored values of the sample nearest to `t` (seconds). */
export function readoutAt(series: RunSeries, t: number): Readout {
  const at = nearest(series.ts, t)
  const price = series.price
  const p = price && price.status === 'available' ? nearest(price.ts, t) : -1
  // A price bar counts only when it falls on the same day as the equity sample.
  const sameDay = p >= 0 && at >= 0 && Math.abs((price?.ts[p] ?? 0) - series.ts[at]) < 86400
  return {
    date: at >= 0 ? new Date(ms(series.ts[at])).toISOString().slice(0, 10) : '—',
    close: sameDay && price ? price.close[p] : null,
    equity: at >= 0 ? series.equity[at] : null,
    benchmark: at >= 0 ? series.benchmark?.[at] ?? null : null,
    drawdown: at >= 0 ? series.drawdown[at] : null,
    inMarket: at >= 0 && inMarket(series.trades, series.ts[at]),
  }
}

export function bandSpans(bands: RunSeries['bands']): Band[] {
  const out: Band[] = []
  const add = (kind: Band['kind'], label: string, first: string, last: string) => {
    const from = Date.parse(first), to = Date.parse(last)
    if (Number.isFinite(from) && Number.isFinite(to) && from < to) out.push({ kind, label, from, to })
  }
  if (bands.tradable) add('tradable', 'Period the rule could trade', bands.tradable.first_ts, bands.tradable.last_ts)
  if (bands.scored) add('scored', 'Scored test period', bands.scored.first_ts, bands.scored.last_ts)
  for (const fold of bands.folds) add('fold', `Walk-forward test ${fold.index + 1}`, fold.start_ts, fold.end_ts)
  return out
}

export function buildStack(series: RunSeries, log: boolean): Stack {
  const x = series.ts.map(ms)
  const benchmark: XY = { x: [], y: [] }
  series.benchmark?.forEach((value, i) => { if (value !== null) { benchmark.x.push(x[i]); benchmark.y.push(value) } })
  const price = series.price && series.price.status === 'available' && series.price.ts.length
    ? { x: series.price.ts.map(ms), close: [...series.price.close] } : null
  const positive = series.equity.every(v => v > 0) && benchmark.y.every(v => v > 0)
  return {
    price,
    equity: { x, y: [...series.equity] },
    benchmark: series.benchmark && benchmark.x.length ? benchmark : null,
    drawdown: { x, y: [...series.drawdown] },
    entries: { x: series.trades.map(t => ms(t.entry_ts)), y: series.trades.map(t => t.entry_price) },
    exits: { x: series.trades.map(t => ms(t.exit_ts)), y: series.trades.map(t => t.exit_price) },
    held: heldSpans(series.trades),
    bands: bandSpans(series.bands),
    logScale: log && positive,
  }
}

export function priceReason(status: string): string | null {
  switch (status) {
    case 'available': return null
    case 'bars_changed_since_run': return 'The stored prices have changed since this run, so they are not drawn. Run the test again to draw them.'
    case 'price_not_saved_with_run': return 'This run did not record which prices it used, so the price pane is not drawn.'
    case 'price_unavailable': return 'The stored prices could not be read, so the price pane is not drawn.'
    default: return 'Prices were not saved with this run, so the price pane is not drawn.'
  }
}

const ISO_DAY = (seconds: number) => new Date(ms(seconds)).toISOString().slice(0, 10)

/** One sentence per fact the panes show; the same words serve the aria-label. */
export function ariaSummary(series: RunSeries): string {
  const n = series.ts.length
  const parts = [`Equity and drawdown chart, ${n} days${n ? ` from ${ISO_DAY(series.ts[0])} to ${ISO_DAY(series.ts[n - 1])}` : ''}`]
  const trades = series.bounds.trades.original
  parts.push(`${trades} trade${trades === 1 ? '' : 's'}`)
  if (series.drawdown.length) parts.push(`deepest drawdown shown ${(Math.min(...series.drawdown) * 100).toFixed(1)}%`)
  parts.push(series.benchmark ? 'with buy and hold for comparison' : 'no buy and hold series')
  const folds = series.bands.folds.length
  if (folds) parts.push(`${folds} walk-forward test period${folds === 1 ? '' : 's'} shaded`)
  const reason = priceReason(series.price?.status ?? 'none')
  parts.push(reason === null ? 'price pane with entry and exit markers' : 'price pane not shown')
  return `${parts.join('; ')}.`
}

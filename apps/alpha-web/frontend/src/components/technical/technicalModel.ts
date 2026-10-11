// Pure display model for the technical chart: observation-indexed coordinates, calendar date
// ticks, gap marks, candle/volume classification, visible extents and number formatting.
// Display coordinates only — no estimation, no resampling, no study arithmetic.

import type { Candle, OverlaySeries } from '../../api/types'

const DAY = 86400
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export type TickKind = 'minor' | 'month' | 'year'
export interface DateTick { index: number; label: string; kind: TickKind }

const utc = (t: number) => new Date(t * 1000)
const two = (n: number) => String(n).padStart(2, '0')
const dayLabel = (t: number) => String(utc(t).getUTCDate())
const hourLabel = (t: number) => { const d = utc(t); return `${two(d.getUTCHours())}:${two(d.getUTCMinutes())}` }
const monthLabel = (t: number) => MONTHS[utc(t).getUTCMonth()]
const yearLabel = (t: number) => String(utc(t).getUTCFullYear())

/** Integer calendar keys per observation, computed once per series so tick selection never allocates. */
export interface CalendarKeys { day: Int32Array; week: Int32Array; month: Int32Array; year: Int32Array }
export function calendarKeys(times: readonly number[]): CalendarKeys {
  const n = times.length
  const keys = { day: new Int32Array(n), week: new Int32Array(n), month: new Int32Array(n), year: new Int32Array(n) }
  for (let i = 0; i < n; i++) {
    const day = Math.floor(times[i] / DAY), d = utc(times[i])
    keys.day[i] = day
    keys.week[i] = Math.floor((day + 3) / 7) // Monday-based; the epoch (1970-01-01) was a Thursday
    keys.year[i] = d.getUTCFullYear()
    keys.month[i] = keys.year[i] * 12 + d.getUTCMonth()
  }
  return keys
}

interface Level { order: number; differs: (i: number) => boolean; label: (t: number) => string }
const MONTH_ORDER = 7, DAY_ORDER = 5

function levels(times: readonly number[], k: CalendarKeys, intraday: boolean): Level[] {
  const hour = (hours: number, order: number): Level => ({ order, label: hourLabel, differs: i => Math.floor(times[i] / (3600 * hours)) !== Math.floor(times[i - 1] / (3600 * hours)) })
  const calendar: Level[] = [
    { order: DAY_ORDER, label: dayLabel, differs: i => k.day[i] !== k.day[i - 1] },
    { order: 6, label: dayLabel, differs: i => k.week[i] !== k.week[i - 1] },
    { order: MONTH_ORDER, label: monthLabel, differs: i => k.month[i] !== k.month[i - 1] },
    { order: 8, label: monthLabel, differs: i => Math.floor(k.month[i] / 3) !== Math.floor(k.month[i - 1] / 3) },
    { order: 9, label: yearLabel, differs: i => k.year[i] !== k.year[i - 1] },
  ]
  return intraday ? [hour(1, 0), hour(2, 1), hour(4, 2), hour(6, 3), hour(12, 4), ...calendar] : calendar
}

export function medianSpacing(times: readonly number[]): number {
  if (times.length < 2) return DAY
  const step = Math.max(1, Math.floor((times.length - 1) / 2000))
  const diffs: number[] = []
  for (let i = 1; i < times.length; i += step) diffs.push(times[i] - times[i - 1])
  diffs.sort((a, b) => a - b)
  return diffs[diffs.length >> 1]
}

/**
 * Calendar ticks for the visible observation window [i0, i1]: the finest level whose ticks stay at
 * least `minPx` apart, plus bold month and year boundaries when the level is finer than a month.
 * A tick sits on the first observation after a boundary (StockCharts places "Nov" on the first bar).
 */
export function dateTicks(times: readonly number[], i0: number, i1: number, widthPx: number, keys: CalendarKeys = calendarKeys(times), intraday = medianSpacing(times) < DAY, minPx = 26): DateTick[] {
  const lo = Math.max(1, Math.ceil(i0)), hi = Math.min(times.length - 1, Math.floor(i1))
  if (hi < lo || widthPx <= 0) return []
  const candidates = levels(times, keys, intraday)
  const span = Math.max(1, i1 - i0)
  let chosen = candidates[candidates.length - 1]
  for (const level of candidates) {
    let count = 0
    for (let i = lo; i <= hi; i++) if (level.differs(i)) count++
    if (count && (widthPx * (hi - lo + 1) / span) / count >= minPx) { chosen = level; break }
  }
  const year = candidates[candidates.length - 1], month = candidates[candidates.length - 3], day = candidates[candidates.length - 5]
  const ticks: DateTick[] = []
  for (let i = lo; i <= hi; i++) {
    const t = times[i]
    if (year.differs(i)) ticks.push({ index: i, label: yearLabel(t), kind: 'year' })
    else if (chosen.order < MONTH_ORDER && month.differs(i)) ticks.push({ index: i, label: monthLabel(t), kind: 'month' })
    else if (chosen.differs(i)) ticks.push({ index: i, label: chosen.label(t), kind: 'minor' })
    else if (chosen.order < DAY_ORDER && day.differs(i)) ticks.push({ index: i, label: dayLabel(t), kind: 'minor' })
  }
  return ticks
}

export type GapCalendar = 'continuous' | 'weekday'
export interface ObservationGap { index: number; missing: number }

/**
 * The series' own calendar: any Saturday/Sunday observation means a 24/7 venue (`continuous`),
 * otherwise weekdays only. Read from the data, never from a settings profile.
 */
export function inferCalendar(times: readonly number[]): GapCalendar {
  return times.some(t => { const weekday = (Math.floor(t / DAY) + 4) % 7; return weekday === 0 || weekday === 6 }) ? 'continuous' : 'weekday'
}

/**
 * Where the gapless axis hides missing observations. `continuous` (24/7 venues) flags spacing above
 * 1.5× the median; `weekday` (daily equities) flags weekdays without a bar. Intraday weekday series
 * are not judged (sessions are not known here).
 */
export function observationGaps(times: readonly number[], calendar: GapCalendar): ObservationGap[] {
  if (times.length < 2) return []
  const interval = medianSpacing(times)
  const out: ObservationGap[] = []
  if (calendar === 'continuous') {
    for (let i = 1; i < times.length; i++) {
      const diff = times[i] - times[i - 1]
      if (diff > interval * 1.5) out.push({ index: i, missing: Math.round(diff / interval) - 1 })
    }
    return out
  }
  if (interval < DAY * 0.9) return []
  for (let i = 1; i < times.length; i++) {
    const a = Math.floor(times[i - 1] / DAY), b = Math.floor(times[i] / DAY)
    let missing = 0
    for (let d = a + 1; d < b; d++) { const weekday = (d + 4) % 7; if (weekday !== 0 && weekday !== 6) missing++ }
    if (missing) out.push({ index: i, missing })
  }
  return out
}

/** StockCharts candle rule: colour from close vs prior close, hollow when close > open. */
export function candleClasses(bars: readonly Candle[]): { up: boolean[]; hollow: boolean[] } {
  const up: boolean[] = new Array(bars.length), hollow: boolean[] = new Array(bars.length)
  for (let i = 0; i < bars.length; i++) {
    const reference = i ? bars[i - 1].c : bars[i].o
    up[i] = bars[i].c >= reference
    hollow[i] = bars[i].c > bars[i].o
  }
  return { up, hollow }
}

/** Min/max of finite values in the clamped index window, or null when there are none. */
export function visibleExtent(columns: readonly (readonly (number | null)[])[], i0: number, i1: number): [number, number] | null {
  let min = Infinity, max = -Infinity
  for (const values of columns) {
    const lo = Math.max(0, Math.floor(i0)), hi = Math.min(values.length - 1, Math.ceil(i1))
    for (let i = lo; i <= hi; i++) { const v = values[i]; if (v !== null && Number.isFinite(v)) { if (v < min) min = v; if (v > max) max = v } }
  }
  return Number.isFinite(min) ? [min, max] : null
}

export function padExtent([min, max]: [number, number], fraction: number): [number, number] {
  const pad = (max - min || Math.abs(max) || 1) * fraction
  return [min - pad, max + pad]
}

/**
 * Decimals shown for prices: what the recorded values carry at seven significant digits, 2–12.
 * Read from the exponential form so sub-1e-6 quotes (printed as `1.2e-7`) keep their digits.
 */
export function priceDecimals(values: readonly number[]): number {
  let decimals = 2
  for (let i = Math.max(0, values.length - 500); i < values.length; i++) {
    const v = values[i]
    if (!Number.isFinite(v) || v === 0) continue
    const [mantissa, exponent] = Number(v.toPrecision(7)).toExponential().split('e')
    const digits = mantissa.includes('.') ? mantissa.length - mantissa.indexOf('.') - 1 : 0
    decimals = Math.max(decimals, digits - Number(exponent))
  }
  return Math.min(12, decimals)
}

export function compactVolume(v: number): string {
  const abs = Math.abs(v)
  for (const [size, suffix] of [[1e12, 'T'], [1e9, 'B'], [1e6, 'M'], [1e3, 'K']] as const) {
    if (abs >= size) return `${Number((v / size).toPrecision(3))}${suffix}`
  }
  return String(Number(v.toPrecision(3)))
}

export function groupedInteger(v: number): string {
  return Math.round(v).toLocaleString('en-US')
}

const SUFFIXES = [':line', ':signal', ':hist', ':upper', ':middle', ':lower', ':price', ':inverse']
/** The CLI indicator spec a series belongs to (`macd:12:26:9:hist` → `macd:12:26:9`). */
export function studySpec(seriesId: string): string {
  for (const suffix of SUFFIXES) if (seriesId.endsWith(suffix)) return seriesId.slice(0, -suffix.length)
  return seriesId
}

const SHORT: Readonly<Record<string, string>> = { sma: 'MA', ema: 'EMA', rsi: 'RSI', macd: 'MACD', bbands: 'BB', atr: 'ATR' }
/** StockCharts-style study label: `sma:50` → `MA(50)`, `macd:12:26:9` → `MACD(12,26,9)`. */
export function studyLabel(spec: string): string {
  const [head, ...params] = spec.split(':')
  const name = SHORT[head] ?? head.toUpperCase()
  return params.length ? `${name}(${params.join(',')})` : name
}

export interface StudyPanel { pane: string; series: OverlaySeries[] }
/** RSI panes sit above price (StockCharts Classic); every other non-price pane below, in order. */
export function panelLayout(indicators: readonly OverlaySeries[]): { price: OverlaySeries[]; above: StudyPanel[]; below: StudyPanel[] } {
  const price = indicators.filter(s => s.pane === 'price')
  const panes = Array.from(new Set(indicators.map(s => s.pane).filter(p => p !== 'price')))
    .map(pane => ({ pane, series: indicators.filter(s => s.pane === pane) }))
  return { price, above: panes.filter(p => p.pane === 'rsi'), below: panes.filter(p => p.pane !== 'rsi') }
}

/** Panel heights at StockCharts' study : price ratio of 1 : 2.9; price never drops below 45%. */
export function panelHeights(totalPx: number, studies: number): { price: number; study: number } {
  if (!studies) return { price: totalPx, study: 0 }
  let study = Math.round(totalPx / (2.9 + studies))
  if (totalPx - study * studies < totalPx * 0.45) study = Math.floor(totalPx * 0.55 / studies)
  return { price: totalPx - study * studies, study }
}

export interface HeaderValues { bar: Candle; change: number | null; changePct: number | null }
/** The bar at `index` and its change from the prior recorded close (display arithmetic only). */
export function headerValues(bars: readonly Candle[], index: number): HeaderValues | null {
  const bar = bars[index]
  if (!bar) return null
  const prev = bars[index - 1]
  if (!prev) return { bar, change: null, changePct: null }
  return { bar, change: bar.c - prev.c, changePct: prev.c ? (bar.c / prev.c - 1) * 100 : null }
}

export function barDate(t: number, intraday: boolean): string {
  const iso = new Date(t * 1000).toISOString()
  return intraday ? `${iso.slice(0, 10)} ${iso.slice(11, 16)}` : iso.slice(0, 10)
}

export function signed(v: number, decimals: number): string {
  return `${v > 0 ? '+' : ''}${v.toFixed(decimals)}`
}

/** Fractional observation index of a UTC time (linear between bars), or null outside coverage. */
export function fractionalIndex(times: readonly number[], t: number): number | null {
  if (!times.length || t < times[0] || t > times[times.length - 1]) return null
  let lo = 0, hi = times.length - 1
  while (lo < hi) { const mid = (lo + hi) >>> 1; if (times[mid] < t) lo = mid + 1; else hi = mid }
  if (times[lo] === t || lo === 0) return lo
  return lo - 1 + (t - times[lo - 1]) / (times[lo] - times[lo - 1])
}

/** StockCharts-style value ticks: steps of 1, 2, 2.5 or 5 × 10^k, about `count` of them. */
export function niceTicks(min: number, max: number, count: number): { ticks: number[]; decimals: number } {
  if (!(max > min) || count < 1) return { ticks: [], decimals: 0 }
  const raw = (max - min) / count, power = Math.pow(10, Math.floor(Math.log10(raw)))
  const step = ([1, 2, 2.5, 5, 10].map(m => m * power).find(s => s >= raw) ?? 10 * power)
  const decimals = Math.max(0, Math.ceil(-Math.log10(step) - 1e-9) + (Math.abs(step / power - 2.5) < 1e-9 ? 1 : 0))
  const ticks: number[] = []
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) ticks.push(Number(v.toFixed(Math.min(20, decimals + 2))))
  return { ticks, decimals }
}


/** Exact native-index mask for width-0.8 volume bars, including intersecting edge bars. */
export function visibleVolumeIndices(count: number, from: number, to: number): number[] {
  if (!Number.isSafeInteger(count) || count < 0 || !Number.isFinite(from) || !Number.isFinite(to) || from > to) {
    throw new RangeError('Volume viewport requires a nonnegative observation count and finite ordered bounds')
  }
  const first = Math.max(0, Math.ceil(from - .4))
  const last = Math.min(count - 1, Math.floor(to + .4))
  return Array.from({ length: Math.max(0, last - first + 1) }, (_, i) => first + i)
}

/** Complementary native-index views allow scalar volume colors without parsing full columns. */
export function visibleVolumeClasses(up: readonly boolean[], from: number, to: number): { up: number[]; down: number[] } {
  const groups: { up: number[]; down: number[] } = { up: [], down: [] }
  for (const i of visibleVolumeIndices(up.length, from, to)) (up[i] ? groups.up : groups.down).push(i)
  return groups
}

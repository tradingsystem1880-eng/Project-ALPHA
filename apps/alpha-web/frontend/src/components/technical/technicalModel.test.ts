import { describe, expect, it } from 'vitest'
import { sprintf } from 'sprintf-js'
import type { Candle, OverlaySeries } from '../../api/types'
import {
  candleClasses, compactVolume, dateTicks, fractionalIndex, niceTicks, headerValues, inferCalendar, observationGaps, panelHeights, panelLayout,
  priceDecimals, studyLabel, studySpec, visibleExtent, visibleVolumeIndices, visibleVolumeClasses, padExtent, chartExtent, tickFormat, displayNumber, signed,
  displayMacdValue,
} from './technicalModel'
import { CLASSIC, DEFAULT_STYLE, studyColors } from './technicalTokens'

const DAY = 86400
// Execute the installed formatter dependency used by Bokeh, not a copied formatting algorithm.

describe('extreme finite display ranges', () => {
  it.each([
    [1e-200, 2e-200], [-2e-200, -1e-200], [-1e-200, 1e-200],
    [1e200, 2e200], [-2e200, -1e200], [-1e200, 1e200],
    [1e16, 1e16 + 2], [1, 1 + Number.EPSILON],
    [Number.MIN_VALUE, Number.MIN_VALUE * 2], [0, Number.MIN_VALUE],
    [-Number.MAX_VALUE, Number.MAX_VALUE],
  ])('keeps finite distinct readable ticks for [%s, %s]', (min, max) => {
    const result = niceTicks(min, max, 5)
    expect(result.ticks.length).toBeGreaterThan(1)
    expect(result.ticks.length).toBeLessThanOrEqual(7)
    expect(result.ticks.every(Number.isFinite)).toBe(true)
    expect(new Set(result.ticks).size).toBe(result.ticks.length)
    expect(result.ticks.every((v, i) => i === 0 || v > result.ticks[i - 1])).toBe(true)
    const format = tickFormat(result)
    expect(format).toMatch(/^%.(?:[0-9]|1[0-6])[fe]$/)
    const labels = result.ticks.map(v => sprintf(format, v))
    expect(new Set(labels).size).toBe(labels.length)
    if (min > 0) expect(result.ticks.every(v => v > 0)).toBe(true)
    if (max < 0) expect(result.ticks.every(v => v < 0)).toBe(true)
    for (let i = 0; i < labels.length; i++) if (result.ticks[i] !== 0) expect(labels[i]).not.toMatch(/^-?0(?:\.0+)?(?:e[+-]?\d+)?$/)
  })
  it('keeps zero/flat and ordinary financial formatting contracts', () => {
    expect(niceTicks(0, 0, 5)).toEqual({ ticks: [], decimals: 0 })
    expect(padExtent([0, 0], .03)).toEqual([-.03, .03])
    expect(tickFormat(niceTicks(0, 100, 5))).toBe('%.0f')
    expect(tickFormat(niceTicks(.51, .529, 4))).toBe('%.3f')
    expect(displayNumber(62.03, 2)).toBe('62.03')
    expect(displayNumber(.0005, 3)).toBe('0.001')
    expect(signed(-.5, 2)).toBe('-0.50')
    expect(displayNumber(-0, 2)).toBe('0.00')
  })
  it('keeps actual formatter labels distinct across decimal scales and signed ranges', () => {
    for (const exponent of [-323, -300, -200, -30, -13, -12, -7, 0, 12, 200, 300, 308]) {
      const unit = 10 ** exponent
      for (const [min, max] of [[unit, unit * 1.5], [-unit * 1.5, -unit], [-unit, unit]]) {
        for (const count of [3, 5, 17]) {
          const result = niceTicks(min, max, count)
          const labels = result.ticks.map(t => sprintf(tickFormat(result), t))
          expect(new Set(labels).size).toBe(labels.length)
          expect(result.ticks.every(Number.isFinite)).toBe(true)
        }
      }
    }
  })
  it('preserves scientific label values without false zeros or lost adjacent values', () => {
    for (const v of [1e-200, -1e-200, 1e200, Number.MIN_VALUE, 1e16, 1e16 + 2]) {
      expect(Number(displayNumber(v, 2))).toBe(v)
    }
    expect(signed(1e-200, 2)).toBe('+1e-200')
    expect(displayNumber(NaN, 2)).toBe('—')
    expect(signed(Infinity, 2)).toBe('—')
  })
  it('suppresses only MACD residuals below one source-price ULP', () => {
    expect(displayMacdValue(-1.7763568394002505e-15, 160)).toBe(0)
    const spacingAt160 = 2 ** -45
    expect(displayMacdValue(spacingAt160, 160)).toBe(spacingAt160)
    expect(displayMacdValue(2.8e-14, 160)).toBe(0)
    expect(displayMacdValue(3e-14, 160)).toBe(3e-14)
    expect(displayMacdValue(5e-14, 160)).toBe(5e-14)
    expect(displayMacdValue(1e-200, 2e-200)).toBe(1e-200)
    expect(displayMacdValue(Number.MIN_VALUE, Number.MIN_VALUE)).toBe(Number.MIN_VALUE)
    expect(displayMacdValue(Number.EPSILON, 1)).toBe(Number.EPSILON)
    expect(displayMacdValue(0, 160)).toBe(0)
    expect(() => displayMacdValue(NaN, 160)).toThrow(RangeError)
    expect(() => displayMacdValue(1, Infinity)).toThrow(RangeError)
    expect(() => displayMacdValue(1, -1)).toThrow(RangeError)
  })
  it('pads subnormal/large finite values without inventing zero width or infinity', () => {
    for (const extent of [[Number.MIN_VALUE, Number.MIN_VALUE], [Number.MAX_VALUE, Number.MAX_VALUE]] as [number, number][]) {
      const [lo, hi] = padExtent(extent, .03)
      expect(Number.isFinite(lo) && Number.isFinite(hi)).toBe(true)
      expect(lo).toBeLessThan(hi)
      expect(lo).toBeLessThanOrEqual(extent[0]); expect(hi).toBeGreaterThanOrEqual(extent[1])
    }
    // Finite endpoints with an overflowing span cannot be faithfully scaled by Bokeh.
    expect(() => padExtent([-Number.MAX_VALUE, Number.MAX_VALUE], .03)).toThrow(RangeError)
    expect(() => padExtent([-8.9e307, 8.9e307], .03)).toThrow(RangeError)
  })
  it('validates the final legend-expanded canvas range, including unsupported subnormal scales', () => {
    const lo = -8e307, base = 8e307, legend = .4
    const hi = Math.min(Number.MAX_VALUE, base + (base - lo) * legend / (1 - legend))
    expect(() => chartExtent([lo, hi], 500)).toThrow(RangeError)
    expect(() => chartExtent([Number.MIN_VALUE, Number.MIN_VALUE * 2], 500)).toThrow(RangeError)
    expect(() => chartExtent([1, 1], 500)).toThrow(RangeError)
    expect(chartExtent([1e-200, 2e-200], 500)).toEqual([1e-200, 2e-200])
    expect(chartExtent([1e200, 2e200], 500)).toEqual([1e200, 2e200])
    for (const pixels of [0, -1, NaN, Infinity]) expect(() => chartExtent([0, 1], pixels)).toThrow(RangeError)
  })
  it('rejects invalid inputs rather than generating unbounded precision/loops', () => {
    for (const [min, max, count] of [[NaN, 1, 5], [0, Infinity, 5], [0, 1, NaN], [0, 1, Infinity], [0, 1, 1.5], [0, 1, 1001]]) {
      expect(() => niceTicks(min, max, count)).toThrow(RangeError)
    }
    for (const decimals of [-1, 1.5, 13, 202, NaN, Infinity]) expect(() => displayNumber(1, decimals)).toThrow(RangeError)
    for (const decimals of [-1, 1.5, NaN, Infinity]) expect(() => tickFormat({ ticks: [0, 1], decimals })).toThrow(RangeError)
    expect(() => tickFormat({ ticks: [Infinity], decimals: 2 })).toThrow(RangeError)
    expect(() => padExtent([NaN, 1], .03)).toThrow(RangeError)
    expect(() => padExtent([0, 1], Infinity)).toThrow(RangeError)
  })
})

describe('visible volume color classes', () => {
  it('partitions original indices by prior-close direction, including unchanged closes', () => {
    const bars = [bar(0, 10, 11), bar(1, 11, 11), bar(2, 11, 10), bar(3, 10, 12)]
    const { up } = candleClasses(bars)
    expect(visibleVolumeClasses(up, 0, 3)).toEqual({ up: [0, 1, 3], down: [2] })
    expect(visibleVolumeClasses(up, 1.6, 2.6)).toEqual({ up: [3], down: [2] })
  })
  it('covers every intersecting bar exactly once through pan and full-history fit', () => {
    const up = Array.from({ length: 25_000 }, (_, i) => i % 3 !== 0)
    for (const [from, to] of [[-1, 25_000], [101.6, 155.4], [-2, -.5], [30_000, 40_000]]) {
      const grouped = visibleVolumeClasses(up, from, to)
      const indices = [...grouped.up, ...grouped.down].sort((a, b) => a - b)
      expect(indices).toEqual(visibleVolumeIndices(up.length, from, to))
      expect(new Set(indices).size).toBe(indices.length)
      expect(grouped.up.every(i => up[i])).toBe(true)
      expect(grouped.down.every(i => !up[i])).toBe(true)
    }
  })
  it('keeps all-up, all-down and empty histories valid without synthesizing bars', () => {
    expect(visibleVolumeClasses([true, true], -1, 3)).toEqual({ up: [0, 1], down: [] })
    expect(visibleVolumeClasses([false, false], -1, 3)).toEqual({ up: [], down: [0, 1] })
    expect(visibleVolumeClasses([], -1, 3)).toEqual({ up: [], down: [] })
  })
})
const at = (iso: string) => Date.parse(`${iso}T00:00:00Z`) / 1000
const days = (start: string, n: number, skipWeekends = false) => {
  const out: number[] = []
  for (let t = at(start); out.length < n; t += DAY) {
    const weekday = new Date(t * 1000).getUTCDay()
    if (!skipWeekends || (weekday !== 0 && weekday !== 6)) out.push(t)
  }
  return out
}
const bar = (t: number, o: number, c: number): Candle => ({ t, o, h: Math.max(o, c) + 1, l: Math.min(o, c) - 1, c, v: 1000 })
const series = (id: string, pane: string): OverlaySeries => ({ id, name: id, pane, style: 'line', values: [], warmup: 0 }) as OverlaySeries

describe('dateTicks', () => {
  it('labels weekly days with bold month and year boundaries at StockCharts density', () => {
    const times = days('2025-11-03', 120, true)
    const ticks = dateTicks(times, 0, times.length - 1, 600)
    const years = ticks.filter(t => t.kind === 'year')
    expect(years.map(t => t.label)).toEqual(['2026'])
    expect(new Date(times[years[0].index] * 1000).toISOString().slice(0, 10)).toBe('2026-01-01')
    const months = ticks.filter(t => t.kind === 'month').map(t => t.label)
    expect(months).toEqual(['Dec', 'Feb', 'Mar', 'Apr'])
    const minors = ticks.filter(t => t.kind === 'minor')
    for (const tick of minors) expect(new Date(times[tick.index] * 1000).getUTCDay()).toBe(1)
  })
  it('coarsens to month names when the window is dense and to years when denser still', () => {
    const times = days('2015-01-01', 3000)
    const wide = dateTicks(times, 0, 400, 600)
    expect(wide.some(t => t.kind === 'minor' && /^[A-Z][a-z]{2}$/.test(t.label))).toBe(true)
    const all = dateTicks(times, 0, times.length - 1, 600)
    expect(all.every(t => t.kind === 'year')).toBe(true)
  })
  it('uses clock labels for intraday series', () => {
    const times = Array.from({ length: 200 }, (_, i) => at('2026-01-05') + i * 3600)
    const ticks = dateTicks(times, 0, 199, 1200)
    expect(ticks.some(t => /^\d\d:\d\d$/.test(t.label))).toBe(true)
  })
  it('returns no ticks for empty windows', () => {
    expect(dateTicks([], 0, 10, 500)).toEqual([])
    expect(dateTicks(days('2026-01-01', 10), 0, 9, 0)).toEqual([])
  })
})

describe('observationGaps', () => {
  it('flags missing observations on a continuous calendar', () => {
    const times = days('2026-01-01', 10)
    times.splice(4, 2)
    expect(observationGaps(times, 'continuous')).toEqual([{ index: 4, missing: 2 }])
  })
  it('ignores weekends but flags missing weekdays on a weekday calendar', () => {
    const times = days('2026-01-05', 15, true)
    expect(observationGaps(times, 'weekday')).toEqual([])
    times.splice(3, 1)
    expect(observationGaps(times, 'weekday')).toEqual([{ index: 3, missing: 1 }])
  })
  it('does not judge intraday weekday series', () => {
    const times = [0, 3600, 7200, 7200 * 30]
    expect(observationGaps(times, 'weekday')).toEqual([])
  })
  it('reads the calendar from the series, not from a settings profile', () => {
    expect(inferCalendar(days('2026-01-05', 15, true))).toBe('weekday')
    expect(inferCalendar(days('2026-01-05', 15))).toBe('continuous')
    // 2026-01-05 is a Monday: hourly bars across one weekday stay on the weekday calendar.
    expect(inferCalendar(Array.from({ length: 24 }, (_, i) => at('2026-01-05') + i * 3600))).toBe('weekday')
  })
})

describe('candleClasses', () => {
  it('colours by prior close and fills by close versus open', () => {
    const bars = [bar(0, 10, 11), bar(1, 12, 11.5), bar(2, 11, 11.2), bar(3, 11.5, 11.1)]
    expect(candleClasses(bars)).toEqual({ up: [true, true, false, false], hollow: [true, false, true, false] })
  })
})

describe('extents and formatting', () => {
  it('finds finite extents in the clamped window', () => {
    expect(visibleExtent([[5, null, 1, NaN, 9]], -3, 3)).toEqual([1, 5])
    expect(visibleExtent([[null, null]], 0, 1)).toBeNull()
    expect(visibleExtent([[1, 2], [7, -4]], 0, 1)).toEqual([-4, 7])
  })
  it('chooses price decimals from recorded values', () => {
    expect(priceDecimals([100, 101])).toBe(2)
    expect(priceDecimals([0.5234, 0.52])).toBe(4)
    expect(priceDecimals([Math.fround(62.03)])).toBe(2)
    expect(priceDecimals([0.000012345678])).toBe(11)
    expect(priceDecimals([1.23e-7])).toBe(9)
    expect(priceDecimals([12345.678])).toBe(2)
  })
  it('compacts volume', () => {
    expect(compactVolume(25_000_000)).toBe('25M')
    expect(compactVolume(1_234_567)).toBe('1.23M')
    expect(compactVolume(950)).toBe('950')
  })
  it('labels studies in StockCharts form', () => {
    expect(studyLabel('sma:50')).toBe('MA(50)')
    expect(studyLabel(studySpec('macd:12:26:9:hist'))).toBe('MACD(12,26,9)')
    expect(studyLabel('bbands:20:2')).toBe('BB(20,2)')
    expect(studyLabel('hawkes:0.1:20')).toBe('HAWKES(0.1,20)')
  })
  it('computes header change from the prior recorded close', () => {
    const bars = [bar(0, 10, 10), bar(1, 10, 11)]
    expect(headerValues(bars, 1)).toMatchObject({ change: 1, changePct: expect.closeTo(10, 9) })
    expect(headerValues(bars, 0)).toMatchObject({ change: null, changePct: null })
    expect(headerValues(bars, 5)).toBeNull()
  })
})

describe('layout', () => {
  it('places RSI above price and other panes below in order', () => {
    const layout = panelLayout([series('macd:12:26:9:line', 'macd'), series('sma:50', 'price'), series('rsi:14', 'rsi'), series('atr:14', 'atr')])
    expect(layout.price.map(s => s.id)).toEqual(['sma:50'])
    expect(layout.above.map(p => p.pane)).toEqual(['rsi'])
    expect(layout.below.map(p => p.pane)).toEqual(['macd', 'atr'])
  })
  it('keeps the StockCharts study ratio and a price floor', () => {
    expect(panelHeights(490, 2)).toEqual({ price: 290, study: 100 })
    const crowded = panelHeights(1000, 6)
    expect(crowded.price).toBe(454)
    expect(panelHeights(500, 0)).toEqual({ price: 500, study: 0 })
  })
  it('pins StockCharts study colours per style', () => {
    expect(studyColors(CLASSIC, ['sma:50', 'sma:200']).get('sma:200')).toBe('#d00030')
    const def = studyColors(DEFAULT_STYLE, ['ema:20', 'sma:50', 'sma:200', 'ema:9'])
    expect([def.get('ema:20'), def.get('sma:50'), def.get('sma:200')]).toEqual(['#006400', '#00008b', '#dd0000'])
    expect(def.get('ema:9')).toBe('#8b4513')
  })
})

describe('index and tick helpers', () => {
  it('preserves tiny finite tick coordinates instead of rounding them to zero', () => {
    const ticks = niceTicks(9.7e-201, 2.03e-200, 5).ticks
    expect(ticks.length).toBeGreaterThan(1)
    expect(ticks.every(t => Number.isFinite(t) && t > 0)).toBe(true)
    expect(new Set(ticks).size).toBe(ticks.length)
  })
  it('maps UTC times to fractional observation indices', () => {
    expect(fractionalIndex([10, 20, 40], 30)).toBe(1.5)
    expect(fractionalIndex([10, 20, 40], 20)).toBe(1)
    expect(fractionalIndex([10, 20, 40], 41)).toBeNull()
  })
  it('chooses 1/2/2.5/5 steps with consistent decimals', () => {
    expect(niceTicks(241, 348, 44)).toEqual({ ticks: expect.arrayContaining([242.5, 245, 347.5]), decimals: 1 })
    expect(niceTicks(0, 100, 5).ticks).toEqual([0, 20, 40, 60, 80, 100])
    expect(niceTicks(0.51, 0.529, 4).decimals).toBe(3)
    expect(niceTicks(1, 1, 4).ticks).toEqual([])
  })
})


describe('visibleVolumeIndices', () => {
  it('includes rectangles that touch either viewport edge', () => {
    expect(visibleVolumeIndices(6, 1.4, 2.6)).toEqual([1, 2, 3])
    expect(visibleVolumeIndices(6, 1.41, 2.59)).toEqual([2])
  })
  it('retains native indices through pan and includes every bar on fit', () => {
    expect(visibleVolumeIndices(25000, 24890.2, 24910.8)).toEqual(Array.from({ length: 22 }, (_, i) => 24890 + i))
    const all = visibleVolumeIndices(25000, -.5, 24999.5)
    expect(all).toHaveLength(25000)
    expect(all[0]).toBe(0)
    expect(all.at(-1)).toBe(24999)
  })
  it('clips to loaded observations and admits no invented bars', () => {
    expect(visibleVolumeIndices(5, -3, .3)).toEqual([0])
    expect(visibleVolumeIndices(5, 5, 6)).toEqual([])
    expect(visibleVolumeIndices(0, 0, 1)).toEqual([])
  })
  it('rejects invalid geometry loudly', () => {
    for (const [count, from, to] of [[-1, 0, 1], [1.5, 0, 1], [5, NaN, 1], [5, 0, Infinity], [5, 2, 1]]) {
      expect(() => visibleVolumeIndices(count, from, to)).toThrow(RangeError)
    }
  })
})

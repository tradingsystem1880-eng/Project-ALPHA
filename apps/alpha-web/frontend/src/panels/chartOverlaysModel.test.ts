import { describe, expect, it } from 'vitest'

import type { ChartAnnotation, OverlaySeries } from '../api/types'
import {
  EMPTY_OVERLAYS,
  drawableAnnotations,
  hasOverlays,
  lineData,
  overlayLegend,
  overlayQuery,
  parseIndicatorSpec,
  parseOverlayConfig,
  splitPanes,
  swingMarkers,
  toggleIndicator,
  togglePattern,
} from './chartOverlaysModel'

const series = (id: string, pane: OverlaySeries['pane'], name = id): OverlaySeries => ({
  id,
  name,
  pane,
  style: 'line',
  values: [null, 1, 2],
  warmup: 1,
})

const annotation = (id: number, label: string, anchors: number[]): ChartAnnotation => ({
  annotation_id: id,
  decision_sequence_id: null,
  kind: 'line',
  label,
  unit: 'price',
  reason: 'fractal L=5; knowable from bar 9',
  anchors: anchors.map((index) => ({ anchor_index: index, ts: 1_000 + index, value: 100 + index })),
})

describe('indicator spec grammar (mirrors alpha chart overlays)', () => {
  it('normalises the documented forms', () => {
    expect(parseIndicatorSpec(' SMA:20 ')).toBe('sma:20')
    expect(parseIndicatorSpec('bbands:20:2.5')).toBe('bbands:20:2.5')
    expect(parseIndicatorSpec('macd:12:26:9')).toBe('macd:12:26:9')
  })
  it('names the problem instead of sending a bad spec to the CLI', () => {
    expect(() => parseIndicatorSpec('foo:2')).toThrow(/unknown indicator "foo"/)
    expect(() => parseIndicatorSpec('sma')).toThrow(/sma takes 1 parameter \(sma:20\)/)
    expect(() => parseIndicatorSpec('sma:abc')).toThrow(/must be numbers/)
    expect(() => parseIndicatorSpec('sma:1')).toThrow(/at least 2/)
    expect(() => parseIndicatorSpec('rsi:2.5')).toThrow(/whole numbers/)
    expect(() => parseIndicatorSpec('bbands:20:0')).toThrow(/width/)
    expect(() => parseIndicatorSpec('macd:26:12:9')).toThrow(/fast window/)
  })
})

describe('overlay config', () => {
  it('toggles indicators by normalised id and patterns by name', () => {
    let config = toggleIndicator(EMPTY_OVERLAYS, 'SMA:20')
    config = toggleIndicator(config, 'rsi:14')
    expect(config.indicators).toEqual(['sma:20', 'rsi:14'])
    expect(toggleIndicator(config, 'sma:20').indicators).toEqual(['rsi:14'])
    config = togglePattern(config, 'swings')
    expect(config.patterns).toEqual(['swings'])
    expect(togglePattern(config, 'swings').patterns).toEqual([])
    expect(hasOverlays(EMPTY_OVERLAYS)).toBe(false)
    expect(hasOverlays(config)).toBe(true)
  })
  it('parses persisted JSON defensively, dropping stale or garbage specs', () => {
    expect(parseOverlayConfig(null)).toEqual(EMPTY_OVERLAYS)
    expect(parseOverlayConfig('nope')).toEqual(EMPTY_OVERLAYS)
    expect(
      parseOverlayConfig({ indicators: ['sma:20', 'bogus:1', 3, 'SMA:20'], patterns: ['swings', 'cups', 4] }),
    ).toEqual({ indicators: ['sma:20'], patterns: ['swings'] })
  })
  it('builds the overlays query in draw order with the linked as-of window', () => {
    const config = { indicators: ['sma:20', 'macd:12:26:9'], patterns: ['swings' as const] }
    expect(overlayQuery(config, { end: '2026-06-30', snapshotId: 'snap-1' })).toBe(
      '?indicator=sma%3A20&indicator=macd%3A12%3A26%3A9&pattern=swings&end=2026-06-30&snapshot=snap-1',
    )
    expect(overlayQuery(EMPTY_OVERLAYS, { end: null, snapshotId: null })).toBe('')
  })
})

describe('response → chart data', () => {
  it('splits price-pane series from oscillator panes in a fixed pane order', () => {
    const rows = [
      series('macd:12:26:9:line', 'macd'),
      series('sma:20', 'price'),
      series('rsi:14', 'rsi'),
      series('bbands:20:2:upper', 'price'),
    ]
    const split = splitPanes(rows)
    expect(split.price.map((row) => row.id)).toEqual(['sma:20', 'bbands:20:2:upper'])
    expect(split.panes.map((group) => [group.pane, group.series.length])).toEqual([
      ['rsi', 1],
      ['macd', 1],
    ])
  })
  it('turns warm-up nulls into whitespace points and refuses a misaligned series', () => {
    expect(lineData([1, 2, 3], [null, 5, 6])).toEqual([{ time: 1 }, { time: 2, value: 5 }, { time: 3, value: 6 }])
    expect(() => lineData([1, 2], [null])).toThrow(/does not match/)
  })
  it('renders single-anchor swings as bar markers and keeps multi-anchor shapes for drawing', () => {
    const rows = [
      annotation(1, 'Swing high', [4]),
      annotation(2, 'Swing low', [9]),
      annotation(3, 'Fib 0.618', [9, 20]),
      annotation(4, 'Descending trendline (3 touches, active)', [2, 9, 20]),
    ]
    expect(swingMarkers(rows)).toEqual([
      { id: 'swing:1', time: 1_004, position: 'aboveBar', text: 'H', title: 'Swing high · fractal L=5; knowable from bar 9' },
      { id: 'swing:2', time: 1_009, position: 'belowBar', text: 'L', title: 'Swing low · fractal L=5; knowable from bar 9' },
    ])
    expect(drawableAnnotations(rows).map((row) => row.annotation_id)).toEqual([3, 4])
    expect(overlayLegend([series('sma:20', 'price', 'SMA 20'), series('macd:12:26:9:line', 'macd', 'MACD 12/26/9 line')], rows)).toBe(
      'OVERLAYS · SMA 20 · MACD 12/26/9 · 2 swings · 1 trendline · 1 fib levels · computed by alpha chart overlays',
    )
    expect(overlayLegend([], [])).toBe('')
  })
})

import { describe, expect, it } from 'vitest'

import type { ChartAnnotation, OverlaySeries } from '../api/types'
import {
  ARITY,
  EMPTY_OVERLAYS,
  INDICATOR_PRESETS,
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

const series = (id: string, pane: string, name = id): OverlaySeries => ({
  id,
  name,
  pane,
  style: 'line',
  values: [null, 1, 2],
  warmup: 1,
})

const annotation = (
  id: number,
  label: string,
  anchors: number[],
  kind: ChartAnnotation['kind'] = anchors.length === 1 ? 'marker' : 'line',
): ChartAnnotation => ({
  annotation_id: id,
  decision_sequence_id: null,
  kind,
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
    expect(parseIndicatorSpec('HAWKES:0.1:168')).toBe('hawkes:0.1:168')
    expect(parseIndicatorSpec('perm_entropy:3:28')).toBe('perm_entropy:3:28')
    expect(parseIndicatorSpec('reversibility:10')).toBe('reversibility:10')
  })
  it('accepts every preset and every arity-table head', () => {
    for (const preset of INDICATOR_PRESETS) expect(parseIndicatorSpec(preset.id)).toBe(preset.id)
    expect(new Set(INDICATOR_PRESETS.map((preset) => preset.id.split(':')[0]))).toEqual(new Set(Object.keys(ARITY)))
  })
  it('names the problem instead of sending a bad spec to the CLI', () => {
    expect(() => parseIndicatorSpec('foo:2')).toThrow(/unknown indicator "foo"/)
    expect(() => parseIndicatorSpec('sma')).toThrow(/sma takes 1 parameter \(sma:20\)/)
    expect(() => parseIndicatorSpec('sma:abc')).toThrow(/must be numbers/)
    expect(() => parseIndicatorSpec('sma:1')).toThrow(/at least 2/)
    expect(() => parseIndicatorSpec('rsi:2.5')).toThrow(/whole numbers/)
    expect(() => parseIndicatorSpec('bbands:20:0')).toThrow(/width/)
    expect(() => parseIndicatorSpec('macd:26:12:9')).toThrow(/fast window/)
    expect(() => parseIndicatorSpec('hawkes:0:168')).toThrow(/decay must be above 0/)
    expect(() => parseIndicatorSpec('hawkes:0.1:1')).toThrow(/at least 2/)
    expect(() => parseIndicatorSpec('reversibility:9')).toThrow(/at least 10/)
    expect(() => parseIndicatorSpec('cmma:10')).toThrow(/cmma takes 2 parameters \(cmma:24:168\)/)
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
  it('splits price-pane series from one sub-pane per oscillator in the order the CLI served them', () => {
    const rows = [
      series('macd:12:26:9:line', 'macd'),
      series('sma:20', 'price'),
      series('rsi:14', 'rsi'),
      series('bbands:20:2:upper', 'price'),
      series('vg_path:12:price', 'vg_path'),
      series('macd:12:26:9:signal', 'macd'),
      series('vg_path:12:inverse', 'vg_path'),
    ]
    const split = splitPanes(rows)
    expect(split.price.map((row) => row.id)).toEqual(['sma:20', 'bbands:20:2:upper'])
    expect(split.panes.map((group) => [group.pane, group.series.length])).toEqual([
      ['macd', 2],
      ['rsi', 1],
      ['vg_path', 2],
    ])
    expect(splitPanes([series('hawkes:0.1:168', 'hawkes')]).panes.map((group) => group.pane)).toEqual(['hawkes'])
  })
  it('turns warm-up nulls into whitespace points and refuses a misaligned series', () => {
    expect(lineData([1, 2, 3], [null, 5, 6])).toEqual([{ time: 1 }, { time: 2, value: 5 }, { time: 3, value: 6 }])
    expect(() => lineData([1, 2], [null])).toThrow(/does not match/)
  })
  it('renders marker annotations as bar markers and keeps multi-anchor shapes for drawing', () => {
    const rows = [
      annotation(1, 'Swing high', [4]),
      annotation(2, 'Swing low', [9]),
      annotation(3, 'Fib 0.618', [9, 20]),
      annotation(4, 'Descending trendline (3 touches, active)', [2, 9, 20]),
      annotation(5, 'DC high', [12]),
      annotation(6, 'Structure L1 low', [15]),
      annotation(7, 'PIPs 5', [1, 5, 9, 14, 20], 'polyline'),
      annotation(8, 'Profile level 101.5', [0, 20]),
    ]
    expect(swingMarkers(rows)).toEqual([
      { id: 'swing:1', time: 1_004, position: 'aboveBar', shape: 'circle', text: 'H', title: 'Swing high · fractal L=5; knowable from bar 9' },
      { id: 'swing:2', time: 1_009, position: 'belowBar', shape: 'circle', text: 'L', title: 'Swing low · fractal L=5; knowable from bar 9' },
      { id: 'swing:5', time: 1_012, position: 'aboveBar', shape: 'square', text: 'H', title: 'DC high · fractal L=5; knowable from bar 9' },
      { id: 'swing:6', time: 1_015, position: 'belowBar', shape: 'square', text: 'L', title: 'Structure L1 low · fractal L=5; knowable from bar 9' },
    ])
    // a legacy single-anchor 'line' is never a marker, and a marker is never drawn as a shape
    expect(swingMarkers([annotation(9, 'Swing low', [3], 'line')])).toEqual([])
    expect(drawableAnnotations(rows).map((row) => row.annotation_id)).toEqual([3, 4, 7, 8])
    expect(
      overlayLegend(
        [series('sma:20', 'price', 'SMA 20'), series('macd:12:26:9:line', 'macd', 'MACD 12/26/9 line')],
        rows.slice(0, 4),
      ),
    ).toBe('OVERLAYS · SMA 20 · MACD 12/26/9 · 2 swings · 1 trendline · 1 fib levels · computed by alpha chart overlays')
    expect(
      overlayLegend([series('vg_path:12:price', 'vg_path', 'VG path 12 price'), series('vg_path:12:inverse', 'vg_path', 'VG path 12 inverse')], rows),
    ).toBe(
      'OVERLAYS · VG path 12 · 2 swings · 2 extremes · 1 trendline · 1 fib levels · 1 profile levels · 1 pattern · computed by alpha chart overlays',
    )
    expect(overlayLegend([], [])).toBe('')
  })
})

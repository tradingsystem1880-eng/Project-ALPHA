// The ALPHA technical chart: one standalone BokehJS document holding a shared-border panel stack
// (RSI above, price + volume underlay, MACD and other studies below) on an observation-indexed x
// axis. Canvas draws the series; a DOM layer per panel draws the calendar date strip, legends,
// axis value tags, gap marks and the crosshair so typography matches StockCharts exactly.
// Every study value is the backend's (`alpha chart overlays`); this module only places it.

import { figure, type Figure } from '@bokeh/bokehjs/build/js/lib/api/figure'
import { Column } from '@bokeh/bokehjs/build/js/lib/models/layouts/column'
import { technicalPng } from './technicalExport'
import { ColumnDataSource } from '@bokeh/bokehjs/build/js/lib/models/sources/column_data_source'
import { CDSView } from '@bokeh/bokehjs/build/js/lib/models/sources/cds_view'
import { IndexFilter } from '@bokeh/bokehjs/build/js/lib/models/filters/index_filter'
import { Range1d } from '@bokeh/bokehjs/build/js/lib/models/ranges/range1d'
import { FixedTicker } from '@bokeh/bokehjs/build/js/lib/models/tickers/fixed_ticker'
import { Grid } from '@bokeh/bokehjs/build/js/lib/models/grids/grid'
import { LinearAxis } from '@bokeh/bokehjs/build/js/lib/models/axes/linear_axis'
import { PrintfTickFormatter } from '@bokeh/bokehjs/build/js/lib/models/formatters/printf_tick_formatter'
import { Span } from '@bokeh/bokehjs/build/js/lib/models/annotations/span'
import { LabelSet } from '@bokeh/bokehjs/build/js/lib/models/annotations/label_set'
import { HoverTool } from '@bokeh/bokehjs/build/js/lib/models/tools/inspectors/hover_tool'
import { MouseMove, MouseLeave, RangesUpdate, LODStart, LODEnd } from '@bokeh/bokehjs/build/js/lib/core/bokeh_events'
import type { PlotView } from '@bokeh/bokehjs/build/js/lib/models/plots/plot_canvas'
import type { Candle, ChartAnnotation, OverlaySeries } from '../../api/types'
import type { EvidenceMarker } from '../../panels/v3Models'
import type { ChartControls } from '../../context/chartControls'
import { logicalRangeForUTC, type ChartLinkRegistry } from '../../shell/chartLinkRegistry'
import { showScientificPlot } from '../bokehLifecycle'
import { scheduleChartResize, cancelChartResize } from '../chartResize'
import {
  calendarKeys, candleClasses, inferCalendar, compactVolume, dateTicks, medianSpacing, fractionalIndex, groupedInteger, niceTicks, observationGaps,
  padExtent, panelHeights, panelLayout, priceDecimals, studyLabel, studySpec, visibleExtent, visibleVolumeClasses,
  type DateTick,
} from './technicalModel'
import { studyColors, type TechnicalStyle } from './technicalTokens'
import { styleTechnicalAxes, tagStyle } from './technicalChrome'

export interface TechnicalComposition {
  bars: readonly Candle[]
  /** Backend overlay series and their timestamps; aligned to bars by exact UTC time. */
  indicators: readonly OverlaySeries[]
  indicatorTimes: readonly number[]
  annotations: readonly ChartAnnotation[]
  style: TechnicalStyle
  /** Price legend title, e.g. `XRP/USDT (1D)`. */
  title: string
  /** UTC window to restore after a recomposition; otherwise the StockCharts-density default. */
  initialRange?: [number, number] | null
}

type Values = (number | null)[]
interface Line { spec: string; id: string; values: Values; color: string; histogram: boolean }
interface Panel {
  kind: 'price' | 'rsi' | 'macd' | 'study'
  fig: Figure
  y: Range1d
  yTicker: FixedTicker
  yFormat: PrintfTickFormatter
  lines: Line[]
  decimals: number
  dateAxis: boolean
  frameHeight: number
  view?: PlotView
  layers?: { legend: HTMLDivElement; marks: HTMLDivElement; cursor: HTMLDivElement }
}

const LEFT = 46, RIGHT = 64, DATE_STRIP = 18, BAR_PX = 5, TICK_PX = 16

function el(parent: HTMLElement, style: Partial<CSSStyleDeclaration>, text?: string, tag = 'div'): HTMLElement {
  const node = parent.ownerDocument.createElement(tag)
  Object.assign(node.style, style)
  if (text !== undefined) node.textContent = text
  parent.append(node)
  return node
}

function fixed(value: number | null | undefined, decimals: number): string {
  return value === null || value === undefined || !Number.isFinite(value) ? '—' : value.toFixed(decimals)
}

/** Last finite value at or before the window end; the tolerance absorbs linked ranges' 1e-6 insets. */
function lastVisible(values: Values, end: number): number | null {
  for (let i = Math.min(values.length - 1, Math.floor(end + 1e-3)); i >= 0; i--) { const v = values[i]; if (v !== null && Number.isFinite(v)) return v }
  return null
}

export async function mountTechnicalChart(node: HTMLElement, c: TechnicalComposition, options: { panelId: string; registry?: ChartLinkRegistry; onCursor: (index: number | null) => void; initialZoom?: number }) {
  const { bars, style } = c
  const n = bars.length
  const times = bars.map(b => b.t)
  const indexOf = new Map(times.map((t, i) => [t, i]))
  const align = (values: readonly (number | null)[]): Values => {
    const out: Values = new Array(n).fill(null)
    c.indicatorTimes.forEach((t, k) => { const i = indexOf.get(t); if (i !== undefined) out[i] = values[k] ?? null })
    return out
  }
  const closes = bars.map(b => b.c), highs = bars.map(b => b.h), lows = bars.map(b => b.l), volumes = bars.map(b => b.v)
  const { up, hollow } = candleClasses(bars)
  const pd = priceDecimals(closes)
  const layout = panelLayout(c.indicators)
  const colors = studyColors(style, c.indicators.map(s => studySpec(s.id)))
  const toLines = (series: readonly OverlaySeries[]): Line[] => series.map(s => {
    const spec = studySpec(s.id)
    const color = s.id.endsWith(':signal') ? style.macdSignal : s.id.endsWith(':line') && spec.startsWith('macd') ? style.macdLine : s.pane === 'rsi' ? style.text : colors.get(spec)!
    return { spec, id: s.id, values: align(s.values), color, histogram: s.style === 'histogram' }
  })

  // ---- geometry
  const width = Math.max(320, node.clientWidth), height = Math.max(200, node.clientHeight)
  let frameWidth = width - LEFT - RIGHT
  const studies = [...layout.above, ...layout.below]
  const strips = 1 + (layout.below.length ? 1 : 0)
  const heights = panelHeights(height - strips * DATE_STRIP - 2, studies.length)

  const x = new Range1d({ start: -0.5, end: n - 0.5, bounds: [-Math.max(5, n * 0.05), n + Math.max(10, n * 0.1)] })
  const makeFigure = (frameHeight: number, dateAxis: boolean, kind: Panel['kind']): Panel => {
    const y = new Range1d({ start: 0, end: 1 })
    const fig = figure({
      x_range: x, y_range: y, frame_width: frameWidth, frame_height: frameHeight,
      tools: 'xpan,xwheel_zoom', active_drag: 'xpan' as never, active_scroll: 'xwheel_zoom' as never, toolbar_location: null,
      y_axis_location: 'right', min_border_left: LEFT, min_border_right: RIGHT, min_border_top: 0, min_border_bottom: dateAxis ? DATE_STRIP : 0,
      background_fill_color: style.plot, border_fill_color: style.canvas, outline_line_color: style.border, outline_line_width: 1,
    })
    const yTicker = new FixedTicker({ ticks: [] }), yFormat = new PrintfTickFormatter({ format: '%.2f' })
    for (const axis of fig.yaxis) Object.assign(axis, { ticker: yTicker, formatter: yFormat })
    styleTechnicalAxes(fig, style); fig.axis.major_label_standoff = 3
    for (const axis of fig.xaxis) { axis.visible = dateAxis; axis.major_label_text_alpha = 0 }
    for (const grid of fig.ygrid) grid.ticker = yTicker
    return { kind, fig, y, yTicker, yFormat, lines: [], decimals: 3, dateAxis, frameHeight }
  }

  const xTicker = new FixedTicker({ ticks: [] }), monthTicker = new FixedTicker({ ticks: [] })
  const panels: Panel[] = []
  for (const group of layout.above) { const p = makeFigure(heights.study, false, 'rsi'); p.lines = toLines(group.series); panels.push(p) }
  const price = makeFigure(heights.price, true, 'price'); price.lines = toLines(layout.price); price.decimals = pd; panels.push(price)
  layout.below.forEach((group, k) => {
    const p = makeFigure(heights.study, k === layout.below.length - 1, group.pane === 'macd' ? 'macd' : 'study')
    p.lines = toLines(group.series); panels.push(p)
  })
  const monthGrids = panels.map(p => {
    for (const axis of p.fig.xaxis) axis.ticker = xTicker
    for (const grid of p.fig.xgrid) grid.ticker = xTicker
    const grid = new Grid({ dimension: 0, ticker: monthTicker, grid_line_color: style.gridMonth, grid_line_width: 1 })
    p.fig.add_layout(grid)
    return grid
  })

  // ---- price panel: volume underlay, candles / OHLC / close line, studies, swings, evidence
  const volumeRange = new Range1d({ start: 0, end: 1 })
  price.fig.extra_y_ranges = { volume: volumeRange }
  const volumeTicker = new FixedTicker({ ticks: [] })
  const volumeAxis = new LinearAxis({ y_range_name: 'volume', ticker: volumeTicker, axis_line_color: null, major_tick_line_color: style.border, major_tick_in: 0, major_tick_out: 3, minor_tick_line_color: null, major_label_text_font: style.font, major_label_text_font_size: `${style.fontSize}px`, major_label_text_color: style.text, major_label_standoff: 3 })
  price.fig.add_layout(volumeAxis, 'left')
  const index = times.map((_, i) => i)
  const color = up.map(u => u ? style.up : style.down)
  const volumeSource = new ColumnDataSource({ data: { x: index, top: volumes } })
  const volumeFilters = { up: new IndexFilter({ indices: [] }), down: new IndexFilter({ indices: [] }) }
  for (const direction of ['up', 'down'] as const) {
    const colors = direction === 'up' ? style.volumeUp : style.volumeDown
    price.fig.vbar({ field: 'x' }, 0.8, { field: 'top' }, 0, { source: volumeSource, view: new CDSView({ filter: volumeFilters[direction] }), y_range_name: 'volume', fill_color: colors.fill, line_color: colors.edge, line_width: 1 })
  }
  const candles = new ColumnDataSource({ data: {
    x: index, open: bars.map(b => b.o), close: closes, high: highs, low: lows, color,
    fill: hollow.map((h, i) => h ? style.plot : color[i]), left: index.map(i => i - style.tick), right: index.map(i => i + style.tick),
  } })
  const wick = price.fig.segment({ field: 'x' }, { field: 'low' }, { field: 'x' }, { field: 'high' }, { source: candles, line_color: { field: 'color' }, line_width: 1 })
  const body = price.fig.vbar({ field: 'x' }, style.body, { field: 'close' }, { field: 'open' }, { source: candles, fill_color: { field: 'fill' }, line_color: { field: 'color' }, line_width: 1 })
  const openTick = price.fig.segment({ field: 'left' }, { field: 'open' }, { field: 'x' }, { field: 'open' }, { source: candles, line_color: { field: 'color' }, line_width: 1 })
  const closeTick = price.fig.segment({ field: 'x' }, { field: 'close' }, { field: 'right' }, { field: 'close' }, { source: candles, line_color: { field: 'color' }, line_width: 1 })
  const closeLine = price.fig.line({ field: 'x' }, { field: 'close' }, { source: candles, line_color: style.up, line_width: 1 })

  const drawLines = (p: Panel) => {
    for (const line of p.lines) {
      const values = line.values.map(v => v ?? NaN)
      if (line.histogram) {
        const fill = p.kind === 'macd' ? style.histFill : line.color, edge = p.kind === 'macd' ? style.histEdge : line.color
        p.fig.vbar({ field: 'x' }, 0.8, { field: 'y' }, 0, { source: new ColumnDataSource({ data: { x: index, y: values } }), fill_color: fill, line_color: edge, line_width: 1 })
      } else {
        p.fig.line({ field: 'x' }, { field: 'y' }, { source: new ColumnDataSource({ data: { x: index, y: values } }), line_color: line.color, line_width: 1 })
      }
    }
  }
  for (const p of panels) {
    if (p.kind === 'rsi') {
      p.decimals = 2
      const rsi = p.lines[0]?.values.map(v => v ?? NaN) ?? []
      const fills = new ColumnDataSource({ data: { x: index, y: rsi, hi: rsi.map(v => Number.isFinite(v) ? Math.max(v, 70) : 70), lo: rsi.map(v => Number.isFinite(v) ? Math.min(v, 30) : 30) } })
      // Warm-up rows collapse onto the band (zero-height area); varea would otherwise bridge NaNs.
      p.fig.varea({ field: 'x' }, 70, { field: 'hi' }, { source: fills, fill_color: style.rsiOverbought, fill_alpha: 0.9 })
      p.fig.varea({ field: 'x' }, { field: 'lo' }, 30, { source: fills, fill_color: style.rsiOversold, fill_alpha: 0.9 })
      for (const level of [70, 30]) p.fig.add_layout(new Span({ location: level, dimension: 'width', line_color: style.rsiBand, line_width: 1 }))
      p.fig.add_layout(new Span({ location: 50, dimension: 'width', line_color: style.rsiBand, line_width: 1, line_dash: 'dashdot' }))
      p.y.setv({ start: 0, end: 100 }); p.yTicker.ticks = [10, 30, 50, 70, 90]; p.yFormat.format = '%d'
    } else if (p.kind !== 'price') {
      p.fig.add_layout(new Span({ location: 0, dimension: 'width', line_color: style.rsiBand, line_width: 1 }))
    }
    drawLines(p)
  }

  const priceAnnotations = c.annotations.filter(a => a.unit === 'price')
  const shapeRows = priceAnnotations.filter(a => a.kind !== 'marker' && a.anchors.length >= 2)
    .map(a => a.anchors.map(p => ({ x: fractionalIndex(times, p.ts), y: p.value })))
  const drawable = shapeRows.filter(row => row.every(p => p.x !== null))
  price.fig.multi_line({ field: 'xs' }, { field: 'ys' }, { source: new ColumnDataSource({ data: { xs: drawable.map(r => r.map(p => p.x!)), ys: drawable.map(r => r.map(p => p.y)) } }), line_color: style.annotation, line_width: 1, line_dash: 'dashed' })
  const markerRows = priceAnnotations.filter(a => a.kind === 'marker' && a.anchors.length === 1)
  const swings = markerRows.filter(a => indexOf.has(a.anchors[0].ts))
  // Annotations anchored outside the loaded bars are not drawn; the count is reported, never hidden.
  const undrawn = shapeRows.length - drawable.length + markerRows.length - swings.length
  if (swings.length) {
    const high = swings.map(a => a.label.endsWith('high'))
    const source = new ColumnDataSource({ data: { x: swings.map(a => indexOf.get(a.anchors[0].ts)!), y: swings.map(a => a.anchors[0].value), text: swings.map(a => a.anchors[0].value.toFixed(pd)), dy: high.map(h => h ? 4 : -13) } })
    price.fig.add_layout(new LabelSet({ x: { field: 'x' }, y: { field: 'y' }, text: { field: 'text' }, y_offset: { field: 'dy' }, source, text_align: 'center', text_font: style.font, text_font_size: `${style.fontSize - 1}px`, text_color: style.text }))
  }
  const events = new ColumnDataSource({ data: { x: [], y: [], label: [], sequence: [], color: [], size: [] } })
  const markers = price.fig.scatter({ field: 'x' }, { field: 'y' }, { source: events, size: { field: 'size' }, fill_color: { field: 'color' }, line_color: style.text, marker: 'diamond' })
  price.fig.add_tools(new HoverTool({ renderers: [markers], tooltips: [['Evidence', '@label'], ['Sequence', '@sequence']] }))
  price.fig.add_tools('tap')
  let onSelect: ((sequence: number) => void) | undefined
  events.selected.change.connect(() => { const k = events.selected.indices[0]; if (k !== undefined) onSelect?.((events.get_column('sequence') as number[])[k]) })

  // ---- autoscale + calendar ticks for the visible observations
  // Declared before any range callback: Bokeh may fire one while the document is still mounting.
  let cursorIndex: number | null = null, hover: { panel: Panel; y: number } | null = null, crosshairOn = true
  // Assigned once the panel views exist; range frames before then only rescale.
  let updateLegends = (_index: number) => {}
  const legendEntries: { panel: Panel; rows: { text: HTMLElement[]; values: (i: number) => string[] }[] }[] = []
  const legendRows = (p: Panel) => new Set(p.lines.map(l => l.spec)).size + (p.kind === 'price' ? 2 : 0)
  let ticks: DateTick[] = []
  const calendar = inferCalendar(times), gaps = observationGaps(times, calendar)
  const keys = calendarKeys(times), intraday = medianSpacing(times) < 86400
  // Ticker writes invalidate Bokeh's axis layout; only write when the tick set really changes.
  const setTicks = (ticker: FixedTicker, next: number[]) => {
    const current = ticker.ticks as number[]
    if (current.length === next.length && current.every((v, i) => v === next[i])) return false
    ticker.ticks = next
    return true
  }
  const autoscale = () => {
    const i0 = x.start, i1 = x.end
    // VBar does not spatially mask offscreen rows. Filter only painting, preserving the full
    // source, native positions and partially intersecting bars; all-data fit restores every row.
    const groups = visibleVolumeClasses(up, i0, i1)
    for (const direction of ['up', 'down'] as const) {
      const admitted = groups[direction], filter = volumeFilters[direction], current = Array.from(filter.indices ?? [])
      if (current.length !== admitted.length || current[0] !== admitted[0] || current.at(-1) !== admitted.at(-1)) {
        filter.indices = admitted
      }
    }
    const count = (p: Panel) => Math.max(3, Math.floor(p.frameHeight / TICK_PX))
    for (const p of panels) {
      if (p.kind === 'rsi') continue
      const columns: Values[] = p.kind === 'price' ? [lows, highs] : p.lines.map(l => l.values)
      const extent = visibleExtent(columns, i0, i1)
      if (!extent) continue
      const zero = p.lines.some(l => l.histogram)
      const [lo, base] = p.kind === 'price' ? padExtent(extent, 0.03) : padExtent([zero ? Math.min(extent[0], 0) : extent[0], zero ? Math.max(extent[1], 0) : extent[1]], 0.06)
      // Headroom so the in-panel legend never sits on the data (StockCharts keeps its legend clear).
      const legend = Math.min(0.4, (legendRows(p) * 11 + 6) / p.frameHeight)
      const hi = base + (base - lo) * legend / (1 - legend)
      if (p.y.start !== lo || p.y.end !== hi) p.y.setv({ start: lo, end: hi })
      const nice = niceTicks(lo, hi, count(p))
      setTicks(p.yTicker, nice.ticks)
      const format = `%.${nice.decimals}f`
      if (p.yFormat.format !== format) p.yFormat.format = format
    }
    const vmax = visibleExtent([volumes], i0, i1)?.[1] ?? 0
    if (vmax > 0) {
      if (volumeRange.end !== vmax * 4) volumeRange.setv({ start: 0, end: vmax * 4 })
      const vt = niceTicks(0, vmax, Math.max(2, Math.floor(price.frameHeight * 0.25 / TICK_PX))).ticks.filter(t => t > 0)
      if (setTicks(volumeTicker, vt)) volumeAxis.major_label_overrides = new Map(vt.map(t => [t, compactVolume(t)]))
    }
    ticks = dateTicks(times, i0, i1, frameWidth, keys, intraday)
    setTicks(xTicker, ticks.map(t => t.index))
    setTicks(monthTicker, ticks.filter(t => t.kind !== 'minor').map(t => t.index))
  }
  let scaleFrame = 0
  const lastIndex = () => Math.min(n - 1, Math.max(0, Math.floor(x.end + 1e-3)))
  // Without a hover the legends read the last visible observation, like the value tags.
  x.change.connect(() => { if (!scaleFrame) scaleFrame = requestAnimationFrame(() => { scaleFrame = 0; autoscale(); if (cursorIndex === null && legendEntries.length) updateLegends(lastIndex()) }) })

  // ---- initial window: restored UTC range, else StockCharts density (~5px per observation)
  const defaultWindow = () => { const visible = Math.min(n, Math.floor(frameWidth / BAR_PX)); x.setv({ start: n - visible - 0.5, end: n - 0.5 + 2 }) }
  const restored = c.initialRange ? logicalRangeForUTC(times, c.initialRange[0], c.initialRange[1]) : null
  if (restored) x.setv({ start: restored.from, end: restored.to }); else defaultWindow()
  autoscale()

  const column = new Column({ children: panels.map(p => p.fig), spacing: 0 })
  const mounted = await showScientificPlot(column, node)
  let observer: ResizeObserver | undefined, unregister: (() => void) | undefined
  try {
  const views = mounted.view.child_views as unknown as PlotView[]
  const font = `${style.fontSize}px ${style.font}`

  // ---- DOM layers
  panels.forEach((p, k) => {
    const view = views[k]; p.view = view
    const root = view.canvas_view.overlays_el
    const base = { position: 'absolute', inset: '0', pointerEvents: 'none', font, color: style.text } as Partial<CSSStyleDeclaration>
    p.layers = { legend: el(root, base) as HTMLDivElement, marks: el(root, base) as HTMLDivElement, cursor: el(root, base) as HTMLDivElement }
    const bbox = view.frame.bbox
    const legend = el(p.layers.legend, { position: 'absolute', left: `${bbox.left + 3}px`, top: `${bbox.top + 2}px`, lineHeight: '11px', whiteSpace: 'nowrap', background: 'transparent' })
    legend.className = 'technical-legend'
    const rows: { text: HTMLElement[]; values: (i: number) => string[] }[] = []
    const addRow = (label: string, swatchColor: string, colorsFor: string[], values: (i: number) => string[], bar = false) => {
      const row = el(legend, { display: 'flex', alignItems: 'center', gap: '3px', color: swatchColor })
      if (bar) {
        // Simple native rectangles preserve the same three bars in DOM and PNG compositing.
        const swatch = el(row, { width: '7px', height: '7px', display: 'flex', gap: '1px' })
        for (const width of [2, 2, 1]) el(swatch, { width: `${width}px`, height: '7px', backgroundColor: style.volumeUp.fill })
      } else el(row, { width: '9px', height: '0', borderTop: `1px solid ${swatchColor}` })
      el(row, {}, label, 'span')
      const text = colorsFor.map(col => el(row, { color: col }, '', 'span'))
      text.forEach((t, i) => { if (i < text.length - 1) t.dataset.sep = ',' })
      rows.push({ text, values })
    }
    if (p.kind === 'price') addRow(c.title, style.text, [style.text], i => [fixed(closes[i], pd)])
    const bySpec = new Map<string, Line[]>()
    for (const line of p.lines) bySpec.set(line.spec, [...(bySpec.get(line.spec) ?? []), line])
    for (const [spec, lines] of bySpec) {
      const decimals = p.kind === 'price' ? pd : p.decimals
      addRow(studyLabel(spec), lines[0].histogram ? style.histEdge : lines[0].color, lines.map(l => l.histogram ? style.histEdge : l.color), i => lines.map(l => fixed(l.values[i], decimals)))
    }
    if (p.kind === 'price') addRow('Volume', style.muted, [style.muted], i => [volumes[i] === undefined ? '—' : groupedInteger(volumes[i])], true)
    legendEntries.push({ panel: p, rows })
  })
  updateLegends = (i: number) => {
    for (const { rows } of legendEntries) for (const row of rows) {
      const values = row.values(i)
      row.text.forEach((t, k) => { t.textContent = values[k] + (t.dataset.sep ?? '') })
    }
  }

  // Repaint marks reuse pooled elements: a pan frame updates text and position, never rebuilds DOM.
  const pools = new Map<HTMLElement, HTMLElement[]>()
  const pooled = (layer: HTMLElement) => {
    const pool = pools.get(layer) ?? []; pools.set(layer, pool)
    let used = 0
    return {
      take(className: string, base: Partial<CSSStyleDeclaration>): HTMLElement {
        const node = pool[used] ?? (pool[used] = el(layer, {}))
        used++
        if (node.className !== className) { node.className = className; node.removeAttribute('style'); node.title = '' }
        Object.assign(node.style, base); node.hidden = false
        return node
      },
      done() { for (let k = used; k < pool.length; k++) pool[k].hidden = true },
    }
  }
  const drawMarks = (p: Panel) => {
    const view = p.view!, marks = pooled(p.layers!.marks)
    const bbox = view.frame.bbox, xs = view.frame.x_scale, ys = view.frame.y_scale
    // value tags: last visible value per series, nudged apart so they never overlap
    const tags: { y: number; text: string; color: string; bold: boolean }[] = []
    if (p.kind === 'price') { const v = lastVisible(closes, x.end); if (v !== null) tags.push({ y: ys.compute(v), text: v.toFixed(pd), color: style.text, bold: true }) }
    for (const line of p.lines) {
      const v = lastVisible(line.values, x.end)
      if (v !== null) tags.push({ y: ys.compute(v), text: v.toFixed(p.kind === 'price' ? pd : p.decimals), color: line.histogram ? style.histEdge : line.color, bold: false })
    }
    // Off-frame values are not tagged; in-frame tags stay inside the frame and never overlap.
    const inFrame = tags.filter(tag => tag.y >= bbox.top - 1 && tag.y <= bbox.bottom + 1).map(tag => ({ ...tag, y: Math.min(bbox.bottom - 6, Math.max(bbox.top + 6, tag.y)) }))
    inFrame.sort((a, b) => a.y - b.y)
    for (let k = 1; k < inFrame.length; k++) if (inFrame[k].y - inFrame[k - 1].y < 12) inFrame[k].y = inFrame[k - 1].y + 12
    for (const tag of inFrame) {
      const node = marks.take('technical-tag', tagStyle(style, bbox.right + 1, tag.y, tag.color, tag.bold))
      if (node.textContent !== tag.text) node.textContent = tag.text
    }
    if (p.dateAxis) {
      // calendar labels under the frame: years and months bold, never overlapping
      const placed: { left: number; right: number }[] = []
      const fits = (left: number, right: number) => left >= bbox.left - 2 && right <= bbox.right + 2 && placed.every(r => right + 3 < r.left || left > r.right + 3)
      const ordered = [...ticks.filter(t => t.kind !== 'minor'), ...ticks.filter(t => t.kind === 'minor')]
      for (const tick of ordered) {
        const cx = xs.compute(tick.index), w = tick.label.length * 6.2 + 2
        if (!fits(cx - w / 2, cx + w / 2)) continue
        placed.push({ left: cx - w / 2, right: cx + w / 2 })
        const node = marks.take(`technical-date ${tick.kind}`, { position: 'absolute', left: `${cx - w / 2}px`, width: `${w}px`, textAlign: 'center', top: `${bbox.bottom + 4}px`, fontWeight: tick.kind === 'minor' ? 'normal' : 'bold' })
        if (node.textContent !== tick.label) node.textContent = tick.label
      }
      for (const gap of gaps) {
        const gx = xs.compute(gap.index - 0.5)
        if (gx < bbox.left || gx > bbox.right) continue
        const mark = marks.take('technical-gap', { position: 'absolute', left: `${gx - 3}px`, top: `${bbox.bottom - 4}px`, width: '0', height: '0', borderLeft: '3px solid transparent', borderRight: '3px solid transparent', borderBottom: `4px solid ${style.down}`, pointerEvents: 'auto' })
        mark.textContent = ''
        // Exchange holidays are not known here, so the mark states the fact rather than "expected".
        const unit = calendar === 'weekday' ? 'weekday' : 'interval'
        mark.title = `${gap.missing} ${unit}${gap.missing === 1 ? '' : 's'} without an observation before ${new Date(times[gap.index] * 1000).toISOString().slice(0, 16)} UTC`
      }
    }
    marks.done()
  }

  // ---- crosshair: one vertical across every panel, horizontal + value tag on the hovered panel.
  // Persistent elements moved by transform: pointer movement never rebuilds DOM or canvas.
  const cursorTag = { position: 'absolute', left: '0', top: '0', height: '11px', lineHeight: '11px', padding: '0 2px', background: style.text, color: style.plot, whiteSpace: 'nowrap', willChange: 'transform' } as Partial<CSSStyleDeclaration>
  const cursors = panels.map(p => {
    const layer = p.layers!.cursor
    const vertical = el(layer, { position: 'absolute', left: '0', width: '0', borderLeft: `1px solid ${style.muted}`, opacity: '0.6', willChange: 'transform' })
    vertical.className = 'technical-cursor'
    const horizontal = el(layer, { position: 'absolute', top: '0', height: '0', borderTop: `1px solid ${style.muted}`, opacity: '0.6', willChange: 'transform' })
    const value = el(layer, cursorTag), date = el(layer, cursorTag)
    for (const node of [vertical, horizontal, value, date]) node.hidden = true
    return { vertical, horizontal, value, date }
  })
  const show = (node: HTMLElement, visible: boolean) => { if (node.hidden === visible) node.hidden = !visible }
  const move = (node: HTMLElement, x: number, y: number) => { const t = `translate3d(${Math.round(x)}px,${Math.round(y)}px,0)`; if (node.style.transform !== t) node.style.transform = t }
  const drawCursor = () => panels.forEach((p, k) => {
    const c = cursors[k], frame = p.view!.frame, bbox = frame.bbox
    const cx = cursorIndex === null ? NaN : frame.x_scale.compute(cursorIndex)
    const visible = crosshairOn && Number.isFinite(cx) && cx >= bbox.left && cx <= bbox.right
    show(c.vertical, visible)
    if (visible) { c.vertical.style.height = `${bbox.height}px`; move(c.vertical, cx, bbox.top) }
    const level = visible && hover?.panel === p
    show(c.horizontal, level); show(c.value, level)
    if (level) {
      const cy = frame.y_scale.compute(hover!.y)
      c.horizontal.style.width = `${bbox.width}px`; move(c.horizontal, bbox.left, cy)
      c.value.textContent = hover!.y.toFixed(p.kind === 'price' ? pd : p.decimals); move(c.value, bbox.right + 1, cy - 6)
    }
    show(c.date, visible && p.dateAxis)
    if (visible && p.dateAxis) {
      const label = new Date(times[cursorIndex!] * 1000).toISOString().slice(0, intraday ? 16 : 10).replace('T', ' ')
      if (c.date.textContent !== label) c.date.textContent = label
      move(c.date, cx - label.length * 3.3, bbox.bottom + 3)
    }
  })
  let shownIndex: number | null | undefined
  const setCursor = (i: number | null, notify = true) => {
    cursorIndex = i === null || i < 0 || i >= n ? null : i
    drawCursor()
    if (cursorIndex === shownIndex) return
    shownIndex = cursorIndex
    updateLegends(cursorIndex ?? lastIndex())
    if (notify) options.onCursor(cursorIndex)
  }
  for (const p of panels) {
    p.fig.on_event(MouseMove, event => {
      const i = Math.round(event.x)
      hover = { panel: p, y: event.y }
      setCursor(i)
      options.registry?.publish(options.panelId, 'cursor', ...(cursorIndex === null ? [] : [times[cursorIndex]]))
    })
    p.fig.on_event(MouseLeave, () => { hover = null; setCursor(null); options.registry?.publish(options.panelId, 'cursor') })
  }
  price.fig.on_event(RangesUpdate, () => publishRange())
  node.dataset.nativeLod = 'idle'
  price.fig.on_event(LODStart, () => { node.dataset.nativeLod = 'active' })
  price.fig.on_event(LODEnd, () => { node.dataset.nativeLod = 'idle' })
  const publishRange = () => { const r = visibleUTC(); if (r) options.registry?.publish(options.panelId, 'range', r[0], r[1]) }
  for (const p of panels) p.view!.repainted.connect(() => { drawMarks(p); drawCursor() })
  for (const p of panels) drawMarks(p)
  setCursor(null, false)
  // The visible window as the UTC times of its first and last whole observations.
  // Observations whose centre lies in the window; the tolerance absorbs linked ranges' 1e-6 insets.
  const visibleUTC = (): [number, number] | null => { const lo = Math.max(0, Math.ceil(x.start - 1e-3)), hi = Math.min(n - 1, Math.floor(x.end + 1e-3)); return hi >= lo ? [times[lo], times[hi]] : null }
  const stampRange = () => { const r = visibleUTC(); node.dataset.visibleRange = r ? JSON.stringify({ from: r[0], to: r[1] }) : '' }
  x.change.connect(stampRange); stampRange()

  unregister = options.registry?.register(options.panelId, {
    range(from, to) { const logical = logicalRangeForUTC(times, from, to); if (logical) { column.document?.interactive_start(price.fig); x.setv({ start: logical.from, end: logical.to }) } },
    cursor(time) { hover = null; setCursor(time === null ? null : indexOf.get(time) ?? null) },
  })

  // ---- resize: keep the observation window, recompute frames after an 80 ms quiet period
  let resizeTimer: ReturnType<typeof setTimeout> | undefined
  let size = [width, height]
  const resize = () => {
    const w = Math.max(320, node.clientWidth), h = Math.max(200, node.clientHeight)
    if (w === size[0] && h === size[1]) return
    size = [w, h]
    const hs = panelHeights(h - strips * DATE_STRIP - 2, studies.length)
    for (const p of panels) { p.frameHeight = p.kind === 'price' ? hs.price : hs.study; p.fig.setv({ frame_width: w - LEFT - RIGHT, frame_height: p.frameHeight }) }
    frameWidth = w - LEFT - RIGHT
    for (const view of views) view.invalidate_layout()
    mounted.view.invalidate_layout()
    autoscale()
  }
  observer = new ResizeObserver(() => { clearTimeout(resizeTimer); cancelChartResize(resize); resizeTimer = setTimeout(() => scheduleChartResize(resize), 80) })
  observer.observe(node)

  // A recomposition restores a window that already carries the toolbar zoom; only later steps apply.
  let zoom = restored ? options.initialZoom ?? 0 : 0
  return {
    controls(next: ChartControls) {
      wick.visible = next.type !== 'line'; body.visible = next.type === 'candles'
      openTick.visible = closeTick.visible = next.type === 'bars'; closeLine.visible = next.type === 'line'
      for (const p of panels) for (const grid of p.fig.grid) grid.visible = next.grid
      for (const grid of monthGrids) grid.visible = next.grid
      crosshairOn = next.crosshair; drawCursor()
      const delta = next.zoom - zoom
      if (delta) { const span = (x.end - x.start) / Math.pow(1.35, delta); x.setv({ start: x.end - span, end: x.end }); publishRange() }
      zoom = next.zoom
      for (const p of panels) drawMarks(p)
    },
    evidence(markersIn: readonly EvidenceMarker[], selected: number | null, select?: (sequence: number) => void) {
      onSelect = select
      const valid = markersIn.filter(e => indexOf.has(e.barTs))
      events.data = { x: valid.map(e => indexOf.get(e.barTs)!), y: valid.map(e => closes[indexOf.get(e.barTs)!]), sequence: valid.map(e => e.sequenceId), label: valid.map(e => e.label), color: valid.map(e => e.tone === 'negative' ? style.evidenceDown : style.evidenceUp), size: valid.map(e => e.sequenceId === selected ? 12 : 7) }
    },
    range(from: number, to: number) { const logical = logicalRangeForUTC(times, from, to); if (!logical) return; x.setv({ start: logical.from, end: logical.to }); publishRange() },
    fit() { x.setv({ start: -0.5, end: n - 0.5 + 2 }); publishRange() },
    visibleUTC,
    async png(header: string[] = []): Promise<Blob> {
      return technicalPng(await mounted.view.export('png').to_blob(), mounted.view.el,
        panels.flatMap(p => [p.layers!.legend, p.layers!.marks]), header, style)
    },
    undrawnAnnotations: undrawn,
    destroy() { cancelAnimationFrame(scaleFrame); unregister?.(); clearTimeout(resizeTimer); cancelChartResize(resize); observer?.disconnect(); mounted.destroy(); mounted.view.el.remove() },
  }
  } catch (error) {
    // Fail loud, but release the shown document, observers and links first.
    cancelAnimationFrame(scaleFrame); unregister?.(); observer?.disconnect(); mounted.destroy(); mounted.view.el.remove()
    throw error
  }
}

export type TechnicalChartController = Awaited<ReturnType<typeof mountTechnicalChart>>

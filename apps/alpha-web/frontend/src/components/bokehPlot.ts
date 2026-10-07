import { figure } from '@bokeh/bokehjs/build/js/lib/api/figure'
import { showScientificPlot } from './bokehLifecycle'
import { scheduleChartResize, cancelChartResize } from './chartResize'
import { ColumnDataSource } from '@bokeh/bokehjs/build/js/lib/models/sources/column_data_source'
import { Range1d } from '@bokeh/bokehjs/build/js/lib/models/ranges/range1d'
import { HoverTool } from '@bokeh/bokehjs/build/js/lib/models/tools/inspectors/hover_tool'
import { MouseMove, MouseLeave, RangesUpdate, LODStart, LODEnd } from '@bokeh/bokehjs/build/js/lib/core/bokeh_events'
import type { Candle, ChartAnnotation } from '../api/types'
import type { EvidenceMarker } from '../panels/v3Models'
import { nearestTimestamp, plotBounds, scientificValues, type ScientificPoint } from './scientificPlotModel'
import type { ChartControls } from '../context/chartControls'
import type { ChartLinkRegistry } from '../shell/chartLinkRegistry'
/** Local BokehJS, no report HTML, CDN, Python execution or statistical calculations. */
export async function mountBokehPlot(node: HTMLElement, unit: string, panelId: string, registry: ChartLinkRegistry | undefined, readout: (text: string, bar?: Candle) => void, area: boolean) {
  const x = new Range1d({ start: 0, end: 1 }), y = new Range1d({ start: 0, end: 1 })
  const source = new ColumnDataSource({ data: { x: [], y: [] } })
  const plot = figure({ x_range: x, y_range: y, x_axis_type: 'datetime', x_axis_label: 'Time (UTC)', y_axis_label: unit.length > 50 ? 'Value (recorded units; see legend)' : unit, tools: 'pan,wheel_zoom,box_zoom,reset,save', active_scroll: 'wheel_zoom', toolbar_location: 'above', width: Math.max(250, node.clientWidth), height: Math.max(100, node.clientHeight), background_fill_color: '#fafafa', border_fill_color: '#fafafa', outline_line_color: '#777', min_border: 8 })
  plot.axis.axis_label_text_font_size = '10px'; plot.axis.major_label_text_font_size = '10px'; plot.axis.axis_label_text_font_style = 'normal'
  plot.axis.major_label_text_font = 'JetBrains Mono Variable'; plot.axis.axis_label_text_color = '#333'; plot.axis.major_label_text_color = '#444'
  plot.grid.grid_line_color = '#dedede'; plot.grid.grid_line_width = .5
  const line = plot.line({ field: 'x' }, { field: 'y' }, { source, line_color: area ? '#b44b48' : '#326c9e', line_width: 1.2 })
  const emptyCandles = () => ({ x: [], open: [], close: [], high: [], low: [], color: [], width: [], left: [], right: [] })
  const candles = new ColumnDataSource({ data: emptyCandles() })
  const wick = plot.segment({ field: 'x' }, { field: 'low' }, { field: 'x' }, { field: 'high' }, { source: candles, line_color: '#555', line_width: 1 })
  const body = plot.vbar({ field: 'x' }, { field: 'width' }, { field: 'close' }, { field: 'open' }, { source: candles, fill_color: { field: 'color' }, line_color: { field: 'color' } })
  const opens = plot.segment({ field: 'left' }, { field: 'open' }, { field: 'x' }, { field: 'open' }, { source: candles, line_color: { field: 'color' } })
  const closes = plot.segment({ field: 'x' }, { field: 'close' }, { field: 'right' }, { field: 'close' }, { source: candles, line_color: { field: 'color' } })
  wick.visible = body.visible = opens.visible = closes.visible = false
  const events = new ColumnDataSource({ data: { x: [], y: [], label: [], sequence: [], color: [], size: [] } })
  const markers = plot.scatter({ field: 'x' }, { field: 'y' }, { source: events, size: { field: 'size' }, fill_color: { field: 'color' }, line_color: '#333', marker: 'diamond' })
  plot.add_tools(new HoverTool({ renderers: [markers], tooltips: [['Evidence', '@label'], ['Sequence', '@sequence']] }))
  plot.add_tools('tap')
  let onSelect: ((sequence: number) => void) | undefined
  events.selected.change.connect(() => { const index = events.selected.indices[0]; if (index !== undefined) onSelect?.((events.get_column('sequence') as number[])[index]) })
  const shapes = new ColumnDataSource({ data: { xs: [], ys: [] } })
  plot.multi_line({ field: 'xs' }, { field: 'ys' }, { source: shapes, line_color: '#8b7636', line_width: 1, line_dash: 'dashed' })
  if (area) plot.varea({ field: 'x' }, 0, { field: 'y' }, { source, fill_color: '#b44b48', fill_alpha: .17 })
  let cursorTime: number | null = null
  let drawCursor = () => {}
  let points: readonly ScientificPoint[] = [], times: number[] = [], zoom = 0, enabled = true, chartType: ChartControls['type'] = 'line', marketBars: readonly Candle[] = []
  const values = new Map<number, number | null>()
  const barsByTime = new Map<number, Candle>()
  const updateCandles = () => {
    if (chartType === 'line') { candles.data = emptyCandles(); return }
    const bars = marketBars, width = Math.max(1, bars.length > 1 ? (bars[1].t - bars[0].t) * 600 : 600)
    candles.data = { x: bars.map(b => b.t * 1000), open: bars.map(b => b.o), close: bars.map(b => b.c), high: bars.map(b => b.h), low: bars.map(b => b.l), color: bars.map(b => b.c >= b.o ? '#467b5e' : '#aa5651'), width: bars.map(() => width), left: bars.map(b => b.t * 1000 - width / 2), right: bars.map(b => b.t * 1000 + width / 2) }
  }
  const fit = () => { const bounds = plotBounds(marketBars.length ? marketBars.flatMap(b => [{ time: b.t, value: b.l }, { time: b.t, value: b.h }]) : points); x.setv({ start: bounds.x[0], end: bounds.x[1], reset_start: bounds.x[0], reset_end: bounds.x[1] }); y.setv({ start: bounds.y[0], end: bounds.y[1], reset_start: bounds.y[0], reset_end: bounds.y[1] }) }
  const setCursor = (time: number | null) => {
    const value = time === null ? null : values.get(time)
    cursorTime = enabled && time !== null && value != null ? time : null
    drawCursor()
    const bar = time === null ? undefined : barsByTime.get(time)
    const text = time !== null && value != null ? `${new Date(time * 1000).toISOString()} · ${value.toPrecision(7)} ${unit}` : 'Cursor —'
    if (bar) readout(text, bar); else readout(text)
  }
  plot.on_event(MouseMove, event => { const time = enabled ? nearestTimestamp(times, event.x / 1000) : null; setCursor(time); registry?.publish(panelId, 'cursor', ...(time === null ? [] : [time])) })
  plot.on_event(MouseLeave, () => { setCursor(null); registry?.publish(panelId, 'cursor') })
  plot.on_event(RangesUpdate, event => registry?.publish(panelId, 'range', event.x0 / 1000, event.x1 / 1000))
  node.dataset.nativeLod = 'idle'
  plot.on_event(LODStart, () => { node.dataset.nativeLod = 'active' })
  plot.on_event(LODEnd, () => { node.dataset.nativeLod = 'idle' })
  const mounted = await showScientificPlot(plot, node)
  // Cursor movement must not upload another canvas texture for each linked plot.
  // Use Bokeh's current frame/scale for a transient DOM overlay; series stay native.
  const cursor = node.ownerDocument.createElement('div')
  cursor.className = 'scientific-cursor'
  Object.assign(cursor.style, { position: 'absolute', width: '0', borderLeft: '1px dashed #888', pointerEvents: 'none', willChange: 'transform' })
  mounted.view.canvas_view.overlays_el.append(cursor)
  drawCursor = () => {
    const frame = mounted.view.frame, bbox = frame.bbox
    const sx = cursorTime === null ? NaN : frame.x_scale.compute(cursorTime * 1000)
    const hidden = !Number.isFinite(sx) || sx < bbox.left || sx > bbox.right
    if (cursor.hidden !== hidden) cursor.hidden = hidden
    if (!hidden) {
      const transform = `translate3d(${sx}px,0,0)`, top = `${bbox.top}px`, height = `${bbox.height}px`
      if (cursor.style.transform !== transform) cursor.style.transform = transform
      if (cursor.style.top !== top) cursor.style.top = top
      if (cursor.style.height !== height) cursor.style.height = height
    }
  }
  mounted.view.repainted.connect(drawCursor)
  drawCursor()
  let unregister: (() => void) | undefined
  const activate = () => { unregister ??= registry?.register(panelId, { range(from, to) { if (times.length && from <= to && to >= times[0] && from <= times.at(-1)!) { plot.document?.interactive_start(plot); x.setv({ start: from * 1000, end: to * 1000 }) } }, cursor: setCursor }) }
  x.change.connect(() => { node.dataset.visibleRange = JSON.stringify({ from: x.start / 1000, to: x.end / 1000 }) })
  // Coalesce splitter movement: Bokeh relayouts axes on every size change.
  // Keep the canvas and ranges, then render the latest dimensions after an 80 ms quiet period.
  let resizeTimer: ReturnType<typeof setTimeout> | undefined
  const resize = () => {
    if (!node.clientWidth || !node.clientHeight) return
    const width = Math.max(250, node.clientWidth), height = Math.max(100, node.clientHeight)
    if (plot.width === width && plot.height === height) return
    plot.document?.interactive_start(plot)
    plot.setv({ width, height })
  }
  const observer = new ResizeObserver(() => {
    clearTimeout(resizeTimer); cancelChartResize(resize)
    resizeTimer = setTimeout(() => scheduleChartResize(resize), 80)
  }); observer.observe(node)
  return {
    activate,
    data(next: readonly ScientificPoint[]) { points = next; times = next.map(p => p.time); values.clear(); for (const p of next) values.set(p.time, p.value); source.data = scientificValues(next); fit() },
    market(bars: readonly Candle[], evidence: readonly EvidenceMarker[], annotations: readonly ChartAnnotation[], selected: number | null, select?: (sequence: number) => void) {
      const changed = marketBars !== bars; marketBars = bars; onSelect = select
      if (changed) { barsByTime.clear(); for (const bar of bars) barsByTime.set(bar.t, bar); updateCandles() }
      const byTime = values; const valid = evidence.filter(e => byTime.has(e.barTs))
      events.data = { x: valid.map(e => e.barTs * 1000), y: valid.map(e => byTime.get(e.barTs)!), sequence: valid.map(e => e.sequenceId), label: valid.map(e => e.label), color: valid.map(e => e.tone === 'negative' ? '#aa5651' : '#467b5e'), size: valid.map(e => e.sequenceId === selected ? 13 : 7) }
      const priceAnnotations = annotations.filter(a => a.unit === 'price' && a.anchors.length >= 2)
      shapes.data = { xs: priceAnnotations.map(a => a.anchors.map(p => p.ts * 1000)), ys: priceAnnotations.map(a => a.anchors.map(p => p.value)) }
      if (changed) fit()
    },
    controls(c: ChartControls) { if (c.type !== chartType) { chartType = c.type; updateCandles() }; plot.grid.visible = c.grid; enabled = c.crosshair; if (!enabled) setCursor(null); if (marketBars.length) { line.visible = c.type === 'line'; wick.visible = c.type !== 'line'; body.visible = c.type === 'candles'; opens.visible = closes.visible = c.type === 'bars' }; const delta = c.zoom - zoom; if (delta) { const mid = (x.start + x.end) / 2, half = (x.end - x.start) / 2 / Math.pow(1.35, delta); x.setv({ start: mid - half, end: mid + half }); registry?.publish(panelId, 'range', x.start / 1000, x.end / 1000) }; zoom = c.zoom },
    range(from: number, to: number) { if (!Number.isFinite(from) || !Number.isFinite(to) || from >= to) return; x.setv({ start: from * 1000, end: to * 1000 }); registry?.publish(panelId, 'range', from, to) },
    fitLinked() { fit(); registry?.publish(panelId, 'range', x.start / 1000, x.end / 1000) },
    fit,
    destroy() { mounted.view.repainted.disconnect(drawCursor); cursor.remove(); unregister?.(); clearTimeout(resizeTimer); cancelChartResize(resize); observer.disconnect(); mounted.destroy(); mounted.view.el.remove() },
  }
}

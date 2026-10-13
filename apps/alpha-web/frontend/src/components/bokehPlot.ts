import { figure } from '@bokeh/bokehjs/build/js/lib/api/figure'
import { showScientificPlot } from './bokehLifecycle'
import { scheduleChartResize, cancelChartResize } from './chartResize'
import { ColumnDataSource } from '@bokeh/bokehjs/build/js/lib/models/sources/column_data_source'
import { Range1d } from '@bokeh/bokehjs/build/js/lib/models/ranges/range1d'
import { SaveTool, SaveToolView } from '@bokeh/bokehjs/build/js/lib/models/tools/actions/save_tool'
import { DatetimeTickFormatter } from '@bokeh/bokehjs/build/js/lib/models/formatters/datetime_tick_formatter'
import { MouseMove, MouseLeave, RangesUpdate, LODStart, LODEnd } from '@bokeh/bokehjs/build/js/lib/core/bokeh_events'
import { nearestTimestamp, plotBounds, scientificValues, type ScientificPoint } from './scientificPlotModel'
import type { ChartControls } from '../context/chartControls'
import type { ChartLinkRegistry } from '../shell/chartLinkRegistry'
import { styleTechnicalAxes, tagStyle, technicalFigureAttrs } from './technical/technicalChrome'
import { padExtent, visibleExtent } from './technical/technicalModel'
import { technicalStyle, type ChartStyleName } from './technical/technicalTokens'
import { technicalPng } from './technical/technicalExport'
/** Local BokehJS recorded time series in the technical chart language; no statistics computed. */
export async function mountBokehPlot(node: HTMLElement, unit: string, panelId: string, registry: ChartLinkRegistry | undefined, readout: (text: string) => void, area: boolean, styleName: ChartStyleName = 'classic') {
  const style = technicalStyle(styleName)
  const x = new Range1d({ start: 0, end: 1 }), y = new Range1d({ start: 0, end: 1 })
  const source = new ColumnDataSource({ data: { x: [], y: [] } })
  // Keep Bokeh's native Save/Copy/Open menu and filename prompt; only its exported image changes.
  class RecordedSaveView extends SaveToolView {
    protected override async _export(): Promise<Blob> {
      return technicalPng(await super._export(), this.parent.el, [tags], [], style)
    }
  }
  const save = new SaveTool()
  save.default_view = RecordedSaveView
  const plot = figure({ ...technicalFigureAttrs(style), x_range: x, y_range: y, x_axis_type: 'datetime', tools: 'xpan,xwheel_zoom,reset', active_drag: 'xpan' as never, active_scroll: 'xwheel_zoom' as never, toolbar_location: 'above', toolbar_inner: true, width: Math.max(250, node.clientWidth), height: Math.max(100, node.clientHeight) })
  plot.add_tools(save)
  // Reset and PNG save stay available on an inner toolbar shown only on hover (no reserved chrome).
  plot.toolbar.autohide = true
  styleTechnicalAxes(plot, style)
  for (const axis of plot.xaxis) axis.formatter = new DatetimeTickFormatter({ days: '%d', months: '%b', years: '%Y' })
  const color = area ? style.down : style.studies[0]
  plot.line({ field: 'x' }, { field: 'y' }, { source, line_color: color, line_width: 1 })
  if (area) plot.varea({ field: 'x' }, 0, { field: 'y' }, { source, fill_color: color, fill_alpha: .14 })
  let cursorTime: number | null = null
  let drawCursor = () => {}
  let points: readonly ScientificPoint[] = [], times: number[] = [], values: (number | null)[] = [], zoom = 0, enabled = true
  const valueAt = new Map<number, number | null>()
  // Tag precision from the whole recorded range, computed once per data() rather than per repaint.
  let decimals = 2
  const decimalsFor = () => { const extent = visibleExtent([values], 0, values.length - 1); return extent ? Math.max(2, Math.min(6, 3 - Math.floor(Math.log10(Math.max(1e-12, Math.abs(extent[1] - extent[0])))))) : 2 }
  const fit = () => { const bounds = plotBounds(points); x.setv({ start: bounds.x[0], end: bounds.x[1], reset_start: bounds.x[0], reset_end: bounds.x[1] }); y.setv({ start: bounds.y[0], end: bounds.y[1], reset_start: bounds.y[0], reset_end: bounds.y[1] }) }
  // Full-height autoscale over the visible observations, like the price stack.
  const lower = (t: number) => { let lo = 0, hi = times.length; while (lo < hi) { const mid = (lo + hi) >>> 1; if (times[mid] < t) lo = mid + 1; else hi = mid } return lo }
  /** Index of the last observation at or before `t` (seconds); -1 when none. */
  const lastAtOrBefore = (t: number) => lower(t + 1e-6) - 1
  let scaleFrame = 0
  const autoscale = () => { scaleFrame = 0; const extent = visibleExtent([values], lower(x.start / 1000), lastAtOrBefore(x.end / 1000)); if (extent) { const [lo, hi] = padExtent(area ? [Math.min(0, extent[0]), Math.max(0, extent[1])] : extent, 0.06); y.setv({ start: lo, end: hi }) } }
  x.change.connect(() => { if (!scaleFrame) scaleFrame = requestAnimationFrame(autoscale) })
  const setCursor = (time: number | null) => {
    const value = time === null ? null : valueAt.get(time)
    cursorTime = enabled && time !== null && value != null ? time : null
    drawCursor()
    readout(time !== null && value != null ? `${new Date(time * 1000).toISOString()} · ${value.toPrecision(7)} ${unit}` : 'Cursor —')
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
  Object.assign(cursor.style, { position: 'absolute', width: '0', borderLeft: `1px solid ${style.muted}`, opacity: '0.6', pointerEvents: 'none', willChange: 'transform' })
  const tags = node.ownerDocument.createElement('div')
  mounted.view.canvas_view.overlays_el.append(cursor, tags)
  // One persistent tag: a repaint moves it and updates its text, never rebuilds DOM.
  const tag = node.ownerDocument.createElement('div')
  tag.className = 'technical-tag'
  Object.assign(tag.style, tagStyle(style, 0, 0, color))
  tag.hidden = true
  tags.append(tag)
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
  // Last visible recorded value as a right-axis tag.
  const drawTag = () => {
    let v: number | null = null
    for (let i = Math.min(values.length - 1, lastAtOrBefore(x.end / 1000)); i >= 0; i--) { const value = values[i]; if (value !== null && Number.isFinite(value)) { v = value; break } }
    if (tag.hidden !== (v === null)) tag.hidden = v === null
    if (v === null) return
    const frame = mounted.view.frame, left = `${frame.bbox.right + 1}px`, top = `${frame.y_scale.compute(v) - 6}px`, text = v.toFixed(decimals)
    if (tag.style.left !== left) tag.style.left = left
    if (tag.style.top !== top) tag.style.top = top
    if (tag.textContent !== text) tag.textContent = text
  }
  const repaint = () => { drawCursor(); drawTag() }
  mounted.view.repainted.connect(repaint)
  repaint()
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
    data(next: readonly ScientificPoint[]) { points = next; times = next.map(p => p.time); values = next.map(p => p.value); decimals = decimalsFor(); valueAt.clear(); for (const p of next) valueAt.set(p.time, p.value); source.data = scientificValues(next); fit() },
    controls(c: ChartControls) { plot.grid.visible = c.grid; enabled = c.crosshair; if (!enabled) setCursor(null); const delta = c.zoom - zoom; if (delta) { const mid = (x.start + x.end) / 2, half = (x.end - x.start) / 2 / Math.pow(1.35, delta); x.setv({ start: mid - half, end: mid + half }); registry?.publish(panelId, 'range', x.start / 1000, x.end / 1000) }; zoom = c.zoom },
    range(from: number, to: number) { if (!Number.isFinite(from) || !Number.isFinite(to) || from >= to) return; x.setv({ start: from * 1000, end: to * 1000 }); registry?.publish(panelId, 'range', from, to) },
    fitLinked() { fit(); registry?.publish(panelId, 'range', x.start / 1000, x.end / 1000) },
    fit,
    destroy() { cancelAnimationFrame(scaleFrame); mounted.view.repainted.disconnect(repaint); cursor.remove(); tags.remove(); unregister?.(); clearTimeout(resizeTimer); cancelChartResize(resize); observer.disconnect(); mounted.destroy(); mounted.view.el.remove() },
  }
}

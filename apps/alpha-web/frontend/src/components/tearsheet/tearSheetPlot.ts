import type { ChartPalette } from '../../theme/themes'
import { figure } from '@bokeh/bokehjs/build/js/lib/api/figure'
import { gridplot } from '@bokeh/bokehjs/build/js/lib/api/gridplot'
import { ColumnDataSource } from '@bokeh/bokehjs/build/js/lib/models/sources/column_data_source'
import { Range1d } from '@bokeh/bokehjs/build/js/lib/models/ranges/range1d'
import { DataRange1d } from '@bokeh/bokehjs/build/js/lib/models/ranges/data_range1d'
import { Span } from '@bokeh/bokehjs/build/js/lib/models/annotations/span'
import { BoxAnnotation } from '@bokeh/bokehjs/build/js/lib/models/annotations/box_annotation'
import { SaveTool, SaveToolView } from '@bokeh/bokehjs/build/js/lib/models/tools/actions/save_tool'
import { MouseMove, MouseLeave } from '@bokeh/bokehjs/build/js/lib/core/bokeh_events'
import { showScientificPlot } from '../bokehLifecycle'
import { styleTechnicalAxes, technicalFigureAttrs } from '../technical/technicalChrome'
import { technicalStyle, type ChartStyleName } from '../technical/technicalTokens'
import { technicalPng } from '../technical/technicalExport'
import type { Band, Stack } from './tearSheetModel'

export interface TearSheetMount {
  /** Visible x window in ms; kept across a remount. */
  window(): [number, number]
  destroy(): void
}

const HEIGHTS = { price: 220, equity: 180, drawdown: 120 }

function bandFill(kind: Band['kind'], index: number, style: ReturnType<typeof technicalStyle>) {
  if (kind === 'tradable') return { color: style.muted, alpha: 0.07 }
  if (kind === 'scored') return { color: style.link, alpha: 0.09 }
  return { color: style.studies[3], alpha: index % 2 ? 0.07 : 0.13 }
}

/** One BokehJS grid: price, equity vs buy and hold, drawdown; one x-range, one linked crosshair. */
export async function mountTearSheet(
  node: HTMLElement, stack: Stack, styleName: ChartStyleName, colors: ChartPalette,
  onMove: (seconds: number | null) => void, initial: [number, number] | null,
): Promise<TearSheetMount> {
  const style = technicalStyle(styleName, colors)
  const times = stack.equity.x
  const full: [number, number] = [times[0], times[times.length - 1]]
  const start = initial ?? full
  const x = new Range1d({ start: start[0], end: start[1], reset_start: full[0], reset_end: full[1] })
  class RecordedSaveView extends SaveToolView {
    protected override async _export(): Promise<Blob> {
      return technicalPng(await super._export(), this.parent.el, [], [], style)
    }
  }
  const save = new SaveTool()
  save.default_view = RecordedSaveView
  const cursors: Span[] = []
  const make = (height: number, logY: boolean, bottom: boolean) => {
    const plot = figure({
      ...technicalFigureAttrs(style), x_range: x, y_range: new DataRange1d({ only_visible: true, range_padding: 0.06 }),
      x_axis_type: 'datetime', y_axis_type: logY ? 'log' : 'linear',
      tools: 'xpan,xwheel_zoom,box_zoom,reset', active_drag: 'xpan' as never, active_scroll: 'xwheel_zoom' as never,
      height, sizing_mode: 'stretch_width', min_border_bottom: bottom ? 24 : 2,
    })
    styleTechnicalAxes(plot, style)
    plot.xaxis.visible = bottom
    const cursor = new Span({ dimension: 'height', location: 0, visible: false, line_color: style.muted, line_width: 1, line_alpha: 0.7 })
    plot.add_layout(cursor)
    cursors.push(cursor)
    plot.on_event(MouseMove, event => {
      for (const c of cursors) { c.location = event.x; c.visible = true }
      onMove(event.x / 1000)
    })
    plot.on_event(MouseLeave, () => { for (const c of cursors) c.visible = false; onMove(null) })
    stack.bands.forEach((band, index) => {
      const fill = bandFill(band.kind, index, style)
      plot.add_layout(new BoxAnnotation({ left: band.from, right: band.to, fill_color: fill.color, fill_alpha: fill.alpha, line_alpha: 0, level: 'underlay' }))
    })
    return plot
  }
  const top = stack.price ? make(HEIGHTS.price, false, false) : null
  if (top && stack.price) {
    const source = new ColumnDataSource({ data: { x: stack.price.x, y: stack.price.close } })
    top.line({ field: 'x' }, { field: 'y' }, { source, line_color: style.text, line_width: 1 })
    for (const span of stack.held) top.add_layout(new BoxAnnotation({ left: span.from, right: span.to, fill_color: style.up, fill_alpha: 0.12, line_alpha: 0, level: 'underlay' }))
    const entries = new ColumnDataSource({ data: { ...stack.entries } }), exits = new ColumnDataSource({ data: { ...stack.exits } })
    top.scatter({ field: 'x' }, { field: 'y' }, { source: entries, marker: 'triangle', size: 9, fill_color: style.up, line_color: style.canvas })
    top.scatter({ field: 'x' }, { field: 'y' }, { source: exits, marker: 'inverted_triangle', size: 9, fill_color: style.down, line_color: style.canvas })
  }
  const equity = make(HEIGHTS.equity, stack.logScale, false)
  equity.line({ field: 'x' }, { field: 'y' }, { source: new ColumnDataSource({ data: { ...stack.equity } }), line_color: style.studies[0], line_width: 1.5 })
  if (stack.benchmark) equity.line({ field: 'x' }, { field: 'y' }, { source: new ColumnDataSource({ data: { ...stack.benchmark } }), line_color: style.muted, line_width: 1 })
  const drawdown = make(HEIGHTS.drawdown, false, true)
  drawdown.varea({ field: 'x' }, 0, { field: 'y' }, { source: new ColumnDataSource({ data: { ...stack.drawdown } }), fill_color: style.down, fill_alpha: 0.3 })
  drawdown.line({ field: 'x' }, { field: 'y' }, { source: new ColumnDataSource({ data: { ...stack.drawdown } }), line_color: style.down, line_width: 1 })
  const panes = [top, equity, drawdown].filter((pane): pane is NonNullable<typeof top> => pane !== null)
  panes[0].add_tools(save)
  const grid = gridplot(panes.map(pane => [pane]), { toolbar_location: 'above', merge_tools: true, sizing_mode: 'stretch_width' })
  const mounted = await showScientificPlot(grid, node)
  return {
    window: () => [x.start, x.end],
    destroy() { mounted.destroy(); mounted.view.el.remove() },
  }
}

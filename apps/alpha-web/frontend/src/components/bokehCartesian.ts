import { figure } from '@bokeh/bokehjs/build/js/lib/api/figure'
import { ColumnDataSource } from '@bokeh/bokehjs/build/js/lib/models/sources/column_data_source'
import { HoverTool } from '@bokeh/bokehjs/build/js/lib/models/tools/inspectors/hover_tool'
import { showScientificPlot } from './bokehLifecycle'
import { styleTechnicalAxes, technicalFigureAttrs } from './technical/technicalChrome'
import { technicalStyle, type ChartStyleName } from './technical/technicalTokens'
export interface ScientificRow { x: number; y: number; right?: number }
/** Backend-authored bins and quantiles; midpoint/width are display coordinates only. */
export async function mountCartesian(node: HTMLElement, rows: ScientificRow[], xLabel: string, yLabel: string, bars: boolean, styleName: ChartStyleName = 'classic') {
  const style = technicalStyle(styleName)
  // Axis titles stay: they carry the units of the backend bins and quantiles.
  // These plots have no workspace Fit/reset, so reset and PNG save stay on an inner toolbar that
  // only appears on hover: no reserved chrome, no layout change.
  const plot = figure({ ...technicalFigureAttrs(style), x_axis_label: xLabel, y_axis_label: yLabel, tools: 'pan,wheel_zoom,box_zoom,reset,save', active_scroll: 'wheel_zoom', toolbar_location: 'above', toolbar_inner: true, width: Math.max(250, node.clientWidth), height: 270 })
  plot.toolbar.autohide = true
  styleTechnicalAxes(plot, style)
  const source = new ColumnDataSource({ data: { x: rows.map(p => bars ? (p.x + (p.right ?? p.x)) / 2 : p.x), left: rows.map(p => p.x), right: rows.map(p => p.right ?? p.x), width: rows.map(p => (p.right ?? p.x) - p.x), y: rows.map(p => p.y) } })
  const glyph = bars ? plot.vbar({ field: 'x' }, { field: 'width' }, { field: 'y' }, 0, { source, fill_color: style.histFill, line_color: style.histEdge, line_width: 1 }) : plot.scatter({ field: 'x' }, { field: 'y' }, { source, size: 4, fill_color: style.studies[0], line_color: null })
  plot.add_tools(new HoverTool({ renderers: [glyph], tooltips: bars ? [['Left boundary', '@left'], ['Right boundary', '@right'], [yLabel, '@y']] : [[xLabel, '@x'], [yLabel, '@y']] }))
  const mounted = await showScientificPlot(plot, node)
  const observer = new ResizeObserver(() => { if (node.clientWidth) plot.width = Math.max(250, node.clientWidth) }); observer.observe(node)
  return () => { observer.disconnect(); mounted.destroy(); mounted.view.el.remove() }
}

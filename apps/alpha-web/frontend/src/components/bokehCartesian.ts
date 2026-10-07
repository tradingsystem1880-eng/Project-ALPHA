import { figure } from '@bokeh/bokehjs/build/js/lib/api/figure'
import { ColumnDataSource } from '@bokeh/bokehjs/build/js/lib/models/sources/column_data_source'
import { HoverTool } from '@bokeh/bokehjs/build/js/lib/models/tools/inspectors/hover_tool'
import { showScientificPlot } from './bokehLifecycle'
export interface ScientificRow { x: number; y: number; right?: number }
/** Backend-authored bins and quantiles; midpoint/width are display coordinates only. */
export async function mountCartesian(node: HTMLElement, rows: ScientificRow[], xLabel: string, yLabel: string, bars: boolean) {
  const plot = figure({ x_axis_label: xLabel, y_axis_label: yLabel, tools: 'pan,wheel_zoom,box_zoom,reset,save', active_scroll: 'wheel_zoom', width: Math.max(250, node.clientWidth), height: 270, toolbar_location: 'above', background_fill_color: '#fafafa', border_fill_color: '#fafafa', outline_line_color: '#777' })
  plot.axis.axis_label_text_font_size = '10px'; plot.axis.major_label_text_font_size = '10px'; plot.axis.axis_label_text_font_style = 'normal'; plot.grid.grid_line_color = '#dedede'
  const source = new ColumnDataSource({ data: { x: rows.map(p => bars ? (p.x + (p.right ?? p.x)) / 2 : p.x), left: rows.map(p => p.x), right: rows.map(p => p.right ?? p.x), width: rows.map(p => (p.right ?? p.x) - p.x), y: rows.map(p => p.y) } })
  const glyph = bars ? plot.vbar({ field: 'x' }, { field: 'width' }, { field: 'y' }, 0, { source, fill_color: '#326c9e', fill_alpha: .6, line_color: '#fafafa' }) : plot.scatter({ field: 'x' }, { field: 'y' }, { source, size: 4, fill_color: '#326c9e', line_color: null })
  plot.add_tools(new HoverTool({ renderers: [glyph], tooltips: bars ? [['Left boundary', '@left'], ['Right boundary', '@right'], [yLabel, '@y']] : [[xLabel, '@x'], [yLabel, '@y']] }))
  const mounted = await showScientificPlot(plot, node)
  const observer = new ResizeObserver(() => { if (node.clientWidth) plot.width = Math.max(250, node.clientWidth) }); observer.observe(node)
  return () => { observer.disconnect(); mounted.destroy(); mounted.view.el.remove() }
}

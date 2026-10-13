// Shared technical-chart chrome for every BokehJS plot that is not the price stack (recorded
// equity/drawdown/Sharpe series, histograms, QQ): no toolbar, right-hand value axis, StockCharts
// fonts, 1px grid and border, light plot surface. Same tokens as the price stack.

import type { Figure } from '@bokeh/bokehjs/build/js/lib/api/figure'
import type { TechnicalStyle } from './technicalTokens'

export function technicalFigureAttrs(style: TechnicalStyle) {
  return {
    toolbar_location: null,
    y_axis_location: 'right' as const,
    background_fill_color: style.plot,
    border_fill_color: style.canvas,
    outline_line_color: style.border,
    outline_line_width: 1,
    min_border: 6,
    // Room for the right-axis value tag, as in the price stack.
    min_border_right: 64,
  }
}

export function styleTechnicalAxes(plot: Figure, style: TechnicalStyle): void {
  plot.axis.major_label_text_font = style.font
  plot.axis.major_label_text_font_size = `${style.fontSize}px`
  plot.axis.major_label_text_color = style.text
  plot.axis.axis_label_text_font = style.font
  plot.axis.axis_label_text_font_size = `${style.fontSize}px`
  plot.axis.axis_label_text_font_style = 'normal'
  plot.axis.axis_label_text_color = style.text
  plot.axis.axis_line_color = null
  plot.axis.major_tick_line_color = style.border
  plot.axis.major_tick_in = 0
  plot.axis.major_tick_out = 3
  plot.axis.minor_tick_line_color = null
  plot.grid.grid_line_color = style.grid
  plot.grid.grid_line_width = 1
}

/** Box style of a right-axis value tag (StockCharts' current-value box), centred on `y`. */
export function tagStyle(style: TechnicalStyle, left: number, y: number, color: string, bold = false): Partial<CSSStyleDeclaration> {
  return { position: 'absolute', left: `${left}px`, top: `${y - 6}px`, height: '11px', lineHeight: '11px', padding: '0 2px', background: style.plot, border: `1px solid ${color}`, color, font: `${bold ? 'bold ' : ''}${style.fontSize}px ${style.font}`, whiteSpace: 'nowrap', pointerEvents: 'none' }
}

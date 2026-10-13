// The ALPHA technical chart language: StockCharts Classic / Default colours measured from
// reference pixels (docs/superpowers/plans/2026-10-07-technical-chart-language.md). One source for
// the Bokeh canvas and, through cssVars(), for the DOM header and legends drawn over it.

export type ChartStyleName = 'classic' | 'default'

export interface TechnicalStyle {
  name: ChartStyleName
  canvas: string
  plot: string
  /** Title band behind the chart header (Default's blue-grey band). */
  header: string
  border: string
  grid: string
  gridMonth: string
  text: string
  muted: string
  /** Header links (range buttons, Save PNG). */
  link: string
  up: string
  down: string
  volumeUp: { fill: string; edge: string }
  volumeDown: { fill: string; edge: string }
  /** Colours assigned to study series ids in order; known ids are pinned below. */
  studies: readonly string[]
  pinned: Readonly<Record<string, string>>
  rsiBand: string
  rsiOverbought: string
  rsiOversold: string
  macdLine: string
  macdSignal: string
  histFill: string
  histEdge: string
  evidenceUp: string
  evidenceDown: string
  annotation: string
  font: string
  fontSize: number
  /** Body width and OHLC tick length as fractions of one observation slot. */
  body: number
  tick: number
}

const SHARED = {
  text: '#000000',
  muted: '#606060',
  link: '#0645ad',
  rsiBand: '#707070',
  evidenceUp: '#1c7c3a',
  evidenceDown: '#d00030',
  annotation: '#8b6d00',
  font: 'Verdana, Tahoma, "DejaVu Sans", sans-serif',
  fontSize: 10,
  body: 0.7,
  tick: 0.35,
}

export const CLASSIC: TechnicalStyle = {
  ...SHARED,
  name: 'classic',
  canvas: '#ffffff',
  plot: '#ffffff',
  header: '#ffffff',
  border: '#c0c0c0',
  grid: '#e8e8e8',
  gridMonth: '#d0d0d0',
  up: '#000000',
  down: '#d00030',
  volumeUp: { fill: '#c0c0c0', edge: '#a8a8a8' },
  volumeDown: { fill: '#e8b8c0', edge: '#d8a8b0' },
  studies: ['#000088', '#d00030', '#006400', '#8b4513', '#800080', '#008b8b'],
  pinned: { 'sma:50': '#000088', 'sma:200': '#d00030', 'ema:20': '#006400', 'ema:50': '#000088' },
  rsiOverbought: '#3c6e3c',
  rsiOversold: '#7a3c3c',
  macdLine: '#000000',
  macdSignal: '#f80000',
  histFill: '#58a8d0',
  histEdge: '#206888',
}

export const DEFAULT_STYLE: TechnicalStyle = {
  ...SHARED,
  name: 'default',
  canvas: '#f1f4fa',
  plot: '#f6f7fb',
  header: '#cdd3df',
  border: '#6c6f7d',
  grid: '#e1e3e9',
  gridMonth: '#cdced5',
  up: '#000000',
  down: '#dd0000',
  volumeUp: { fill: '#b2c5b5', edge: '#95ae97' },
  volumeDown: { fill: '#d5a1b5', edge: '#c87b97' },
  studies: ['#006400', '#00008b', '#dd0000', '#8b4513', '#800080', '#008b8b'],
  pinned: { 'ema:20': '#006400', 'sma:50': '#00008b', 'sma:200': '#dd0000', 'ema:50': '#00008b' },
  rsiOverbought: '#4f7f5a',
  rsiOversold: '#8a4a5e',
  macdLine: '#000000',
  macdSignal: '#990033',
  histFill: '#93bcb7',
  histEdge: '#386760',
}

export function technicalStyle(name: ChartStyleName): TechnicalStyle {
  return name === 'default' ? DEFAULT_STYLE : CLASSIC
}

/** Colour per study spec id: pinned ids keep their StockCharts colour, the rest cycle in order. */
export function studyColors(style: TechnicalStyle, ids: readonly string[]): Map<string, string> {
  const out = new Map<string, string>()
  const used = new Set<string>()
  for (const id of ids) if (style.pinned[id] && !out.has(id)) { out.set(id, style.pinned[id]); used.add(style.pinned[id]) }
  const free = style.studies.filter(c => !used.has(c))
  let n = 0
  for (const id of ids) if (!out.has(id)) out.set(id, free.length ? free[n++ % free.length] : style.studies[n++ % style.studies.length])
  return out
}

/** CSS custom properties so the DOM header/legends share the canvas tokens. */
export function cssVars(style: TechnicalStyle): Record<string, string> {
  return {
    '--tc-canvas': style.canvas,
    '--tc-plot': style.plot,
    '--tc-header': style.header,
    '--tc-border': style.border,
    '--tc-text': style.text,
    '--tc-muted': style.muted,
    '--tc-link': style.link,
    '--tc-up': style.up,
    '--tc-down': style.down,
    '--tc-font': `${style.fontSize}px ${style.font}`,
    '--tc-family': style.font,
  }
}

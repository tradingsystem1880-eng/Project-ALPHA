// Chart overlays (spec 2026-09-01 §4.2 Phase 5 S3): the price chart asks `alpha chart overlays`
// for indicator series and pattern annotations and only draws them — every number, every
// warm-up null and every "knowable by the last bar" decision is the CLI's. This module holds the
// pure pieces: the per-profile selection the Insert › Indicators dialog edits, the spec grammar
// mirrored from the CLI so a typo fails here rather than as a 400, the query it becomes, and the
// mapping from the response to Lightweight Charts data (price-pane lines, one sub-pane per
// oscillator, swing markers, drawable multi-anchor annotations).

import type { ChartAnnotation, OverlaySeries } from '../api/types'

export const PATTERNS = ['swings', 'trendlines', 'levels'] as const
export type PatternName = (typeof PATTERNS)[number]

export const PATTERN_LABEL: Readonly<Record<PatternName, string>> = Object.freeze({
  swings: 'Swing highs / lows (fractal, confirmed only)',
  trendlines: 'Descending trendlines (confirmed anchors)',
  levels: 'Fibonacci retracement of the last confirmed leg',
})

export interface OverlayConfig {
  /** CLI indicator specs, e.g. `sma:20`, `macd:12:26:9`; order is draw order. */
  indicators: readonly string[]
  patterns: readonly PatternName[]
}

export const EMPTY_OVERLAYS: OverlayConfig = Object.freeze({
  indicators: Object.freeze([]) as readonly string[],
  patterns: Object.freeze([]) as readonly PatternName[],
})

/** The same arity table as `alpha_cli.chart_cmds.INDICATORS`. */
const ARITY: Readonly<Record<string, number>> = Object.freeze({
  sma: 1,
  ema: 1,
  bbands: 2,
  rsi: 1,
  atr: 1,
  macd: 3,
})

export const INDICATOR_PRESETS: readonly { id: string; label: string }[] = Object.freeze([
  { id: 'sma:20', label: 'SMA 20' },
  { id: 'sma:50', label: 'SMA 50' },
  { id: 'sma:200', label: 'SMA 200' },
  { id: 'ema:21', label: 'EMA 21' },
  { id: 'bbands:20:2', label: 'Bollinger 20 ±2σ' },
  { id: 'rsi:14', label: 'RSI 14' },
  { id: 'atr:14', label: 'ATR 14' },
  { id: 'macd:12:26:9', label: 'MACD 12/26/9' },
])

/** Normalise `name:p1[:p2[:p3]]` or throw an Error whose message names the problem. */
export function parseIndicatorSpec(text: string): string {
  const [head = '', ...rest] = text.trim().toLowerCase().split(':')
  const arity = ARITY[head]
  if (arity === undefined) throw new Error(`unknown indicator "${head}"; choose ${Object.keys(ARITY).join(', ')}`)
  if (rest.length !== arity) throw new Error(`${head} takes ${arity} parameter${arity === 1 ? '' : 's'} (${example(head)})`)
  const params = rest.map((part) => Number(part))
  if (params.some((value) => !Number.isFinite(value))) throw new Error(`parameters must be numbers (${example(head)})`)
  const windows = head === 'bbands' ? params.slice(0, 1) : params
  if (windows.some((value) => !Number.isInteger(value) || value < 2)) throw new Error('windows must be whole numbers of at least 2')
  if (head === 'bbands' && params[1] <= 0) throw new Error('Bollinger width must be above 0')
  if (head === 'macd' && !(params[0] < params[1])) throw new Error('MACD fast window must be shorter than slow')
  return [head, ...params.map((value) => String(value))].join(':')
}

function example(head: string): string {
  return INDICATOR_PRESETS.find((preset) => preset.id.startsWith(`${head}:`))?.id ?? head
}

export function isPattern(value: unknown): value is PatternName {
  return typeof value === 'string' && (PATTERNS as readonly string[]).includes(value)
}

/** A persisted config from untrusted JSON: unknown shapes fall back to nothing selected. */
export function parseOverlayConfig(raw: unknown): OverlayConfig {
  if (!raw || typeof raw !== 'object') return EMPTY_OVERLAYS
  const { indicators, patterns } = raw as { indicators?: unknown; patterns?: unknown }
  const specs: string[] = []
  for (const item of Array.isArray(indicators) ? indicators : []) {
    if (typeof item !== 'string') continue
    try {
      const spec = parseIndicatorSpec(item)
      if (!specs.includes(spec)) specs.push(spec)
    } catch {
      // a stale or hand-edited spec is dropped, never sent to the CLI
    }
  }
  return {
    indicators: specs,
    patterns: (Array.isArray(patterns) ? patterns : []).filter(isPattern),
  }
}

export function toggleIndicator(config: OverlayConfig, spec: string): OverlayConfig {
  const id = parseIndicatorSpec(spec)
  const indicators = config.indicators.includes(id)
    ? config.indicators.filter((item) => item !== id)
    : [...config.indicators, id]
  return { ...config, indicators }
}

export function togglePattern(config: OverlayConfig, pattern: PatternName): OverlayConfig {
  const patterns = config.patterns.includes(pattern)
    ? config.patterns.filter((item) => item !== pattern)
    : [...config.patterns, pattern]
  return { ...config, patterns }
}

export function hasOverlays(config: OverlayConfig): boolean {
  return config.indicators.length > 0 || config.patterns.length > 0
}

/** The `/api/overlays/{symbol}` query for a config over the linked as-of window. */
export function overlayQuery(
  config: OverlayConfig,
  window: { end: string | null; snapshotId: string | null },
): string {
  const params = new URLSearchParams()
  for (const spec of config.indicators) params.append('indicator', spec)
  for (const pattern of config.patterns) params.append('pattern', pattern)
  if (window.end) params.set('end', window.end)
  if (window.snapshotId) params.set('snapshot', window.snapshotId)
  const text = params.toString()
  return text ? `?${text}` : ''
}

export type SubPane = Exclude<OverlaySeries['pane'], 'price'>
export const SUB_PANE_ORDER: readonly SubPane[] = Object.freeze(['rsi', 'atr', 'macd'])

/** Price-pane series first, then one group per oscillator pane in fixed order. */
export function splitPanes(indicators: readonly OverlaySeries[]): {
  price: OverlaySeries[]
  panes: { pane: SubPane; series: OverlaySeries[] }[]
} {
  const price = indicators.filter((series) => series.pane === 'price')
  const panes = SUB_PANE_ORDER.map((pane) => ({
    pane,
    series: indicators.filter((series) => series.pane === pane),
  })).filter((group) => group.series.length > 0)
  return { price, panes }
}

export type LinePoint = { time: number; value: number } | { time: number }

/** Lightweight Charts data: a nulled warm-up value becomes a whitespace point, never a zero. */
export function lineData(t: readonly number[], values: readonly (number | null)[]): LinePoint[] {
  if (t.length !== values.length) throw new Error(`overlay length ${values.length} does not match ${t.length} bars`)
  return values.map((value, index) => (value === null ? { time: t[index] } : { time: t[index], value }))
}

export interface SwingMarker {
  id: string
  time: number
  position: 'aboveBar' | 'belowBar'
  text: 'H' | 'L'
  title: string
}

/** Single-anchor swing annotations become bar markers; everything else stays a drawn shape. */
export function swingMarkers(annotations: readonly ChartAnnotation[]): SwingMarker[] {
  return annotations
    .filter((row) => row.anchors.length === 1 && row.label.startsWith('Swing'))
    .map((row) => {
      const high = row.label === 'Swing high'
      return {
        id: `swing:${row.annotation_id}`,
        time: row.anchors[0].ts,
        position: high ? 'aboveBar' : 'belowBar',
        text: high ? 'H' : 'L',
        title: `${row.label} · ${row.reason}`,
      }
    })
}

export function drawableAnnotations(annotations: readonly ChartAnnotation[]): ChartAnnotation[] {
  return annotations.filter((row) => row.anchors.length >= 2)
}

/** One-line legend for the chart foot: what is drawn, and that the CLI computed it. */
export function overlayLegend(indicators: readonly OverlaySeries[], annotations: readonly ChartAnnotation[]): string {
  const names = Array.from(new Set(indicators.map((series) => series.name.replace(/ (line|signal|histogram|mid|[+-].*)$/, ''))))
  const parts = [...names]
  const swings = annotations.filter((row) => row.anchors.length === 1).length
  const lines = annotations.filter((row) => row.label.startsWith('Descending')).length
  const fibs = annotations.filter((row) => row.label.startsWith('Fib')).length
  if (swings) parts.push(`${swings} swings`)
  if (lines) parts.push(`${lines} trendline${lines === 1 ? '' : 's'}`)
  if (fibs) parts.push(`${fibs} fib levels`)
  return parts.length ? `OVERLAYS · ${parts.join(' · ')} · computed by alpha chart overlays` : ''
}

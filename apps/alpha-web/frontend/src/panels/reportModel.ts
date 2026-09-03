// Report model — the Strategy Performance Report's tree, Summary table and watermark chip as pure
// functions of the run detail and the figure catalogue (spec 2026-09-01 §4.4). It maps onto the
// existing figure sections and manifest fields only and never computes a statistic: a value the
// manifest did not record is shown as `not recorded`.

import type { FigureCatalogueItem, TradeRow } from '../api/types'
import { asNum, asStr, isFiniteNum } from '../util/format'

export interface ReportLeaf {
  id: string
  label: string
  figureIds: string[]
  empty: boolean
  reason: string | null
}

export interface ReportGroup {
  label: string
  leaves: ReportLeaf[]
}

export interface ReportTreeInput {
  kind: string
  isValidate: boolean
  hasTrades: boolean
  /** Rows the trades projection returned; shown as `List of trades (N)` once loaded. */
  tradeCount?: number | null
  items: FigureCatalogueItem[]
}

export function reportTree(input: ReportTreeInput): ReportGroup[] {
  const bySection = new Map<string, FigureCatalogueItem[]>()
  for (const item of input.items) {
    bySection.set(item.section, [...(bySection.get(item.section) ?? []), item])
  }
  const claimed = new Set<string>()
  const figureLeaf = (id: string, label: string, items: FigureCatalogueItem[]): ReportLeaf => {
    const drawable = items.some((item) => item.available)
    return {
      id,
      label,
      figureIds: items.map((item) => item.figure_id),
      empty: !drawable,
      reason: drawable
        ? null
        : items.length
          ? 'no drawable figure in this section'
          : 'no figures in this section',
    }
  }
  const sectionLeaf = (id: string, label: string, section: string): ReportLeaf => {
    claimed.add(section)
    return figureLeaf(id, label, bySection.get(section) ?? [])
  }
  const fixed = (id: string, label: string, present: boolean, reason: string): ReportLeaf => ({
    id,
    label,
    figureIds: [],
    empty: !present,
    reason: present ? null : reason,
  })
  const strategy = [
    fixed('summary', 'Summary', true, ''),
    sectionLeaf('performance', 'Ratios & performance', 'performance'),
    sectionLeaf('equity', 'Equity, risk & drawdown', 'risk'),
    sectionLeaf('signals', 'Signals', 'signals'),
  ]
  const trade = [
    fixed(
      'trades',
      typeof input.tradeCount === 'number' && input.hasTrades ? `List of trades (${input.tradeCount})` : 'List of trades',
      input.hasTrades,
      'no trades recorded',
    ),
    sectionLeaf('pnl', 'P&L distribution', 'trades'),
  ]
  const periodical = [sectionLeaf('periodical', 'Calendar & yearly returns', 'periodical')]
  const robustness = [
    fixed('gates', 'Gates', input.isValidate, 'not a validate run'),
    sectionLeaf('robustness', 'Can we believe it', 'robustness'),
    fixed('stress', 'Stress test', input.kind === 'runs', 'stress test needs a single-strategy run'),
  ]
  const rest = [...bySection.entries()]
    .filter(([section]) => !claimed.has(section))
    .flatMap(([, items]) => items)
  robustness.push(figureLeaf('other', 'Other analysis', rest))
  return [
    { label: 'Strategy Analysis', leaves: strategy },
    { label: 'Trade Analysis', leaves: trade },
    { label: 'Periodical Analysis', leaves: periodical },
    { label: 'Robustness', leaves: robustness },
    { label: 'Settings & data', leaves: [fixed('artifacts', 'Artifacts', true, '')] },
  ]
}

export interface SummaryRow {
  label: string
  value: string
}

const METRIC_LABELS: [string, string][] = [
  ['total_return', 'Total return'],
  ['cagr', 'CAGR'],
  ['annual_volatility', 'Volatility'],
  ['sharpe', 'Sharpe'],
  ['max_drawdown', 'Max drawdown'],
]
const NOT_RECORDED = ['Win rate', 'Profit factor', 'Exposure', 'Max drawdown date']

const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null
const isoDate = (v: unknown): string | null =>
  typeof v === 'string' && /^\d{4}-\d{2}-\d{2}/.test(v) ? v.slice(0, 10) : null
const ratio = (v: unknown): string | null => (isFiniteNum(v) ? v.toFixed(3) : null)
const money = (v: unknown): string | null =>
  isFiniteNum(v)
    ? v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : null

/** Key/value rows from what the manifest recorded, in reading order; nothing is derived. */
export function summaryRows(manifest: Record<string, unknown>): SummaryRow[] {
  const rows: SummaryRow[] = []
  const push = (label: string, value: string | null): void => {
    if (value !== null) rows.push({ label, value })
  }
  push('Strategy', asStr(obj(manifest.params)?.strategy_name))
  const symbols = manifest.symbols
  push(
    'Symbol',
    asStr(manifest.symbol) ?? (Array.isArray(symbols) ? symbols.map(String).join(', ') : null),
  )
  push('Snapshot', asStr(manifest.snapshot_id))
  const metadata = obj(manifest.metadata)
  const first = isoDate(metadata?.first_ts)
  const last = isoDate(metadata?.last_ts)
  if (first && last) push('Period', `${first} → ${last}`)
  push('Starting equity', money(manifest.starting_equity))
  push('Final equity', money(manifest.final_equity))
  const trades = asNum(manifest.n_trades)
  push('Trades', trades === null ? null : String(trades))
  const metrics = obj(manifest.metrics) ?? {}
  const oos = obj(manifest.oos_metrics) ?? {}
  for (const [key, label] of METRIC_LABELS) push(label, ratio(metrics[key] ?? oos[key]))
  push('Deflated Sharpe', ratio(obj(manifest.dsr)?.dsr))
  push('Verdict', asStr(obj(manifest.verdict)?.overall) ?? asStr(manifest.verdict))
  if (typeof manifest.passed === 'boolean') push('Passed', manifest.passed ? 'yes' : 'no')
  for (const label of NOT_RECORDED) push(label, 'not recorded')
  return rows
}

export interface WatermarkChip {
  text: string
  title: string
}

/** One compact chip for the report title bar; the full sentences travel in its title. */
export function watermarkChip(gate: string | null, context: string | null): WatermarkChip | null {
  const sentences: string[] = []
  if (gate) sentences.push(`${gate} — launched under an owner research-gate override.`)
  if (context && context !== gate) {
    sentences.push(`${context} — this run is not governed research evidence.`)
  }
  if (!sentences.length) return null
  return { text: gate ?? (context as string), title: sentences.join(' ') }
}

function csvCell(value: string | number | null): string {
  if (value === null) return ''
  const text = String(value)
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

/** The trades projection as CSV, column order from the first row, nothing computed. */
export function tradesCsv(rows: readonly TradeRow[]): string {
  if (!rows.length) return ''
  const columns = Object.keys(rows[0])
  return [columns.join(','), ...rows.map((row) => columns.map((column) => csvCell(row[column] ?? null)).join(','))].join('\n')
}

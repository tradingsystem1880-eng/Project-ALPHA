// Report model — the Strategy Performance Report's tree, Summary table and watermark chip as pure
// functions of the run detail and the figure catalogue (spec 2026-09-01 §4.4). It maps onto the
// existing figure sections and manifest fields only and never computes a statistic: a value the
// manifest did not record is shown as `not recorded`.

import type { FigureCatalogueItem, TradeRow } from '../api/types'
import { asNum, asStr, isFiniteNum } from '../util/format'
import { manifestWord } from './readingModel'

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

/** The equity curve with its drawdown windows leads the tab; the other figures keep their order. */
const EQUITY_FIRST = ['equity_underwater', 'drawdown_episodes']
function equityLeaf(leaf: ReportLeaf): ReportLeaf {
  const rank = (id: string) => (EQUITY_FIRST.includes(id) ? EQUITY_FIRST.indexOf(id) : EQUITY_FIRST.length)
  return { ...leaf, figureIds: [...leaf.figureIds].sort((a, b) => rank(a) - rank(b)) }
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
    equityLeaf(sectionLeaf('equity', 'Equity, risk & drawdown', 'risk')),
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
  /** A short plain explanation of a standard metric name, shown muted after the label. */
  hint?: string
}

const METRIC_LABELS: [string, string][] = [
  ['total_return', 'Total return'],
  ['cagr', 'CAGR'],
  ['annual_volatility', 'Volatility'],
  ['sharpe', 'Sharpe'],
  ['max_drawdown', 'Max drawdown'],
]
const NOT_RECORDED = ['Win rate', 'Profit factor', 'Exposure', 'Max drawdown date']

const METRIC_HINTS: Record<string, string> = { 'Profit factor': 'gross gains divided by gross losses' }

const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null
const isoDate = (v: unknown): string | null =>
  typeof v === 'string' && /^\d{4}-\d{2}-\d{2}/.test(v) ? v.slice(0, 10) : null
const ratio = (v: unknown): string | null => (isFiniteNum(v) ? v.toFixed(3) : null)
const money = (v: unknown): string | null =>
  isFiniteNum(v)
    ? v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : null

const pct1 = (v: unknown): string | null => (isFiniteNum(v) ? `${(v * 100).toFixed(1)}%` : null)

/** One Monte Carlo family as its stored percentiles in plain words; no letter and no stage word. */
function monteCarloFamilyText(family: Record<string, unknown>): string {
  const loss = obj(family.loss_probability)
  const range = pct1(loss?.lower) && pct1(loss?.upper) ? ` (95% range ${pct1(loss?.lower)} to ${pct1(loss?.upper)})` : ''
  const parts = [
    isFiniteNum(family.n_paths) ? `${family.n_paths.toLocaleString('en-US')} paths` : null,
    pct1(family.terminal_return_q50) && `median final return ${pct1(family.terminal_return_q50)}`,
    pct1(family.terminal_return_q05) && `5th percentile ${pct1(family.terminal_return_q05)}`,
    pct1(family.terminal_return_q95) && `95th percentile ${pct1(family.terminal_return_q95)}`,
    pct1(family.maximum_drawdown_q50) && `median largest fall ${pct1(family.maximum_drawdown_q50)}`,
    pct1(family.maximum_drawdown_q95) && `largest fall at the 95th percentile ${pct1(family.maximum_drawdown_q95)}`,
    pct1(loss?.point) && `share of paths ending below zero ${pct1(loss?.point)}${range}`,
  ]
  return parts.filter(Boolean).join(' · ') || 'not recorded'
}

/** The line under the trades table: the starting capital the P&L refers to, as the run recorded it. */
export function startingCapitalCaption(manifest: Record<string, unknown>): string {
  // Backtests record `starting_equity`; rule tests and validate runs record `metadata.starting_cash`.
  const capital = money(manifest.starting_equity) ?? money(obj(manifest.metadata)?.starting_cash)
  return capital === null ? 'P&L: starting capital not recorded.' : `P&L is measured from a starting capital of ${capital}.`
}

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
  push('Reading', manifestWord(manifest)?.text ?? null)
  const families = Array.isArray(manifest.families) ? manifest.families : manifest.family ? [manifest.family] : []
  for (const family of families) {
    const row = obj(family)
    if (row && asStr(row.family)) push(`Monte Carlo · ${asStr(row.family)}`, monteCarloFamilyText(row))
  }
  for (const label of NOT_RECORDED) rows.push({ label, value: 'not recorded', ...(METRIC_HINTS[label] ? { hint: METRIC_HINTS[label] } : {}) })
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

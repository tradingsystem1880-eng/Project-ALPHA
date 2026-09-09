// Scanner + Alerts (spec 2026-09-01 §4.2 Phase 5 S5): pure helpers for the Scanner document and
// the Toolbox Alerts tab. A scan is a saved rule set over a universe; `alpha scan run` returns the
// signal on each symbol's last point-in-time bar, `alpha scan check` appends only changed signals
// to the alert log. Nothing here evaluates a rule — it formats what the CLI said.

import type { ScanAlert, ScanRow, ScanSummary } from '../api/types'

export type SignalTone = 'up' | 'down' | 'flat'

export function signalTone(signal: number): SignalTone {
  return signal > 0 ? 'up' : signal < 0 ? 'down' : 'flat'
}

export function signalLabel(signal: number): string {
  return signal > 0 ? 'LONG' : signal < 0 ? 'SHORT' : 'flat'
}

/** Universe text for a scan row: `every stored symbol` or the explicit list. */
export function universeText(scan: Pick<ScanSummary, 'universe'>): string {
  const universe = scan.universe
  if (!universe) return '—'
  if (universe.kind === 'stored') return 'every stored symbol'
  const symbols = universe.symbols ?? []
  return symbols.length > 4 ? `${symbols.slice(0, 4).join(', ')} +${symbols.length - 4}` : symbols.join(', ')
}

/** Rows sorted so matches (non-zero) lead, then by symbol; flat rows keep the tail. */
export function orderRows(rows: readonly ScanRow[]): ScanRow[] {
  return [...rows].sort((a, b) => {
    const hit = Number(b.signal !== 0) - Number(a.signal !== 0)
    return hit !== 0 ? hit : a.symbol.localeCompare(b.symbol)
  })
}

/** Column order for the operand value cells: the union of value labels across rows, stable. */
export function valueColumns(rows: readonly ScanRow[]): string[] {
  const seen = new Set<string>()
  for (const row of rows) for (const key of Object.keys(row.values)) seen.add(key)
  return [...seen]
}

export function formatValue(value: number | undefined): string {
  if (value === undefined || !Number.isFinite(value)) return '—'
  return Number(value.toPrecision(6)).toLocaleString('en-US', { maximumFractionDigits: 6 })
}

/** `flat → LONG`, `LONG → SHORT`, or `→ LONG` on a first sighting. */
export function alertTransition(alert: Pick<ScanAlert, 'previous' | 'signal'>): string {
  const before = alert.previous === null || alert.previous === undefined ? '' : `${signalLabel(alert.previous)} `
  return `${before}→ ${signalLabel(alert.signal)}`
}

/** Newest first for the Toolbox; the CLI serves oldest-first within its tail. */
export function newestFirst(alerts: readonly ScanAlert[]): ScanAlert[] {
  return [...alerts].reverse()
}

/** Parse the universe field: blank means every stored symbol. */
export function parseUniverse(text: string): string[] | null {
  const symbols = text
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  return symbols.length ? symbols : null
}

export const SCAN_ID_PATTERN = /^[a-z0-9][a-z0-9_-]{0,63}$/

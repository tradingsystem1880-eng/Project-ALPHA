import type { ArchiveChartDataset } from '../api/client'
import type { LinkedState } from '../context/linked'

export function contextKey(linked: LinkedState, archive: ArchiveChartDataset | null): string {
  return JSON.stringify([linked.linkGroup, linked.projectId, linked.symbol, linked.timeframe,
    linked.start, linked.end, linked.snapshotId, linked.runId, archive?.manifest_id ?? null])
}
export function evaluationUnavailable(linked: LinkedState, archive: ArchiveChartDataset | null): string | null {
  if (archive) return 'Archive chart only. Conditions require admitted canonical data; no store substitution.'
  if (linked.runId) return 'Recorded run selected. Read its recorded signal trace; current-store conditions are unavailable.'
  if (linked.snapshotId) return 'Selected snapshot is not supported by the condition evaluator; no current-store fallback.'
  if (!linked.symbol) return 'Select a stored market to evaluate conditions.'
  return null
}
export function scanChartContext(symbol: string, barDate: string) {
  return { symbol, start: null, end: barDate, snapshotId: null, runId: null }
}

export const RESULT_TABS = ['Scan results', 'Trades', 'Results', 'Run library'] as const
export type ResultTab = typeof RESULT_TABS[number]

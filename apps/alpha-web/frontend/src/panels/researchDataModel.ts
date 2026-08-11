// Pure projections for the ResearchDataExplorer: audit badges, range labels, and the
// provenance-chain summary. Registration itself is owner-CLI only (fail-closed on
// receipts); this model only renders what the read plane serves.

import type { ResearchDatasetRefRow } from '../api/types'

export interface DatasetAuditBadge {
  state: 'unaudited' | 'clean' | 'limiting' | 'blocking'
  label: string
}

function auditCount(audit: Record<string, unknown> | null, field: string): number {
  if (!audit) return 0
  const summary = audit['summary']
  if (summary === null || typeof summary !== 'object' || Array.isArray(summary)) return 0
  const value = (summary as Record<string, unknown>)[field]
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

export function datasetAuditBadge(
  latestAudit: Record<string, unknown> | null,
): DatasetAuditBadge {
  if (!latestAudit) return { state: 'unaudited', label: 'NOT AUDITED' }
  const blocking = auditCount(latestAudit, 'blocking_count')
  const limiting = auditCount(latestAudit, 'limiting_count')
  if (blocking > 0) return { state: 'blocking', label: `${blocking} BLOCKING` }
  if (limiting > 0) return { state: 'limiting', label: `${limiting} LIMITING` }
  return { state: 'clean', label: 'AUDITED CLEAN' }
}

export function datasetRangeLabel(row: ResearchDatasetRefRow): string {
  const cadence = row.bar_duration_minutes === null ? 'daily' : `${row.bar_duration_minutes}m`
  return `${row.start_ts} → ${row.end_ts} · ${cadence}`
}

/** The receipt→registration provenance line: which exact bytes this ref is bound to. */
export function datasetOriginSummary(row: ResearchDatasetRefRow): string {
  const origin = row.origin as Record<string, unknown>
  const short = (value: unknown): string =>
    typeof value === 'string' ? `${value.slice(0, 12)}…` : '—'
  if (row.dataset_kind === 'snapshot') {
    return `snapshot ${String(origin['snapshot_id'] ?? '—')} · manifest ${short(origin['manifest_sha256'])}`
  }
  if (row.dataset_kind === 'store_slice') {
    return `canonical store · provenance ${short(origin['provenance_sha256'])}`
  }
  return `quantpad receipt ${String(origin['receipt_id'] ?? '—')} · response ${short(origin['response_sha256'])}`
}

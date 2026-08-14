// Pure projections for the ResearchDataExplorer: audit badges, range labels, and the
// provenance-chain summary. Registration itself is owner-CLI only (fail-closed on
// receipts); this model only renders what the read plane serves.

import type { CryptoFamily, ResearchDatasetRefRow } from '../api/types'

export type CryptoDataSection =
  | 'assets'
  | 'cex'
  | 'derivatives'
  | 'options'
  | 'onchain'
  | 'dex'
  | 'quality'
  | 'storage'

export type CryptoMarketCategory = 'spot' | 'linear' | 'inverse' | 'option'

export function cryptoMarketChoicesForFamily(family: CryptoFamily): CryptoMarketCategory[] {
  if (family === 'comparison_bars') return ['spot']
  if (family === 'instrument_catalog') return ['spot', 'linear', 'inverse', 'option']
  if (
    family === 'option_instruments'
    || family === 'option_quotes'
    || family === 'historical_volatility'
  ) return ['option']
  if (family === 'derivative_trades' || family === 'derivative_book_snapshots') {
    return ['linear', 'inverse', 'option']
  }
  if (
    family === 'funding'
    || family === 'open_interest'
    || family === 'long_short_ratio'
    || family === 'derivative_bars'
    || family === 'mark_bars'
    || family === 'index_bars'
    || family === 'premium_bars'
  ) return ['linear', 'inverse']
  return ['spot', 'linear', 'inverse']
}

export function cryptoSectionForFamily(family: CryptoFamily): CryptoDataSection {
  if (family === 'asset_metadata' || family === 'market_reference') return 'assets'
  if (
    family === 'market_bars'
    || family === 'trades'
    || family === 'aggregate_trades'
    || family === 'book_snapshots'
    || family === 'comparison_bars'
  ) return 'cex'
  if (
    family === 'funding'
    || family === 'instrument_catalog'
    || family === 'derivative_bars'
    || family === 'derivative_trades'
    || family === 'derivative_book_snapshots'
    || family === 'open_interest'
    || family === 'long_short_ratio'
    || family === 'mark_bars'
    || family === 'index_bars'
    || family === 'premium_bars'
  ) return 'derivatives'
  if (
    family === 'option_instruments'
    || family === 'option_quotes'
    || family === 'historical_volatility'
  ) return 'options'
  if (family === 'onchain_metrics') return 'onchain'
  if (family === 'dex_pools' || family === 'dex_ohlcv' || family === 'dex_transactions') return 'dex'
  return 'quality'
}

export interface CryptoCanonicalActionInput {
  loading?: boolean
  storageState?: 'ready' | 'blocked'
  storageBlocker?: string | null
  qualifiedCount?: number
  selectedCount?: number
}

export interface CryptoCanonicalAction {
  state: 'loading' | 'blocked' | 'ready'
  label: string
}

export function cryptoCanonicalAction(input: CryptoCanonicalActionInput): CryptoCanonicalAction {
  if (input.loading || !input.storageState) {
    return { state: 'loading', label: 'Checking storage and qualified coverage…' }
  }
  if (input.storageState === 'blocked') {
    return {
      state: 'blocked',
      label: input.storageBlocker === 'bulk_volume_not_mounted'
        ? 'Reconnect the reviewed Expansion volume, then refresh storage.'
        : 'Resolve the reported storage blocker, then refresh storage.',
    }
  }
  if ((input.qualifiedCount ?? 0) === 0) {
    return { state: 'ready', label: 'Estimate one bounded dataset acquisition.' }
  }
  if ((input.selectedCount ?? 0) > 0) {
    const count = input.selectedCount ?? 0
    return {
      state: 'ready',
      label: `Freeze the ${count} selected qualified dataset${count === 1 ? '' : 's'} into a snapshot.`,
    }
  }
  return { state: 'ready', label: 'Select qualified datasets for one exact frozen snapshot.' }
}

interface CryptoVersionIdentity {
  provider: string
  venue: string
  market_type: string
  family: string
  instrument: string
  quote_asset: string | null
  frequency: string
  units: string
  manifest_id: string
  fetched_at: string | null
}

export function latestCryptoManifestIds(items: CryptoVersionIdentity[]): Set<string> {
  const latest = new Map<string, CryptoVersionIdentity>()
  for (const item of items) {
    const key = [
      item.provider,
      item.venue,
      item.market_type,
      item.family,
      item.instrument,
      item.quote_asset ?? '',
      item.frequency,
      item.units,
    ].join('\u0000')
    const existing = latest.get(key)
    const rank = `${item.fetched_at ?? ''}\u0000${item.manifest_id}`
    const existingRank = existing
      ? `${existing.fetched_at ?? ''}\u0000${existing.manifest_id}`
      : ''
    if (!existing || rank > existingRank) latest.set(key, item)
  }
  return new Set([...latest.values()].map((item) => item.manifest_id))
}

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

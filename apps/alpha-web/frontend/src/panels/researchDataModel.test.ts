import { describe, expect, it } from 'vitest'

import type { ResearchDatasetRefRow } from '../api/types'
import {
  datasetAuditBadge,
  datasetOriginSummary,
  datasetRangeLabel,
  cryptoCanonicalAction,
  cryptoSectionForFamily,
  latestCryptoManifestIds,
} from './researchDataModel'

function row(overrides: Partial<ResearchDatasetRefRow> = {}): ResearchDatasetRefRow {
  return {
    ref_id: `rd_${'a'.repeat(64)}`,
    dataset_kind: 'snapshot',
    instrument: 'AAPL',
    provider: 'tiingo',
    start_ts: '2020-01-01',
    end_ts: '2020-06-01',
    bar_duration_minutes: null,
    origin: { snapshot_id: 'snap1', manifest_sha256: 'b'.repeat(64) },
    research_only: true,
    registered_by: 'owner',
    registered_at: '2026-08-09T00:00:00Z',
    latest_audit: null,
    ...overrides,
  }
}

describe('research data model', () => {
  it('classifies audit badges from recorded counts only', () => {
    expect(datasetAuditBadge(null)).toEqual({ state: 'unaudited', label: 'NOT AUDITED' })
    expect(
      datasetAuditBadge({ summary: { blocking_count: 2, limiting_count: 0 } }),
    ).toEqual({ state: 'blocking', label: '2 BLOCKING' })
    expect(
      datasetAuditBadge({ summary: { blocking_count: 0, limiting_count: 1 } }),
    ).toEqual({ state: 'limiting', label: '1 LIMITING' })
    expect(
      datasetAuditBadge({ summary: { blocking_count: 0, limiting_count: 0 } }),
    ).toEqual({ state: 'clean', label: 'AUDITED CLEAN' })
  })

  it('labels ranges with their native cadence', () => {
    expect(datasetRangeLabel(row())).toBe('2020-01-01 → 2020-06-01 · daily')
    expect(datasetRangeLabel(row({ bar_duration_minutes: 60 }))).toBe(
      '2020-01-01 → 2020-06-01 · 60m',
    )
  })

  it('summarises the exact origin binding per dataset kind', () => {
    expect(datasetOriginSummary(row())).toBe(
      `snapshot snap1 · manifest ${'b'.repeat(12)}…`,
    )
    expect(
      datasetOriginSummary(
        row({ dataset_kind: 'store_slice', origin: { provenance_sha256: 'c'.repeat(64) } }),
      ),
    ).toBe(`canonical store · provenance ${'c'.repeat(12)}…`)
    expect(
      datasetOriginSummary(
        row({
          dataset_kind: 'quantpad_receipt',
          origin: { receipt_id: 'f'.repeat(32), response_sha256: 'd'.repeat(64) },
        }),
      ),
    ).toBe(`quantpad receipt ${'f'.repeat(32)} · response ${'d'.repeat(12)}…`)
  })

  it('maps every provider-native family into the intended owner section', () => {
    expect(cryptoSectionForFamily('market_bars')).toBe('cex')
    expect(cryptoSectionForFamily('funding')).toBe('derivatives')
    expect(cryptoSectionForFamily('option_quotes')).toBe('options')
    expect(cryptoSectionForFamily('onchain_metrics')).toBe('onchain')
    expect(cryptoSectionForFamily('dex_pools')).toBe('dex')
    expect(cryptoSectionForFamily('asset_metadata')).toBe('assets')
  })

  it('derives exactly one canonical next action from server state', () => {
    expect(cryptoCanonicalAction({ loading: true })).toEqual({
      state: 'loading',
      label: 'Checking storage and qualified coverage…',
    })
    expect(
      cryptoCanonicalAction({ storageState: 'blocked', storageBlocker: 'bulk_volume_not_mounted' }),
    ).toEqual({
      state: 'blocked',
      label: 'Reconnect the reviewed Expansion volume, then refresh storage.',
    })
    expect(cryptoCanonicalAction({ storageState: 'ready', qualifiedCount: 0 })).toEqual({
      state: 'ready',
      label: 'Estimate one bounded dataset acquisition.',
    })
    expect(
      cryptoCanonicalAction({ storageState: 'ready', qualifiedCount: 2, selectedCount: 1 }),
    ).toEqual({
      state: 'ready',
      label: 'Freeze the 1 selected qualified dataset into a snapshot.',
    })
  })

  it('selects the newest receipt per exact provider-native dataset identity', () => {
    const base = {
      provider: 'bybit', venue: 'bybit', market_type: 'linear', family: 'funding',
      instrument: 'BTCUSDT', quote_asset: 'USDT', frequency: 'funding_interval',
      units: 'dimensionless_rate',
    } as const
    expect(latestCryptoManifestIds([
      { ...base, manifest_id: 'a'.repeat(64), fetched_at: '2026-08-14T00:00:00Z' },
      { ...base, manifest_id: 'b'.repeat(64), fetched_at: '2026-08-15T00:00:00Z' },
      { ...base, quote_asset: 'USD', manifest_id: 'c'.repeat(64), fetched_at: null },
    ])).toEqual(new Set(['b'.repeat(64), 'c'.repeat(64)]))
  })
})

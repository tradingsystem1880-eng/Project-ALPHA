import { describe, expect, it } from 'vitest'

import type { ResearchDatasetRefRow } from '../api/types'
import {
  datasetAuditBadge,
  datasetOriginSummary,
  datasetRangeLabel,
  cryptoCanonicalAction,
  cryptoFeatureInputSelection,
  cryptoMarketChoicesForFamily,
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
    expect(cryptoSectionForFamily('market_membership')).toBe('derivatives')
  })

  it('builds feature inputs only from exact compatible qualified selections', () => {
    const coverage = (family: 'mark_bars' | 'index_bars' | 'premium_bars', id: string, instrument = 'BTCUSDT') => ({
      manifest_id: id.repeat(64), provider: 'bybit', venue: 'bybit', market_type: 'linear' as const,
      family, instrument, base_asset: 'BTC', quote_asset: 'USDT', frequency: '1h',
      units: 'quote_per_base', state: 'qualified' as const, artifact_sha256: 'a'.repeat(64),
      row_count: 2, fetched_at: '2026-08-15T00:00:00Z', method_version: 'crypto-quality-v1',
      timestamp_convention: 'UTC period open', failures: [], warnings: [],
      observed_start: '2026-08-14T00:00:00Z', observed_end: '2026-08-15T00:00:00Z',
    })
    const items = [coverage('mark_bars', '1'), coverage('index_bars', '2'), coverage('premium_bars', '3')]
    expect(cryptoFeatureInputSelection('basis', items, new Set(items.map((item) => item.manifest_id)))).toEqual({
      inputs: { mark: '1'.repeat(64), index: '2'.repeat(64), premium: '3'.repeat(64) },
      blocker: null,
    })
    expect(cryptoFeatureInputSelection('basis', items, new Set([items[0].manifest_id]))).toEqual({
      inputs: {}, blocker: 'Select qualified index bars, premium bars data.',
    })
    const mismatched = [items[0], coverage('index_bars', '2', 'ETHUSDT'), items[2]]
    expect(cryptoFeatureInputSelection('basis', mismatched, new Set(mismatched.map((item) => item.manifest_id))).blocker)
      .toBe('Select inputs for the same provider, venue, market, instrument, base, and quote.')
  })

  it('makes the truthful Bybit option market the only option-family choice', () => {
    expect(cryptoMarketChoicesForFamily('option_instruments')).toEqual(['option'])
    expect(cryptoMarketChoicesForFamily('option_quotes')).toEqual(['option'])
    expect(cryptoMarketChoicesForFamily('historical_volatility')).toEqual(['option'])
    expect(cryptoMarketChoicesForFamily('derivative_trades')).toEqual([
      'linear', 'inverse', 'option',
    ])
    expect(cryptoMarketChoicesForFamily('funding')).toEqual(['linear', 'inverse'])
    expect(cryptoMarketChoicesForFamily('comparison_bars')).toEqual(['spot'])
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

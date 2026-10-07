import { describe, expect, it } from 'vitest'
import { assetGroups } from './assetChoices'
import type { ArchiveChartDataset } from '../api/client'
const series = (id: string, quote = 'USD', frequency: ArchiveChartDataset['frequency'] = '1h'): ArchiveChartDataset => ({
  schema_version: 1, provider: 'bybit', venue: 'bybit', market_type: 'inverse', family: 'derivative_bars',
  instrument: `BTC${quote}`, base_asset: 'BTC', quote_asset: quote, frequency,
  units: 'quote_price', timestamp_convention: 'interval_start_utc', manifest_id: id,
  manifest_ids: [id], manifest_count: 1, start: null, end: null, row_count: 2, verification: 'metadata_only',
})
describe('asset groups', () => {
  it('groups alias labels without discarding source identities or quote currencies', () => {
    const groups = assetGroups(['BTC-USD', 'BTC/USD', 'BTC/USD', 'BTC/USDT'], [series('a'), series('b', 'USD', '4h')])
    expect(groups.map(group => group.label)).toEqual(['BTC/USD', 'BTC/USDT'])
    expect(groups[0].choices.map(choice => choice.id)).toEqual(['stored:BTC-USD', 'stored:BTC/USD', 'archive:a', 'archive:b'])
    expect(groups[0].choices[2]).toMatchObject({ kind: 'archive', dataset: { manifest_id: 'a', frequency: '1h' } })
  })
  it('distinguishes contracts and exact manifests in source labels', () => {
    const groups = assetGroups([], [series('a'.repeat(64)), { ...series('b'.repeat(64)), instrument: 'BTCUSD-20261225' }])
    expect(groups[0].choices[0].description).toContain('BTCUSD')
    expect(groups[0].choices[0].description).toContain('aaaaaaaaaa')
    expect(groups[0].choices[1].description).toContain('BTCUSD-20261225')
    expect(groups[0].choices[1].description).toContain('bbbbbbbbbb')
  })
  it('keeps every archive instrument and does not guess missing asset identities', () => {
    const unknown = { ...series('x'), instrument: 'UNKNOWN', base_asset: '', quote_asset: '' }
    expect(assetGroups([], [series('a'), series('b', 'USDT'), unknown]).map(group => group.label)).toEqual(['BTC/USD', 'BTC/USDT', 'UNKNOWN'])
  })
})

import { expect, it } from 'vitest'
import type { ArchiveChartDataset } from '../api/client'
import { nativeSources } from './nativeSourceModel'
const dataset = { instrument: 'ETHUSDT', base_asset: 'ETH', quote_asset: 'USDT', provider: 'bybit', venue: 'bybit', market_type: 'linear', family: 'derivative_bars', frequency: '1h' } as ArchiveChartDataset
it('offers hourly archives for a stored pair without merging USD and USDT', () => {
  expect(nativeSources({ kind: 'market', symbol: 'ETH/USDT', start: null, end: null, snapshotId: null }, [dataset])).toEqual([dataset])
  expect(nativeSources({ kind: 'market', symbol: 'ETH/USD', start: null, end: null, snapshotId: null }, [dataset])).toEqual([])
})
it('pins provider, venue and market identity and never substitutes run prices', () => {
  expect(nativeSources({ kind: 'archive', dataset }, [dataset, { ...dataset, venue: 'binance' }, { ...dataset, market_type: 'spot' }])).toEqual([dataset])
  expect(nativeSources({ kind: 'run', runId: 'a'.repeat(16) }, [dataset])).toEqual([])
})

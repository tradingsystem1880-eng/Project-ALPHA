import { describe, expect, it } from 'vitest'

import type { Candle } from '../api/types'
import { MARKET_WATCH_TABS, watchRow, watchRows, watchSymbols } from './marketWatchModel'

const bar = (c: number, t = 0): Candle => ({ t, o: c, h: c, l: c, c, v: 1 })

describe('marketWatchModel', () => {
  it('lists the watchlist first, then stored pairs, de-duplicated and same style only', () => {
    expect(watchSymbols('crypto', ['SOL/USDT', 'AAPL', 'DOGE/USDT', 'BTC/USDT'])).toEqual([
      'BTC/USDT',
      'ETH/USDT',
      'XRP/USDT',
      'SOL/USDT',
      'DOGE/USDT',
    ])
    expect(watchSymbols('equities', ['BTC/USDT', 'MSFT', 'SPY'])).toEqual(['SPY', 'AAPL', 'MSFT'])
  })

  it('reads red/green from the last two bars', () => {
    expect(watchRow('BTC/USDT', [bar(100), bar(101)])).toEqual({
      symbol: 'BTC/USDT',
      last: '101',
      change: '+1.00%',
      tone: 'up',
    })
    expect(watchRow('BTC/USDT', [bar(100), bar(98)]).tone).toBe('down')
    expect(watchRow('BTC/USDT', [bar(100), bar(98)]).change).toBe('-2.00%')
    expect(watchRow('BTC/USDT', [bar(100), bar(100)])).toMatchObject({ change: '0.00%', tone: 'flat' })
  })

  it('never invents a price', () => {
    expect(watchRow('SOL/USDT', null)).toEqual({ symbol: 'SOL/USDT', last: '—', change: '—', tone: 'none' })
    expect(watchRow('SOL/USDT', [])).toMatchObject({ last: '—', tone: 'none' })
    expect(watchRow('SOL/USDT', [bar(Number.NaN)])).toMatchObject({ last: '—', tone: 'none' })
    // One bar: a last price but no daily change to report.
    expect(watchRow('SOL/USDT', [bar(12.5)])).toEqual({ symbol: 'SOL/USDT', last: '12.5', change: '—', tone: 'none' })
    expect(watchRow('SOL/USDT', [bar(0), bar(1)]).change).toBe('—')
  })

  it('builds rows for the profile from the quotes it was handed', () => {
    const rows = watchRows('crypto', [], { 'BTC/USDT': [bar(100), bar(110)] })
    expect(rows[0]).toMatchObject({ symbol: 'BTC/USDT', change: '+10.00%', tone: 'up' })
    expect(rows.slice(1).every((row) => row.last === '—' && row.tone === 'none')).toBe(true)
  })

  it('offers the three spec tabs', () => {
    expect([...MARKET_WATCH_TABS]).toEqual(['Symbols', 'Details', 'Data'])
  })
})

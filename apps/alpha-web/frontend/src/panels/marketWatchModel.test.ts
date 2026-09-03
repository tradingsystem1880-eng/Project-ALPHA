import { describe, expect, it } from 'vitest'

import type { Candle } from '../api/types'
import {
  MARKET_WATCH_TABS,
  ageText,
  applyTicker,
  baseAsset,
  displaySymbol,
  isStale,
  relatedRows,
  shouldPoll,
  tickerExchange,
  venueLabel,
  watchRow,
  watchRows,
  watchSymbols,
} from './marketWatchModel'

const bar = (c: number, t = 0): Candle => ({ t, o: c, h: c, l: c, c, v: 1 })
const NOW = Date.UTC(2023, 10, 16) // 2023-11-16
const quote = (bars: Candle[], source: string | null = 'ccxt:binance') => ({ bars, provenance: { source } })

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

  it('reads red/green from the last two bars and names the venue and bar date', () => {
    expect(watchRow('BTC/USDT', quote([bar(100), bar(101, 1_700_000_000)]), NOW)).toEqual({
      symbol: 'BTC/USDT',
      label: 'BTCUSDT',
      venue: 'Binance',
      last: '101',
      change: '+1.00%',
      tone: 'up',
      asOf: '2023-11-14',
      age: '1d',
      stale: false,
    })
    expect(watchRow('BTC/USDT', quote([bar(100), bar(98)]), NOW).tone).toBe('down')
    expect(watchRow('BTC/USDT', quote([bar(100), bar(98)]), NOW).change).toBe('-2.00%')
    expect(watchRow('BTC/USDT', quote([bar(100), bar(100)]), NOW)).toMatchObject({ change: '0.00%', tone: 'flat' })
  })

  it('never invents a price', () => {
    expect(watchRow('SOL/USDT', null, NOW)).toEqual({
      symbol: 'SOL/USDT',
      label: 'SOLUSDT',
      venue: null,
      last: '—',
      change: '—',
      tone: 'none',
      asOf: null,
      age: null,
      stale: false,
    })
    expect(watchRow('SOL/USDT', quote([]), NOW)).toMatchObject({ last: '—', tone: 'none', asOf: null })
    expect(watchRow('SOL/USDT', quote([bar(Number.NaN)]), NOW)).toMatchObject({ last: '—', tone: 'none' })
    // One bar: a last price but no daily change to report.
    expect(watchRow('SOL/USDT', quote([bar(12.5)]), NOW)).toMatchObject({ last: '12.5', change: '—', tone: 'none', asOf: '1970-01-01' })
    expect(watchRow('SOL/USDT', quote([bar(0), bar(1)]), NOW).change).toBe('—')
  })

  it('marks a bar older than two days as stale history, not a quote', () => {
    const twoDaysAgo = NOW / 1000 - 2 * 86_400
    expect(isStale(twoDaysAgo + 1, NOW)).toBe(false)
    expect(isStale(twoDaysAgo - 1, NOW)).toBe(true)
    expect(ageText(twoDaysAgo, NOW)).toBe('2d')
    expect(ageText(NOW / 1000 + 60, NOW)).toBe('0d')
    expect(watchRow('BTC/USD', quote([bar(1), bar(2, 0)], 'ccxt:coinbase'), NOW)).toMatchObject({
      venue: 'Coinbase',
      asOf: '1970-01-01',
      age: '19677d',
      stale: true,
    })
  })

  it('names venues from the provenance source and never guesses one', () => {
    expect(venueLabel('ccxt:binance')).toBe('Binance')
    expect(venueLabel('ccxt:coinbase')).toBe('Coinbase')
    expect(venueLabel('tiingo')).toBe('Tiingo')
    expect(venueLabel('yfinance')).toBe('Yahoo')
    expect(venueLabel('ccxt:okx')).toBe('Okx')
    expect(venueLabel(null)).toBeNull()
    expect(venueLabel('')).toBeNull()
  })

  it('spells symbols the artboard way and groups related quotes by base asset', () => {
    expect(displaySymbol('BTC/USDT')).toBe('BTCUSDT')
    expect(displaySymbol('AAPL')).toBe('AAPL')
    expect(baseAsset('BTC/USDT')).toBe('BTC')
    expect(baseAsset('BTC-USD')).toBe('BTC')
    expect(baseAsset('AAPL')).toBe('AAPL')
    const rows = watchRows(
      'crypto',
      ['BTC/USD', 'XRP/USD'],
      { 'BTC/USDT': quote([bar(100), bar(110)]), 'BTC/USD': quote([bar(100), bar(90)], 'ccxt:coinbase') },
      NOW,
    )
    expect(relatedRows('BTC/USDT', rows).map((row) => `${row.label} ${row.venue}`)).toEqual([
      'BTCUSDT Binance',
      'BTCUSD Coinbase',
    ])
    expect(rows[0]).toMatchObject({ symbol: 'BTC/USDT', change: '+10.00%', tone: 'up' })
    expect(rows.filter((row) => row.symbol !== 'BTC/USDT' && row.symbol !== 'BTC/USD').every((row) => row.last === '—')).toBe(true)
  })

  it('polls public tickers only while asked for and visible', () => {
    expect(shouldPoll(true, 'visible')).toBe(true)
    expect(shouldPoll(true, 'hidden')).toBe(false)
    expect(shouldPoll(false, 'visible')).toBe(false)
  })

  it('quotes a row only from its own venue and never from a venue without a public ticker', () => {
    const row = watchRow('BTC/USDT', quote([bar(100), bar(110, 0)]), NOW)
    expect(tickerExchange(row)).toBe('binance')
    expect(tickerExchange(watchRow('BTC/USD', quote([bar(1)], 'ccxt:coinbase'), NOW))).toBe('coinbase')
    expect(tickerExchange(watchRow('AAPL', quote([bar(1)], 'tiingo'), NOW))).toBeNull()
    expect(tickerExchange(watchRow('SOL/USDT', null, NOW))).toBeNull()
    const live = applyTicker(row, { symbol: 'BTC/USDT', exchange: 'binance', last: 112.5, ts: '2026-09-03T14:02:11+00:00' })
    expect(live).toMatchObject({ last: '112.5', asOf: 'live', age: 'live', stale: false, change: '+10.00%' })
    // Another venue, another symbol, or a nonsense price leaves the stored close in place.
    expect(applyTicker(row, { symbol: 'BTC/USDT', exchange: 'coinbase', last: 1, ts: '' })).toBe(row)
    expect(applyTicker(row, { symbol: 'ETH/USDT', exchange: 'binance', last: 1, ts: '' })).toBe(row)
    expect(applyTicker(row, { symbol: 'BTC/USDT', exchange: 'binance', last: Number.NaN, ts: '' })).toBe(row)
    expect(applyTicker(row, null)).toBe(row)
  })

  it('offers the three spec tabs', () => {
    expect(MARKET_WATCH_TABS).toEqual(['Symbols', 'Details', 'Data'])
  })
})

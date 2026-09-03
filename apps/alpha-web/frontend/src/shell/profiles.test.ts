import { describe, expect, it } from 'vitest'

import { dockOf, documentOf } from './documents'
import { MARKET_NEUTRAL_WINDOWS, PROFILES, profile, showsWindow, symbolFitsProfile } from './profiles'
import { pullDefaults, starterSymbols } from '../panels/dataManagerModel'

function deepFrozen(value: unknown): boolean {
  if (value === null || typeof value !== 'object') return true
  if (!Object.isFrozen(value)) return false
  return Object.values(value as object).every(deepFrozen)
}

describe('PROFILES', () => {
  it('declares exactly crypto and equities, frozen and data-only', () => {
    expect(Object.keys(PROFILES).sort()).toEqual(['crypto', 'equities'])
    expect(deepFrozen(PROFILES)).toBe(true)
    for (const manifest of Object.values(PROFILES)) {
      expect(Object.values(manifest).some((field) => typeof field === 'function')).toBe(false)
      expect(manifest.id in PROFILES).toBe(true)
    }
  })

  it('crypto shows only crypto data, functions and vocabulary', () => {
    const crypto = profile('crypto')
    for (const hidden of ['options', 'screener', 'corporate-actions'] as const) {
      expect(crypto.windows).not.toContain(hidden)
    }
    expect(crypto.paperVenues).not.toContain('ibkr')
    expect(crypto.providers[0]).toBe('ccxt')
    expect(crypto.providers).toEqual(expect.arrayContaining(['binance', 'bybit', 'coingecko', 'geckoterminal', 'coinmetrics']))
    expect(crypto.defaultSource).toBe('ccxt')
    expect(crypto.defaultVenue).toBe('binance')
    expect(crypto.symbolStyle).toBe('pair')
    expect(crypto.starterWatchlist).toEqual(['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT'])
  })

  it('equities hides crypto-only families and shows the four equity providers', () => {
    const equities = profile('equities')
    expect(equities.providers).toEqual(['tiingo', 'yfinance', 'stooq', 'quantpad'])
    expect(equities.defaultSource).toBe('tiingo')
    for (const hidden of ['funding', 'open-interest', 'onchain', 'dex', 'crowding'] as const) {
      expect(equities.windows).not.toContain(hidden)
    }
    expect(equities.paperVenues).not.toContain('binance-sandbox')
    expect(equities.starterWatchlist).toEqual(['SPY', 'AAPL'])
    expect(equities.symbolStyle).toBe('ticker')
  })

  it('market-neutral windows appear in both', () => {
    for (const id of ['crypto', 'equities'] as const) {
      for (const window of MARKET_NEUTRAL_WINDOWS) expect(showsWindow(id, window)).toBe(true)
      for (const window of ['forecast', 'ml-lab', 'jobs', 'governance'] as const) {
        expect(showsWindow(id, window)).toBe(true)
      }
    }
    expect(showsWindow('equities', 'funding')).toBe(false)
    expect(showsWindow('crypto', 'options')).toBe(false)
  })

  it('pullDefaults and starterSymbols are derived from the manifest', () => {
    for (const id of ['crypto', 'equities'] as const) {
      const manifest = profile(id)
      expect(pullDefaults(id)).toEqual({
        symbol: manifest.defaultSymbol,
        source: manifest.defaultSource,
        exchange: manifest.defaultVenue ?? 'binance',
      })
      expect(starterSymbols(id)).toEqual([...manifest.starterWatchlist])
    }
  })

  it('names only windows and docks the registries can open', () => {
    for (const manifest of Object.values(PROFILES)) {
      for (const window of manifest.windows) expect(documentOf(window).id).toBe(window)
      for (const dock of manifest.docks) expect(dockOf(dock).id).toBe(dock)
    }
  })

  it('rejects an unknown profile instead of returning an empty manifest', () => {
    expect(() => profile('futures' as 'crypto')).toThrow(/unknown profile/)
  })
})

describe('symbolFitsProfile', () => {
  it('reads the fit from the symbol style alone', () => {
    expect(symbolFitsProfile('crypto', 'XRP/USDT')).toBe(true)
    expect(symbolFitsProfile('crypto', 'AAPL')).toBe(false)
    expect(symbolFitsProfile('equities', 'AAPL')).toBe(true)
    expect(symbolFitsProfile('equities', 'BTC-USD')).toBe(true)
    expect(symbolFitsProfile('equities', 'XRP/USDT')).toBe(false)
  })
})


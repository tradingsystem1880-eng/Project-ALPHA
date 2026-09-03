import { beforeEach, describe, expect, it } from 'vitest'

import { pairsByVenue, resetStoredVenues, setStoredVenue } from './storedQuotes'

describe('storedQuotes', () => {
  beforeEach(() => resetStoredVenues())

  it('counts stored pairs per venue and never counts a pair without one', () => {
    expect(pairsByVenue({ 'BTC/USDT': 'Binance', 'ETH/USDT': 'Binance', 'BTC/USD': 'Coinbase', 'SOL/USDT': null })).toEqual({
      Binance: 2,
      Coinbase: 1,
    })
    expect(pairsByVenue({})).toEqual({})
  })

  it('publishes a venue once per pair', () => {
    setStoredVenue('BTC/USDT', 'Binance')
    setStoredVenue('BTC/USDT', 'Binance')
    expect(pairsByVenue({ 'BTC/USDT': 'Binance' })).toEqual({ Binance: 1 })
  })
})

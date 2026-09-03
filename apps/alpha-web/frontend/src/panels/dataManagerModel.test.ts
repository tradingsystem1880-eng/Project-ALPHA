import { describe, expect, it } from 'vitest'

import {
  listingHint,
  pullDefaults,
  retryStartFrom,
  starterSymbols,
  storageRow,
  validateDates,
} from './dataManagerModel'

describe('pull defaults', () => {
  it('starts the crypto profile on XRP/USDT at Binance and equities on AAPL at Tiingo', () => {
    expect(pullDefaults('crypto')).toEqual({ symbol: 'XRP/USDT', source: 'ccxt', exchange: 'binance' })
    expect(pullDefaults('equities')).toEqual({ symbol: 'AAPL', source: 'tiingo', exchange: 'binance' })
  })
})

describe('starter symbols', () => {
  it('offers the profile watchlist for the symbol combobox', () => {
    expect(starterSymbols('crypto')).toEqual(['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT'])
    expect(starterSymbols('equities')).toEqual(['SPY', 'AAPL'])
  })
})

describe('retry start from a failed pull', () => {
  it("reads the CLI's own retry start out of the pre-listing failure", () => {
    const message =
      'No data for XRP/USDT on binance before 2018-05-04 (first listed). Start there? (--start 2018-05-04)'
    expect(retryStartFrom(message)).toBe('2018-05-04')
  })

  it('offers nothing for any other failure', () => {
    expect(retryStartFrom('Invalid value: --end 2015-01-01 precedes --start 2020-01-01')).toBeNull()
    expect(retryStartFrom(null)).toBeNull()
  })
})

describe('date validation', () => {
  it('accepts an ordered pair of real ISO dates', () => {
    expect(validateDates('2015-01-01', '2026-06-30')).toBeNull()
    expect(validateDates('2024-02-29', '2024-02-29')).toBeNull()
  })

  it('names the impossible calendar date the owner typed', () => {
    expect(validateDates('2015-01-01', '2026-06-31')).toBe('end 2026-06-31 is not a real calendar date')
    expect(validateDates('2023-02-29', '2026-06-30')).toBe('start 2023-02-29 is not a real calendar date')
  })

  it('rejects anything that is not YYYY-MM-DD', () => {
    expect(validateDates('01/01/2015', '2026-06-30')).toBe('start 01/01/2015 must be written YYYY-MM-DD')
    expect(validateDates('2015-01-01', '')).toBe('end (empty) must be written YYYY-MM-DD')
  })

  it('names a reversed range', () => {
    expect(validateDates('2026-06-30', '2015-01-01')).toBe('end 2015-01-01 precedes start 2026-06-30')
  })
})

describe('storage row', () => {
  it('shows the unmounted Expansion SSD as an amber blocker', () => {
    expect(
      storageRow({
        state: 'blocked',
        blocker: 'bulk_volume_not_mounted',
        bulk_root_label: 'Expansion',
        free_bytes: null,
        total_bytes: null,
      }),
    ).toEqual({
      label: 'Expansion SSD not mounted',
      tone: 'amber',
      detail: 'Reconnect the Expansion volume, then refresh.',
      free: null,
    })
  })

  it('reports free space when the volume is mounted', () => {
    expect(
      storageRow({
        state: 'ready',
        blocker: null,
        bulk_root_label: 'Expansion',
        free_bytes: 1_200_000_000_000,
        total_bytes: 2_000_000_000_000,
      }),
    ).toEqual({ label: 'Expansion SSD mounted', tone: 'ok', detail: '1200 GB free of 2000 GB', free: '1.20 TB' })
  })

  it('keeps other blockers visible without inventing a cause', () => {
    expect(
      storageRow({
        state: 'blocked',
        blocker: 'reserve_exceeded',
        bulk_root_label: 'Expansion',
        free_bytes: null,
        total_bytes: null,
      }),
    ).toEqual({ label: 'Expansion SSD blocked', tone: 'amber', detail: 'reserve_exceeded', free: null })
  })

  it('is amber until the storage status has loaded', () => {
    expect(storageRow(null)).toEqual({
      label: 'Expansion SSD',
      tone: 'amber',
      detail: 'Storage status not loaded',
      free: null,
    })
  })
})

describe('listing hint', () => {
  const xrp = { first_bar_ts: '2018-05-04T00:00:00+00:00' }

  it('offers the listing date as the retry start when the request predates it', () => {
    expect(listingHint(xrp, '2015-01-01', '2018-05-13')).toEqual({
      listed: '2018-05-04',
      bars: 10,
      retryFrom: '2018-05-04',
    })
  })

  it('needs no retry when the window starts after the listing', () => {
    expect(listingHint(xrp, '2020-01-01', '2020-01-31')).toEqual({
      listed: '2018-05-04',
      bars: 31,
      retryFrom: null,
    })
  })

  it('refuses an invalid window instead of estimating from NaN', () => {
    expect(() => listingHint(xrp, '2020-01-01', '2019-12-31')).toThrow('precedes')
  })
})

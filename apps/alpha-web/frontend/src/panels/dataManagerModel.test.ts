import { describe, expect, it } from 'vitest'

import {
  listingHint,
  pullDefaults,
  retryStartFrom,
  starterSymbols,
  storageRow,
  storageNote,
  firstStoredSymbol,
  storedRows,
  STORAGE_SET_COMMAND,
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
  it('shows the unmounted storage as an amber blocker', () => {
    expect(
      storageRow({
        state: 'blocked',
        blocker: 'bulk_volume_not_mounted',
        bulk_root_label: 'Bulk',
        free_bytes: null,
        total_bytes: null,
      }),
    ).toEqual({
      label: 'Storage: not configured',
      tone: 'amber',
      detail: 'Connect the configured storage volume, then refresh.',
      free: null,
    })
  })

  it('reports free space when the volume is mounted', () => {
    expect(
      storageRow({
        state: 'ready',
        blocker: null,
        bulk_root_label: 'Bulk',
        free_bytes: 1_200_000_000_000,
        total_bytes: 2_000_000_000_000,
      }),
    ).toEqual({ label: 'Storage ready', tone: 'ok', detail: '1200 GB free of 2000 GB', free: '1.20 TB' })
  })

  it('keeps other blockers visible without inventing a cause', () => {
    expect(
      storageRow({
        state: 'blocked',
        blocker: 'reserve_exceeded',
        bulk_root_label: 'Bulk',
        free_bytes: null,
        total_bytes: null,
      }),
    ).toEqual({ label: 'Storage: low on free space', tone: 'amber', detail: 'reserve_exceeded', free: null })
  })

  it('is amber until the storage status has loaded', () => {
    expect(storageRow(null)).toEqual({
      label: 'Storage: not configured',
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

describe('storage note', () => {
  const unset = { state: 'blocked', blocker: 'bulk_volume_uuid_not_configured', bulk_root_label: 'bulk', free_bytes: null, total_bytes: null } as const

  it('is a calm note with the exact command when the reserve was never set', () => {
    const note = storageNote(unset)
    expect(note?.tone).toBe('calm')
    expect(note?.text).toContain('Stock bars do not need it')
    expect(note?.command).toBe(STORAGE_SET_COMMAND)
    expect(STORAGE_SET_COMMAND).toContain('scripts/storage_settings.py write')
  })

  it('is a real blocker for a full disk or an unmounted volume, and absent when ready', () => {
    expect(storageNote({ ...unset, blocker: 'bulk_storage_reserve_blocked' })?.tone).toBe('blocked')
    expect(storageNote({ ...unset, blocker: 'bulk_volume_not_mounted' })?.tone).toBe('blocked')
    expect(storageNote({ state: 'ready', blocker: null, bulk_root_label: 'bulk', free_bytes: 1, total_bytes: 2 })).toBeNull()
    expect(storageNote(null)).toBeNull()
  })
})

describe('default pull symbol', () => {
  it('keeps the default when stored, else the first stored symbol that fits the profile', () => {
    expect(firstStoredSymbol(['QQQ', 'SPY'], 'equities', 'SPY')).toBe('SPY')
    expect(firstStoredSymbol(['BTC/USDT', 'QQQ', 'SPY'], 'equities', 'AAPL')).toBe('QQQ')
    expect(firstStoredSymbol([], 'equities', 'AAPL')).toBe('AAPL')
    expect(firstStoredSymbol(['QQQ'], 'crypto', 'BTC/USDT')).toBe('BTC/USDT')
  })
})

describe('stored rows', () => {
  const asset = (name: string, bars: number, last: string) => ({ asset: name, bar_count: bars, last_bar: last }) as never

  it('lists symbol, bars, newest bar and how many days it trails today', () => {
    expect(storedRows([asset('SPY', 8511, '2026-11-19T00:00:00+00:00')], '2026-11-21')).toEqual([
      { symbol: 'SPY', bars: 8511, newest: '2026-11-19', daysBehind: 2, health: 'newest bar is 2 days old' },
    ])
    expect(storedRows([asset('QQQ', 10, '2026-11-21T00:00:00+00:00')], '2026-11-21')[0].health).toBe('up to date')
  })
})

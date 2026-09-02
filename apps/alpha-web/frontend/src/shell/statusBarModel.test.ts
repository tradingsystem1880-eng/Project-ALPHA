import { describe, expect, it } from 'vitest'

import { storageRow } from '../panels/dataManagerModel'
import { hoveredText, statusSegments, utcClock } from './statusBarModel'

const NOON = Date.UTC(2026, 8, 3, 12, 34, 56)

describe('statusBarModel', () => {
  it('lays the segments out in spec order', () => {
    const segments = statusSegments({
      profile: 'crypto',
      providers: [
        { id: 'ccxt', configured: true },
        { id: 'bybit', configured: false },
        { id: 'tiingo', configured: true },
      ],
      storage: storageRow({ state: 'ready', blocker: null, bulk_root_label: 'Expansion', free_bytes: 5e11, total_bytes: 1e12 }),
      now: NOON,
      hovered: null,
      barsLoaded: 1200,
    })
    expect(segments.map((item) => item.id)).toEqual([
      'help',
      'profile',
      'providers',
      'ssd',
      'paper',
      'clock',
      'ohlc',
      'bars',
    ])
    expect(segments[1].text).toBe('Crypto')
    // Only the profile's providers tick; tiingo is an equities provider.
    expect(segments[2].text).toBe('ccxt ✓  bybit ·')
    expect(segments[3]).toMatchObject({ text: 'Expansion SSD mounted', tone: 'ok', title: '500 GB free of 1000 GB' })
    expect(segments[4].text).toBe('Paper only · no live routing')
    expect(segments[5].text).toBe('12:34:56 UTC')
    expect(segments[7].text).toBe('1200 bars')
  })

  it('renders an injected clock and refuses an invalid one', () => {
    expect(utcClock(NOON)).toBe('12:34:56 UTC')
    expect(() => utcClock(Number.NaN)).toThrow(/invalid time/)
  })

  it('relays the unmounted SSD as amber and never a cached ready', () => {
    const [ssd] = statusSegments({
      profile: 'crypto',
      providers: [],
      storage: storageRow({ state: 'blocked', blocker: 'bulk_volume_not_mounted', bulk_root_label: 'Expansion', free_bytes: null, total_bytes: null }),
      now: NOON,
      hovered: null,
      barsLoaded: 0,
    }).filter((item) => item.id === 'ssd')
    expect(ssd).toMatchObject({ text: 'Expansion SSD not mounted', tone: 'warn' })
    const [notLoaded] = statusSegments({
      profile: 'equities',
      providers: [],
      storage: storageRow(null),
      now: NOON,
      hovered: null,
      barsLoaded: 0,
    }).filter((item) => item.id === 'ssd')
    expect(notLoaded.tone).toBe('warn')
  })

  it('prints — for no hovered bar and throws on a non-finite price', () => {
    expect(hoveredText(null)).toBe('O — H — L — C —')
    expect(hoveredText({ t: 0, o: 100, h: 101.5, l: 99.25, c: 100.75, v: 1 })).toBe('O 100 H 101.5 L 99.25 C 100.75')
    expect(() => hoveredText({ t: 0, o: Number.NaN, h: 1, l: 1, c: 1, v: 1 })).toThrow(/non-finite/)
  })
})

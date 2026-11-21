import { describe, expect, it } from 'vitest'

import { storageRow } from '../panels/dataManagerModel'
import { barsText, hoveredText, staleBuildSegment, statusSegments, utcClock } from './statusBarModel'

const NOON = Date.UTC(2026, 8, 3, 12, 34, 56)

describe('statusBarModel', () => {
  it('lays the segments out in artboard order', () => {
    const segments = statusSegments({
      profile: 'crypto',
      providers: [
        { id: 'binance', configured: true },
        { id: 'bybit', configured: false },
        { id: 'tiingo', configured: true },
      ],
      storage: storageRow({ state: 'ready', blocker: null, bulk_root_label: 'Bulk', free_bytes: 1.95e12, total_bytes: 2e12 }),
      now: NOON,
      hovered: null,
      barsLoaded: 2738,
    })
    expect(segments.map((item) => item.id)).toEqual(['help', 'profile', 'providers', 'ssd', 'paper', 'clock', 'ohlc', 'bars'])
    expect(segments[0].text).toBe('For Help, press F1')
    expect(segments[1].text).toBe('Profile: Crypto')
    // Only the profile's providers tick, by display name; tiingo is an equities provider.
    expect(segments[2].text).toBe('Binance ✓  Bybit ·')
    expect(segments[3]).toMatchObject({ text: 'Storage ready', tone: 'ok', title: '1950 GB free of 2000 GB' })
    expect(segments[4].text).toBe('Paper only · no live routing')
    expect(segments[5].text).toBe('3 Sep 2026, 12:34 UTC')
    expect(segments[6].text).toBe('O: — H: — L: — C: — V: —')
    expect(segments[7].text).toBe('2,738 / 2,738 bars')
  })

  it('renders an injected clock and refuses an invalid one', () => {
    expect(utcClock(NOON)).toBe('3 Sep 2026, 12:34 UTC')
    expect(() => utcClock(Number.NaN)).toThrow(/invalid time/)
  })

  it('relays the unmounted storage as amber and never a cached ready', () => {
    const [ssd] = statusSegments({
      profile: 'crypto',
      providers: [],
      storage: storageRow({ state: 'blocked', blocker: 'bulk_volume_not_mounted', bulk_root_label: 'Bulk', free_bytes: null, total_bytes: null }),
      now: NOON,
      hovered: null,
      barsLoaded: 0,
    }).filter((item) => item.id === 'ssd')
    expect(ssd).toMatchObject({ text: 'Storage: not configured', tone: 'warn' })
    const [notLoaded] = statusSegments({
      profile: 'equities',
      providers: [],
      storage: storageRow(null),
      now: NOON,
      hovered: null,
      barsLoaded: 0,
    }).filter((item) => item.id === 'ssd')
    expect(notLoaded).toMatchObject({ text: 'Storage: not configured', tone: 'warn' })
  })

  it('prints — for no hovered bar and throws on a non-finite price', () => {
    expect(hoveredText(null)).toBe('O: — H: — L: — C: — V: —')
    expect(hoveredText({ t: 0, o: 100, h: 101.5, l: 99.25, c: 100.75, v: 31204 })).toBe(
      'O: 100 H: 101.5 L: 99.25 C: 100.75 V: 31,204',
    )
    expect(() => hoveredText({ t: 0, o: Number.NaN, h: 1, l: 1, c: 1, v: 1 })).toThrow(/non-finite/)
    expect(barsText(0)).toBe('0 / 0 bars')
  })

  it('warns in one plain line when the screen was built from other code than the running code', () => {
    const older = staleBuildSegment({ code_commit: 'bbbb', build_commit: 'aaaa', build_time: '2026-11-16T08:00:00Z' })
    expect(older?.text).toBe('This screen was built from older code. Run the setup again.')
    expect(older?.title).toContain('aaaa')
    expect(staleBuildSegment({ code_commit: 'aaaa', build_commit: 'aaaa', build_time: 'x' })).toBeNull()
    // A build with no record at all is the oldest kind of stale build.
    expect(staleBuildSegment({ code_commit: 'bbbb', build_commit: 'unknown', build_time: 'unknown' })?.id).toBe('stale')
    // Without a known running commit, or without a health answer, say nothing.
    expect(staleBuildSegment({ code_commit: 'unknown', build_commit: 'aaaa', build_time: 'x' })).toBeNull()
    expect(staleBuildSegment(null)).toBeNull()
  })

  it('puts the stale-build line in the status bar after the clock', () => {
    const base = {
      profile: 'equities' as const,
      providers: [],
      storage: storageRow(null),
      now: NOON,
      hovered: null,
      barsLoaded: 0,
      health: { code_commit: 'bbbb', build_commit: 'aaaa', build_time: 'x' },
    }
    expect(statusSegments(base).map((item) => item.id)).toContain('stale')
    expect(statusSegments({ ...base, health: null }).map((item) => item.id)).not.toContain('stale')
  })

  it('shows a storage reserve that was never set as a neutral note, not a warning', () => {
    const base = {
      profile: 'equities' as const, providers: [], now: NOON, hovered: null, barsLoaded: 0,
      storage: storageRow({ state: 'blocked', blocker: 'bulk_volume_uuid_not_configured', bulk_root_label: 'bulk', free_bytes: null, total_bytes: null }),
    }
    const ssd = (storageUnset: boolean) => statusSegments({ ...base, storageUnset }).find((item) => item.id === 'ssd')
    expect(ssd(true)?.tone).toBe('none')
    expect(ssd(true)?.title).toContain('Stock bars do not need it')
    expect(ssd(false)?.tone).toBe('warn')
  })
})

// Status bar (spec 2026-09-01 §4.2 item 8): help hint · profile · provider ticks · Expansion SSD ·
// `Paper only · no live routing` · UTC clock · hovered OHLCV · bars loaded. Pure: the clock is
// injected, the SSD segment is the Data Manager's honest storage row (never a cached "ready"), a
// missing hovered bar reads `—`, and a non-finite price throws rather than printing a number.

import type { Candle } from '../api/types'
import type { StorageRow } from '../panels/dataManagerModel'
import type { Profile } from '../state/settings'
import { profile as manifest } from './profiles'

export interface StatusSegment {
  id: 'help' | 'profile' | 'providers' | 'ssd' | 'paper' | 'clock' | 'ohlc' | 'bars'
  text: string
  tone: 'none' | 'ok' | 'warn'
  title?: string
}

export interface ProviderTick {
  id: string
  configured: boolean
}

export interface StatusBarInput {
  profile: Profile
  providers: readonly ProviderTick[]
  storage: StorageRow
  /** Milliseconds since the epoch, injected by the caller. */
  now: number
  hovered: Candle | null
  barsLoaded: number
}

export function utcClock(now: number): string {
  const date = new Date(now)
  if (Number.isNaN(date.getTime())) throw new Error('status bar clock: invalid time')
  return `${date.toISOString().slice(11, 19)} UTC`
}

function price(value: number): string {
  if (!Number.isFinite(value)) throw new Error('status bar: non-finite price in hovered bar')
  return value.toLocaleString('en-US', { maximumFractionDigits: 6 })
}

export function hoveredText(bar: Candle | null): string {
  if (bar === null) return 'O — H — L — C —'
  return `O ${price(bar.o)} H ${price(bar.h)} L ${price(bar.l)} C ${price(bar.c)}`
}

export function statusSegments(input: StatusBarInput): StatusSegment[] {
  const shown = new Set(manifest(input.profile).providers)
  const ticks = input.providers
    .filter((item) => shown.has(item.id))
    .map((item) => `${item.id} ${item.configured ? '✓' : '·'}`)
  return [
    { id: 'help', text: 'F1 help · ⌘K commands', tone: 'none' },
    { id: 'profile', text: manifest(input.profile).label, tone: 'none' },
    { id: 'providers', text: ticks.length ? ticks.join('  ') : 'providers —', tone: 'none' },
    {
      id: 'ssd',
      text: input.storage.label,
      tone: input.storage.tone === 'ok' ? 'ok' : 'warn',
      title: input.storage.detail,
    },
    { id: 'paper', text: 'Paper only · no live routing', tone: 'none' },
    { id: 'clock', text: utcClock(input.now), tone: 'none' },
    { id: 'ohlc', text: hoveredText(input.hovered), tone: 'none' },
    { id: 'bars', text: `${input.barsLoaded} bars`, tone: 'none' },
  ]
}

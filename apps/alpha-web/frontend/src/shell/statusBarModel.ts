// Status bar (spec 2026-09-01 §4.2 item 8; artboard 1-Terminal): `For Help, press F1` · profile ·
// provider ticks by display name · Expansion SSD free space · `Paper only · no live routing` ·
// UTC date-time · hovered OHLCV · bars loaded. Pure: the clock is injected, the SSD segment is
// the Data Manager's honest storage row (never a cached "ready"), a missing hovered bar reads `—`,
// and a non-finite price throws rather than printing a number.

import type { Candle } from '../api/types'
import type { StorageRow } from '../panels/dataManagerModel'
import { venueLabel as providerLabel } from '../panels/marketWatchModel'
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

/** `2026-09-01 14:02 UTC`. */
export function utcClock(now: number): string {
  const date = new Date(now)
  if (Number.isNaN(date.getTime())) throw new Error('status bar clock: invalid time')
  return `${date.toISOString().slice(0, 16).replace('T', ' ')} UTC`
}

function price(value: number): string {
  if (!Number.isFinite(value)) throw new Error('status bar: non-finite price in hovered bar')
  return value.toLocaleString('en-US', { maximumFractionDigits: 6 })
}

export function hoveredText(bar: Candle | null): string {
  if (bar === null) return 'O: — H: — L: — C: — V: —'
  return `O: ${price(bar.o)} H: ${price(bar.h)} L: ${price(bar.l)} C: ${price(bar.c)} V: ${price(bar.v)}`
}

export function barsText(loaded: number): string {
  const text = loaded.toLocaleString('en-US')
  return `${text} / ${text} bars`
}

export function ssdText(storage: StorageRow): string {
  return storage.tone === 'ok' && storage.free ? `Expansion SSD ${storage.free} free` : storage.label
}

export function statusSegments(input: StatusBarInput): StatusSegment[] {
  const shown = new Set(manifest(input.profile).providers)
  const ticks = input.providers
    .filter((item) => shown.has(item.id))
    .map((item) => `${providerLabel(item.id)} ${item.configured ? '✓' : '·'}`)
  return [
    { id: 'help', text: 'For Help, press F1', tone: 'none' },
    { id: 'profile', text: `Profile: ${manifest(input.profile).label}`, tone: 'none' },
    { id: 'providers', text: ticks.length ? ticks.join('  ') : 'providers —', tone: 'none' },
    {
      id: 'ssd',
      text: ssdText(input.storage),
      tone: input.storage.tone === 'ok' ? 'ok' : 'warn',
      title: input.storage.detail,
    },
    { id: 'paper', text: 'Paper only · no live routing', tone: 'none' },
    { id: 'clock', text: utcClock(input.now), tone: 'none' },
    { id: 'ohlc', text: hoveredText(input.hovered), tone: 'none' },
    { id: 'bars', text: barsText(input.barsLoaded), tone: 'none' },
  ]
}

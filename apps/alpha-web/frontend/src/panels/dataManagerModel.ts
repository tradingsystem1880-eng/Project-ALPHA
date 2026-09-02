// Data Manager model — the pure helpers behind the Data Manager panel: profile-driven pull
// defaults, the date guard that mirrors the CLI's own checks, the Expansion SSD storage row, and
// what a venue's first listed bar means for the requested window. No React, no fetch.

import type { CryptoStorage, FirstBar } from '../api/types'
import { profile as manifest } from '../shell/profiles'
import type { Profile } from '../state/settings'

export interface PullDefaults {
  symbol: string
  source: string
  exchange: string
}

/** Read from the profile manifest; the CLI ignores `exchange` for non-ccxt sources. */
export function pullDefaults(profile: Profile): PullDefaults {
  const found = manifest(profile)
  return {
    symbol: found.defaultSymbol,
    source: found.defaultSource,
    exchange: found.defaultVenue ?? 'binance',
  }
}

/** The profile's starter watchlist, offered beside the stored pairs in the symbol combobox. */
export function starterSymbols(profile: Profile): string[] {
  return [...manifest(profile).starterWatchlist]
}

const RETRY_START = /\(--start (\d{4}-\d{2}-\d{2})\)/

/** The retry start the CLI itself proposes in a pre-listing failure, else null. */
export function retryStartFrom(message: string | null): string | null {
  return message === null ? null : (RETRY_START.exec(message)?.[1] ?? null)
}

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

function calendarProblem(name: 'start' | 'end', value: string): string | null {
  const match = ISO_DATE.exec(value)
  if (!match) return `${name} ${value || '(empty)'} must be written YYYY-MM-DD`
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])]
  const date = new Date(Date.UTC(year, month - 1, day))
  const real =
    date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
  return real ? null : `${name} ${value} is not a real calendar date`
}

/** Why `alpha data pull` would reject this window, or null when both dates are real and ordered. */
export function validateDates(start: string, end: string): string | null {
  const problem = calendarProblem('start', start) ?? calendarProblem('end', end)
  if (problem) return problem
  return end < start ? `end ${end} precedes start ${start}` : null
}

export interface StorageRow {
  label: string
  tone: 'ok' | 'amber'
  detail: string
}

type StorageStatus = Pick<
  CryptoStorage,
  'state' | 'blocker' | 'bulk_root_label' | 'free_bytes' | 'total_bytes'
>

/** One honest row for the Expansion SSD: mounted with free space, a named blocker, or not loaded. */
export function storageRow(storage: StorageStatus | null): StorageRow {
  if (storage === null) {
    return { label: 'Expansion SSD', tone: 'amber', detail: 'Storage status not loaded' }
  }
  if (storage.state === 'blocked') {
    return storage.blocker === 'bulk_volume_not_mounted'
      ? {
          label: 'Expansion SSD not mounted',
          tone: 'amber',
          detail: 'Reconnect the Expansion volume, then refresh.',
        }
      : { label: 'Expansion SSD blocked', tone: 'amber', detail: storage.blocker ?? 'blocked' }
  }
  const { free_bytes: free, total_bytes: total } = storage
  const detail =
    typeof free === 'number' && typeof total === 'number'
      ? `${gigabytes(free)} GB free of ${gigabytes(total)} GB`
      : storage.bulk_root_label
  return { label: 'Expansion SSD mounted', tone: 'ok', detail }
}

function gigabytes(bytes: number): number {
  return Math.round(bytes / 1e9)
}

export interface ListingHint {
  listed: string
  bars: number
  retryFrom: string | null
}

const DAY_MS = 86_400_000

/**
 * What the venue's first bar means for a requested window: the listing date, the daily bars a
 * pull from max(start, listed) to end would fetch, and the start to retry from when the request
 * predates the listing.
 */
export function listingHint(
  firstBar: Pick<FirstBar, 'first_bar_ts'>,
  start: string,
  end: string,
): ListingHint {
  const problem = validateDates(start, end)
  if (problem) throw new Error(problem)
  const listed = firstBar.first_bar_ts.slice(0, 10)
  const from = start < listed ? listed : start
  const bars =
    end < from
      ? 0
      : (Date.parse(`${end}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / DAY_MS + 1
  return { listed, bars, retryFrom: start < listed ? listed : null }
}

// Data Manager model — the pure helpers behind the Data Manager panel: profile-driven pull
// defaults, the date guard that mirrors the CLI's own checks, the storage row, and
// what a venue's first listed bar means for the requested window. No React, no fetch.

import type { CryptoStorage, FirstBar, MarketAsset } from '../api/types'
import { profile as manifest } from '../shell/profiles'
import { symbolFitsProfile } from '../shell/profiles'
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
  /** Free space as `1.95 TB` / `500 GB` when the mounted volume reports it; else null. */
  free: string | null
}

type StorageStatus = Pick<
  CryptoStorage,
  'state' | 'blocker' | 'bulk_root_label' | 'free_bytes' | 'total_bytes'
>
type StatusStorage = StorageStatus

/** One honest row for storage: mounted with free space, a named blocker, or not loaded. */
export function storageRow(storage: StorageStatus | null): StorageRow {
  if (storage === null) {
    return { label: 'Storage: not configured', tone: 'amber', detail: 'Storage status not loaded', free: null }
  }
  if (storage.state === 'blocked') {
    return storage.blocker === 'bulk_volume_not_mounted'
      ? {
          label: 'Storage: not configured',
          tone: 'amber',
          detail: 'Connect the configured storage volume, then refresh.',
          free: null,
        }
      : { label: storage.blocker === 'reserve_exceeded' ? 'Storage: low on free space' : 'Storage: not configured', tone: 'amber', detail: storage.blocker ?? 'blocked', free: null }
  }
  const { free_bytes: free, total_bytes: total } = storage
  const sized = typeof free === 'number' && typeof total === 'number'
  const detail = sized ? `${gigabytes(free)} GB free of ${gigabytes(total)} GB` : storage.bulk_root_label
  return { label: 'Storage ready', tone: 'ok', detail, free: sized ? freeSpace(free) : null }
}

function gigabytes(bytes: number): number {
  return Math.round(bytes / 1e9)
}

/** `1.95 TB` above a terabyte, else whole gigabytes — the status bar's free-space figure. */
export function freeSpace(bytes: number): string {
  return bytes >= 1e12 ? `${(bytes / 1e12).toFixed(2)} TB` : `${gigabytes(bytes)} GB`
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

/** The once-only step that sets the crypto-data storage reserve (`docs/operations/storage-settings.md`); a dry run that writes nothing. */
export const STORAGE_SET_COMMAND = [
  'uv run python scripts/storage_settings.py write --data-dir /home/hunta/alpha-data',
  '--bulk-root /home/hunta/alpha-data/bulk',
  '--durable-hosting-reference "Dell internal disk /dev/sda2 (ext4); owner decision 2026-11-14; not backed up"',
  '--reserve-gb 10 --advisory-gb 20 --decided-by owner --decided-on 2026-11-14',
  '--decision-record "ADR-0043; owner chat 2026-11-14: use the Dell\'s available disk for now"',
].join(' ')

export interface StorageNote {
  tone: 'calm' | 'blocked'
  text: string
  command: string | null
}

/** A note on crypto-data storage: calm and plain when it was never set up; a blocker only when something is really blocked. */
export function storageNote(storage: StatusStorage | null): StorageNote | null {
  if (storage === null || storage.state !== 'blocked') return null
  if (storage.blocker === 'bulk_volume_uuid_not_configured') {
    return {
      tone: 'calm',
      text:
        'Crypto data storage is not set up yet. Stock bars do not need it. Set it once before you download crypto data. '
        + 'This command only prints what it would write; add --apply to write it.',
      command: STORAGE_SET_COMMAND,
    }
  }
  return {
    tone: 'blocked',
    text: storage.blocker === 'bulk_volume_not_mounted'
      ? 'The configured storage volume is not connected. Connect it, then refresh.'
      : `Storage is blocked: ${storage.blocker ?? 'reason not reported'}.`,
    command: null,
  }
}

/** The symbol the Pull form starts on: the profile default when it is stored, else the first stored symbol that fits the profile. */
export function firstStoredSymbol(stored: readonly string[], profile: Profile, fallback: string): string {
  if (stored.includes(fallback)) return fallback
  return stored.find((symbol) => symbolFitsProfile(profile, symbol)) ?? fallback
}

export interface StoredRow {
  symbol: string
  bars: number
  newest: string
  daysBehind: number
  health: string
}

/** One row per stored symbol: bar count, newest bar and how old it is against `today` (YYYY-MM-DD). */
export function storedRows(assets: readonly Pick<MarketAsset, 'asset' | 'bar_count' | 'last_bar'>[], today: string): StoredRow[] {
  return assets.map((item) => {
    const newest = item.last_bar.slice(0, 10)
    const daysBehind = Math.max(0, Math.round((Date.parse(`${today}T00:00:00Z`) - Date.parse(`${newest}T00:00:00Z`)) / DAY_MS))
    return {
      symbol: item.asset,
      bars: item.bar_count,
      newest,
      daysBehind,
      health: daysBehind === 0 ? 'up to date' : `newest bar is ${daysBehind} day${daysBehind === 1 ? '' : 's'} old`,
    }
  })
}

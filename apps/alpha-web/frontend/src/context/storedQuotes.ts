// Which venue each stored pair was pulled from, published by Market Watch (it already reads every
// pair's provenance) and read by the Navigator for its `Binance (5 pairs)` counts, so the venue
// of a pair is fetched once. A pair with no stored bars is published as null.

import { useSyncExternalStore } from 'react'

export type StoredVenues = Readonly<Record<string, string | null>>

let state: StoredVenues = {}
const listeners = new Set<() => void>()

export function setStoredVenue(symbol: string, venue: string | null): void {
  if (state[symbol] === venue && symbol in state) return
  state = { ...state, [symbol]: venue }
  for (const listener of listeners) listener()
}

export function resetStoredVenues(): void {
  state = {}
  for (const listener of listeners) listener()
}

export function useStoredVenues(): StoredVenues {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => state,
  )
}

/** Venue label → number of stored pairs; pairs without a venue are not counted anywhere. */
export function pairsByVenue(venues: StoredVenues): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const venue of Object.values(venues)) {
    if (venue) counts[venue] = (counts[venue] ?? 0) + 1
  }
  return counts
}

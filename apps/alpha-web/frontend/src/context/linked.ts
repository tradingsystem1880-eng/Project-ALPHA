// Global linked context (active symbol + as-of range) as a tiny external store.
//
// A module-level store (not React context) so it works across Dockview's panel portals: any panel
// can read it with useLinked() and any producer (run/symbol select) can broadcast with setLinked().

import { useEffect, useState, useSyncExternalStore } from 'react'

export interface LinkedState {
  symbol: string | null
  start: string | null
  end: string | null
  runId: string | null
}

let state: LinkedState = { symbol: null, start: null, end: null, runId: null }
const listeners = new Set<() => void>()

export function getLinked(): LinkedState {
  return state
}

export function setLinked(patch: Partial<LinkedState>): void {
  state = { ...state, ...patch }
  listeners.forEach((l) => l())
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb)
  return () => {
    listeners.delete(cb)
  }
}

export function useLinked(): LinkedState {
  return useSyncExternalStore(subscribe, getLinked, getLinked)
}

// Local state for a panel input that seeds from, and follows, one linked-context field. The panel
// still calls setLinked({...}) itself to broadcast a new value to other panels.
export function useLinkedField(
  field: keyof LinkedState,
  fallback: string,
): [string, (value: string) => void] {
  const current = useLinked()[field]
  const [value, setValue] = useState(current ?? fallback)
  useEffect(() => {
    if (current) setValue(current)
  }, [current])
  return [value, setValue]
}

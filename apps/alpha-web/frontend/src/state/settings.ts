// Global UI settings (display density + explanation mode) as a tiny external store.
//
// Mirrors context/linked.ts: a module-level store (not React context) so it works across
// Dockview's separate panel roots. Persisted to localStorage; density is also mirrored onto
// <html> so pure CSS can react (html[data-density='compact'] tightens the density knobs) —
// explain mode has no CSS consumers and is read through useSettings() only.

import { useSyncExternalStore } from 'react'

export type Density = 'comfortable' | 'compact'
export type ExplainMode = 'narrative' | 'terse'

export interface Settings {
  density: Density
  explain: ExplainMode
}

const STORAGE_KEY = 'alpha.settings'
const DEFAULTS: Settings = { density: 'comfortable', explain: 'narrative' }

let state: Settings = DEFAULTS
const listeners = new Set<() => void>()

function load(): Settings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULTS
    const parsed = JSON.parse(raw) as Partial<Settings>
    return {
      density: parsed.density === 'compact' ? 'compact' : 'comfortable',
      explain: parsed.explain === 'terse' ? 'terse' : 'narrative',
    }
  } catch {
    return DEFAULTS
  }
}

function applyAttrs(): void {
  document.documentElement.setAttribute('data-density', state.density)
}

/** Load persisted settings and stamp the <html> data attributes. Call once at boot. */
export function initSettings(): void {
  state = load()
  applyAttrs()
}

export function getSettings(): Settings {
  return state
}

export function setSettings(patch: Partial<Settings>): void {
  state = { ...state, ...patch }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    /* storage full/blocked — settings still apply for this session */
  }
  applyAttrs()
  listeners.forEach((l) => l())
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb)
  return () => {
    listeners.delete(cb)
  }
}

export function useSettings(): Settings {
  return useSyncExternalStore(subscribe, getSettings, getSettings)
}

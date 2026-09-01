// Global UI settings (display density + explanation mode + market profile) as a tiny external store.
//
// Mirrors context/linked.ts: a module-level store (not React context) so it works across
// Dockview's separate panel roots. Persisted to localStorage; density and profile are also
// mirrored onto <html> so pure CSS can react (html[data-density='compact'] tightens the density
// knobs; html[data-profile] has no CSS consumer yet) — explain mode is read through useSettings().

import { useSyncExternalStore } from 'react'

export type Density = 'comfortable' | 'compact'
export type ExplainMode = 'narrative' | 'terse'
export type WorkspaceMode = 'guided' | 'advanced'
export type Profile = 'crypto' | 'equities'

export interface Settings {
  density: Density
  explain: ExplainMode
  profile: Profile
  projectModes: Record<string, WorkspaceMode>
}

const STORAGE_KEY = 'alpha.settings'
const DEFAULTS: Settings = {
  density: 'comfortable',
  explain: 'narrative',
  profile: 'crypto',
  projectModes: {},
}

let state: Settings = DEFAULTS
const listeners = new Set<() => void>()

/** Persisted settings from their JSON, every unknown or garbage field falling back to its default. */
export function parseSettings(raw: string | null): Settings {
  if (!raw) return DEFAULTS
  try {
    const parsed = JSON.parse(raw) as Partial<Settings>
    return {
      density: parsed.density === 'compact' ? 'compact' : 'comfortable',
      explain: parsed.explain === 'terse' ? 'terse' : 'narrative',
      profile: parsed.profile === 'equities' ? 'equities' : 'crypto',
      projectModes: Object.fromEntries(
        Object.entries(parsed.projectModes ?? {}).filter(
          (entry): entry is [string, WorkspaceMode] =>
            entry[1] === 'guided' || entry[1] === 'advanced',
        ),
      ),
    }
  } catch {
    return DEFAULTS
  }
}

function load(): Settings {
  try {
    return parseSettings(localStorage.getItem(STORAGE_KEY))
  } catch {
    return DEFAULTS
  }
}

export function workspaceModeFor(settings: Settings, projectId: string | null): WorkspaceMode {
  return projectId ? (settings.projectModes[projectId] ?? 'guided') : 'guided'
}

function applyAttrs(): void {
  document.documentElement.setAttribute('data-density', state.density)
  document.documentElement.setAttribute('data-profile', state.profile)
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

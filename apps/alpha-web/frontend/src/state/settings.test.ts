import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Settings } from './settings'
import { initSettings, parseSettings, setSettings, workspaceModeFor } from './settings'

const settings: Settings = {
  density: 'comfortable',
  explain: 'narrative',
  profile: 'crypto',
  projectModes: { advanced_project: 'advanced' },
}

describe('workspace detail mode', () => {
  it('defaults every project and the unlinked workspace to guided mode', () => {
    expect(workspaceModeFor(settings, null)).toBe('guided')
    expect(workspaceModeFor(settings, 'new_project')).toBe('guided')
  })

  it('restores advanced mode only for the project that selected it', () => {
    expect(workspaceModeFor(settings, 'advanced_project')).toBe('advanced')
    expect(workspaceModeFor(settings, 'another_project')).toBe('guided')
  })
})

describe('profile setting', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('defaults to crypto and falls back to it on garbage', () => {
    expect(parseSettings(null).profile).toBe('crypto')
    expect(parseSettings('{"profile":"equities"}').profile).toBe('equities')
    expect(parseSettings('{"profile":"forex"}').profile).toBe('crypto')
    expect(parseSettings('not json').profile).toBe('crypto')
  })

  it('mirrors the profile onto <html data-profile> at boot and on change', () => {
    const setAttribute = vi.fn()
    const store = new Map<string, string>([['alpha.settings', '{"profile":"equities"}']])
    vi.stubGlobal('document', { documentElement: { setAttribute } })
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, value),
    })
    initSettings()
    expect(setAttribute).toHaveBeenCalledWith('data-profile', 'equities')
    setSettings({ profile: 'crypto' })
    expect(setAttribute).toHaveBeenLastCalledWith('data-profile', 'crypto')
    expect(JSON.parse(store.get('alpha.settings') ?? '{}').profile).toBe('crypto')
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Settings } from './settings'
import { CHART_TEMPLATE_VERSION, initSettings, parseSettings, setSettings, workspaceModeFor } from './settings'
import { CLASSIC_TEMPLATE } from '../panels/chartOverlaysModel'

const settings: Settings = {
  density: 'comfortable',
  explain: 'narrative',
  profile: 'crypto',
  projectModes: { advanced_project: 'advanced' },
  liveTicker: false,
  chartStyle: 'classic',
  chartTemplate: CHART_TEMPLATE_VERSION,
  overlays: { crypto: { indicators: [], patterns: [] }, equities: { indicators: [], patterns: [] } },
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
    expect(parseSettings('{"liveTicker":true}').liveTicker).toBe(true)
    expect(parseSettings('{"liveTicker":"yes"}').liveTicker).toBe(false)
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

describe('chart overlays setting', () => {
  it('keeps one overlay selection per profile and drops garbage specs', () => {
    const parsed = parseSettings(
      JSON.stringify({
        overlays: { crypto: { indicators: ['sma:20', 'nope'], patterns: ['swings'] }, equities: 'junk' },
      }),
    )
    expect(parsed.overlays.crypto).toEqual({ indicators: ['sma:20'], patterns: ['swings'] })
    expect(parsed.overlays.equities).toEqual({ indicators: CLASSIC_TEMPLATE.indicators, patterns: [] })
    expect(parseSettings(null).overlays.crypto).toEqual(CLASSIC_TEMPLATE)
  })
  it('offers the Classic studies template once, only where no studies were chosen', () => {
    const before = parseSettings(JSON.stringify({ overlays: { crypto: { indicators: [], patterns: ['swings'] }, equities: { indicators: ['ema:9'], patterns: [] } } }))
    expect(before.overlays.crypto).toEqual({ indicators: CLASSIC_TEMPLATE.indicators, patterns: ['swings'] })
    expect(before.overlays.equities.indicators).toEqual(['ema:9'])
    const cleared = parseSettings(JSON.stringify({ chartTemplate: CHART_TEMPLATE_VERSION, overlays: { crypto: { indicators: [], patterns: [] } } }))
    expect(cleared.overlays.crypto).toEqual({ indicators: [], patterns: [] })
  })
  it('defaults the chart style to StockCharts Classic', () => {
    expect(parseSettings(null).chartStyle).toBe('classic')
    expect(parseSettings(JSON.stringify({ chartStyle: 'default' })).chartStyle).toBe('default')
    expect(parseSettings(JSON.stringify({ chartStyle: 'neon' })).chartStyle).toBe('classic')
  })
})

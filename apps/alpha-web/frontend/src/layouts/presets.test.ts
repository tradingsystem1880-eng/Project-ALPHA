import { describe, expect, it, vi } from 'vitest'

import {
  LAYOUT_KEY,
  V2_PANEL_COMPONENT_ALIASES,
  WORKSPACE_PRESETS,
  buildWorkspaceLayout,
  restoreStoredLayout,
} from './presets'

const V2_LAYOUT = {
  grid: {
    root: {
      type: 'branch',
      size: 1440,
      data: [
        {
          type: 'leaf',
          size: 900,
          data: {
            id: 'group-main',
            views: ['RunBrowser-0', 'ActivityFeed-0'],
            activeView: 'RunBrowser-0',
          },
        },
        {
          type: 'leaf',
          size: 540,
          data: {
            id: 'group-lab',
            views: ['StrategyLab-lab'],
            activeView: 'StrategyLab-lab',
          },
        },
      ],
    },
    width: 1440,
    height: 900,
    orientation: 'HORIZONTAL',
  },
  panels: {
    'RunBrowser-0': {
      id: 'RunBrowser-0',
      contentComponent: 'RunBrowser',
      title: 'Runs',
      params: {},
    },
    'ActivityFeed-0': {
      id: 'ActivityFeed-0',
      contentComponent: 'ActivityFeed',
      title: 'Activity',
      params: {},
    },
    'StrategyLab-lab': {
      id: 'StrategyLab-lab',
      contentComponent: 'StrategyLab',
      title: 'Strategy Lab',
      params: { defaultCommand: 'validate' },
    },
  },
  activeGroup: 'group-main',
}

function fakeDock() {
  const panels: { id: string }[] = []
  return {
    panels,
    clear: vi.fn(() => panels.splice(0)),
    addPanel: vi.fn((options: { id: string; component: string }) => {
      const panel = { id: options.id, api: { setActive: vi.fn() } }
      panels.push(panel)
      return panel
    }),
    fromJSON: vi.fn(() => panels.push({ id: 'restored' })),
  }
}

describe('v3 workspace presets', () => {
  it('ships the six named desks with Market Desk as the default', () => {
    expect(WORKSPACE_PRESETS.map((preset) => preset.id)).toEqual([
      'market',
      'development',
      'kronos',
      'ml',
      'portfolio',
      'operations',
    ])
    expect(WORKSPACE_PRESETS[0]?.name).toBe('Market Desk')
  })

  it.each(WORKSPACE_PRESETS)('builds $name with unique deterministic panels', (preset) => {
    const dock = fakeDock()
    buildWorkspaceLayout(dock as never, preset.id)

    const calls = dock.addPanel.mock.calls.map(([options]) => options)
    expect(dock.clear).toHaveBeenCalledOnce()
    expect(calls.length).toBeGreaterThanOrEqual(4)
    expect(new Set(calls.map((call) => call.id)).size).toBe(calls.length)
    expect(calls.map((call) => call.component)).toEqual(
      expect.arrayContaining(preset.requiredComponents),
    )
  })

  it('documents every historical v2 component as a canonical identity alias', () => {
    expect(Object.keys(V2_PANEL_COMPONENT_ALIASES).sort()).toEqual(
      [
        'ActivityFeed',
        'AiConsole',
        'DataExplorer',
        'Glossary',
        'JobMonitor',
        'OptionsGreeks',
        'PaperMonitor',
        'Pipeline',
        'PriceChart',
        'ProviderSystem',
        'RiskMonitor',
        'RunBrowser',
        'RunDetail',
        'Screener',
        'StrategyLab',
        'Workspaces',
      ].sort(),
    )
    expect(
      Object.entries(V2_PANEL_COMPONENT_ALIASES).every(([legacy, canonical]) => legacy === canonical),
    ).toBe(true)
  })

  it('migrates a real-shaped v2 layout without modifying its legacy source', () => {
    const dock = fakeDock()
    const legacy = JSON.stringify(V2_LAYOUT)
    const values = new Map([['alpha.layout.v2', legacy]])
    const storage = {
      getItem: vi.fn((key: string) => values.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => values.set(key, value)),
    }

    expect(restoreStoredLayout(dock as never, storage)).toBe(true)
    expect(dock.fromJSON).toHaveBeenCalledWith(V2_LAYOUT)
    expect(values.get('alpha.layout.v2')).toBe(legacy)
    expect(values.get(LAYOUT_KEY)).toBe(JSON.stringify(V2_LAYOUT))
  })

  it('skips an unknown legacy component without loading or overwriting either layout key', () => {
    const dock = fakeDock()
    const unknown = JSON.parse(JSON.stringify(V2_LAYOUT)) as typeof V2_LAYOUT
    unknown.panels['StrategyLab-lab'].contentComponent = 'RemovedPrototypePanel'
    const legacy = JSON.stringify(unknown)
    const values = new Map([['alpha.layout.v2', legacy]])
    const storage = {
      getItem: vi.fn((key: string) => values.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => values.set(key, value)),
    }

    expect(restoreStoredLayout(dock as never, storage)).toBe(false)
    expect(dock.fromJSON).not.toHaveBeenCalled()
    expect(dock.clear).not.toHaveBeenCalled()
    expect(storage.setItem).not.toHaveBeenCalled()
    expect(values.get('alpha.layout.v2')).toBe(legacy)
    expect(values.has(LAYOUT_KEY)).toBe(false)
  })

  it('writes no v3 copy when Dockview rejects an otherwise valid migrated layout', () => {
    const dock = fakeDock()
    dock.fromJSON.mockImplementationOnce(() => {
      throw new Error('invalid Dockview graph')
    })
    const legacy = JSON.stringify(V2_LAYOUT)
    const values = new Map([['alpha.layout.v2', legacy]])
    const storage = {
      getItem: vi.fn((key: string) => values.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => values.set(key, value)),
    }

    expect(restoreStoredLayout(dock as never, storage)).toBe(false)
    expect(dock.clear).toHaveBeenCalledOnce()
    expect(storage.setItem).not.toHaveBeenCalled()
    expect(values.get('alpha.layout.v2')).toBe(legacy)
    expect(values.has(LAYOUT_KEY)).toBe(false)
  })
})

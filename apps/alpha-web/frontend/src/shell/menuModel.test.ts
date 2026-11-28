import { describe, expect, it } from 'vitest'

import type { CommandDef } from '../api/types'
import { GROUP_MENU, MENUS, assignCommands, commandGroup, commandHome, menuBar, visibleMenus } from './menuModel'

const command = (id: string): CommandDef => ({ id, args: [], options: [], run_type: null })

const CATALOG_GROUPS = [
  'backtest',
  'context',
  'crypto-data',
  'data',
  'diagnose',
  'forecast',
  'info',
  'labels',
  'ledger',
  'lookalike',
  'ml',
  'monte-carlo',
  'optim',
  'partner',
  'project',
  'propfirm',
  'provider',
  'report',
  'research',
  'results',
  'risk',
  'strategy-candidate',
  'setup',
  'test',
  'tool',
  'unusual',
  'validate',
]

describe('menuModel', () => {
  it('places the honesty self-test under Research', () => {
    expect(assignCommands([command('partner selftest')]).Research).toEqual([
      { kind: 'command', id: 'partner selftest', label: 'partner selftest' },
    ])
  })

  it('lists the eleven menus in spec order', () => {
    expect([...MENUS]).toEqual([
      'File',
      'Edit',
      'View',
      'Insert',
      'Charts',
      'Data',
      'Research',
      'Strategy',
      'Backtest',
      'Window',
      'Help',
    ])
  })

  it('reads the group as the first word of a command id', () => {
    expect(commandGroup('backtest run')).toBe('backtest')
    expect(commandGroup('research sources claim add')).toBe('research')
    expect(commandGroup('validate')).toBe('validate')
  })

  it('places every catalog command in exactly one menu', () => {
    const catalog = CATALOG_GROUPS.map((group) => command(`${group} something`))
    const menus = assignCommands(catalog)
    const placed = Object.values(menus).flat().filter((item) => item.kind === 'command')
    expect(placed.map((item) => (item.kind === 'command' ? item.id : '')).sort()).toEqual(
      catalog.map((item) => item.id).sort(),
    )
    for (const group of CATALOG_GROUPS) expect(GROUP_MENU[group]).toBeDefined()
  })

  it('throws on a command group with no menu instead of dropping it', () => {
    expect(() => assignCommands([command('quantum thing')])).toThrow(/"quantum" \(quantum thing\) has no menu/)
  })

  it('lists the open documents under Window and pins Settings under View; no raw commands', () => {
    const menus = menuBar(
      [
        { key: 'chart', window: 'chart', title: 'Chart' },
        { key: 'report:aaaaaaaa', window: 'report', title: 'Run A' },
      ],
      'report:aaaaaaaa',
      [
        { id: 'chart', title: 'Chart' },
        { id: 'compare', title: 'Compare' },
      ],
    )
    expect(menus.Window).toEqual([
      { kind: 'shell', id: 'new-chart', label: 'New chart window' },
      { kind: 'document', key: 'chart', label: 'Chart', active: false },
      { kind: 'document', key: 'report:aaaaaaaa', label: 'Run A', active: true },
    ])
    expect(menus.Insert).toEqual([{ kind: 'shell', id: 'indicators', label: 'Indicators…' }])
    expect(menus.View).toEqual([
      { kind: 'open', window: 'chart', label: 'Chart' },
      { kind: 'open', window: 'compare', label: 'Compare' },
      { kind: 'shell', id: 'settings', label: 'Settings' },
    ])
    expect(menus.Backtest).toEqual([])
    expect(menus.Research).toEqual([])
    expect(menus.Help).toEqual([{ kind: 'shell', id: 'palette', label: 'Search  Ctrl+K' }])
    expect(visibleMenus(menus)).toEqual(['View', 'Insert', 'Window', 'Help'])
  })

  it('reflects the dock toggles under View', () => {
    const menus = menuBar([], null, [], {
      docks: [
        { id: 'MarketWatch', label: 'Market Watch', open: true },
        { id: 'DataManager', label: 'Data Manager', open: false },
      ],
    })
    expect(menus.View).toEqual([
      { kind: 'dock', id: 'MarketWatch', label: 'Market Watch', open: true },
      { kind: 'dock', id: 'DataManager', label: 'Data Manager', open: false },
      { kind: 'shell', id: 'settings', label: 'Settings' },
    ])
  })
})

describe('commandHome', () => {
  it('sends owner-authority groups to the document that performs them and data groups to the dock', () => {
    expect(commandHome('provider check')).toEqual({ kind: 'window', id: 'jobs' })
    expect(commandHome('crypto-data acquire')).toEqual({ kind: 'dock', id: 'DataManager' })
    expect(commandHome('data pull')).toEqual({ kind: 'dock', id: 'DataManager' })
  })

  it('leaves empirical launchers to the Strategy Lab', () => {
    expect(commandHome('backtest run')).toBeNull()
    expect(commandHome('validate')).toBeNull()
    expect(commandHome('')).toBeNull()
  })
})

describe('chart windows', () => {
  it('offers Tile charts as a checkbox only when the shell reports the tiling state', () => {
    const plain = menuBar([], null, [])
    expect(plain.Window.some((item) => item.kind === 'shell' && item.id === 'tile')).toBe(false)
    const tiled = menuBar([], null, [], { tiled: true })
    expect(tiled.Window[1]).toEqual({ kind: 'shell', id: 'tile', label: 'Tile charts', checked: true })
    expect(menuBar([], null, [], { tiled: false }).Window[1]).toEqual({
      kind: 'shell',
      id: 'tile',
      label: 'Tile charts',
      checked: false,
    })
  })
})

it('puts the trial ledger in Research', () => {
  expect(assignCommands([command('ledger summary')]).Research).toEqual([
    { kind: 'command', id: 'ledger summary', label: 'ledger summary' },
  ])
})

it('opens RD-Agent from View and the shared command-palette document registry', async () => {
  const { DOCUMENTS } = await import('./documents')
  const { showsWindow } = await import('./profiles')
  const { documentRoute } = await import('./workflowModel')
  const entry = DOCUMENTS.find(item => item.id === 'rdagent')
  expect(entry?.title).toBe('RD-Agent')
  expect(menuBar([], null, DOCUMENTS).View).toContainEqual({ kind: 'open', window: 'rdagent', label: 'RD-Agent' })
  expect(showsWindow('crypto', 'rdagent')).toBe(true)
  expect(showsWindow('equities', 'rdagent')).toBe(true)
  expect(documentRoute('rdagent')).toEqual({ page: 'research', pane: 'RdAgentPanel' })
})

it('puts setup finding in Research', () => {
  expect(assignCommands([command('setup find')]).Research).toEqual([
    { kind: 'command', id: 'setup find', label: 'setup find' },
  ])
})

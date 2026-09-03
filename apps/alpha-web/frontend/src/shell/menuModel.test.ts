import { describe, expect, it } from 'vitest'

import type { CommandDef } from '../api/types'
import { GROUP_MENU, MENUS, assignCommands, commandGroup, menuBar } from './menuModel'

const command = (id: string): CommandDef => ({ id, args: [], options: [], run_type: null })

const CATALOG_GROUPS = [
  'backtest',
  'crypto-data',
  'data',
  'evidence',
  'forecast',
  'info',
  'ml',
  'monte-carlo',
  'optim',
  'options',
  'owner-auth',
  'paper',
  'project',
  'propfirm',
  'provider',
  'quantpad-data',
  'report',
  'research',
  'risk',
  'screener',
  'strategy-candidate',
  'suite',
  'validate',
]

describe('menuModel', () => {
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

  it('lists the open documents under Window and pins Governance under View', () => {
    const menus = menuBar(
      [command('backtest run')],
      [
        { key: 'chart', window: 'chart', title: 'Chart' },
        { key: 'report:aaaaaaaa', window: 'report', title: 'Run A' },
      ],
      'report:aaaaaaaa',
      [
        { id: 'chart', title: 'Chart' },
        { id: 'governance', title: 'Governance' },
      ],
    )
    expect(menus.Window).toEqual([
      { kind: 'document', key: 'chart', label: 'Chart', active: false },
      { kind: 'document', key: 'report:aaaaaaaa', label: 'Run A', active: true },
    ])
    expect(menus.View).toEqual([
      { kind: 'open', window: 'chart', label: 'Chart' },
      { kind: 'open', window: 'governance', label: 'Governance' },
      { kind: 'shell', id: 'settings', label: 'Settings' },
    ])
    expect(menus.Backtest).toEqual([{ kind: 'command', id: 'backtest run', label: 'backtest run' }])
  })
})

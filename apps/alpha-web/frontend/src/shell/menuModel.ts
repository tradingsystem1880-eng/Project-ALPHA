// Menu bar (spec 2026-09-01 §4.2 item 2): eleven menus in spec order, the discoverable index of
// every command the CLI-backed API exposes. A command's group is the first word of its id
// (`backtest run` → `backtest`); every group maps to exactly one menu and an unmapped group throws,
// so a new CLI group can never silently vanish from the terminal.

import type { CommandDef } from '../api/types'
import type { OpenDocument } from './mdiModel'
import type { DockId, WindowId } from './profiles'

export const MENUS = [
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
] as const
export type MenuName = (typeof MENUS)[number]

/** CLI command group → menu. Every group `alpha info commands` can emit must appear here. */
export const GROUP_MENU: Readonly<Record<string, MenuName>> = Object.freeze({
  report: 'File',
  confirm: 'File',
  project: 'Edit',
  data: 'Data',
  context: 'Data',
  'crypto-data': 'Data',
  home: 'Data',
  provider: 'Data',
  research: 'Research',
  ledger: 'Research',
  rdagent: 'Research',
  partner: 'Research',
  lookalike: 'Research',
  unusual: 'Research',
  assistant: 'Research',
  tool: 'Research',
  next: 'Research',
  idea: 'Research',
  library: 'Research',
  follow: 'Research',
  nightly: 'Research',
  options: 'Research',
  setup: 'Research',
  labels: 'Research',
  'strategy-candidate': 'Strategy',
  rules: 'Strategy',
  ml: 'Strategy',
  forecast: 'Strategy',
  optim: 'Strategy',
  backtest: 'Backtest',
  validate: 'Backtest',
  test: 'Backtest',
  results: 'Backtest',
  diagnose: 'Backtest',
  'monte-carlo': 'Backtest',
  propfirm: 'Backtest',
  risk: 'Backtest',
  info: 'Help',
})

export type MenuItem =
  | { kind: 'command'; id: string; label: string }
  | { kind: 'document'; key: string; label: string; active: boolean }
  | { kind: 'open'; window: WindowId; label: string }
  | { kind: 'shell'; id: ShellItemId; label: string; checked?: boolean }
  | { kind: 'dock'; id: DockId; label: string; open: boolean }

export type ShellItemId = 'palette' | 'settings' | 'indicators' | 'new-chart' | 'tile'

/** The shell state the View and Research menus reflect; both parts are optional. */
export interface ShellMenuState {
  docks?: readonly { id: DockId; label: string; open: boolean }[]
  /** Whether the chart documents are tiled side by side (Window › Tile charts). */
  tiled?: boolean
}

export function commandGroup(id: string): string {
  return id.split(' ', 1)[0]
}

/** Place every catalog command in exactly one menu; throws on a group with no home. */
export function assignCommands(catalog: readonly CommandDef[]): Record<MenuName, MenuItem[]> {
  const menus = Object.fromEntries(MENUS.map((name) => [name, [] as MenuItem[]])) as Record<
    MenuName,
    MenuItem[]
  >
  for (const command of catalog) {
    const group = commandGroup(command.id)
    const menu = GROUP_MENU[group]
    if (!menu) throw new Error(`command group "${group}" (${command.id}) has no menu`)
    menus[menu].push({ kind: 'command', id: command.id, label: command.id })
  }
  return menus
}

export type CommandHome = { kind: 'window'; id: WindowId } | { kind: 'dock'; id: 'DataManager' }

const COMMAND_HOMES: Readonly<Record<string, CommandHome>> = {
  assistant: { kind: 'window', id: 'chart' },
  provider: { kind: 'window', id: 'jobs' },
  data: { kind: 'dock', id: 'DataManager' },
  'crypto-data': { kind: 'dock', id: 'DataManager' },
}

/** Where a menu command is actually performed: the document (or dock) that owns its group,
 *  or null when the generic Strategy Lab launcher is the right place (backtest, validate…). */
export function commandHome(commandId: string): CommandHome | null {
  const root = commandId.trim().split(/\s+/)[0] ?? ''
  return COMMAND_HOMES[root] ?? null
}

/**
 * The menu bar the owner sees: the documents the profile can open, the dock toggles and Settings
 * (View), Indicators (Insert), the open documents (Window) and the palette (Help). Raw CLI
 * commands are not listed: they are terminal steps, not screens. A menu with no item is hidden.
 */
export function menuBar(
  open: readonly OpenDocument[],
  active: string | null,
  available: readonly { id: WindowId; title: string }[],
  shell: ShellMenuState = {},
): Record<MenuName, MenuItem[]> {
  const menus = Object.fromEntries(MENUS.map((name) => [name, [] as MenuItem[]])) as Record<MenuName, MenuItem[]>
  for (const item of available) menus.View.push({ kind: 'open', window: item.id, label: item.title })
  for (const dock of shell.docks ?? []) menus.View.push({ kind: 'dock', id: dock.id, label: dock.label, open: dock.open })
  menus.View.push({ kind: 'shell', id: 'settings', label: 'Settings' })
  menus.Insert.push({ kind: 'shell', id: 'indicators', label: 'Indicators…' })
  menus.Help.push({ kind: 'shell', id: 'palette', label: 'Search  Ctrl+K' })
  menus.Window.push({ kind: 'shell', id: 'new-chart', label: 'New chart window' })
  if (shell.tiled !== undefined) {
    menus.Window.push({ kind: 'shell', id: 'tile', label: 'Tile charts', checked: shell.tiled })
  }
  for (const item of open) {
    menus.Window.push({ kind: 'document', key: item.key, label: item.title, active: item.key === active })
  }
  return menus
}

/** The menus that have at least one item, in menu-bar order. */
export function visibleMenus(menus: Record<MenuName, MenuItem[]>): MenuName[] {
  return MENUS.filter((name) => menus[name].length > 0)
}

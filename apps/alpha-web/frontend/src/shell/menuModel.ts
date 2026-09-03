// Menu bar (spec 2026-09-01 §4.2 item 2): eleven menus in spec order, the discoverable index of
// every command the CLI-backed API exposes. A command's group is the first word of its id
// (`backtest run` → `backtest`); every group maps to exactly one menu and an unmapped group throws,
// so a new CLI group can never silently vanish from the terminal. Governance is pinned under View.

import type { CommandDef } from '../api/types'
import type { OpenDocument } from './mdiModel'
import type { WindowId } from './profiles'

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
  'owner-auth': 'File',
  project: 'Edit',
  suite: 'Edit',
  evidence: 'Insert',
  screener: 'Charts',
  options: 'Charts',
  data: 'Data',
  'crypto-data': 'Data',
  'quantpad-data': 'Data',
  provider: 'Data',
  research: 'Research',
  'strategy-candidate': 'Strategy',
  ml: 'Strategy',
  forecast: 'Strategy',
  optim: 'Strategy',
  backtest: 'Backtest',
  validate: 'Backtest',
  'monte-carlo': 'Backtest',
  propfirm: 'Backtest',
  risk: 'Backtest',
  paper: 'Backtest',
  info: 'Help',
})

export type MenuItem =
  | { kind: 'command'; id: string; label: string }
  | { kind: 'document'; key: string; label: string; active: boolean }
  | { kind: 'open'; window: WindowId; label: string }
  | { kind: 'shell'; id: 'palette' | 'settings'; label: string }

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

/**
 * The full menu bar: catalog commands, the shell's own entries, the documents the profile can
 * open (View, Governance among them) and the open documents (Window).
 */
export function menuBar(
  catalog: readonly CommandDef[],
  open: readonly OpenDocument[],
  active: string | null,
  available: readonly { id: WindowId; title: string }[],
): Record<MenuName, MenuItem[]> {
  const menus = assignCommands(catalog)
  for (const item of available) menus.View.push({ kind: 'open', window: item.id, label: item.title })
  menus.View.push({ kind: 'shell', id: 'settings', label: 'Settings' })
  menus.Help.unshift({ kind: 'shell', id: 'palette', label: 'Search commands ⌘K' })
  for (const item of open) {
    menus.Window.push({ kind: 'document', key: item.key, label: item.title, active: item.key === active })
  }
  return menus
}

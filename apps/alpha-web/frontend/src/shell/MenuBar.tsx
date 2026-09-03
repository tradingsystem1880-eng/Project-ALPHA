// Menu bar (spec 2026-09-01 §4.2 item 2): eleven menus, keyboard operable — ArrowLeft/Right move
// between menus (and switch an open one), Enter/Space/ArrowDown open, ArrowUp/Down walk the items,
// Escape closes and returns focus. Catalog commands prefill the Strategy Development lab, so a
// menu item always lands on the command's real launch surface.

import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import type { CommandDef } from '../api/types'
import { openStrategyLab } from '../panels/actions'
import type { OpenDocument } from './mdiModel'
import { MENUS, menuBar, type MenuItem, type MenuName } from './menuModel'
import type { WindowId } from './profiles'

interface Props {
  open: readonly OpenDocument[]
  active: string | null
  available: readonly { id: WindowId; title: string }[]
  onOpenWindow: (id: WindowId) => void
  onActivate: (key: string) => void
  onPalette: () => void
  onSettings: () => void
}

export function MenuBar({ open, active, available, onOpenWindow, onActivate, onPalette, onSettings }: Props) {
  const [catalog, setCatalog] = useState<CommandDef[]>([])
  const [openMenu, setOpenMenu] = useState<MenuName | null>(null)
  const bar = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let live = true
    api
      .commands()
      .then((list) => live && setCatalog(list))
      .catch(() => live && setCatalog([]))
    return () => {
      live = false
    }
  }, [])

  useEffect(() => {
    if (!openMenu) return
    const onDown = (event: MouseEvent) => {
      if (bar.current && !bar.current.contains(event.target as Node)) setOpenMenu(null)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [openMenu])

  const menus = menuBar(catalog, open, active, available)

  const focusMenu = useCallback((name: MenuName) => {
    bar.current?.querySelector<HTMLButtonElement>(`[data-menu="${name}"]`)?.focus()
  }, [])

  const select = (item: MenuItem) => {
    setOpenMenu(null)
    if (item.kind === 'command') openStrategyLab({ command: item.id, args: '' })
    else if (item.kind === 'document') onActivate(item.key)
    else if (item.kind === 'open') onOpenWindow(item.window)
    else if (item.id === 'palette') onPalette()
    else onSettings()
  }

  const onTopKey = (name: MenuName, index: number) => (event: React.KeyboardEvent) => {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (step) {
      event.preventDefault()
      const next = MENUS[(index + step + MENUS.length) % MENUS.length]
      focusMenu(next)
      if (openMenu) setOpenMenu(next)
    } else if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      setOpenMenu(name)
      window.setTimeout(() => {
        bar.current?.querySelector<HTMLButtonElement>(`[data-menu-of="${name}"] [role="menuitem"]`)?.focus()
      }, 0)
    } else if (event.key === 'Escape') {
      setOpenMenu(null)
    }
  }

  const onItemKey = (name: MenuName) => (event: React.KeyboardEvent<HTMLButtonElement>) => {
    const items = [
      ...(bar.current?.querySelectorAll<HTMLButtonElement>(`[data-menu-of="${name}"] [role="menuitem"]`) ?? []),
    ]
    const index = items.indexOf(event.currentTarget)
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const step = event.key === 'ArrowDown' ? 1 : -1
      items[(index + step + items.length) % items.length]?.focus()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setOpenMenu(null)
      focusMenu(name)
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault()
      const at = MENUS.indexOf(name)
      const next = MENUS[(at + (event.key === 'ArrowRight' ? 1 : -1) + MENUS.length) % MENUS.length]
      setOpenMenu(next)
      focusMenu(next)
    }
  }

  return (
    <div className="menubar" role="menubar" aria-label="Terminal menu" ref={bar}>
      {MENUS.map((name, index) => (
        <div key={name} className="menu">
          <button
            type="button"
            role="menuitem"
            data-menu={name}
            className={`menu-title${openMenu === name ? ' open' : ''}`}
            aria-haspopup="menu"
            aria-expanded={openMenu === name}
            onClick={() => setOpenMenu((current) => (current === name ? null : name))}
            onMouseEnter={() => openMenu && setOpenMenu(name)}
            onKeyDown={onTopKey(name, index)}
          >
            {name}
          </button>
          {openMenu === name ? (
            <div className="menu-pop" role="menu" aria-label={name} data-menu-of={name}>
              {menus[name].length === 0 ? (
                <span className="menu-empty muted">nothing here yet</span>
              ) : (
                menus[name].map((item) => (
                  <button
                    key={`${item.kind}:${'id' in item ? item.id : 'key' in item ? item.key : item.window}`}
                    type="button"
                    role="menuitem"
                    className={`menu-item${item.kind === 'document' && item.active ? ' active' : ''}`}
                    onClick={() => select(item)}
                    onKeyDown={onItemKey(name)}
                  >
                    {item.kind === 'command' ? <span className="mono">alpha {item.label}</span> : item.label}
                  </button>
                ))
              )}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  )
}

// ⌘K command palette — open panels (and, later, launch runs) without touching the mouse.

import { Command } from 'cmdk'

import { PANEL_MENU } from '../panels/registry'

interface Props {
  open: boolean
  onClose: () => void
  onOpenPanel: (component: string, title: string) => void
}

export function CommandPalette({ open, onClose, onOpenPanel }: Props) {
  if (!open) return null
  return (
    <div className="cmdk-scrim" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}>
        <Command className="cmdk" label="Command palette">
          <Command.Input placeholder="Search panels & actions…" autoFocus />
          <Command.List>
            <Command.Empty>No matches.</Command.Empty>
            <Command.Group heading="Open panel">
              {PANEL_MENU.map((p) => (
                <Command.Item
                  key={p.component}
                  value={p.title}
                  onSelect={() => {
                    onOpenPanel(p.component, p.title)
                    onClose()
                  }}
                >
                  {p.title}
                  {p.hint ? <span className="hint">{p.hint}</span> : null}
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  )
}

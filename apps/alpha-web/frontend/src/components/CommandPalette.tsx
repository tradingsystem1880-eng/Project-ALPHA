// ⌘K command palette v2 — panels, actions, symbols, runs, and workspaces without the mouse.
// Symbol + run pages lazy-load their lists on first open; selections write linked context or
// open panels through the callbacks the shell provides.

import { Command } from 'cmdk'
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { RunListItem, WorkspaceMeta } from '../api/types'
import { setLinked } from '../context/linked'
import { PANEL_MENU } from '../panels/registry'
import { getSettings, setSettings } from '../state/settings'
import { shortId } from '../util/format'

interface Props {
  open: boolean
  onClose: () => void
  onOpenPanel: (component: string, title: string) => void
  onOpenRun: (runId: string) => void
  onLoadWorkspace: (slug: string) => void
  onSaveWorkspace: () => void
}

type Page = 'root' | 'symbols' | 'runs' | 'workspaces'

export function CommandPalette({
  open,
  onClose,
  onOpenPanel,
  onOpenRun,
  onLoadWorkspace,
  onSaveWorkspace,
}: Props) {
  const [page, setPage] = useState<Page>('root')
  const [symbols, setSymbols] = useState<string[] | null>(null)
  const [runs, setRuns] = useState<RunListItem[] | null>(null)
  const [workspaces, setWorkspaces] = useState<WorkspaceMeta[] | null>(null)

  useEffect(() => {
    if (!open) setPage('root')
  }, [open])
  useEffect(() => {
    if (page === 'symbols' && symbols === null)
      api.symbols().then((s) => setSymbols(s.symbols)).catch(() => setSymbols([]))
    if (page === 'runs' && runs === null)
      api.runs('?limit=30').then((r) => setRuns(r.items)).catch(() => setRuns([]))
    if (page === 'workspaces' && workspaces === null)
      api.workspaces().then(setWorkspaces).catch(() => setWorkspaces([]))
  }, [page, symbols, runs, workspaces])

  if (!open) return null

  const close = () => {
    setPage('root')
    onClose()
  }

  return (
    <div className="cmdk-scrim" onClick={close}>
      <div onClick={(e) => e.stopPropagation()}>
        <Command
          className="cmdk"
          label="Command palette"
          onKeyDown={(e) => {
            if (e.key === 'Backspace' && page !== 'root') {
              const target = e.target as HTMLInputElement
              if (!target.value) {
                e.preventDefault()
                setPage('root')
              }
            }
          }}
        >
          <Command.Input
            placeholder={
              page === 'root'
                ? 'Search panels & actions…'
                : page === 'symbols'
                  ? 'Set active symbol…'
                  : page === 'runs'
                    ? 'Open run…'
                    : 'Load workspace…'
            }
            autoFocus
          />
          <Command.List>
            <Command.Empty>No matches.</Command.Empty>

            {page === 'root' ? (
              <>
                <Command.Group heading="Actions">
                  <Command.Item value="set symbol" onSelect={() => setPage('symbols')}>
                    Set symbol… <span className="hint">linked context</span>
                  </Command.Item>
                  <Command.Item value="open run" onSelect={() => setPage('runs')}>
                    Open run… <span className="hint">by id·recent</span>
                  </Command.Item>
                  <Command.Item
                    value="toggle density compact comfortable"
                    onSelect={() => {
                      setSettings({
                        density: getSettings().density === 'compact' ? 'comfortable' : 'compact',
                      })
                      close()
                    }}
                  >
                    Toggle density <span className="hint">compact ↔ comfortable</span>
                  </Command.Item>
                  <Command.Item
                    value="toggle explanations narrative terse"
                    onSelect={() => {
                      setSettings({
                        explain: getSettings().explain === 'terse' ? 'narrative' : 'terse',
                      })
                      close()
                    }}
                  >
                    Toggle explanations <span className="hint">narrative ↔ terse</span>
                  </Command.Item>
                  <Command.Item
                    value="save workspace"
                    onSelect={() => {
                      onSaveWorkspace()
                      close()
                    }}
                  >
                    Save workspace… <span className="hint">named layout</span>
                  </Command.Item>
                  <Command.Item value="load workspace" onSelect={() => setPage('workspaces')}>
                    Load workspace… <span className="hint">saved layouts</span>
                  </Command.Item>
                </Command.Group>
                <Command.Group heading="Open panel">
                  {PANEL_MENU.map((p) => (
                    <Command.Item
                      key={p.component}
                      value={p.title}
                      onSelect={() => {
                        onOpenPanel(p.component, p.title)
                        close()
                      }}
                    >
                      {p.title}
                      {p.hint ? <span className="hint">{p.hint}</span> : null}
                    </Command.Item>
                  ))}
                </Command.Group>
              </>
            ) : null}

            {page === 'symbols' ? (
              <Command.Group heading="Symbols with stored bars">
                {(symbols ?? []).map((s) => (
                  <Command.Item
                    key={s}
                    value={s}
                    onSelect={() => {
                      setLinked({ symbol: s })
                      close()
                    }}
                  >
                    {s}
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}

            {page === 'runs' ? (
              <Command.Group heading="Recent runs">
                {(runs ?? []).map((r) => (
                  <Command.Item
                    key={r.run_id}
                    value={`${r.run_id} ${r.kind} ${r.label ?? ''} ${r.command ?? ''}`}
                    onSelect={() => {
                      onOpenRun(r.run_id)
                      close()
                    }}
                  >
                    <span className="mono">{shortId(r.run_id)}</span>
                    <span className="hint">
                      {r.kind} · {r.label ?? '—'}
                      {r.verdict ? ` · ${r.verdict}` : ''}
                    </span>
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}

            {page === 'workspaces' ? (
              <Command.Group heading="Saved workspaces">
                {(workspaces ?? []).map((w) => (
                  <Command.Item
                    key={w.slug}
                    value={w.name}
                    onSelect={() => {
                      onLoadWorkspace(w.slug)
                      close()
                    }}
                  >
                    {w.name}
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}
          </Command.List>
        </Command>
      </div>
    </div>
  )
}

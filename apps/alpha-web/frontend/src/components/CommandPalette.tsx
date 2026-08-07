// ⌘K palette — screens, symbols, runs and view settings without the mouse.
// Panels are no longer openable individually: every panel now lives on a screen laid out for
// its job, so the palette navigates to screens rather than spawning windows.

import { Command } from 'cmdk'
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { RunListItem } from '../api/types'
import { setLinked } from '../context/linked'
import { SCREENS, type ScreenId } from '../shell/screens'
import { getSettings, setSettings } from '../state/settings'
import { shortId } from '../util/format'

interface Props {
  open: boolean
  onClose: () => void
  onOpenScreen: (id: ScreenId) => void
  onOpenRun: (runId: string) => void
}

type Page = 'root' | 'symbols' | 'runs'

const PLACEHOLDER: Record<Page, string> = {
  root: 'Go to a screen, a run, or a symbol…',
  symbols: 'Set active symbol…',
  runs: 'Open run…',
}

export function CommandPalette({ open, onClose, onOpenScreen, onOpenRun }: Props) {
  const [page, setPage] = useState<Page>('root')
  const [symbols, setSymbols] = useState<string[] | null>(null)
  const [runs, setRuns] = useState<RunListItem[] | null>(null)

  useEffect(() => {
    if (!open) setPage('root')
  }, [open])
  useEffect(() => {
    if (page === 'symbols' && symbols === null)
      api.symbols().then((s) => setSymbols(s.symbols)).catch(() => setSymbols([]))
    if (page === 'runs' && runs === null)
      api.runs('?limit=30').then((r) => setRuns(r.items)).catch(() => setRuns([]))
  }, [page, symbols, runs])

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
          <Command.Input placeholder={PLACEHOLDER[page]} autoFocus />
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
                </Command.Group>
                <Command.Group heading="Go to">
                  {SCREENS.map((item) => (
                    <Command.Item
                      key={item.id}
                      value={`screen ${item.label} ${item.purpose}`}
                      onSelect={() => {
                        onOpenScreen(item.id)
                        close()
                      }}
                    >
                      {item.label}
                      <span className="hint">{item.purpose}</span>
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

          </Command.List>
        </Command>
      </div>
    </div>
  )
}

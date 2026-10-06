// ⌘K palette — documents, symbols, runs and view settings without the mouse. It opens the
// documents the current profile shows; the shell decides what a document is.

import { Command } from 'cmdk'
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { RunListItem } from '../api/types'
import { setLinked } from '../context/linked'
import type { functionEntries } from '../shell/terminalModel'
import type { PageId } from '../shell/workflowModel'
import { symbolFitsProfile } from '../shell/profiles'
import type { WindowId } from '../shell/profiles'
import { getSettings, setSettings } from '../state/settings'
import { shortId } from '../util/format'

interface Props {
  functions: ReturnType<typeof functionEntries>
  onNavigate: (page: PageId, pane: string) => void
  open: boolean
  onClose: () => void
  documents: readonly { id: WindowId; title: string }[]
  onOpenDocument: (id: WindowId) => void
  onOpenRun: (runId: string) => void
  onNewIdea: () => void
}

type Page = 'root' | 'symbols' | 'runs'

const PLACEHOLDER: Record<Page, string> = {
  root: 'Open a document, a run, or a symbol…',
  symbols: 'Set active symbol…',
  runs: 'Open run…',
}

export function CommandPalette({ functions, onNavigate, open, onClose, documents, onOpenDocument, onOpenRun, onNewIdea }: Props) {
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const profile = getSettings().profile
  const [page, setPage] = useState<Page>('root')
  const [search, setSearch] = useState('')
  const changePage = (next: Page) => { setSearch(''); setPage(next) }
  const [symbols, setSymbols] = useState<string[] | null>(null)
  const [runs, setRuns] = useState<RunListItem[] | null>(null)

  useEffect(() => {
    if (!open) { setSearch(''); setPage('root'); setSymbols(null); setRuns(null); setError(null) }
  }, [open])
  useEffect(() => {
    if (!open || page === 'root') return
    let active = true
    setError(null)
    if (page === 'symbols') {
      setSymbols(null)
      api.symbols().then(result => { if (active) setSymbols(result.symbols.filter(symbol => symbolFitsProfile(profile, symbol))) }).catch(cause => { if (active) setError(String(cause)) })
    } else {
      setRuns(null)
      api.runs('?limit=30').then(result => { if (active) setRuns(result.items) }).catch(cause => { if (active) setError(String(cause)) })
    }
    return () => { active = false }
  }, [open, page, profile, attempt])

  if (!open) return null

  const close = () => {
    changePage('root')
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
                changePage('root')
              }
            }
          }}
        >
          <Command.Input value={search} onValueChange={setSearch} placeholder={PLACEHOLDER[page]} autoFocus />
          <Command.List>
            {error ? <div role="alert">{error}<button className="btn" onClick={() => setAttempt(value => value + 1)}>Retry search</button></div> : page === 'symbols' && symbols === null || page === 'runs' && runs === null ? <p role="status">Loading {page}…</p> : <Command.Empty>No matches.</Command.Empty>}

            {page === 'root' ? (
              <>
                <Command.Group heading="Actions">
                  <Command.Item
                    value="new idea new research capture observation"
                    onSelect={() => {
                      onNewIdea()
                      close()
                    }}
                  >
                    New Idea / New Research <span className="hint">capture · no rules asked</span>
                  </Command.Item>
                  <Command.Item value="set symbol" onSelect={() => changePage('symbols')}>
                    Set symbol… <span className="hint">linked context</span>
                  </Command.Item>
                  <Command.Item value="open run" onSelect={() => changePage('runs')}>
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
                <Command.Group heading="Functions">
                  {functions.map(item => <Command.Item key={item.code} value={`${item.code} ${item.title} ${item.section}`} onSelect={() => { onNavigate(item.page, item.pane); close() }}>
                    <span>{item.title}</span><span className="hint">{item.code} · {item.section}</span>
                  </Command.Item>)}
                </Command.Group>
                <Command.Group heading="Open document">
                  {documents.map((item) => (
                    <Command.Item
                      key={item.id}
                      value={`document ${item.title}`}
                      onSelect={() => {
                        onOpenDocument(item.id)
                        close()
                      }}
                    >
                      {item.title}
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

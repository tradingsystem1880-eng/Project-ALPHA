// The shell: topbar (brand, working SYM/ASOF linked-context controls, density/explain toggles,
// palette, live status), the Dockview desk, completion toasts, and the ⌘K palette.
// First run (or an incompatible saved layout) opens the curated multi-pane desk preset.

import {
  DockviewReact,
  themeAbyss,
  type DockviewApi,
  type DockviewReadyEvent,
} from 'dockview-react'
import 'dockview-react/dist/styles/dockview.css'
import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from './api/client'
import { CommandPalette } from './components/CommandPalette'
import { Toasts } from './components/Toasts'
import { setLinked, useLinked } from './context/linked'
import { buildDeskLayout, LAYOUT_KEY } from './layouts/presets'
import { openRunDetail, runIdFromHash } from './panels/actions'
import { PANELS } from './panels/registry'
import { initActivity, useActivityField } from './state/activity'
import { setSettings, useSettings } from './state/settings'

function SymControl() {
  const linked = useLinked()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')
  if (!editing)
    return (
      <button onClick={() => { setValue(linked.symbol ?? ''); setEditing(true) }} title="Set the active symbol (linked across panels)">
        <span className="tag">SYM</span>
        <span className="sym">{linked.symbol ?? '—'}</span>
      </button>
    )
  return (
    <input
      className="sym-input mono"
      value={value}
      autoFocus
      spellCheck={false}
      onChange={(e) => setValue(e.target.value.toUpperCase())}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          const s = value.trim()
          if (s) setLinked({ symbol: s })
          setEditing(false)
        } else if (e.key === 'Escape') setEditing(false)
      }}
      onBlur={() => setEditing(false)}
      placeholder="SPY"
    />
  )
}

function AsofControl() {
  const linked = useLinked()
  const [open, setOpen] = useState(false)
  return (
    <span className="asof-wrap">
      <button className="range" title="As-of window (linked across panels)" onClick={() => setOpen((o) => !o)}>
        <span className="tag">ASOF</span>
        {`${linked.start ?? '—'} → ${linked.end ?? 'latest'}`}
      </button>
      {open ? (
        <span className="asof-pop" onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}>
          <label>
            <span className="eyebrow">start</span>
            <input
              className="field"
              type="date"
              value={linked.start ?? ''}
              onChange={(e) => setLinked({ start: e.target.value || null })}
            />
          </label>
          <label>
            <span className="eyebrow">end (as-of)</span>
            <input
              className="field"
              type="date"
              value={linked.end ?? ''}
              onChange={(e) => setLinked({ end: e.target.value || null })}
            />
          </label>
          <button className="btn" onClick={() => setLinked({ start: null, end: null })}>
            clear
          </button>
          <button className="btn primary" onClick={() => setOpen(false)}>
            done
          </button>
        </span>
      ) : null}
    </span>
  )
}

function StatusCluster() {
  const connection = useActivityField('connection')
  const runningJobs = useActivityField('runningJobs')
  const dotClass = connection === 'live' ? '' : connection === 'connecting' ? 'busy' : 'down'
  return (
    <div className="status" title={`activity stream: ${connection}`}>
      <span className={`dot ${dotClass}`} />
      {connection === 'live' ? 'live' : connection}
      {runningJobs > 0 ? <span className="chip kind">{runningJobs} running</span> : null}
    </div>
  )
}

export function App() {
  const dockRef = useRef<DockviewApi | null>(null)
  const seq = useRef(0)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const { density, explain } = useSettings()

  useEffect(() => {
    initActivity()
  }, [])

  const onReady = useCallback((event: DockviewReadyEvent) => {
    dockRef.current = event.api
    const saved = localStorage.getItem(LAYOUT_KEY)
    let restored = false
    if (saved) {
      try {
        event.api.fromJSON(JSON.parse(saved))
        restored = event.api.panels.length > 0
      } catch {
        restored = false
      }
    }
    if (!restored) buildDeskLayout(event.api)
    event.api.onDidLayoutChange(() => {
      try {
        localStorage.setItem(LAYOUT_KEY, JSON.stringify(event.api.toJSON()))
      } catch {
        /* ignore storage quota / serialization errors */
      }
    })
    // hash deep-link: /#run=<id> opens that run's story (openRunDetail keeps the hash current)
    const linked = runIdFromHash()
    if (linked) openRunDetail(event.api, linked)
  }, [])

  useEffect(() => {
    const onHash = () => {
      const runId = runIdFromHash()
      if (runId && dockRef.current) openRunDetail(dockRef.current, runId)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const openPanel = useCallback((component: string, title: string) => {
    const dv = dockRef.current
    if (!dv) return
    const existing = dv.panels.find((p) => p.id.startsWith(`${component}-`))
    if (existing) {
      existing.api.setActive()
      return
    }
    seq.current += 1
    dv.addPanel({ id: `${component}-${seq.current}`, component, title })
  }, [])

  const openRun = useCallback((runId: string) => {
    if (dockRef.current) openRunDetail(dockRef.current, runId)
  }, [])

  const loadWorkspace = useCallback((slug: string) => {
    const dv = dockRef.current
    if (!dv) return
    void api.getWorkspace(slug).then((doc) => {
      try {
        dv.fromJSON(doc.dockview as never)
      } catch (e) {
        console.error('workspace restore failed', e)
        if (dv.panels.length === 0) buildDeskLayout(dv)
        return
      }
      if (doc.linked_context) setLinked(doc.linked_context)
    })
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'j') {
        e.preventDefault()
        openPanel('JobMonitor', 'Jobs')
      } else if (e.key === 'Escape') {
        setPaletteOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [openPanel])

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="mark">ALPHA</span>
          <span className="sub">WORKSTATION</span>
        </div>
        <div className="linked">
          <SymControl />
          <AsofControl />
        </div>
        <div className="spacer" />
        <button
          className="kbd"
          title="Display density"
          onClick={() => setSettings({ density: density === 'compact' ? 'comfortable' : 'compact' })}
        >
          {density === 'compact' ? '▤ compact' : '▢ comfortable'}
        </button>
        <button
          className="kbd"
          title="Explanation voice — full narratives or terse annotations"
          onClick={() => setSettings({ explain: explain === 'terse' ? 'narrative' : 'terse' })}
        >
          {explain === 'terse' ? '# terse' : '¶ narrative'}
        </button>
        <button className="kbd" onClick={() => setPaletteOpen(true)}>
          Search <kbd>⌘K</kbd>
        </button>
        <StatusCluster />
      </header>
      <div className="dock">
        <DockviewReact components={PANELS} onReady={onReady} theme={themeAbyss} />
      </div>
      <Toasts onOpenRun={openRun} />
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onOpenPanel={openPanel}
        onOpenRun={openRun}
        onLoadWorkspace={loadWorkspace}
        onSaveWorkspace={() => openPanel('Workspaces', 'Workspaces')}
      />
    </div>
  )
}

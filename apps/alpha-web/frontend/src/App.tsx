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
import { restoreLinked, setLinked, useLinked, type LinkGroup } from './context/linked'
import {
  buildDeskLayout,
  buildWorkspaceLayout,
  LAYOUT_KEY,
  restoreStoredLayout,
  WORKSPACE_PRESETS,
  type WorkspacePresetId,
} from './layouts/presets'
import { openRunDetail, runIdFromHash } from './panels/actions'
import { PANELS } from './panels/registry'
import { initActivity, useActivityField } from './state/activity'
import { setSettings, useSettings } from './state/settings'
import { shortId } from './util/format'

function DeskControl({
  value,
  onChange,
}: {
  value: WorkspacePresetId | 'custom'
  onChange: (value: WorkspacePresetId) => void
}) {
  return (
    <label className="desk-control" title="Switch curated workstation layout">
      <span className="tag">DESK</span>
      <select
        value={value}
        onChange={(event) => {
          if (event.target.value !== 'custom') onChange(event.target.value as WorkspacePresetId)
        }}
      >
        {value === 'custom' ? <option value="custom">CUSTOM</option> : null}
        {WORKSPACE_PRESETS.map((preset) => (
          <option key={preset.id} value={preset.id}>
            {preset.shortName}
          </option>
        ))}
      </select>
    </label>
  )
}

function LinkGroupControl() {
  const linked = useLinked()
  return (
    <label className="group-control" title="Active panel link group">
      <span className="tag">LINK</span>
      <select
        value={linked.linkGroup}
        onChange={(event) => setLinked({ linkGroup: event.target.value as LinkGroup })}
      >
        {(['A', 'B', 'C', 'D'] as const).map((group) => (
          <option key={group}>{group}</option>
        ))}
      </select>
    </label>
  )
}

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

function ResearchContextControl() {
  const linked = useLinked()
  const [open, setOpen] = useState(false)
  return (
    <span className="research-context-wrap">
      <button
        className="research-context-summary"
        title="Project, version, universe, timeframe, snapshot, and run context"
        onClick={() => setOpen((value) => !value)}
      >
        <span><b>PRJ</b> {linked.projectId ?? '—'}</span>
        <span><b>VER</b> {linked.versionId ?? '—'}</span>
        <span><b>UNI</b> {linked.universe ?? '—'}</span>
        <span><b>TF</b> {linked.timeframe}</span>
        <span><b>SNAP</b> {linked.snapshotId ?? '—'}</span>
        <span><b>RUN</b> {linked.runId ? shortId(linked.runId) : '—'}</span>
      </button>
      {open ? (
        <span className="research-context-pop" onKeyDown={(event) => event.key === 'Escape' && setOpen(false)}>
          <label>
            <span className="eyebrow">project</span>
            <input className="field" value={linked.projectId ?? ''} onChange={(event) => setLinked({ projectId: event.target.value || null })} placeholder="project id" />
          </label>
          <label>
            <span className="eyebrow">version</span>
            <input className="field" value={linked.versionId ?? ''} onChange={(event) => setLinked({ versionId: event.target.value || null })} placeholder="version id" />
          </label>
          <label>
            <span className="eyebrow">universe</span>
            <input className="field" value={linked.universe ?? ''} onChange={(event) => setLinked({ universe: event.target.value || null })} placeholder="universe id" />
          </label>
          <label>
            <span className="eyebrow">timeframe</span>
            <select className="field" value={linked.timeframe} disabled><option value="1D">1D · daily</option></select>
          </label>
          <label>
            <span className="eyebrow">snapshot</span>
            <input className="field" value={linked.snapshotId ?? ''} onChange={(event) => setLinked({ snapshotId: event.target.value || null })} placeholder="snapshot id" />
          </label>
          <label>
            <span className="eyebrow">run</span>
            <input className="field" value={linked.runId ?? ''} onChange={(event) => setLinked({ runId: event.target.value || null })} placeholder="run id" />
          </label>
          <button className="btn primary" onClick={() => setOpen(false)}>done</button>
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
  const [activePreset, setActivePreset] = useState<WorkspacePresetId | 'custom'>('market')
  const { density, explain } = useSettings()

  useEffect(() => {
    initActivity()
  }, [])

  const onReady = useCallback((event: DockviewReadyEvent) => {
    dockRef.current = event.api
    const restored = restoreStoredLayout(event.api, localStorage)
    if (!restored) buildDeskLayout(event.api)
    setActivePreset(restored ? 'custom' : 'market')
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
      if (doc.linked_context) restoreLinked(doc.linked_context)
      setActivePreset('custom')
    })
  }, [])

  const loadPreset = useCallback((id: WorkspacePresetId) => {
    const dv = dockRef.current
    if (!dv) return
    buildWorkspaceLayout(dv, id)
    setActivePreset(id)
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
        <DeskControl value={activePreset} onChange={loadPreset} />
        <div className="linked">
          <LinkGroupControl />
          <SymControl />
          <AsofControl />
        </div>
        <ResearchContextControl />
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
        onLoadPreset={loadPreset}
        onSaveWorkspace={() => openPanel('Workspaces', 'Workspaces')}
      />
    </div>
  )
}

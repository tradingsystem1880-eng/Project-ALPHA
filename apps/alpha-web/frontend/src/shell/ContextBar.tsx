import type { ArchiveChartDataset } from '../api/client'
import { archivePairLabel } from '../components/assetChoices'
import { openArchiveMarket, openStoredMarket, openCryptoData } from '../panels/actions'
/**
 * One context control, replacing five.
 *
 * The old top bar carried DESK, LINK, SYM, ASOF and a six-field PRJ/VER/UNI/TF/SNAP/RUN
 * strip, each its own popover. That is a lot of chrome for state that is really one thing:
 * *what am I looking at*. The chip reads the artboard way — `BTCUSDT · Binance · D1` — and
 * opens a single editor for the symbol, the window, the project and the run.
 *
 * The A/B/C/D link groups are gone. They let panels follow different contexts inside one
 * desk, which only made sense when you could tile arbitrary panels; with one context per
 * screen the mechanism cost more comprehension than it bought.
 */

import { AssetSelect } from '../components/AssetSelect'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { useAreaVersion } from '../state/activity'
import { inventoryPages, projectChoices, projectSelectionPatch, type ProjectChoice } from './projectContextModel'

import { setLinked, useLinked } from '../context/linked'
import { displaySymbol } from '../panels/marketWatchModel'
import { useSettings } from '../state/settings'
import { useStoredVenues } from '../context/storedQuotes'

export function ContextBar({ archive = null }: { archive?: ArchiveChartDataset | null }) {
  const linked = useLinked()
  const { profile } = useSettings()
  const venues = useStoredVenues()
  const venue = archive?.venue ?? (linked.symbol ? venues[linked.symbol] : null)
  const [open, setOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)
  const revision = useAreaVersion('research')
  const [projects, setProjects] = useState<ProjectChoice[]>([])
  const [projectError, setProjectError] = useState<string | null>(null)
  const [projectLoading, setProjectLoading] = useState(false)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let live = true
    setProjectLoading(true); setProjectError(null); setProjects([])
    Promise.allSettled([
      inventoryPages(offset => api.projects(50, offset)),
      inventoryPages(offset => api.researchCases({ limit: 50, offset })),
    ]).then(([strategy, research]) => {
      if (!live) return
      setProjects(projectChoices(strategy.status === 'fulfilled' ? strategy.value : [], research.status === 'fulfilled' ? research.value : [], profile))
      const failures = [strategy.status === 'rejected' ? `Projects: ${String(strategy.reason)}` : null, research.status === 'rejected' ? `Research cases: ${String(research.reason)}` : null].filter(Boolean)
      setProjectError(failures.length ? failures.join('; ') : null)
      setProjectLoading(false)
    })
    return () => { live = false }
  }, [profile, revision, retry])

  useEffect(() => {
    if (!open) return
    const onDown = (event: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="context" ref={wrap} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <label className="toolbar-profile">
        <span>Project</span>
        <select className="field" aria-label="Project context" value={linked.projectId ?? ''} style={{ maxWidth: 180 }} onChange={event => setLinked(projectSelectionPatch(linked, event.target.value || null))}>
          <option value="">No project — browse data</option>
          {linked.projectId && !projects.some(p => p.id === linked.projectId) ? <option value={linked.projectId}>Selected: {linked.projectId}</option> : null}
          {projects.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
      </label>
      {linked.projectId ? <button className="btn" title="Clear project, version, run and snapshot; retain the viewed market and date window" onClick={() => setLinked(projectSelectionPatch(linked, null))}>Clear project</button> : null}
      {projectLoading ? <span role="status">Loading projects…</span> : null}
      {projectError ? <button className="btn" title={projectError} onClick={() => setOpen(true)}>Project inventory failed</button> : null}
      <button
        className="context-chip"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        aria-label="Symbol, venue and timeframe"
        title={`What every document is showing · ${linked.start ?? 'start'} → ${linked.end ?? 'latest'}${linked.runId ? ` · run ${linked.runId.slice(0, 8)}` : ''}`}
      >
        <span className="context-symbol">{archive ? archivePairLabel(archive) : linked.symbol ? displaySymbol(linked.symbol) : 'no symbol'}</span>
        {venue ? (
          <>
            <span className="context-sep">·</span>
            <span className="context-venue">{venue}</span>
          </>
        ) : null}
        <span className="context-sep">·</span>
        <span className="context-tf">{archive?.frequency ?? 'D1'}</span>
        <span className="context-caret" aria-hidden="true">▾</span>
      </button>

      {open ? (
        <div className="context-pop" role="dialog" aria-label="Working context">
          {projectError ? <div role="alert"><p>{projectError}</p><button className="btn" onClick={() => setRetry(value => value + 1)}>Retry project inventory</button></div> : null}
          <label>
            <span className="eyebrow">Symbol</span>
            <AssetSelect value={archive ? archivePairLabel(archive) : linked.symbol ?? ''} label="Active asset" onChange={symbol => { openStoredMarket(symbol); setOpen(false) }} onArchiveSelect={dataset => { openArchiveMarket(dataset); setOpen(false) }} />
          </label>
          <div className="context-pair">
            <label>
              <span className="eyebrow">From</span>
              <input
                className="field"
                type="date"
                value={linked.start ?? ''}
                onChange={(event) => setLinked({ start: event.target.value || null })}
              />
            </label>
            <label>
              <span className="eyebrow">To (as-of)</span>
              <input
                className="field"
                type="date"
                value={linked.end ?? ''}
                onChange={(event) => setLinked({ end: event.target.value || null })}
              />
            </label>
          </div>
          <label className="advanced-only">
            <span className="eyebrow">Strategy version</span>
            <input
              className="field mono"
              value={linked.versionId ?? ''}
              placeholder="version id"
              onChange={(event) => setLinked({ versionId: event.target.value || null })}
            />
          </label>
          <label className="advanced-only">
            <span className="eyebrow">Data snapshot</span>
            <input
              className="field mono"
              value={linked.snapshotId ?? ''}
              placeholder="snapshot id"
              onChange={(event) => setLinked({ snapshotId: event.target.value || null })}
            />
          </label>
          {/* The run is part of what you are looking at -- the price chart overlays its
              causal trace -- so this is where you set or clear one without going back to the
              Navigator. */}
          <label className="advanced-only">
            <span className="eyebrow">Run</span>
            <input
              className="field mono"
              value={linked.runId ?? ''}
              placeholder="run id"
              spellCheck={false}
              onChange={(event) => setLinked({ runId: event.target.value.trim() || null })}
            />
          </label>
          <p className="context-note muted">
            {archive ? `Archive chart: ${archive.venue} · ${archive.market_type} · ${archive.frequency}. Strategy context remains ${linked.symbol ?? 'unselected'}.` : 'Stored daily bars. Select a pair and then its source / native interval when offered.'}
          </p>
          <div className="context-actions">
            {profile === 'crypto' ? <button className="btn" onClick={() => { openCryptoData(); setOpen(false) }}>Browse all crypto datasets</button> : null}
            <button
              className="btn ghost"
              onClick={() => setLinked({ start: null, end: null, runId: null })}
            >
              Clear window
            </button>
            <button className="btn primary" onClick={() => setOpen(false)}>
              Done
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

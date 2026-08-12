/**
 * One context control, replacing five.
 *
 * The old top bar carried DESK, LINK, SYM, ASOF and a six-field PRJ/VER/UNI/TF/SNAP/RUN
 * strip, each its own popover. That is a lot of chrome for state that is really one thing:
 * *what am I looking at*. It reads as one sentence here — symbol, window, project — and
 * opens a single editor.
 *
 * The A/B/C/D link groups are gone. They let panels follow different contexts inside one
 * desk, which only made sense when you could tile arbitrary panels; with one context per
 * screen the mechanism cost more comprehension than it bought.
 */

import { useEffect, useRef, useState } from 'react'

import { setLinked, useLinked } from '../context/linked'
import { shortId } from '../util/format'

export function ContextBar() {
  const linked = useLinked()
  const [open, setOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)

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

  const window_ = `${linked.start ?? 'start'} → ${linked.end ?? 'latest'}`

  return (
    <div className="context" ref={wrap}>
      <button
        className="context-chip"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        title="What every screen is currently showing"
      >
        <span className="context-symbol mono">{linked.symbol ?? 'no symbol'}</span>
        <span className="context-sep">·</span>
        <span className="context-window">{window_}</span>
        {linked.projectId ? (
          <>
            <span className="context-sep">·</span>
            <span className="context-project">{shortId(linked.projectId)}</span>
          </>
        ) : null}
        {linked.runId ? (
          <>
            <span className="context-sep">·</span>
            <span className="context-run mono">{shortId(linked.runId)}</span>
          </>
        ) : null}
      </button>

      {open ? (
        <div className="context-pop" role="dialog" aria-label="Working context">
          <label>
            <span className="eyebrow">Symbol</span>
            <input
              className="field mono"
              value={linked.symbol ?? ''}
              spellCheck={false}
              placeholder="SPY"
              onChange={(event) =>
                setLinked({ symbol: event.target.value.toUpperCase() || null })
              }
            />
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
            <span className="eyebrow">Project</span>
            <input
              className="field mono"
              value={linked.projectId ?? ''}
              placeholder="project id"
              onChange={(event) => setLinked({ projectId: event.target.value || null })}
            />
          </label>
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
              causal trace -- and the chip already shows it, so this is where you set or
              clear one without going back to the Library. */}
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
            Timeframe is daily. Everything above is shared by every screen.
          </p>
          <div className="context-actions">
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

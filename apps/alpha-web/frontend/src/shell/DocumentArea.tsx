// The MDI document area (spec 2026-09-01 §4.2 item 5; artboard 1-Terminal): a document header
// bar (its context line and the minimise · maximise · close glyphs), the active document's
// panes — main panes as tabs, side panes as a narrower tabbed column — and the bottom document
// tabs. Only the active document mounts, so nothing polls behind a hidden tab. ArrowLeft/Right on
// a document tab moves and activates; Delete closes. Maximise hides the docks; minimise is
// disabled because a document lives in its tab, never on a desktop.

import { useEffect, useState, type FunctionComponent } from 'react'

import type { PanelHandleProps } from '../context/panelHandle'
import { documentOf, panesByArea, type DocumentPane } from './documents'
import { Icon } from './icons'
import type { MdiState } from './mdiModel'
import { windowOf } from './mdiModel'
import { PanelHost } from './PanelHost'

/** A request from the shell to bring one named pane to the front. */
export interface PaneFocus {
  pane: string
  /** Bumped on every request so asking twice for the same pane still focuses it. */
  seq: number
}

function PaneColumn({
  area,
  panes,
  focus,
  contextKey,
}: {
  area: 'main' | 'side'
  panes: DocumentPane[]
  focus: PaneFocus | null
  contextKey: string
}) {
  const [active, setActive] = useState(0)
  useEffect(() => {
    if (!focus) return
    const index = panes.findIndex((item) => item.name === focus.pane)
    if (index >= 0) setActive(index)
  }, [focus, panes])
  const pane = panes[Math.min(active, panes.length - 1)]
  return (
    <section className={`area area--${area}`} aria-label={pane.title}>
      {panes.length > 1 ? (
        <nav className="area-tabs" role="tablist" aria-label={`${area} panes`}>
          {panes.map((item, index) => (
            <button
              key={item.name}
              type="button"
              role="tab"
              aria-selected={index === active}
              className={`area-tab${index === active ? ' active' : ''}`}
              onClick={() => setActive(index)}
            >
              {item.title}
            </button>
          ))}
        </nav>
      ) : null}
      <div className="area-body">
        <PanelHost
          key={`${pane.name}:${contextKey}`}
          name={pane.name}
          component={pane.component as FunctionComponent<PanelHandleProps>}
          params={pane.params}
        />
      </div>
    </section>
  )
}

export function DocumentArea({
  mdi,
  focus,
  contextKey,
  header,
  maximised,
  onActivate,
  onClose,
  onToggleMaximise,
}: {
  mdi: MdiState
  focus: PaneFocus | null
  contextKey: string
  /** The header line for the active document (the chart's context, else its title). */
  header: string
  maximised: boolean
  onActivate: (key: string) => void
  onClose: (key: string) => void
  onToggleMaximise: () => void
}) {
  const active = mdi.documents.find((item) => item.key === mdi.active) ?? null
  const definition = active ? documentOf(windowOf(active.key)) : null
  const areas = definition ? panesByArea(definition) : null

  const onTabKey = (index: number) => (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'Delete') {
      event.preventDefault()
      onClose(mdi.documents[index].key)
      return
    }
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    event.preventDefault()
    const next = mdi.documents[(index + step + mdi.documents.length) % mdi.documents.length]
    onActivate(next.key)
    const tabs = event.currentTarget.parentElement?.parentElement
    window.setTimeout(() => {
      tabs?.querySelector<HTMLButtonElement>(`[data-key="${CSS.escape(next.key)}"]`)?.focus()
    }, 0)
  }

  return (
    <div className="mdi">
      {active ? (
        <div className="doc-head">
          <span className="doc-head-title" title={header}>
            {header}
          </span>
          <span className="spacer" />
          <button
            type="button"
            className="dock-glyph"
            disabled
            aria-label={`Minimise ${active.title}`}
            title="A document lives in its tab below; there is no desktop to minimise to"
          >
            <Icon name="minimise" size={12} />
          </button>
          <button
            type="button"
            className="dock-glyph"
            aria-label={maximised ? `Restore ${active.title}` : `Maximise ${active.title}`}
            aria-pressed={maximised}
            title={maximised ? 'Restore the docks' : 'Maximise — hide the docks'}
            onClick={onToggleMaximise}
          >
            <Icon name={maximised ? 'restore' : 'maximise'} size={12} />
          </button>
          <button
            type="button"
            className="dock-glyph"
            aria-label={`Close ${active.title}`}
            title={`Close ${active.title}`}
            onClick={() => onClose(active.key)}
          >
            <Icon name="close" size={12} />
          </button>
        </div>
      ) : null}
      <div className={`mdi-body${areas && areas.side.length ? ' mdi-body--split' : ''}`}>
        {active && areas ? (
          <>
            <PaneColumn
              key={`${active.key}:main`}
              area="main"
              panes={areas.main}
              focus={focus}
              contextKey={contextKey}
            />
            {areas.side.length ? (
              <PaneColumn
                key={`${active.key}:side`}
                area="side"
                panes={areas.side}
                focus={focus}
                contextKey={contextKey}
              />
            ) : null}
          </>
        ) : (
          <div className="mdi-empty">
            <p className="muted">No document open. Use the View menu or the Navigator.</p>
          </div>
        )}
      </div>
      <nav className="mdi-tabs" aria-label="Open documents">
        <div role="tablist" aria-label="Documents">
          {mdi.documents.map((item, index) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              data-key={item.key}
              aria-selected={item.key === mdi.active}
              className={`mdi-tab${item.key === mdi.active ? ' active' : ''}`}
              title="Delete closes this document"
              onClick={() => onActivate(item.key)}
              onKeyDown={onTabKey(index)}
            >
              {item.title}
            </button>
          ))}
        </div>
      </nav>
    </div>
  )
}

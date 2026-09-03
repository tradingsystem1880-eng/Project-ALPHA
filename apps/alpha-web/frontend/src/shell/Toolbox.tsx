// Toolbox dock (spec 2026-09-01 §4.2 item 6): Jobs · Trades · Backtests · Data pulls · Log as one
// tabbed strip under the documents. Only the active tab mounts. Jobs is the dense job table with
// the real failure text; Trades the paper sessions; Backtests the run comparison; Data pulls the
// provider readiness that every pull depends on; Log the activity feed.

import { useEffect, useState, type FunctionComponent } from 'react'

import type { PanelHandleProps } from '../context/panelHandle'
import { ActivityFeed } from '../panels/ActivityFeed'
import { CompareRuns } from '../panels/CompareRuns'
import { JobMonitor } from '../panels/JobMonitor'
import { PaperMonitor } from '../panels/PaperMonitor'
import { ProviderSystem } from '../panels/ProviderSystem'
import { dockOf } from './documents'
import { PanelHost } from './PanelHost'

const TABS = dockOf('Toolbox').tabs

const PANELS: Record<string, { name: string; component: FunctionComponent<PanelHandleProps> }> = {
  Jobs: { name: 'JobMonitor', component: JobMonitor },
  Trades: { name: 'PaperMonitor', component: PaperMonitor },
  Backtests: { name: 'CompareRuns', component: CompareRuns },
  'Data pulls': { name: 'ProviderSystem', component: ProviderSystem },
  Log: { name: 'ActivityFeed', component: ActivityFeed },
}

const OPEN_KEY = 'alpha.shell.toolbox'

/** Open by default on a tall window; a 720px-high terminal keeps the documents room. */
function initialOpen(): boolean {
  const stored = localStorage.getItem(OPEN_KEY)
  if (stored === 'open') return true
  if (stored === 'closed') return false
  return window.innerHeight >= 800
}

export function Toolbox() {
  const [tab, setTab] = useState<string>(TABS[0])
  const [open, setOpen] = useState(initialOpen)
  useEffect(() => {
    localStorage.setItem(OPEN_KEY, open ? 'open' : 'closed')
  }, [open])
  const panel = PANELS[tab]
  if (!panel) throw new Error(`toolbox tab ${tab} has no panel`)
  return (
    <section className={`toolbox${open ? ' toolbox--open' : ''}`} aria-label="Toolbox">
      <div className="area-tabs toolbox-strip">
      <nav className="toolbox-tabs" role="tablist" aria-label="Toolbox tabs">
        {TABS.map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={tab === item}
            className={`area-tab${tab === item ? ' active' : ''}`}
            onClick={() => {
              setTab(item)
              setOpen(true)
            }}
          >
            {item}
          </button>
        ))}
      </nav>
      <span className="spacer" />
      <button
        type="button"
        className="area-tab toolbox-toggle"
        aria-expanded={open}
        aria-label={open ? 'Collapse the Toolbox' : 'Expand the Toolbox'}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? '▾' : '▴'}
      </button>
      </div>
      {open ? (
        <div className="area-body">
          <PanelHost key={panel.name} name={panel.name} component={panel.component} />
        </div>
      ) : null}
    </section>
  )
}

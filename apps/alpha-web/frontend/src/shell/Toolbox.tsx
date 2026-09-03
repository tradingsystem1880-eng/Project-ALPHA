// Toolbox dock (spec 2026-09-01 §4.2 item 6; artboard 1-Terminal): Jobs N · Trades · Backtests ·
// Data pulls · Log · Alerts as one tab strip under the documents, tabs at the bottom. Only the
// active tab mounts. Jobs is the dense job table with the real failure text; Trades the paper
// sessions; Backtests the run comparison; Data pulls the provider readiness that every pull
// depends on; Log the activity feed. Alerts is disabled: there is no alert engine to relay.

import type { FunctionComponent } from 'react'
import { useState } from 'react'

import type { PanelHandleProps } from '../context/panelHandle'
import { ActivityFeed } from '../panels/ActivityFeed'
import { CompareRuns } from '../panels/CompareRuns'
import { JobMonitor } from '../panels/JobMonitor'
import { PaperMonitor } from '../panels/PaperMonitor'
import { ProviderSystem } from '../panels/ProviderSystem'
import { useActivityField } from '../state/activity'
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

const DISABLED: Readonly<Record<string, string>> = {
  Alerts: 'No alert engine exists to relay; nothing here would be real',
}

export function Toolbox({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [tab, setTab] = useState<string>(TABS[0])
  const runningJobs = useActivityField('runningJobs')
  const panel = PANELS[tab]
  if (!panel) throw new Error(`toolbox tab ${tab} has no panel`)
  return (
    <section className={`toolbox${open ? ' toolbox--open' : ''}`} aria-label="Toolbox">
      {open ? (
        <div className="area-body">
          <PanelHost key={panel.name} name={panel.name} component={panel.component} />
        </div>
      ) : null}
      <div className="rd-tabs dock-tabs toolbox-strip">
        <nav className="toolbox-tabs" role="tablist" aria-label="Toolbox tabs">
          {TABS.map((item) => (
            <button
              key={item}
              type="button"
              role="tab"
              aria-selected={tab === item}
              className={`rd-tab${tab === item ? ' active' : ''}`}
              disabled={item in DISABLED}
              title={DISABLED[item]}
              onClick={() => {
                setTab(item)
                onOpenChange(true)
              }}
            >
              {item}
              {item === 'Jobs' && runningJobs > 0 ? <span className="tab-count">{runningJobs}</span> : null}
            </button>
          ))}
        </nav>
        <span className="spacer" />
        <button
          type="button"
          className="rd-tab toolbox-toggle"
          aria-expanded={open}
          aria-label={open ? 'Collapse the Toolbox' : 'Expand the Toolbox'}
          onClick={() => onOpenChange(!open)}
        >
          {open ? '▾' : '▴'}
        </button>
      </div>
    </section>
  )
}

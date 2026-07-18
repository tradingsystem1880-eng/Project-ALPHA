// The curated first-run desk: a real multi-pane terminal instead of one lonely panel.
// Built imperatively with addPanel + position (never hand-serialized layout JSON — that format
// is dockview-internal and fragile across versions).

import type { DockviewApi } from 'dockview-react'

export const LAYOUT_KEY = 'alpha.layout.v2' // bumped from alpha.layout: panel set changed

export function buildDeskLayout(api: DockviewApi): void {
  // center column: run browser over the activity tape
  const runs = api.addPanel({ id: 'RunBrowser-0', component: 'RunBrowser', title: 'Runs' })
  api.addPanel({
    id: 'ActivityFeed-0',
    component: 'ActivityFeed',
    title: 'Activity',
    position: { referencePanel: runs.id, direction: 'below' },
  })
  // right column: the lab (launch things)
  api.addPanel({
    id: 'StrategyLab-lab',
    component: 'StrategyLab',
    title: 'Strategy Lab',
    position: { referencePanel: runs.id, direction: 'right' },
  })
  // bottom strip: jobs
  api.addPanel({
    id: 'JobMonitor-0',
    component: 'JobMonitor',
    title: 'Jobs',
    position: { direction: 'below' },
  })
  runs.api.setActive()
}

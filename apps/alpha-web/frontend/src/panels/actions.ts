// Shared panel actions (kept out of registry.tsx to avoid a registry ↔ panel import cycle).

import type { DockviewApi } from 'dockview-react'

import { shortId } from '../util/format'

// Open (or focus, if already open) the Run Detail panel for a run id.
export function openRunDetail(containerApi: DockviewApi, runId: string): void {
  const id = `run-detail-${runId}`
  const existing = containerApi.getPanel(id)
  if (existing) {
    existing.api.setActive()
    return
  }
  containerApi.addPanel({ id, component: 'RunDetail', title: shortId(runId), params: { runId } })
}

export interface LabPrefill {
  command: string
  args: string
}

// Open the Strategy Lab, optionally prefilled with a suggested command (from the explanation
// engine's next-step actions). The lab reads `params.prefill` on mount / param change.
export function openStrategyLab(containerApi: DockviewApi, prefill?: LabPrefill): void {
  const existing = containerApi.panels.find((p) => p.id.startsWith('StrategyLab-'))
  if (existing) {
    existing.api.setActive()
    if (prefill) existing.api.updateParameters({ prefill })
    return
  }
  containerApi.addPanel({
    id: `StrategyLab-lab`,
    component: 'StrategyLab',
    title: 'Strategy Lab',
    params: prefill ? { prefill } : {},
  })
}

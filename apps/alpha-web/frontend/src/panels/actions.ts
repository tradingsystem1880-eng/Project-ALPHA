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

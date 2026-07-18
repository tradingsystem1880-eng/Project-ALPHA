// Shared panel actions (kept out of registry.tsx to avoid a registry ↔ panel import cycle).

import type { DockviewApi } from 'dockview-react'

import { shortId } from '../util/format'

// Open (or focus, if already open) the Run Detail panel for a run id. The URL hash mirrors the
// opened run (`#run=<id>`) so the address bar is always a shareable deep link; the shell parses
// it at boot and on hashchange.
export function openRunDetail(containerApi: DockviewApi, runId: string): void {
  window.location.hash = `run=${runId}`
  const id = `run-detail-${runId}`
  const existing = containerApi.getPanel(id)
  if (existing) {
    existing.api.setActive()
    return
  }
  containerApi.addPanel({ id, component: 'RunDetail', title: shortId(runId), params: { runId } })
}

/** The run id in the current URL hash (`#run=<16 hex>`), if any. */
export function runIdFromHash(): string | null {
  const match = /#run=([0-9a-f]{16})\b/.exec(window.location.hash)
  return match ? match[1] : null
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

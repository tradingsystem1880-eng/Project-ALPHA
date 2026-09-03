// R6h (spec §15, ADR-0026): the one banner every gated strategy surface renders while the
// linked project's research gate is open. It relays the pure-model reason verbatim and links
// straight to the research case holding the gate; it never derives gate state itself.

import { requestResearchCase } from '../context/researchCase'
import type { StrategyGateLock } from '../panels/researchGateModel'

export function ResearchGateLockNotice({
  lock,
  projectId,
  projectName,
}: {
  lock: StrategyGateLock
  projectId: string
  projectName?: string | null
}) {
  return (
    <div className="workbench-notice research-gate-lock" role="status">
      <strong>RESEARCH GATE OPEN</strong>
      <span>{lock.reason}</span>
      <span className="muted">The case's next owner step is one Touch ID away in its cockpit.</span>
      <button className="btn primary" onClick={() => requestResearchCase(projectId)}>
        Open research case{projectName ? ` · ${projectName}` : ''}
      </button>
    </div>
  )
}

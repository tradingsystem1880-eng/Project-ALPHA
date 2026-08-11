// R6h (spec §15): resolve the linked project's research-gate lock for panels that are not
// project-scoped themselves (Strategy Lab, Pipeline). The lock derives ONLY from the
// projection's recorded `research_gate_state`; with no linked project there is no gate, and a
// failed projection read never locks — the CLI/store remain the enforcing authority, the SPA
// gate exists to surface the reason before a server rejection would.

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import { useLinked } from '../context/linked'
import { strategyGateLock, type StrategyGateLock } from './researchGateModel'

export interface LinkedProjectGate {
  lock: StrategyGateLock | null
  projectId: string | null
  projectName: string | null
}

const UNGATED: LinkedProjectGate = { lock: null, projectId: null, projectName: null }

export function useLinkedProjectGate(): LinkedProjectGate {
  const linked = useLinked()
  const [gate, setGate] = useState<LinkedProjectGate>(UNGATED)

  useEffect(() => {
    const projectId = linked.projectId
    if (!projectId) {
      setGate(UNGATED)
      return
    }
    let live = true
    api
      .project(projectId)
      .then((detail) => {
        if (!live) return
        setGate({
          lock: strategyGateLock(detail.research_gate_state),
          projectId,
          projectName: detail.name,
        })
      })
      .catch(() => {
        if (live) setGate({ lock: null, projectId, projectName: null })
      })
    return () => {
      live = false
    }
  }, [linked.projectId])

  return gate
}

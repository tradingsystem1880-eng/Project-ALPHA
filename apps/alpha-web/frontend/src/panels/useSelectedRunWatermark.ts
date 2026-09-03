// The research-gate watermark of the run the shell has selected, relayed from its projection.
// Shared by the topbar status chip and the Governance dialog so both read the same string.

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import { useLinked } from '../context/linked'
import { researchGateWatermark } from './researchGateModel'

export function useSelectedRunWatermark(): string | null {
  const linked = useLinked()
  const [watermark, setWatermark] = useState<string | null>(null)
  useEffect(() => {
    const runId = linked.runId
    if (!runId) {
      setWatermark(null)
      return
    }
    let live = true
    api
      .run(runId)
      .then((detail) => live && setWatermark(researchGateWatermark(detail)))
      .catch(() => live && setWatermark(null))
    return () => {
      live = false
    }
  }, [linked.runId])
  return watermark
}

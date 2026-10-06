import { useEffect, useRef, useState } from 'react'
import type { ScientificRow } from './bokehCartesian'
export function ScientificCartesianCanvas({ rows, title, xLabel, yLabel, bars }: { rows: ScientificRow[]; title: string; xLabel: string; yLabel: string; bars: boolean }) {
  const host = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let live = true, destroy: (() => void) | undefined
    setError(null)
    import('./bokehCartesian').then(async ({ mountCartesian }) => {
      if (!live) return
      const dispose = await mountCartesian(host.current!, rows, xLabel, yLabel, bars)
      if (!live) dispose(); else destroy = dispose
    }).catch(reason => { if (live) setError(String(reason)) })
    return () => { live = false; destroy?.() }
  }, [rows, xLabel, yLabel, bars])
  return <>{error ? <p role="alert">{title} unavailable: {error}</p> : null}<div ref={host} className="scientific-cartesian-host" role="group" aria-label={`Interactive Bokeh ${title}; ${xLabel} versus ${yLabel}. Recorded values table below.`}/></>
}

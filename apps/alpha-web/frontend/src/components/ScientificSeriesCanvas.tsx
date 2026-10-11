import { useEffect, useRef, useState } from 'react'
import type { ChartControls } from '../context/chartControls'
import type { ChartLinkRegistry } from '../shell/chartLinkRegistry'
import { useSettings } from '../state/settings'
import type { ScientificPoint } from './scientificPlotModel'
import type { mountBokehPlot } from './bokehPlot'
import { ScientificRangeControls } from './ScientificRangeControls'
export function ScientificSeriesCanvas({ points, unit, panelId, registry, area = false, controls, reset = 0 }: { points: readonly ScientificPoint[]; unit: string; panelId: string; registry?: ChartLinkRegistry; area?: boolean; controls?: ChartControls; reset?: number }) {
  const host = useRef<HTMLDivElement>(null), readout = useRef<HTMLSpanElement>(null), cursorData = useRef<HTMLSpanElement>(null)
  const cursorExpanded = useRef(false)
  const cursorText = useRef('Cursor —')
  const updateCursorData = () => { if (cursorData.current) cursorData.current.textContent = cursorText.current }
  const controller = useRef<Awaited<ReturnType<typeof mountBokehPlot>> | null>(null)
  const latest = useRef({ points, controls, reset }); latest.current = { points, controls, reset }
  const { chartStyle } = useSettings()
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const node = host.current!
    let live = true
    setError(null); setReady(false)
    import('./bokehPlot').then(async ({ mountBokehPlot }) => {
      if (!live) return
      const plot = await mountBokehPlot(node, unit, panelId, registry, text => { if (cursorText.current === text) return; cursorText.current = text; if (readout.current?.firstChild) readout.current.firstChild.nodeValue = text; if (cursorExpanded.current) updateCursorData() }, area, chartStyle)
      if (!live) { plot.destroy(); return }
      plot.activate(); controller.current = plot; plot.data(latest.current.points); if (latest.current.controls) plot.controls(latest.current.controls); setReady(true)
    }).catch(reason => { if (live) setError(String(reason)) })
    return () => { live = false; controller.current?.destroy(); controller.current = null }
  }, [unit, panelId, registry, area, chartStyle])
  useEffect(() => { controller.current?.data(points) }, [points])
  useEffect(() => { if (controls) controller.current?.controls(controls) }, [controls])
  useEffect(() => { if (reset) controller.current?.fit() }, [reset])
  return <div className="scientific-series"><ScientificRangeControls key={points[0]?.time} points={points} unit={unit} ready={ready} onFit={() => controller.current?.fitLinked()} onRange={(from, to) => controller.current?.range(from, to)}/><div className="plot-readout mono"><span>UTC</span><span ref={readout}>Cursor —</span></div>{error ? <p role="alert">Scientific plot unavailable: {error}</p> : null}<details className="scientific-cursor-data" onToggle={e => { cursorExpanded.current = e.currentTarget.open; if (cursorExpanded.current) updateCursorData() }}><summary>Cursor data</summary><span className="cursor-values" ref={cursorData}>Move the cursor over a plotted observation.</span><p>{unit} · Missing observations remain unavailable.</p></details><div className="scientific-series-host" ref={host} role="group" aria-label={`Interactive scientific time series; ${unit}; time in UTC. Recorded values table available below.`}/></div>
}

// Minimal React wrapper around uPlot (tiny, canvas, no build magic). The caller passes fully-formed,
// memoized uPlot options + aligned data; the wrapper owns lifecycle + resize.

import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

interface Props {
  data: uPlot.AlignedData
  options: Omit<uPlot.Options, 'width' | 'height'>
  height?: number
}

export function UplotChart({ data, options, height = 220 }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const width = host.clientWidth || 640
    const chart = new uPlot({ ...options, width, height } as uPlot.Options, data, host)
    const ro = new ResizeObserver(() => chart.setSize({ width: host.clientWidth || width, height }))
    ro.observe(host)
    return () => {
      ro.disconnect()
      chart.destroy()
    }
  }, [data, options, height])

  return <div ref={hostRef} className="uplot-host" />
}

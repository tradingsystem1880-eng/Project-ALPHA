// TradingView Lightweight Charts candlestick + volume canvas, themed to the workstation palette.

import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  createChart,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useEffect, useRef } from 'react'

import type { Candle } from '../api/types'
import { CHART } from '../util/chartTheme'

export function PriceChartCanvas({ bars }: { bars: Candle[] }) {
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const chart = createChart(host, {
      width: host.clientWidth,
      height: host.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: CHART.muted,
        fontFamily: 'JetBrains Mono Variable, JetBrains Mono, ui-monospace, monospace',
        fontSize: 11,
      },
      grid: { vertLines: { color: CHART.grid }, horzLines: { color: CHART.grid } },
      rightPriceScale: { borderColor: CHART.line },
      timeScale: { borderColor: CHART.line },
      crosshair: { mode: CrosshairMode.Normal },
    })
    const series = chart.addSeries(CandlestickSeries, {
      upColor: CHART.up,
      downColor: CHART.down,
      borderVisible: false,
      wickUpColor: CHART.up,
      wickDownColor: CHART.down,
    })
    series.setData(
      bars.map((b) => ({ time: b.t as UTCTimestamp, open: b.o, high: b.h, low: b.l, close: b.c })),
    )
    // volume underlay on its own scale, bottom 18% of the pane
    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
      lastValueVisible: false,
      priceLineVisible: false,
    })
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    volume.setData(
      bars.map((b) => ({
        time: b.t as UTCTimestamp,
        value: b.v,
        color: b.c >= b.o ? 'rgba(46, 160, 74, 0.35)' : 'rgba(239, 83, 80, 0.35)',
      })),
    )
    chart.timeScale().fitContent()
    const ro = new ResizeObserver(() =>
      chart.applyOptions({ width: host.clientWidth, height: host.clientHeight }),
    )
    ro.observe(host)
    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [bars])

  return <div ref={hostRef} className="price-host" />
}

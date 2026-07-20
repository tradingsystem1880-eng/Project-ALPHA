import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  createChart,
  type MouseEventParams,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useEffect, useRef } from 'react'

import type { Candle, ForecastPath } from '../api/types'
import { CHART } from '../util/chartTheme'

interface Props {
  history: Candle[]
  sample: ForecastPath
  forecastTs: number[]
  originTs: number
}

export function KronosKlineCanvas({ history, sample, forecastTs, originTs }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const boundaryRef = useRef<HTMLDivElement>(null)
  const crosshairRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const host = hostRef.current
    const boundary = boundaryRef.current
    const crosshair = crosshairRef.current
    if (!host || !boundary || !crosshair) return
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
      timeScale: { borderColor: CHART.line, timeVisible: true },
      crosshair: { mode: CrosshairMode.Normal },
    })
    const actual = chart.addSeries(CandlestickSeries, {
      upColor: CHART.up,
      downColor: CHART.down,
      borderVisible: false,
      wickUpColor: CHART.up,
      wickDownColor: CHART.down,
      priceLineVisible: false,
    })
    actual.setData(
      history.map((bar) => ({
        time: bar.t as UTCTimestamp,
        open: bar.o,
        high: bar.h,
        low: bar.l,
        close: bar.c,
      })),
    )
    const projected = chart.addSeries(CandlestickSeries, {
      upColor: 'rgba(79, 141, 255, 0.72)',
      downColor: 'rgba(215, 166, 59, 0.72)',
      borderUpColor: CHART.accent,
      borderDownColor: CHART.gold,
      wickUpColor: CHART.accent,
      wickDownColor: CHART.gold,
      priceLineVisible: false,
    })
    projected.setData(
      forecastTs.map((time, index) => ({
        time: time as UTCTimestamp,
        open: sample.opens[index],
        high: sample.highs[index],
        low: sample.lows[index],
        close: sample.closes[index],
      })),
    )
    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
      lastValueVisible: false,
      priceLineVisible: false,
    })
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.84, bottom: 0 } })
    volume.setData([
      ...history.map((bar) => ({
        time: bar.t as UTCTimestamp,
        value: bar.v,
        color: bar.c >= bar.o ? 'rgba(46, 160, 74, 0.25)' : 'rgba(239, 83, 80, 0.25)',
      })),
      ...forecastTs.map((time, index) => ({
        time: time as UTCTimestamp,
        value: sample.volumes[index],
        color: 'rgba(79, 141, 255, 0.26)',
      })),
    ])

    const positionBoundary = () => {
      const x = chart.timeScale().timeToCoordinate(originTs as UTCTimestamp)
      if (x === null) {
        boundary.hidden = true
        return
      }
      boundary.hidden = false
      boundary.style.left = `${Math.round(x)}px`
    }
    chart.timeScale().fitContent()
    positionBoundary()
    chart.timeScale().subscribeVisibleTimeRangeChange(positionBoundary)
    const handleCrosshair = (param: MouseEventParams) => {
      const actualPoint = param.seriesData.get(actual)
      const projectedPoint = param.seriesData.get(projected)
      const candle =
        actualPoint && 'open' in actualPoint
          ? actualPoint
          : projectedPoint && 'open' in projectedPoint
            ? projectedPoint
            : null
      const volumePoint = param.seriesData.get(volume)
      if (!candle || typeof param.time !== 'number') {
        crosshair.textContent = 'CROSSHAIR —'
        return
      }
      const volumeValue = volumePoint && 'value' in volumePoint ? volumePoint.value : null
      crosshair.textContent =
        `${new Date(param.time * 1_000).toISOString()}  ` +
        `O ${Number(candle.open).toFixed(4)}  H ${Number(candle.high).toFixed(4)}  ` +
        `L ${Number(candle.low).toFixed(4)}  C ${Number(candle.close).toFixed(4)}  ` +
        `V ${volumeValue === null ? '—' : Number(volumeValue).toFixed(0)}`
    }
    chart.subscribeCrosshairMove(handleCrosshair)
    const ro = new ResizeObserver(() => {
      chart.applyOptions({ width: host.clientWidth, height: host.clientHeight })
      positionBoundary()
    })
    ro.observe(host)
    return () => {
      ro.disconnect()
      chart.timeScale().unsubscribeVisibleTimeRangeChange(positionBoundary)
      chart.unsubscribeCrosshairMove(handleCrosshair)
      chart.remove()
    }
  }, [forecastTs, history, originTs, sample])

  return (
    <div className="kronos-kline-wrap">
      <div ref={hostRef} className="kronos-kline-host" />
      <div ref={boundaryRef} className="forecast-origin-boundary" aria-hidden="true">
        <span>FORECAST ORIGIN</span>
      </div>
      <div ref={crosshairRef} className="chart-crosshair-readout mono" aria-live="polite">
        CROSSHAIR —
      </div>
    </div>
  )
}

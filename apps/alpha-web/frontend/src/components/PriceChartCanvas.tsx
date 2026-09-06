// TradingView Lightweight Charts candlestick + volume canvas, themed to the workstation palette.

import {
  BarSeries,
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type MouseEventParams,
  type SeriesMarker,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useEffect, useRef } from 'react'

import { barSpacingFor, useChartControls } from '../context/chartControls'
import { setChartHover } from '../context/chartHover'
import type { Candle, ChartAnnotation, ChartOverlays, ChartTraceEvent } from '../api/types'
import { drawableAnnotations, lineData, splitPanes, swingMarkers } from '../panels/chartOverlaysModel'
import type { EvidenceMarker } from '../panels/v3Models'
import { CHART } from '../util/chartTheme'
import { createChartAnnotationPrimitive } from './ChartAnnotationPrimitive'

interface Props {
  bars: Candle[]
  evidence?: EvidenceMarker[]
  annotations?: ChartAnnotation[]
  selectedSequenceId?: number | null
  selectedTrade?: ChartTraceEvent | null
  onSelectEvidence?: (sequenceId: number) => void
  /** `alpha chart overlays` for the same window: drawn as-is, never recomputed here. */
  overlays?: ChartOverlays | null
}

const OVERLAY_COLORS = [CHART.accent, CHART.gold, CHART.up, CHART.down, CHART.muted]
const SUB_PANE_HEIGHT = 90

function markerColor(marker: EvidenceMarker): string {
  if (marker.tone === 'selection') return CHART.accent
  if (marker.tone === 'positive') return CHART.up
  if (marker.tone === 'negative') return CHART.down
  return CHART.muted
}

function seriesMarker(marker: EvidenceMarker, selected: boolean): SeriesMarker<UTCTimestamp> {
  const isBelow = marker.kind === 'fill' || marker.kind === 'entry'
  return {
    id: marker.id,
    time: marker.barTs as UTCTimestamp,
    position: isBelow ? 'belowBar' : 'aboveBar',
    shape:
      marker.kind === 'decision'
        ? 'circle'
        : marker.kind === 'fill'
          ? marker.tone === 'negative'
            ? 'arrowDown'
            : 'arrowUp'
          : 'square',
    color: markerColor(marker),
    size: selected ? 1.8 : 1.1,
    ...(selected || marker.id.startsWith('paper:') ? { text: marker.label } : {}),
  }
}

export function PriceChartCanvas({
  bars,
  evidence = [],
  annotations = [],
  selectedSequenceId = null,
  selectedTrade = null,
  onSelectEvidence,
  overlays = null,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const crosshairRef = useRef<HTMLDivElement>(null)
  const controls = useChartControls()

  useEffect(() => {
    const host = hostRef.current
    const crosshair = crosshairRef.current
    if (!host || !crosshair) return
    const chart = createChart(host, {
      width: host.clientWidth,
      height: host.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: CHART.muted,
        fontFamily: 'JetBrains Mono Variable, JetBrains Mono, ui-monospace, monospace',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: CHART.grid, visible: controls.grid },
        horzLines: { color: CHART.grid, visible: controls.grid },
      },
      rightPriceScale: { borderColor: CHART.line },
      timeScale: { borderColor: CHART.line },
      crosshair: { mode: controls.crosshair ? CrosshairMode.Normal : CrosshairMode.Hidden },
    })
    const ohlc = bars.map((b) => ({ time: b.t as UTCTimestamp, open: b.o, high: b.h, low: b.l, close: b.c }))
    const series =
      controls.type === 'line'
        ? chart.addSeries(LineSeries, { color: CHART.accent, lineWidth: 2, priceLineVisible: false })
        : controls.type === 'bars'
          ? chart.addSeries(BarSeries, { upColor: CHART.up, downColor: CHART.down, thinBars: false })
          : chart.addSeries(CandlestickSeries, {
              upColor: CHART.up,
              downColor: CHART.down,
              borderVisible: false,
              wickUpColor: CHART.up,
              wickDownColor: CHART.down,
            })
    if (controls.type === 'line') series.setData(ohlc.map((b) => ({ time: b.time, value: b.close })))
    else series.setData(ohlc)
    const byTime = new Map(bars.map((b) => [b.t, b]))
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
    // Overlays: price-pane lines share the candle scale; each oscillator gets its own pane below.
    // Points before the first candle (the CLI serves the whole as-of window, the chart may start
    // later) are dropped so the time scale does not stretch left of the visible history.
    const firstBar = bars[0]?.t ?? Number.NEGATIVE_INFINITY
    const overlayPoints = (values: readonly (number | null)[]) =>
      lineData(overlays?.t ?? [], values)
        .filter((point) => point.time >= firstBar)
        .map((point) => ({ ...point, time: point.time as UTCTimestamp }))
    if (overlays) {
      const { price, panes } = splitPanes(overlays.indicators)
      price.forEach((row, index) => {
        const line = chart.addSeries(LineSeries, {
          color: OVERLAY_COLORS[index % OVERLAY_COLORS.length],
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          title: row.name,
        })
        line.setData(overlayPoints(row.values))
      })
      panes.forEach((group, paneOffset) => {
        const paneIndex = paneOffset + 1
        group.series.forEach((row, index) => {
          const color = OVERLAY_COLORS[index % OVERLAY_COLORS.length]
          const sub =
            row.style === 'histogram'
              ? chart.addSeries(HistogramSeries, { color, priceLineVisible: false, lastValueVisible: false, title: row.name }, paneIndex)
              : chart.addSeries(LineSeries, { color, lineWidth: 1, priceLineVisible: false, lastValueVisible: true, title: row.name }, paneIndex)
          sub.setData(overlayPoints(row.values))
        })
        chart.panes()[paneIndex]?.setHeight(SUB_PANE_HEIGHT)
      })
    }
    const annotationPrimitive = createChartAnnotationPrimitive([
      ...annotations,
      ...drawableAnnotations(overlays?.annotations ?? []),
    ])
    series.attachPrimitive(annotationPrimitive)
    if (
      selectedTrade?.event_type === 'trade' &&
      selectedTrade.entry_ts !== null &&
      selectedTrade.exit_ts !== null &&
      selectedTrade.entry_price !== null &&
      selectedTrade.exit_price !== null
    ) {
      const holding = chart.addSeries(LineSeries, {
        color:
          selectedTrade.realized_return !== null && selectedTrade.realized_return < 0
            ? CHART.down
            : CHART.up,
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
        title:
          selectedTrade.realized_return === null
            ? 'HOLDING'
            : `HOLDING ${(selectedTrade.realized_return * 100).toFixed(2)}%`,
      })
      holding.setData([
        {
          time: selectedTrade.entry_ts as UTCTimestamp,
          value: selectedTrade.entry_price,
        },
        {
          time: selectedTrade.exit_ts as UTCTimestamp,
          value: selectedTrade.exit_price,
        },
      ])
    }
    const markerRows = evidence.map((marker) => ({ marker, id: marker.id }))
    const swings: SeriesMarker<UTCTimestamp>[] = swingMarkers(overlays?.annotations ?? [])
      .filter((marker) => marker.time >= firstBar)
      .map((marker) => ({
        id: marker.id,
        time: marker.time as UTCTimestamp,
        position: marker.position,
        shape: 'circle',
        color: CHART.gold,
        size: 0.6,
        text: marker.text,
      }))
    const markerPlugin = createSeriesMarkers(
      series,
      [...swings, ...evidence.map((marker) => seriesMarker(marker, marker.sequenceId === selectedSequenceId))],
      { zOrder: 'top' },
    )
    const handleClick = (param: MouseEventParams) => {
      const objectId = param.hoveredInfo?.objectId ?? param.hoveredObjectId
      if (typeof objectId !== 'string') return
      const row = markerRows.find((candidate) => candidate.id === objectId)
      if (row) onSelectEvidence?.(row.marker.sequenceId)
    }
    chart.subscribeClick(handleClick)
    const handleCrosshair = (param: MouseEventParams) => {
      const candle = typeof param.time === 'number' ? byTime.get(param.time) : undefined
      if (!candle) {
        crosshair.textContent = 'CROSSHAIR —'
        setChartHover({ bar: null })
        return
      }
      setChartHover({ bar: candle })
      crosshair.textContent =
        `${new Date(candle.t * 1_000).toISOString()}  ` +
        `O ${candle.o.toFixed(4)}  H ${candle.h.toFixed(4)}  ` +
        `L ${candle.l.toFixed(4)}  C ${candle.c.toFixed(4)}  ` +
        `V ${candle.v.toFixed(0)}`
    }
    chart.subscribeCrosshairMove(handleCrosshair)

    const selectedMarkers = evidence.filter(
      (marker) =>
        marker.sequenceId === selectedSequenceId ||
        (selectedTrade !== null && marker.sequenceId === selectedTrade.sequence_id),
    )
    const selectedIndexes = selectedMarkers
      .map((marker) => bars.findIndex((bar) => bar.t === marker.barTs))
      .filter((index) => index >= 0)
    if (selectedIndexes.length) {
      const firstIndex = Math.min(...selectedIndexes)
      const lastIndex = Math.max(...selectedIndexes)
      const from = bars[Math.max(0, firstIndex - 5)]?.t
      const to = bars[Math.min(bars.length - 1, lastIndex + 5)]?.t
      if (from !== undefined && to !== undefined) {
        chart.timeScale().setVisibleRange({ from: from as UTCTimestamp, to: to as UTCTimestamp })
      }
    } else {
      chart.timeScale().fitContent()
    }
    if (controls.zoom !== 0) {
      const base = chart.timeScale().options().barSpacing
      chart.timeScale().applyOptions({ barSpacing: barSpacingFor(base, controls.zoom) })
    }
    const ro = new ResizeObserver(() =>
      chart.applyOptions({ width: host.clientWidth, height: host.clientHeight }),
    )
    ro.observe(host)
    return () => {
      ro.disconnect()
      chart.unsubscribeClick(handleClick)
      chart.unsubscribeCrosshairMove(handleCrosshair)
      series.detachPrimitive(annotationPrimitive)
      markerPlugin.detach()
      chart.remove()
    }
  }, [annotations, bars, controls, evidence, onSelectEvidence, overlays, selectedSequenceId, selectedTrade])

  return (
    <>
      <div ref={hostRef} className="price-host" />
      <div ref={crosshairRef} className="chart-crosshair-readout mono" aria-live="polite">
        CROSSHAIR —
      </div>
    </>
  )
}

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
  type IChartApi, type LogicalRange,
  type ISeriesMarkersPluginApi, type Time,
  type ISeriesApi,
} from 'lightweight-charts'
import { useEffect, useMemo, useRef } from 'react'
import { scheduleChartResize, cancelChartResize } from './chartResize'

import { barSpacingFor, useChartControls, type ChartControls } from '../context/chartControls'
import { setChartHover } from '../context/chartHover'
import type { Candle, ChartAnnotation, ChartOverlays, ChartTraceEvent } from '../api/types'
import { drawableAnnotations, lineData, splitPanes, swingMarkers } from '../panels/chartOverlaysModel'
import type { EvidenceMarker } from '../panels/v3Models'
import { logicalRangeForUTC, type ChartLinkRegistry } from '../shell/chartLinkRegistry'
import { CHART } from '../util/chartTheme'
import { createChartAnnotationPrimitive } from './ChartAnnotationPrimitive'

interface Props {
  controls?: ChartControls
  reset?: number
  panelId?: string
  registry?: ChartLinkRegistry
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
const EMPTY: never[] = []

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
  controls: panelControls, reset = 0, panelId = "chart", registry,
  evidence = EMPTY,
  annotations = EMPTY,
  selectedSequenceId = null,
  selectedTrade = null,
  onSelectEvidence,
  overlays = null,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const crosshairRef = useRef<HTMLDivElement>(null)
  const sharedControls = useChartControls()
  const controls = panelControls ?? sharedControls
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line' | 'Bar' | 'Candlestick'> | null>(null)
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const byTime = useRef(new Map<number, Candle>())
  useEffect(() => { byTime.current = new Map(bars.map(b => [b.t, b])) }, [bars])
  const latest = useRef({ bars, evidence, onSelectEvidence })
  latest.current = { bars, evidence, onSelectEvidence }
  const savedRange = useRef<LogicalRange | null>(null)
  const remoteRange = useRef(true)
  const timestamps = useMemo(() => bars.map(b => b.t), [bars])
  const times = useRef(timestamps); times.current = timestamps
  const zoomRef = useRef(0)

  useEffect(() => {
    const host = hostRef.current
    const crosshair = crosshairRef.current
    if (!host || !crosshair) return
    let renderedWidth = host.clientWidth, renderedHeight = host.clientHeight
    const chart = createChart(host, {
      width: renderedWidth,
      height: renderedHeight,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: CHART.muted,
        fontFamily: 'JetBrains Mono Variable, JetBrains Mono, ui-monospace, monospace',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: CHART.grid, visible: true },
        horzLines: { color: CHART.grid, visible: true },
      },
      rightPriceScale: { borderColor: CHART.line },
      timeScale: { borderColor: CHART.line },
      crosshair: { mode: CrosshairMode.Normal },
    })
    chartRef.current = chart
    zoomRef.current = 0
    let resizeTimer: ReturnType<typeof setTimeout> | undefined
    const resize = () => {
      const width = host.clientWidth, height = host.clientHeight
      if (!width || !height || (width === renderedWidth && height === renderedHeight)) return
      const range = chart.timeScale().getVisibleLogicalRange()
      chart.resize(width, height)
      renderedWidth = width; renderedHeight = height
      if (range) chart.timeScale().setVisibleLogicalRange(range)
    }
    const ro = new ResizeObserver(() => {
      clearTimeout(resizeTimer); cancelChartResize(resize)
      resizeTimer = setTimeout(() => scheduleChartResize(resize), 80)
    })
    ro.observe(host)
    const barAt = (time: unknown) => typeof time === 'number' ? byTime.current.get(time) : undefined
    const handleCrosshair = (param: MouseEventParams) => {
      const candle = barAt(param.time)
      crosshair.textContent = candle ? `${new Date(candle.t * 1000).toISOString()} O ${candle.o.toFixed(4)} H ${candle.h.toFixed(4)} L ${candle.l.toFixed(4)} C ${candle.c.toFixed(4)} V ${candle.v.toFixed(0)}` : 'CROSSHAIR —'
      setChartHover({ bar: candle ?? null })
      registry?.publish(panelId, 'cursor', ...(candle ? [candle.t] : []))
    }
    const handleClick = (param: MouseEventParams) => {
      const id = param.hoveredInfo?.objectId ?? param.hoveredObjectId
      const marker = latest.current.evidence.find(row => row.id === id)
      if (marker) latest.current.onSelectEvidence?.(marker.sequenceId)
    }
    const handleRange = () => {
      host.dataset.visibleRange = JSON.stringify(chart.timeScale().getVisibleLogicalRange())
      const r = chart.timeScale().getVisibleRange()
      host.dataset.utcRange = JSON.stringify(r)
      if (!remoteRange.current && r && typeof r.from === 'number' && typeof r.to === 'number') registry?.publish(panelId, 'range', r.from, r.to)
    }
    const unregister = registry?.register(panelId, {
      range(from, to) { const logical = logicalRangeForUTC(times.current, from, to); if (logical) { remoteRange.current = true; chart.timeScale().setVisibleLogicalRange(logical) } },
      cursor(time) { const bar = barAt(time); if (bar && seriesRef.current) chart.setCrosshairPosition(bar.c, bar.t as UTCTimestamp, seriesRef.current); else chart.clearCrosshairPosition() },
    })
    const localGesture = () => { remoteRange.current = false }
    host.addEventListener('pointerdown', localGesture, true); host.addEventListener('wheel', localGesture, { passive: true, capture: true }); host.addEventListener('keydown', localGesture, true)
    chart.subscribeCrosshairMove(handleCrosshair); chart.subscribeClick(handleClick)
    chart.timeScale().subscribeVisibleTimeRangeChange(handleRange)
    return () => { unregister?.(); host.removeEventListener('pointerdown', localGesture, true); host.removeEventListener('wheel', localGesture, true); host.removeEventListener('keydown', localGesture, true); clearTimeout(resizeTimer); cancelChartResize(resize); ro.disconnect(); chart.remove(); chartRef.current = null }
  }, [panelId, registry])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    chart.applyOptions({ grid: { vertLines: { visible: controls.grid }, horzLines: { visible: controls.grid } }, crosshair: { mode: controls.crosshair ? CrosshairMode.Normal : CrosshairMode.Hidden } })
    const delta = controls.zoom - zoomRef.current
    if (delta) remoteRange.current = false
    if (delta) chart.timeScale().applyOptions({ barSpacing: barSpacingFor(chart.timeScale().options().barSpacing, delta) })
    zoomRef.current = controls.zoom
  }, [controls.grid, controls.crosshair, controls.zoom])
  useEffect(() => { if (reset) { remoteRange.current = false; chartRef.current?.timeScale().fitContent() } }, [reset])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    const range = savedRange.current ?? chart.timeScale().getVisibleLogicalRange()
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
    seriesRef.current = series
    const markerPlugin = createSeriesMarkers(series, [], { zOrder: 'top' })
    markersRef.current = markerPlugin
    if (range) chart.timeScale().setVisibleLogicalRange(range)
    else { chart.timeScale().fitContent(); if (zoomRef.current) chart.timeScale().applyOptions({ barSpacing: barSpacingFor(chart.timeScale().options().barSpacing, zoomRef.current) }) }
    const composition = chart.panes().flatMap(p => p.getSeries())
    return () => {
      if (chartRef.current !== chart) return
      savedRange.current = chart.timeScale().getVisibleLogicalRange()
      markerPlugin.detach(); markersRef.current = null; seriesRef.current = null
      series.detachPrimitive(annotationPrimitive)
      for (const item of composition) chart.removeSeries(item)
    }
  }, [bars, overlays, annotations, controls.type])

  useEffect(() => {
    const firstBar = bars[0]?.t ?? -Infinity
    const swings: SeriesMarker<UTCTimestamp>[] = swingMarkers(overlays?.annotations ?? []).filter(m => m.time >= firstBar).map(m => ({ id: m.id, time: m.time as UTCTimestamp, position: m.position, shape: 'circle', color: CHART.gold, size: 0.6, text: m.text }))
    markersRef.current?.setMarkers([...swings, ...evidence.map(m => seriesMarker(m, m.sequenceId === selectedSequenceId))].sort((a, b) => Number(a.time) - Number(b.time)))
  }, [bars, overlays, annotations, controls.type, evidence, selectedSequenceId])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !selectedTrade || selectedTrade.entry_ts === null || selectedTrade.exit_ts === null || selectedTrade.entry_price === null || selectedTrade.exit_price === null || selectedTrade.entry_ts >= selectedTrade.exit_ts) return
    const holding = chart.addSeries(LineSeries, { color: (selectedTrade.realized_return ?? 0) < 0 ? CHART.down : CHART.up, lineWidth: 2, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false, title: 'HOLDING' })
    holding.setData([{ time: selectedTrade.entry_ts as UTCTimestamp, value: selectedTrade.entry_price }, { time: selectedTrade.exit_ts as UTCTimestamp, value: selectedTrade.exit_price }])
    return () => { if (chartRef.current === chart) chart.removeSeries(holding) }
  }, [selectedTrade, bars, overlays, annotations, controls.type])

  return (
    <>
      <div ref={hostRef} className="price-host" />
      <div ref={crosshairRef} className="chart-crosshair-readout mono" aria-live="polite">
        CROSSHAIR —
      </div>
    </>
  )
}

import { useEffect, useRef } from 'react'
import { AreaSeries, ColorType, CrosshairMode, LineSeries, createChart, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts'
import { logicalRangeForUTC, type ChartLinkRegistry } from '../shell/chartLinkRegistry'
import { barSpacingFor, type ChartControls } from '../context/chartControls'
import { ScientificSeriesCanvas } from './ScientificSeriesCanvas'
import { RecordedValuesTable } from './RecordedValuesTable'
import type { PlotRenderer } from '../shell/chartWorkspaceModel'
import { CHART } from '../util/chartTheme'
export interface RecordedPoint { time: number; value: number | null }
/** Draw backend values unchanged. Whitespace entries preserve unavailable intervals. */
function MarketRecordedSeries({ points, label, unit, panelId, registry, area = false, controls, reset = 0 }: { points: RecordedPoint[]; label: string; unit: string; panelId: string; registry?: ChartLinkRegistry; area?: boolean; controls?: ChartControls; reset?: number }) {
  const host = useRef<HTMLDivElement>(null)
  const readout = useRef<HTMLSpanElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line' | 'Area'> | null>(null)
  const times = useRef<number[]>([])
  const values = useRef(new Map<number, number | null>())
  const remoteRange = useRef(true)
  const zoom = useRef(0)
  useEffect(() => {
    if (!host.current) return
    const node = host.current
    const chart = createChart(node, { layout: { background: { type: ColorType.Solid, color: CHART.bg }, textColor: CHART.muted, fontFamily: 'JetBrains Mono Variable, monospace', fontSize: 11 }, grid: { vertLines: { color: CHART.grid }, horzLines: { color: CHART.grid } }, timeScale: { borderColor: CHART.line }, rightPriceScale: { borderColor: CHART.line } })
    const series = area ? chart.addSeries(AreaSeries, { lineColor: CHART.down, topColor: '#e5484d44', bottomColor: '#e5484d08', lineWidth: 1 }) : chart.addSeries(LineSeries, { color: CHART.ink, lineWidth: 1 })
    chartRef.current = chart; seriesRef.current = series; zoom.current = 0
    const localGesture = () => { remoteRange.current = false }
    node.addEventListener('pointerdown', localGesture, true); node.addEventListener('wheel', localGesture, true); node.addEventListener('keydown', localGesture, true)
    let measured = false
    const observer = new ResizeObserver(() => { if (!node.clientWidth || !node.clientHeight) return; const range = measured ? chart.timeScale().getVisibleLogicalRange() : null; measured = true; chart.resize(node.clientWidth, node.clientHeight); if (range) chart.timeScale().setVisibleLogicalRange(range) }); observer.observe(node)
    chart.subscribeCrosshairMove(event => {
      const time = typeof event.time === 'number' ? event.time : null
      const value = time === null ? undefined : values.current.get(time)
      if (readout.current) readout.current.textContent = time !== null && value != null ? `${new Date(time * 1000).toISOString()} · ${value.toPrecision(6)} ${unit}` : 'Cursor —'
      registry?.publish(panelId, 'cursor', ...(time !== null ? [time] : []))
    })
    chart.timeScale().subscribeVisibleTimeRangeChange(range => { if (!remoteRange.current && range && typeof range.from === 'number' && typeof range.to === 'number') registry?.publish(panelId, 'range', range.from, range.to) })
    const unregister = registry?.register(panelId, { range(from, to) { const logical = logicalRangeForUTC(times.current, from, to); if (logical) { remoteRange.current = true; chart.timeScale().setVisibleLogicalRange(logical) } }, cursor(time) { const value = time === null ? undefined : values.current.get(time); if (time !== null && value != null) chart.setCrosshairPosition(value, time as UTCTimestamp, series); else chart.clearCrosshairPosition() } })
    return () => { unregister?.(); node.removeEventListener('pointerdown', localGesture, true); node.removeEventListener('wheel', localGesture, true); node.removeEventListener('keydown', localGesture, true); observer.disconnect(); chart.remove(); chartRef.current = null; seriesRef.current = null }
  }, [panelId, registry, area, unit])
  useEffect(() => {
    times.current = points.map(p => p.time)
    values.current = new Map(points.map(p => [p.time, p.value]))
    seriesRef.current?.setData(points.map(p => p.value === null ? { time: p.time as UTCTimestamp } : { time: p.time as UTCTimestamp, value: p.value }))
    chartRef.current?.timeScale().fitContent()
  }, [points])
  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !controls) return
    chart.applyOptions({ grid: { vertLines: { visible: controls.grid }, horzLines: { visible: controls.grid } }, crosshair: { mode: controls.crosshair ? CrosshairMode.Normal : CrosshairMode.Hidden } })
    const delta = controls.zoom - zoom.current
    if (delta) { remoteRange.current = false; chart.timeScale().applyOptions({ barSpacing: barSpacingFor(chart.timeScale().options().barSpacing, delta) }) }
    zoom.current = controls.zoom
  }, [controls])
  useEffect(() => { if (reset) { remoteRange.current = false; chartRef.current?.timeScale().fitContent() } }, [reset])
  return <div className="recorded-series"><div className="plot-legend">{label} · {unit} · UTC <span ref={readout} className="mono">Cursor —</span><button className="btn" onClick={() => { remoteRange.current = false; chartRef.current?.timeScale().fitContent() }}>Fit plot</button></div><div className="recorded-series-host" ref={host} />
    <RecordedValuesTable points={points} label={label} unit={unit} panelId={panelId}/></div>
}

export function RecordedSeries(props: { points: RecordedPoint[]; label: string; unit: string; panelId: string; registry?: ChartLinkRegistry; area?: boolean; controls?: ChartControls; reset?: number; renderer?: PlotRenderer }) {
  if (props.renderer === 'market') return <MarketRecordedSeries {...props}/>
  return <div className="recorded-series"><div className="plot-legend">{props.label} · {props.unit} · UTC</div><ScientificSeriesCanvas {...props}/><RecordedValuesTable {...props}/></div>
}

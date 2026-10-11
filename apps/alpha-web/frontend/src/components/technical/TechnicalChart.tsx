import { useEffect, useMemo, useRef, useState } from 'react'
import type { Candle, ChartAnnotation, ChartOverlays } from '../../api/types'
import type { EvidenceMarker } from '../../panels/v3Models'
import type { ChartControls } from '../../context/chartControls'
import type { ChartLinkRegistry } from '../../shell/chartLinkRegistry'
import { skippedText, type ShortStudy } from '../../panels/chartOverlaysModel'
import { ScientificRangeControls } from '../ScientificRangeControls'
import type { TechnicalChartController } from './technicalRenderer'
import { barDate, groupedInteger, headerValues, medianSpacing, priceDecimals, signed } from './technicalModel'
import { cssVars, technicalStyle, type ChartStyleName } from './technicalTokens'

const EMPTY: never[] = []

interface Props {
  bars: Candle[]
  title: string
  styleName: ChartStyleName
  evidence?: EvidenceMarker[]
  annotations?: ChartAnnotation[]
  selectedSequenceId?: number | null
  onSelectEvidence?: (sequence: number) => void
  overlays?: ChartOverlays | null
  skipped?: readonly ShortStudy[]
  controls?: ChartControls
  reset?: number
  panelId?: string
  registry?: ChartLinkRegistry
}

/**
 * The default analytical price chart (StockCharts Classic/Default grammar): a dense OHLC header,
 * then one BokehJS panel stack. Native observed bars and backend study values only.
 */
export function TechnicalChart({ bars, title, styleName, evidence = EMPTY, annotations = EMPTY, selectedSequenceId = null, onSelectEvidence, overlays = null, skipped = EMPTY, controls, reset = 0, panelId = 'technical-price', registry }: Props) {
  const host = useRef<HTMLDivElement>(null), header = useRef<HTMLSpanElement>(null)
  const controller = useRef<TechnicalChartController | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [undrawn, setUndrawn] = useState(0)
  // The window handed to the latest mount: survives a rebuild that starts before the last mount resolved.
  const windowRef = useRef<[number, number] | null>(null)
  const style = technicalStyle(styleName)
  const intraday = useMemo(() => medianSpacing(bars.map(b => b.t)) < 86400, [bars])
  const decimals = useMemo(() => priceDecimals(bars.map(b => b.c)), [bars])
  const points = useMemo(() => bars.map(b => ({ time: b.t, value: b.c })), [bars])
  const latest = useRef({ evidence, selectedSequenceId, onSelectEvidence, controls })
  latest.current = { evidence, selectedSequenceId, onSelectEvidence, controls }

  const writeHeader = (index: number | null) => {
    const values = headerValues(bars, index ?? bars.length - 1)
    if (!header.current || !values) return
    const { bar, change, changePct } = values
    const tone = change === null || change === 0 ? '' : change > 0 ? 'up' : 'down'
    header.current.dataset.tone = tone
    header.current.textContent = `${barDate(bar.t, intraday)}  Open ${bar.o.toFixed(decimals)}  High ${bar.h.toFixed(decimals)}  Low ${bar.l.toFixed(decimals)}  Close ${bar.c.toFixed(decimals)}  Volume ${groupedInteger(bar.v)}  Chg ${change === null ? '—' : `${change > 0 ? '▲' : change < 0 ? '▼' : ''}${signed(change, decimals)} (${changePct === null ? '—' : `${signed(changePct, 2)}%`})`}`
  }

  // Composition: bars, studies, annotations and style rebuild the panel stack; the visible UTC
  // window survives the rebuild. Evidence, selection and toolbar controls update in place.
  useEffect(() => {
    const node = host.current!
    let live = true
    const previous = controller.current?.visibleUTC() ?? windowRef.current
    windowRef.current = previous
    controller.current?.destroy(); controller.current = null
    setReady(false); setError(null)
    import('./technicalRenderer').then(async ({ mountTechnicalChart }) => {
      if (!live) return
      const chart = await mountTechnicalChart(node, {
        bars, style, title,
        indicators: overlays?.indicators ?? [], indicatorTimes: overlays?.t ?? [],
        annotations: [...annotations, ...(overlays?.annotations ?? [])],
        initialRange: previous,
      }, {
        panelId, registry, initialZoom: latest.current.controls?.zoom ?? 0,
        onCursor: writeHeader,
      })
      if (!live) { chart.destroy(); return }
      controller.current = chart
      setUndrawn(chart.undrawnAnnotations)
      const now = latest.current
      chart.evidence(now.evidence, now.selectedSequenceId, now.onSelectEvidence)
      if (now.controls) chart.controls(now.controls)
      setReady(true)
    }).catch(reason => { if (live) setError(String(reason)) })
    return () => { live = false }
    // writeHeader reads the same bars; the composition identity is the dependency list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bars, overlays, annotations, style, title, panelId, registry])
  useEffect(() => () => { controller.current?.destroy(); controller.current = null }, [])
  useEffect(() => { controller.current?.evidence(evidence, selectedSequenceId, onSelectEvidence) }, [evidence, selectedSequenceId, onSelectEvidence])
  useEffect(() => { if (controls) controller.current?.controls(controls) }, [controls])
  useEffect(() => { if (reset) controller.current?.fit() }, [reset])
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => writeHeader(null), [bars, decimals, intraday])

  const undrawnText = undrawn ? `${undrawn} annotation${undrawn === 1 ? '' : 's'} outside the loaded bars not drawn` : ''
  const savePng = async () => {
    const blob = await controller.current?.png([title, header.current?.textContent ?? '', undrawnText, skippedText(skipped)].filter(Boolean))
    if (!blob) return
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${title.replace(/[^A-Za-z0-9._-]+/g, '_')}.png`
    link.click()
    URL.revokeObjectURL(link.href)
  }

  return <div className="technical-chart" data-chart-style={style.name} style={cssVars(style) as React.CSSProperties}>
    <div className="technical-header">
      <strong className="technical-title">{title}</strong>
      <span className="technical-ohlc" ref={header} />
      {undrawn ? <span className="technical-skipped" title="Their anchors fall outside the loaded observations, so they cannot be placed on this axis.">{undrawnText}</span> : null}
      {skipped.length ? <span className="technical-skipped" title="The as-of window is shorter than these studies read; alpha chart overlays refused them, so they are not drawn.">{skippedText(skipped)}</span> : null}
      <span className="technical-tools">
        <ScientificRangeControls key={points[0]?.time} points={points} unit="native quote units" ready={ready} onFit={() => controller.current?.fit()} onRange={(from, to) => controller.current?.range(from, to)} />
        <button className="technical-link" disabled={!ready} onClick={() => void savePng()} title="Save this chart stack as a PNG">Save PNG</button>
      </span>
    </div>
    {error ? <p role="alert">Technical chart unavailable: {error}</p> : null}
    <div className="technical-host" ref={host} role="group" aria-label={`Technical price chart ${title}; observation-spaced UTC time axis; native quote units. The OHLCV table below has the same bars.`} />
  </div>
}

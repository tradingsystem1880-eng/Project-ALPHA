import { useMemo, useState } from 'react'
import type { Candle, ChartAnnotation, ChartOverlays } from '../api/types'
import type { EvidenceMarker } from '../panels/v3Models'
import type { ChartControls } from '../context/chartControls'
import type { ChartLinkRegistry } from '../shell/chartLinkRegistry'
import { ScientificSeriesCanvas } from './ScientificSeriesCanvas'
const EMPTY: never[] = []
/** Native observed prices and backend indicators. No resampling, estimated indicators or fills. */
export function ScientificMarketCanvas({ bars, evidence = EMPTY, annotations = EMPTY, selectedSequenceId = null, onSelectEvidence, overlays, controls, reset, panelId = 'scientific-price', registry }: { bars: Candle[]; evidence?: EvidenceMarker[]; annotations?: ChartAnnotation[]; selectedSequenceId?: number | null; onSelectEvidence?: (sequence: number) => void; overlays?: ChartOverlays | null; controls?: ChartControls; reset?: number; panelId?: string; registry?: ChartLinkRegistry }) {
  const [auxiliaryMounted, setAuxiliaryMounted] = useState(false)
  const points = useMemo(() => bars.map(b => ({ time: b.t, value: b.c })), [bars])
  const volume = useMemo(() => auxiliaryMounted ? bars.map(b => ({ time: b.t, value: b.v })) : [], [bars, auxiliaryMounted])
  const indicators = useMemo(() => auxiliaryMounted ? overlays?.indicators.map(series => ({ series, points: overlays.t.map((time, n) => ({ time, value: series.values[n] ?? null })) })) ?? [] : [], [overlays, auxiliaryMounted])
  const market = useMemo(() => ({ bars, evidence, annotations: [...annotations, ...(overlays?.annotations ?? EMPTY)], selected: selectedSequenceId, select: onSelectEvidence }), [bars, evidence, annotations, overlays, selectedSequenceId, onSelectEvidence])
  return <div className="scientific-market">
    <div className="scientific-market-price"><ScientificSeriesCanvas points={points} unit="Price (native quote units)" panelId={panelId} registry={registry} controls={controls} reset={reset} market={market}/></div>
    <details className="scientific-market-details" onToggle={event => { if (event.currentTarget.open) setAuxiliaryMounted(true) }}><summary>Volume and backend indicator plots · {overlays?.indicators.length ?? 0} series</summary>
      {auxiliaryMounted ? <><div className="scientific-indicator"><ScientificSeriesCanvas points={volume} unit="Volume (native source units)" panelId={`${panelId}-volume`} controls={controls} reset={reset}/></div>
      {indicators.map(({ series, points }, i) => <div className="scientific-indicator" key={`${series.name}-${i}`}><div className="plot-legend">{series.name} · {"backend units unspecified"} · {series.pane} · backend computed</div><ScientificSeriesCanvas points={points} unit={"backend units unspecified"} panelId={`${panelId}-indicator-${i}`} controls={controls} reset={reset}/></div>)}
      </> : null}
      <p>Auxiliary plots use independent ranges. Main panel UTC linking is controlled from Panels.</p>
    </details>
  </div>
}

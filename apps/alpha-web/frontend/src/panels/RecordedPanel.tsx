import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { EquitySeries, NativeTearSheetProjection, PortfolioAnalyticsProjection, RunDetail } from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { RecordedSeries, type RecordedPoint } from '../components/RecordedSeries'
import { CorrelationPlot, ScientificPlots } from '../components/ScientificPlots'
import type { PlotRenderer, PanelKind } from '../shell/chartWorkspaceModel'
import type { ChartControls } from '../context/chartControls'
import type { ChartLinkRegistry } from '../shell/chartLinkRegistry'
import { RunFigures } from './FigureReport'
interface Response { runId: string; kind: PanelKind; detail: RunDetail | null; equity: EquitySeries | null; native: NativeTearSheetProjection | null; portfolio: PortfolioAnalyticsProjection | null; error: string | null }
export function RecordedPanel({ runId, kind, panelId, registry, controls, reset, renderer }: { runId: string | null; kind: PanelKind; panelId: string; registry?: ChartLinkRegistry; controls?: ChartControls; reset?: number; renderer?: PlotRenderer }) {
  const [response, setResponse] = useState<Response | null>(null)
  useEffect(() => {
    let live = true
    if (!runId) return
    const result: Response = { runId, kind, detail: null, equity: null, native: null, portfolio: null, error: null }
    const request = kind === 'equity' || kind === 'drawdown' ? api.equity(runId).then(v => { result.equity = v }) : kind === 'correlation' ? api.portfolioAnalytics(runId).then(v => { result.portfolio = v }) : kind === 'figures' ? Promise.resolve() : api.nativeTearsheet(runId).then(v => { result.native = v })
    Promise.allSettled([api.run(runId).then(v => { result.detail = v }), request]).then(results => {
      const errors = results.filter((r): r is PromiseRejectedResult => r.status === 'rejected')
      result.error = errors.length ? errors.map(r => String(r.reason)).join('; ') : null
      if (live) setResponse(result)
    })
    return () => { live = false }
  }, [runId, kind])
  const data = response?.runId === runId && response.kind === kind ? response : null
  const points = useMemo<RecordedPoint[]>(() => {
    if (!data) return []
    if (data.equity) return data.equity.ts.map((time, i) => ({ time, value: (kind === 'drawdown' ? data.equity!.drawdown[i] : data.equity!.equity[i]) ?? null }))
    if (!data.native) return []
    if (kind === 'benchmark') return data.native.benchmark.map(p => ({ time: p.ts, value: p.available ? p.benchmark_equity : null }))
    if (kind === 'exposure' || kind === 'turnover') return data.native.exposure_turnover.map(p => ({ time: p.end_ts, value: kind === 'exposure' ? p.exposure_available ? p.gross_exposure : null : p.turnover_available ? p.turnover : null }))
    return data.native.rolling.map(p => ({ time: p.ts, value: kind === 'volatility' ? p.volatility : p.sharpe }))
  }, [data, kind])
  if (!runId) return <Placeholder big="Recorded run required">Choose a run source for this panel. Market candles do not supply research diagnostics.</Placeholder>
  if (!data) return <Placeholder>Loading recorded {kind}…</Placeholder>
  const unit = kind === 'equity' || kind === 'benchmark' ? 'backend equity units (currency/normalization unspecified)' : kind === 'sharpe' ? 'ratio' : 'fraction'
  return <div className="recorded-panel">
    <div className="recorded-provenance mono">Run {runId} · {data.detail?.run_context_watermark} · {data.detail?.research_gate_watermark}<span>Recorded evidence · no approval authority</span></div>
    {data.error ? <p role="alert">{kind} unavailable: {data.error}</p> : kind === 'figures' ? <RunFigures runId={runId}/> : kind === 'correlation' && data.portfolio ? <CorrelationPlot portfolio={data.portfolio}/> : kind === 'diagnostics' && data.native ? <ScientificPlots native={data.native}/> : !points.length || !points.some(p => p.value !== null) ? <Placeholder big={`${kind} unavailable`}>No available recorded values. {data.native?.benchmark.find(p => p.unavailable_reason)?.unavailable_reason} {data.native?.exposure_turnover.find(p => p.exposure_unavailable_reason)?.exposure_unavailable_reason} {data.native?.exposure_turnover.find(p => p.turnover_unavailable_reason)?.turnover_unavailable_reason}</Placeholder> : <RecordedSeries renderer={renderer} points={points} label={kind === 'sharpe' || kind === 'volatility' ? `Rolling ${kind === 'sharpe' ? 'Sharpe' : 'volatility'} (backend window ${data.native?.rolling[0]?.window ?? 'unavailable'})` : kind} unit={unit} panelId={panelId} registry={registry} area={kind === 'drawdown'} controls={controls} reset={reset}/>}
    {data.native ? <details className="recorded-bounds"><summary>Sampling and provenance</summary><table className="blotter compact" aria-label="Recorded projection sampling"><thead><tr><th>Series</th><th>Returned / original</th><th>Sampling</th><th>Truncated</th></tr></thead><tbody>{Object.entries(data.native.bounds ?? {}).map(([name, bound]) => typeof bound === 'number' ? null : <tr key={name}><td>{name.replaceAll('_', ' ')}</td><td className="num">{bound.returned} / {bound.original}</td><td>{bound.sampling === 'all' ? 'All values' : 'Endpoint-uniform sample'}</td><td>{bound.truncated ? 'Yes — more values exist' : 'No'}</td></tr>)}</tbody></table><details><summary>Raw provenance and bounds</summary><pre>{JSON.stringify({ available: data.native.available, bounds: data.native.bounds, provenance: data.native.provenance }, null, 2)}</pre></details></details> : null}
  </div>
}

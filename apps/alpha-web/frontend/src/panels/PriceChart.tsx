// Price — candlesticks for the linked symbol over the linked as-of window (PIT-adjusted). Typing a
// symbol here rebroadcasts it to every linked panel.

import type { IDockviewPanelProps } from 'dockview-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import type { Candle, ChartBundle } from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { PanelLinkControl } from '../components/PanelLinkControl'
import { PriceChartCanvas } from '../components/PriceChartCanvas'
import { usePanelLinked } from '../context/usePanelLinked'
import {
  matchingTraceSequence,
  matchingTradeTrace,
  selectTraceEvent,
  useChartSelection,
} from '../state/chartSelection'
import { openDevelopmentCenter } from './actions'
import { ChartDataAlternative } from './ChartDataAlternative'
import { TraceEvidencePanel } from './TraceEvidencePanel'
import { buildEvidenceMarkers } from './v3Models'

export function PriceChart(props: IDockviewPanelProps) {
  const panelLink = usePanelLinked(props)
  const { linked, setLinked: setPanelLinked } = panelLink
  const [symbol, setSymbol] = useState(linked.symbol ?? '')
  const [bars, setBars] = useState<Candle[] | null>(null)
  const [bundle, setBundle] = useState<ChartBundle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const chartSelection = useChartSelection()

  useEffect(() => {
    setSymbol(linked.symbol ?? '')
  }, [linked.symbol])

  useEffect(() => {
    if (linked.runId) return
    if (!symbol) {
      setBars(null)
      return
    }
    let live = true
    setError(null)
    setBars(null)
    const params = new URLSearchParams()
    if (linked.start) params.set('start', linked.start)
    if (linked.end) params.set('end', linked.end)
    if (linked.snapshotId) params.set('snapshot', linked.snapshotId)
    const query = params.toString() ? `?${params.toString()}` : ''
    api
      .candles(symbol, query)
      .then((c) => live && setBars(c.bars))
      .catch((e: unknown) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [symbol, linked.start, linked.end, linked.snapshotId, linked.runId])

  useEffect(() => {
    if (!linked.runId) {
      setBundle(null)
      return
    }
    let live = true
    setError(null)
    setBars(null)
    setBundle(null)
    api
      .chartBundle(linked.runId, 5_000, linked.start, linked.end)
      .then((next) => {
        if (!live) return
        setBundle(next)
        setBars(next.bars)
        const runSymbol = next.provenance.symbol
        const runSnapshot = next.provenance.snapshot_id
        if (runSymbol) setSymbol(runSymbol)
        if (runSymbol !== linked.symbol || runSnapshot !== linked.snapshotId) {
          setPanelLinked({
            ...(runSymbol ? { symbol: runSymbol } : {}),
            snapshotId: runSnapshot,
          })
        }
      })
      .catch((reason: unknown) => {
        if (!live) return
        setBundle(null)
        setError(String(reason))
      })
    return () => {
      live = false
    }
  }, [linked.runId, linked.snapshotId, linked.symbol, linked.start, linked.end, setPanelLinked])

  const evidence = useMemo(
    () => (bars && bundle ? buildEvidenceMarkers(bundle, bars.map((bar) => bar.t)) : []),
    [bars, bundle],
  )
  const selectedSequenceId = useMemo(
    () =>
      bundle
        ? matchingTraceSequence(chartSelection, bundle.run_id, bundle.trace)
        : null,
    [bundle, chartSelection],
  )
  const selected = useMemo(
    () => bundle?.trace.find((event) => event.sequence_id === selectedSequenceId) ?? null,
    [bundle, selectedSequenceId],
  )
  const selectedTrade = useMemo(
    () => (bundle && selected ? matchingTradeTrace(selected, bundle.trace) : null),
    [bundle, selected],
  )
  const selectEvidence = useCallback((sequenceId: number) => {
    if (!bundle) return
    const event = bundle.trace.find((candidate) => candidate.sequence_id === sequenceId)
    if (event) selectTraceEvent(bundle.run_id, event, bundle.trace)
  }, [bundle])

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Price</span>
        <PanelLinkControl controller={panelLink} />
        <input
          className="field sym-input"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && setPanelLinked({ symbol })}
          placeholder="symbol"
          spellCheck={false}
        />
        {bars ? <span className="count">{bars.length} bars</span> : null}
        {bundle ? (
          <span className={`chip ${bundle.trace_status === 'available' ? 'kind' : ''}`}>
            {bundle.trace_status === 'available' ? `${bundle.trace.length} returned causal events` : 'trace unavailable'}
          </span>
        ) : null}
        {bundle ? <span className="chip">{bundle.provenance.command ?? 'run'} · artifact v{bundle.provenance.artifact_contract_version ?? 'legacy'}</span> : null}
      </div>
      <div className="panel-body price-body price-evidence-layout">
        {error ? (
          <Placeholder big="no data">{error}</Placeholder>
        ) : !symbol ? (
          <Placeholder big="no symbol">Pick one in Data Explorer or a run, or type it above</Placeholder>
        ) : !bars ? (
          <Placeholder>loading…</Placeholder>
        ) : bars.length === 0 ? (
          <Placeholder>no bars in window</Placeholder>
        ) : (
          <div className="price-chart-frame">
            <div className="price-chart-canvas-wrap">
              <PriceChartCanvas
                bars={bars}
                evidence={evidence}
                annotations={bundle?.annotations ?? []}
                selectedSequenceId={selectedSequenceId}
                selectedTrade={selectedTrade}
                onSelectEvidence={selectEvidence}
              />
            </div>
            <div className="chart-foot mono">
              <span>PRICE · NATIVE QUOTE UNITS</span>
              <span>TIME · UTC</span>
              <span>AS OF {linked.end ?? new Date((bundle?.provenance.as_of ?? bars.at(-1)!.t) * 1_000).toISOString().slice(0, 10)}</span>
              <span>SNAPSHOT · {linked.snapshotId ?? 'CURRENT STORE'}</span>
              <span>D decision · F fill · ENTRY / EXIT artifact markers</span>
            </div>
          </div>
        )}
        {bars && bundle?.trace_status === 'trace_unavailable' ? (
          <div className="trace-unavailable">
            <strong>TRACE UNAVAILABLE</strong>
            <span>Legacy evidence is never reconstructed. Rerun this specification to emit a v3 causal trace.</span>
            <button className="btn" onClick={() => openDevelopmentCenter(props.containerApi!)}>
              Rerun for causal trace
            </button>
          </div>
        ) : null}
        {bars && bundle?.trace_status === 'available' ? (
          <TraceEvidencePanel
            bundle={bundle}
            selected={selected}
            selectedSequenceId={selectedSequenceId}
            onSelectEvidence={selectEvidence}
          />
        ) : null}
        {bars ? (
          <ChartDataAlternative
            bars={bars}
            truncated={bundle?.truncated.bars ?? false}
            runId={bundle?.run_id ?? null}
            symbol={symbol}
          />
        ) : null}
      </div>
    </div>
  )
}

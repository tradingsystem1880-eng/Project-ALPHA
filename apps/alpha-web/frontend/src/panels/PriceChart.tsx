// Price — candlesticks for the linked symbol over the linked as-of window (PIT-adjusted). Typing a
// symbol here rebroadcasts it to every linked panel.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { DEFAULT_LINKED, type LinkedState } from '../context/linked'
import type { PanelSource } from '../shell/chartWorkspaceModel'
import type { ChartControls } from '../context/chartControls'
import type { ChartLinkRegistry } from '../shell/chartLinkRegistry'
import { setChartHover } from '../context/chartHover'
import { api, type ArchiveChartDataset } from '../api/client'
import { ArchiveChartSelect } from '../components/ArchiveChartSelect'
import type { Candle, CandleProvenance, ChartBundle, ChartOverlays, PaperCandleMarker } from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { ScientificMarketCanvas } from '../components/ScientificMarketCanvas'
import type { PlotRenderer } from '../shell/chartWorkspaceModel'
import { PriceChartCanvas } from '../components/PriceChartCanvas'
import { usePanelLinked } from '../context/usePanelLinked'
import {
  matchingTraceSequence,
  matchingTradeTrace,
  selectTraceEvent,
  useChartSelection,
} from '../state/chartSelection'
import { useSettings } from '../state/settings'
import { openArchiveMarket, openDevelopmentCenter, openIndicators } from './actions'
import { ChartDataAlternative } from './ChartDataAlternative'
import { hasOverlays, overlayLegend, overlayQuery } from './chartOverlaysModel'
import { TraceEvidencePanel } from './TraceEvidencePanel'
import {
  buildEvidenceMarkers,
  visibleEvidenceMarkers,
  type EvidenceLayer,
} from './v3Models'
import type { PanelHandleProps } from '../context/panelHandle'

export function PriceChart(props: PanelHandleProps) {
  const panelLink = usePanelLinked(props)
  const workspace = props.params as { onChooseSource?: () => void; renderer?: PlotRenderer; visible?: boolean; canonicalContext?: LinkedState; source?: PanelSource; controls?: ChartControls; reset?: number; panelId?: string; registry?: ChartLinkRegistry; table?: boolean } | undefined
  const canonicalRef = useRef(panelLink.linked)
  if (workspace?.visible !== false) canonicalRef.current = panelLink.linked
  const source = workspace?.source
  const isolated = source && source.kind !== 'primary'
  const linked = !isolated ? workspace?.canonicalContext ?? canonicalRef.current : { ...DEFAULT_LINKED, ...(source.kind === 'run' ? { runId: source.runId } : source.kind === 'market' ? source : { symbol: source.dataset.instrument }) }
  const updateCanonical = panelLink.setLinked
  const setPanelLinked = useCallback((patch: Parameters<typeof panelLink.setLinked>[0]) => { if (!isolated) updateCanonical(patch) }, [isolated, updateCanonical])
  // A tiled chart window (`chart:<symbol>`) is pinned to its own symbol; the plain Chart follows
  // the linked symbol like every other panel.
  const instance = (props.params as { instance?: unknown } | undefined)?.instance
  const pinned = isolated && source.kind === 'market' ? source.symbol : typeof instance === 'string' && instance ? instance : null
  const parameters = props.params as { archive?: ArchiveChartDataset | null; onArchiveChange?: (value: ArchiveChartDataset | null) => void } | undefined
  const archive = source?.kind === 'archive' ? source.dataset : isolated || pinned ? null : parameters?.archive ?? null
  const setArchive = isolated ? () => undefined : parameters?.onArchiveChange ?? (() => undefined)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [storedSymbol, setSymbol] = useState(pinned ?? linked.symbol ?? '')
  const symbol = archive?.instrument ?? storedSymbol
  const { profile, overlays: overlaySettings } = useSettings()
  const overlayConfig = overlaySettings[profile]
  const [overlays, setOverlays] = useState<ChartOverlays | null>(null)
  const [overlayError, setOverlayError] = useState<string | null>(null)
  const [bars, setBars] = useState<Candle[] | null>(null)
  const [bundle, setBundle] = useState<ChartBundle | null>(null)
  const [paperMarkers, setPaperMarkers] = useState<PaperCandleMarker[]>([])
  const [candleProvenance, setCandleProvenance] = useState<CandleProvenance | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [evidenceLayer, setEvidenceLayer] = useState<EvidenceLayer>('executions')
  const chartSelection = useChartSelection()

  // The status bar reads the loaded bar count and the hovered bar from the chart hover store.
  useEffect(() => {
    setChartHover({ barsLoaded: bars?.length ?? 0 })
    return () => setChartHover({ bar: null, barsLoaded: 0 })
  }, [bars])
  useEffect(() => {
    if (!pinned) setSymbol(linked.symbol ?? '')
  }, [linked.symbol, linked.projectId, linked.linkGroup, linked.runId, profile, pinned])

  // Overlays come from `alpha chart overlays` over the same as-of window as the candles; a
  // failure keeps the candles and says why the overlay is missing. Run documents draw the run's
  // own annotations instead.
  const overlayQueryText = overlayQuery(overlayConfig, { end: linked.end ?? null, snapshotId: archive ? null : linked.snapshotId ?? null }) + (archive ? `&manifest_id=${archive.manifest_id}` : '')
  const wantOverlays = !linked.runId && Boolean(symbol) && hasOverlays(overlayConfig)
  useEffect(() => {
    if (!wantOverlays) {
      setOverlays(null)
      setOverlayError(null)
      return
    }
    let live = true
    setOverlays(null)
    setOverlayError(null)
    api
      .overlays(symbol, overlayQueryText)
      .then((result) => {
        if (!live) return
        setOverlays(result)
        setOverlayError(null)
      })
      .catch((cause: unknown) => {
        if (!live) return
        setOverlays(null)
        setOverlayError(String(cause))
      })
    return () => {
      live = false
    }
  }, [wantOverlays, symbol, overlayQueryText])

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
    if (archive) params.set('manifest_id', archive.manifest_id)
    else if (linked.snapshotId) params.set('snapshot', linked.snapshotId)
    const query = params.toString() ? `?${params.toString()}` : ''
    api
      .candles(symbol, query)
      .then((c) => {
        if (!live) return
        setBars(c.bars)
        setPaperMarkers(c.paper_markers)
        setCandleProvenance(c.provenance)
      })
      .catch((e: unknown) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [symbol, linked.start, linked.end, linked.snapshotId, linked.runId, archive])

  useEffect(() => {
    if (!linked.runId) {
      setBundle(null)
      return
    }
    let live = true
    setError(null)
    setBars(null)
    setPaperMarkers([])
    setCandleProvenance(null)
    setBundle(null)
    api
      .chartBundle(linked.runId, 1_000, linked.start, linked.end)
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
    () => {
      if (bars && bundle) return buildEvidenceMarkers(bundle, bars.map((bar) => bar.t))
      return paperMarkers.map((marker) => ({
        id: `paper:${marker.session_id}:${marker.sequence}`,
        sequenceId: marker.sequence,
        kind: marker.event_type === 'fill' ? 'fill' as const : 'decision' as const,
        barTs: marker.t,
        exactTs: marker.exact_ts,
        label: `P ${marker.event_type.toUpperCase()}${marker.side ? ` ${marker.side}` : ''}`,
        tone: marker.side?.toUpperCase().includes('SELL') ? 'negative' as const : 'positive' as const,
      }))
    },
    [bars, bundle, paperMarkers],
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
  const visibleEvidence = useMemo(
    () => visibleEvidenceMarkers(evidence, evidenceLayer, selectedSequenceId),
    [evidence, evidenceLayer, selectedSequenceId],
  )
  const selectEvidence = useCallback((sequenceId: number) => {
    if (!bundle) return
    const event = bundle.trace.find((candidate) => candidate.sequence_id === sequenceId)
    if (event) selectTraceEvent(bundle.run_id, event, bundle.trace)
  }, [bundle])

  const PriceCanvas = workspace?.renderer === 'market' ? PriceChartCanvas : ScientificMarketCanvas
  return (
    <div className="panel price-panel">
      <div className="panel-toolbar price-toolbar">
        <span className="title">Price</span>
        <input
          className="field sym-input"
          value={symbol}
          onChange={(e) => { setArchive(null); setSymbol(e.target.value) }}
          readOnly={Boolean(archive) || Boolean(isolated) || Boolean(linked.runId)}
          onKeyDown={(e) => !archive && !isolated && !linked.runId && e.key === 'Enter' && setPanelLinked({ symbol })}
          placeholder="symbol"
          spellCheck={false}
        />
        {!linked.runId && !pinned && !isolated ? <button className="btn" onClick={() => setArchiveOpen(value => !value)}>External archive…</button> : null}
        {archive && !isolated ? <button className="btn" onClick={() => { setArchive(null); setSymbol(linked.symbol ?? '') }}>Return to stored chart</button> : null}
        {archive ? <span className="chip">{archive.venue} · {archive.market_type} · {archive.frequency} · archive {archive.manifest_id.slice(0, 10)}</span> : null}
        {bars ? <span className="count">{bars.length} bars</span> : null}
        {!linked.runId ? (
          <button
            type="button"
            className="btn"
            onClick={openIndicators}
            title="Choose the indicator series and pattern layers alpha chart overlays computes for this chart"
          >
            Indicators…{hasOverlays(overlayConfig) ? ` (${overlayConfig.indicators.length + overlayConfig.patterns.length})` : ''}
          </button>
        ) : null}
        {overlayError ? (
          <span className="chip fail" role="status" title={overlayError}>
            overlays unavailable · {overlayError}
          </span>
        ) : null}
        {bundle ? (
          <span className={`chip chart-trace-count ${bundle.trace_status === 'available' ? 'kind' : ''}`}>
            {bundle.trace_status === 'available' ? `${bundle.trace.length} returned causal events` : 'trace unavailable'}
          </span>
        ) : null}
        {bundle ? <span className="chip chart-run-provenance">{bundle.provenance.command ?? 'run'} · artifact v{bundle.provenance.artifact_contract_version ?? 'legacy'}</span> : null}
        {!bundle && paperMarkers.length ? <span className="chip kind">{paperMarkers.length} paper events</span> : null}
        {!bundle && candleProvenance ? (
          <span className={`chip ${candleProvenance.quality_status === 'legacy_unqualified' ? 'fail' : 'pass'}`}>
            {candleProvenance.source} · {candleProvenance.venue ?? 'venue n/a'} · {candleProvenance.timeframe} · {candleProvenance.quality_status}
          </span>
        ) : null}
        {bundle?.trace_status === 'available' ? (
          <span className="chart-layer-controls" aria-label="Chart evidence layer">
            {(['executions', 'decisions', 'all'] as const).map((layer) => (
              <button key={layer} className={`btn${evidenceLayer === layer ? ' selected' : ''}`} aria-pressed={evidenceLayer === layer} onClick={() => setEvidenceLayer(layer)}>{layer}</button>
            ))}
            <span className="muted mono">{visibleEvidence.length}/{evidence.length} markers shown</span>
          </span>
        ) : null}
      </div>
      {archiveOpen ? <ArchiveChartSelect onClose={() => setArchiveOpen(false)} onSelect={item => { openArchiveMarket(item); setArchiveOpen(false) }} /> : null}
      <div className="panel-body price-body price-evidence-layout">
        {error ? (
          <Placeholder big={linked.runId ? "Recorded price unavailable" : "no data"}>{linked.runId ? "Frozen snapshot required; current market data is never substituted. " : ""}{error}</Placeholder>
        ) : !symbol ? (
          <Placeholder big="Choose data to chart"><p>Browse stored markets or open a verified native archive. No project is required.</p>{workspace?.onChooseSource ? <button className="btn" onClick={workspace.onChooseSource}>Choose chart source</button> : null}{!isolated ? <button className="btn" onClick={() => setArchiveOpen(true)}>Browse native archives</button> : null}</Placeholder>
        ) : !bars ? (
          <Placeholder>loading…</Placeholder>
        ) : bars.length === 0 ? (
          <Placeholder>{linked.runId ? bundle?.bars_status === 'not_applicable' ? "Price is not applicable to this recorded run." : `Frozen price snapshot unavailable or no recorded bars in this window (${bundle?.bars_status ?? 'unavailable'}). Current market data is never substituted.` : "no bars in window"}</Placeholder>
        ) : (
          <div className="price-chart-frame">
            <div className="price-chart-canvas-wrap" hidden={workspace?.table}>
              <PriceCanvas
                bars={bars}
                controls={workspace?.controls} reset={workspace?.reset} panelId={workspace?.panelId} registry={workspace?.registry}
                evidence={visibleEvidence}
                annotations={bundle?.annotations}
                selectedSequenceId={selectedSequenceId}
                selectedTrade={selectedTrade}
                onSelectEvidence={selectEvidence}
                overlays={overlays}
              />
            </div>
            <div className="chart-foot mono">
              <span>PRICE · NATIVE QUOTE UNITS</span>
              <span>TIME · UTC</span>
              {candleProvenance?.volume_unit ? <span>VOLUME · {candleProvenance.volume_unit.toUpperCase()} ASSET</span> : null}
              <span>AS OF {linked.end ?? new Date((bundle?.provenance.as_of ?? bars.at(-1)!.t) * 1_000).toISOString().slice(0, 10)}</span>
              <span>{archive ? `ARCHIVE · ${archive.manifest_id.slice(0, 12)} · ${archive.market_type} · reconstructed history` : `SNAPSHOT · ${linked.snapshotId ?? 'CURRENT STORE'}`}</span>
              <span>D decision · F fill · P paper journal event</span>
              {overlays ? <span className="overlay-legend">{overlayLegend(overlays.indicators, overlays.annotations)}</span> : null}
            </div>
          </div>
        )}
        {bars && bundle?.trace_status === 'trace_unavailable' ? (
          <div className="trace-unavailable">
            <strong>TRACE UNAVAILABLE</strong>
            <span>Legacy evidence is never reconstructed. Rerun this specification to emit a v3 causal trace.</span>
            <button className="btn" onClick={() => openDevelopmentCenter()}>
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
            expanded={workspace?.table}
            truncated={bundle?.truncated.bars ?? false}
            runId={bundle?.run_id ?? null}
            symbol={symbol}
          />
        ) : null}
      </div>
    </div>
  )
}

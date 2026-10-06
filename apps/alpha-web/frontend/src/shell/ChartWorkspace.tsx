import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { ArchiveChartSelect } from '../components/ArchiveChartSelect'
import { nativeSources } from './nativeSourceModel'
import { api, type ArchiveChartDataset } from '../api/client'
import { useLinked } from '../context/linked'
import { PriceChart } from '../panels/PriceChart'
import { RecordedPanel } from '../panels/RecordedPanel'
import type { Profile } from '../state/settings'
import { ChartControls } from './Toolbar'
import { PanelHost } from './PanelHost'
import { MarketDesk } from './MarketDesk'
import { PanelSourceEditor } from './PanelSourceEditor'
import { WorkspaceSplitter } from './WorkspaceSplitter'
import { createChartLinkRegistry } from './chartLinkRegistry'
import { LAYOUTS, PANEL_KINDS, closePanel, duplicatePanel, panel, restoreWorkspace, type AnalyticalPanel, type PanelSource, type WorkspaceLayout, type PanelKind, type PlotRenderer } from './chartWorkspaceModel'
const PANEL_LABELS: Record<PanelKind, string> = { price: 'Price chart', table: 'OHLCV table', equity: 'Equity', drawdown: 'Drawdown', sharpe: 'Rolling Sharpe', volatility: 'Rolling volatility', benchmark: 'Benchmark', exposure: 'Exposure', turnover: 'Turnover', diagnostics: 'Diagnostics', correlation: 'Correlation', figures: 'Scientific figures' }
const LAYOUT_LABELS: Record<WorkspaceLayout, string> = { single: 'Single chart', 'side-by-side': 'Two columns', stacked: 'Two rows', 'three-row': 'Three rows', grid: 'Four panels' }
function readWorkspace(profile: Profile) {
  try { const old = JSON.parse(localStorage.getItem('alpha.comparison-desks.v1') ?? '{}'); return restoreWorkspace(JSON.parse(localStorage.getItem(`alpha.chart-workspace.v1.${profile}`) ?? 'null'), old[profile] ?? []) }
  catch { return restoreWorkspace(null) }
}
function sourceLabel(source: PanelSource): string {
  return source.kind === 'primary' ? 'Canonical context' : source.kind === 'run' ? `Run ${source.runId}` : source.kind === 'archive' ? `${source.dataset.instrument} · ${source.dataset.venue} · ${source.dataset.frequency} · archive ${source.dataset.manifest_id.slice(0, 12)}` : source.symbol ? `${source.symbol} · stored market · pinned` : 'Choose a market or archive'
}
function placement(layout: WorkspaceLayout, index: number, ratios: [number, number]): CSSProperties {
  const x = ratios[0] * 100, y = ratios[1] * 100
  if (layout === 'single') return index === 0 ? { inset: 0 } : { inset: 0, visibility: 'hidden', pointerEvents: 'none' }
  if (layout === 'side-by-side') return { left: `${index === 0 ? 0 : x}%`, right: index === 0 ? `${100 - x}%` : 0, top: 0, bottom: 0, ...(index > 1 ? { visibility: 'hidden' as const } : {}) }
  if (layout === 'stacked') return { top: `${index === 0 ? 0 : y}%`, bottom: index === 0 ? `${100 - y}%` : 0, left: 0, right: 0, ...(index > 1 ? { visibility: 'hidden' as const } : {}) }
  if (layout === 'three-row') { const first = ratios[0] * 100, second = first + (100 - first) * ratios[1]; return { left: 0, right: 0, top: `${[0, first, second][index] ?? 0}%`, bottom: `${[100 - first, 100 - second, 0][index] ?? 0}%`, ...(index > 2 ? { visibility: 'hidden' as const } : {}) } }
  return { left: `${index % 2 ? x : 0}%`, right: index % 2 ? 0 : `${100 - x}%`, top: `${index >= 2 ? y : 0}%`, bottom: index >= 2 ? 0 : `${100 - y}%` }
}
export function ChartWorkspace({ profile, archive, onArchiveChange, visible = true, command, onCommandHandled, onFooterMount }: { profile: Profile; archive: ArchiveChartDataset | null; onArchiveChange: (value: ArchiveChartDataset | null) => void; visible?: boolean; command?: { sequence: number; profile: Profile; action: 'canonical' | 'duplicate' | 'tile'; archive?: ArchiveChartDataset } | null; onCommandHandled?: (sequence: number) => void; onFooterMount?: (node: HTMLDivElement | null) => void }) {
  const canonical = useLinked()
  const linkedRef = useRef(canonical)
  const observedContext = useRef(canonical)
  if (visible && observedContext.current !== canonical) linkedRef.current = canonical
  observedContext.current = canonical
  const linked = linkedRef.current
  const [state, setState] = useState(() => readWorkspace(profile))
  const [nativePicker, setNativePicker] = useState<{ panelId: string; interval: string; instrument: string } | null>(null)
  const [editor, setEditor] = useState<string | null>(null)
  const [resets, setResets] = useState<Record<string, number>>({})
  const [datasetError, setDatasetError] = useState<string | null>(null)
  const [datasets, setDatasets] = useState<ArchiveChartDataset[]>([])
  const buttons = useRef(new Map<string, HTMLButtonElement>())
  const registry = useMemo(createChartLinkRegistry, [])
  registry.configure(state.linkRange, state.linkCursor)
  const active = state.panels.find(p => p.id === state.active) ?? state.panels[0]
  const patchPanel = (id: string, patch: Partial<AnalyticalPanel>) => setState(s => ({ ...s, panels: s.panels.map(p => p.id === id ? { ...p, ...patch } : p) }))
  useEffect(() => { try { localStorage.setItem(`alpha.chart-workspace.v1.${profile}`, JSON.stringify({ ...state, maximized: null })) } catch { /* Presentation remains usable without storage. */ } }, [state, profile])
  const restore = useCallback(() => { const id = state.maximized; setState(s => ({ ...s, maximized: null })); if (id) requestAnimationFrame(() => buttons.current.get(id)?.focus()) }, [state.maximized])
  useEffect(() => { if (!state.maximized) return; const key = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); restore() } }; window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key) }, [state.maximized, restore])
  const resolvedSource = (p: AnalyticalPanel): PanelSource => p.source.kind !== 'primary' ? p.source : archive ? { kind: 'archive', dataset: archive } : linked.runId ? { kind: 'run', runId: linked.runId } : { kind: 'market', symbol: linked.symbol ?? '', start: linked.start, end: linked.end, snapshotId: linked.snapshotId }
  const activeSource = resolvedSource(active)
  useEffect(() => { let live = true; if (profile === 'crypto') api.chartDatasets().then(v => { if (live) { setDatasets(v.datasets); setDatasetError(null) } }).catch(e => { if (live) { setDatasets([]); setDatasetError(String(e)) } }); return () => { live = false } }, [profile])
  const compatibles = nativeSources(activeSource, datasets)
  const native = activeSource.kind === 'archive' ? activeSource.dataset.frequency : '1d'
  const presets = (kinds: PanelKind[]) => {
    const source = resolvedSource(active)
    setState(s => ({ ...s, panels: kinds.map((kind, i) => panel(i === 0 ? 'primary' : `preset-${i}`, i === 0 && kinds.length === 2 ? structuredClone(s.panels.find(p => p.id === 'primary')?.source ?? { kind: 'primary' }) : structuredClone(source), kind)), active: 'primary', layout: kinds.length === 2 ? 'side-by-side' : kinds.length === 3 ? 'three-row' : 'grid', maximized: null }))
  }
  const arrange = (layout: WorkspaceLayout) => setState(s => {
    const n = layout === 'single' ? 1 : layout === 'three-row' ? 3 : layout === 'grid' ? 4 : 2
    let next = s; while (next.panels.length < n) next = duplicatePanel(next, next.active, resolvedSource(next.panels.find(p => p.id === next.active)!))
    return { ...next, layout, active: next.panels[0].id }
  })
  const commandHandler = useRef<(action: NonNullable<typeof command>) => void>(() => undefined)
  commandHandler.current = action => {
    if (action.action === 'canonical') { linkedRef.current = canonical; setState(s => ({ ...s, active: 'primary', panels: s.panels.map(p => p.id === 'primary' ? { ...p, kind: 'price', source: { kind: 'primary' } } : p) })) }
    else if (action.action === 'tile') arrange('grid')
    else setState(s => duplicatePanel(s, s.active, resolvedSource(s.panels.find(p => p.id === s.active)!)))
  }
  const lastCommand = useRef<number | null>(null)
  const handled = useRef(onCommandHandled); handled.current = onCommandHandled
  useEffect(() => { if (command && command.profile === profile && command.sequence !== lastCommand.current) { lastCommand.current = command.sequence; commandHandler.current(command); handled.current?.(command.sequence) } }, [command, profile])
  const toolbar = <><select className="field" aria-label="Plot renderer" value={active.renderer} onChange={e => patchPanel(active.id, { renderer: e.target.value as PlotRenderer })}><option value="scientific">Research · Bokeh</option><option value="market">Market · Lightweight</option></select><ChartControls market={active.kind === 'price' || active.kind === 'table'} disabled={['diagnostics', 'correlation', 'figures'].includes(active.kind)} value={active.controls} onChange={patch => patchPanel(active.id, { controls: { ...active.controls, ...patch } })}/><button className="btn" disabled={['diagnostics', 'correlation', 'figures'].includes(active.kind)} onClick={() => { patchPanel(active.id, { controls: { ...active.controls, zoom: 0 } }); setResets(s => ({ ...s, [active.id]: (s[active.id] ?? 0) + 1 })) }}>Fit / reset</button>
    <span className="native-timeframes" aria-label="Native timeframe">{['15m', '1h', '4h', '1d', '1w'].map(interval => { const match = compatibles.find(d => d.frequency.toLowerCase() === interval); const selected = native.toLowerCase() === interval; return <button key={interval} className="btn" aria-pressed={selected} disabled={!selected && !match} title={selected ? 'Recorded native interval' : match ? 'Choose a verified native source' : datasetError ? `Native source inventory unavailable: ${datasetError}` : 'No compatible native source; browser resampling is unavailable'} onClick={() => { if (!match) return; if (activeSource.kind === 'archive') { if (active.source.kind === 'primary') onArchiveChange(match); else patchPanel(active.id, { source: { kind: 'archive', dataset: match } }) } else setNativePicker({ panelId: active.id, interval, instrument: match.instrument }) }}>{interval.toUpperCase()}</button> })}</span>
    <select className="field" aria-label="Analytical layout" value={state.layout} onChange={e => arrange(e.target.value as WorkspaceLayout)}>{LAYOUTS.map(l => <option key={l} value={l}>{LAYOUT_LABELS[l]}</option>)}</select>
    <details className="desk-options"><summary>Panels</summary><div><button className="btn" disabled={activeSource.kind !== 'run'} onClick={() => presets(['equity', 'drawdown', 'diagnostics', 'figures'])}>Research report · plots / diagnostics / figures</button><button className="btn" onClick={() => presets(['price', 'table'])}>Chart / table</button><button className="btn" onClick={() => presets(['price', 'diagnostics'])}>Chart / diagnostics</button><button className="btn" disabled={activeSource.kind !== 'run'} onClick={() => presets(['price', 'equity', 'drawdown'])}>Price / equity / drawdown</button><button className="btn" disabled={activeSource.kind !== 'run'} onClick={() => presets(['price', 'equity', 'drawdown', 'sharpe'])}>Price / equity / drawdown / rolling Sharpe</button><label><input type="checkbox" checked={state.linkRange} onChange={e => setState(s => ({ ...s, linkRange: e.target.checked }))}/>Link UTC ranges</label><label><input type="checkbox" checked={state.linkCursor} onChange={e => setState(s => ({ ...s, linkCursor: e.target.checked }))}/>Link UTC cursors</label></div></details></>
  const target = document.getElementById('analytical-toolbar')
  return <MarketDesk onFooterMount={onFooterMount} profile={profile} archive={archive} tools={target ? null : toolbar}>
    {target ? createPortal(toolbar, target) : null}
    <div className={`analytical-workspace layout-${state.layout}${state.maximized ? ' has-maximized' : ''}`} aria-label="Analytical workspace" style={{ '--split-x': state.ratios[0], '--split-y': state.ratios[1] } as CSSProperties}>
      {state.panels.map((p, i) => { const source = resolvedSource(p); const runId = source.kind === 'run' ? source.runId : null; const maximized = state.maximized === p.id
        return <section role="group" key={p.id} className={`analytical-panel${state.active === p.id ? ' active-panel' : ''}${maximized ? ' panel-maximized' : ''}`} data-panel-id={p.id} aria-label={`${p.kind} panel ${p.id}`} style={state.maximized ? maximized ? undefined : { ...placement(state.layout, i, state.ratios), visibility: 'hidden' } : placement(state.layout, i, state.ratios)} onFocusCapture={() => state.active !== p.id && setState(s => ({ ...s, active: p.id }))} onPointerDownCapture={() => state.active !== p.id && setState(s => ({ ...s, active: p.id }))}>
          <header className="analytical-title"><span title={sourceLabel(source)}>{PANEL_LABELS[p.kind]} · {p.source.kind === 'primary' ? `Canonical · ${sourceLabel(source).replace(' · pinned', '')}` : sourceLabel(source)}</span><select className="field" aria-label={`Replace panel ${p.id}`} value={p.kind} onChange={e => patchPanel(p.id, { kind: e.target.value as PanelKind })}>{PANEL_KINDS.map(k => <option key={k} value={k}>{PANEL_LABELS[k]}</option>)}</select><button className="btn" title="Choose a market, exact archive or recorded run for this panel" onClick={() => setEditor(p.id)}>Source</button><button className="btn" aria-label={`Duplicate panel ${p.id}`} disabled={state.panels.length >= 4} onClick={() => setState(s => duplicatePanel(s, p.id, source))}>⧉</button><button ref={node => { if (node) buttons.current.set(p.id, node); else buttons.current.delete(p.id) }} className="btn" aria-label={`${maximized ? 'Restore' : 'Maximize'} panel ${p.id}`} onClick={() => maximized ? restore() : setState(s => ({ ...s, active: p.id, maximized: p.id }))}>{maximized ? 'Restore · Esc' : '□'}</button><button className="btn" aria-label={`Close panel ${p.id}`} disabled={p.id === 'primary' || state.panels.length === 1} onClick={() => setState(s => closePanel(s, p.id))}>×</button></header>
          <div className="analytical-content" role="region" aria-label={p.kind === 'price' || p.kind === 'table' ? 'Price' : p.kind}>{p.kind === 'price' || p.kind === 'table' ? <PanelHost key={JSON.stringify(p.source)} name="PriceChart" component={PriceChart} params={{ source: p.source, canonicalContext: linked, archive: p.source.kind === 'primary' ? archive : null, onArchiveChange, onChooseSource: () => setEditor(p.id), renderer: p.renderer, controls: p.controls, reset: resets[p.id], panelId: p.id, registry, visible, table: p.kind === 'table' }}/> : <RecordedPanel renderer={p.renderer} kind={p.kind} runId={runId} panelId={p.id} registry={registry} controls={p.controls} reset={resets[p.id]}/>}</div>
        </section>
      })}
      {!state.maximized && (state.layout === 'side-by-side' || state.layout === 'grid') ? <WorkspaceSplitter axis="vertical" value={state.ratios[0]} onChange={v => setState(s => ({ ...s, ratios: [v, s.ratios[1]] }))}/> : null}
      {!state.maximized && (state.layout === 'stacked' || state.layout === 'grid') ? <WorkspaceSplitter axis="horizontal" value={state.ratios[1]} onChange={v => setState(s => ({ ...s, ratios: [s.ratios[0], v] }))}/> : null}
      {!state.maximized && state.layout === 'three-row' ? <><WorkspaceSplitter axis="horizontal" value={state.ratios[0]} onChange={v => setState(s => ({ ...s, ratios: [v, s.ratios[1]] }))}/><WorkspaceSplitter axis="horizontal" value={state.ratios[0] + (1 - state.ratios[0]) * state.ratios[1]} onChange={v => setState(s => ({ ...s, ratios: [s.ratios[0], Math.max(0.15, Math.min(0.85, (v - s.ratios[0]) / (1 - s.ratios[0])))] }))}/></> : null}
    </div>
    {nativePicker ? <div className="panel-source-editor" role="dialog" aria-label="Choose native timeframe source"><p>Select the exact venue and market. Native archive evidence is separate from a recorded strategy run.</p><ArchiveChartSelect initialQuery={nativePicker.instrument} initialTimeframe={nativePicker.interval} onClose={() => setNativePicker(null)} onSelect={dataset => { const selected = state.panels.find(p => p.id === nativePicker.panelId); if (selected?.source.kind === 'primary') onArchiveChange(dataset); else patchPanel(nativePicker.panelId, { source: { kind: 'archive', dataset } }); setNativePicker(null) }}/></div> : null}
    {editor ? <PanelSourceEditor onClose={() => setEditor(null)} onChange={source => patchPanel(editor, { source })}/> : null}
  </MarketDesk>
}

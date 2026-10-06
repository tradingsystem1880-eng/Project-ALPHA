/** Presentation only. A source is never inferred from another panel's context. */
import type { ArchiveChartDataset } from '../api/client'
import type { ChartControls } from '../context/chartControls'
export type PanelSource = { kind: 'primary' } | { kind: 'market'; symbol: string; start: string | null; end: string | null; snapshotId: string | null } | { kind: 'archive'; dataset: ArchiveChartDataset } | { kind: 'run'; runId: string }
export const PANEL_KINDS = ['price', 'table', 'equity', 'drawdown', 'sharpe', 'volatility', 'benchmark', 'exposure', 'turnover', 'diagnostics', 'correlation', 'figures'] as const
export type PanelKind = typeof PANEL_KINDS[number]
export const LAYOUTS = ['single', 'side-by-side', 'stacked', 'three-row', 'grid'] as const
export type WorkspaceLayout = typeof LAYOUTS[number]
export const DEFAULT_CONTROLS: ChartControls = { type: 'candles', crosshair: true, grid: true, zoom: 0 }
export type PlotRenderer = 'scientific' | 'market'
export interface AnalyticalPanel { renderer: PlotRenderer; id: string; kind: PanelKind; source: PanelSource; controls: ChartControls }
export interface ChartWorkspaceState { version: 1; panels: AnalyticalPanel[]; active: string; layout: WorkspaceLayout; ratios: [number, number]; maximized: string | null; linkRange: boolean; linkCursor: boolean }
export function panel(id: string, source: PanelSource = { kind: 'primary' }, kind: PanelKind = 'price'): AnalyticalPanel { return { id, source, kind, renderer: 'scientific', controls: { ...DEFAULT_CONTROLS } } }
function sourceOf(value: unknown): PanelSource | null {
  if (!value || typeof value !== 'object') return null
  const v = value as Record<string, unknown>
  if (v.kind === 'primary') return { kind: 'primary' }
  if (v.kind === 'run' && typeof v.runId === 'string' && /^[a-f0-9]{16}$/.test(v.runId)) return { kind: 'run', runId: v.runId }
  if (v.kind === 'market' && typeof v.symbol === 'string' && v.symbol.length > 0 && v.symbol.length < 100) return { kind: 'market', symbol: v.symbol, start: typeof v.start === 'string' ? v.start : null, end: typeof v.end === 'string' ? v.end : null, snapshotId: typeof v.snapshotId === 'string' ? v.snapshotId : null }
  if (v.kind === 'archive' && v.dataset && typeof v.dataset === 'object') {
    const d = v.dataset as ArchiveChartDataset
    if (typeof d.manifest_id === 'string' && /^[a-f0-9]{64}$/.test(d.manifest_id) && [d.instrument, d.frequency, d.venue, d.market_type].every(x => typeof x === 'string' && x.length > 0)) return { kind: 'archive', dataset: d }
  }
  return null
}
export function restoreWorkspace(raw: unknown, comparisons: string[] = []): ChartWorkspaceState {
  const v = raw && typeof raw === 'object' ? raw as Partial<ChartWorkspaceState> : {}
  const panels: AnalyticalPanel[] = [panel('primary'), ...comparisons.slice(0, 3).map((symbol, i) => panel(`migrated-${i}`, { kind: 'market', symbol, start: null, end: null, snapshotId: null }))]
  if (Array.isArray(v.panels)) {
    const valid: AnalyticalPanel[] = []
    for (const p of v.panels.slice(0, 4)) {
      const source = sourceOf(p?.source)
      if (source?.kind === 'primary' && p?.id !== 'primary') continue
      if (!p || typeof p.id !== 'string' || !/^[\w-]{1,80}$/.test(p.id) || valid.some(x => x.id === p.id) || !source || !PANEL_KINDS.includes(p.kind)) continue
      const c = p.controls
      valid.push({ ...panel(p.id, source, p.kind), renderer: p.renderer === 'market' ? 'market' : 'scientific', controls: { type: ['candles', 'bars', 'line'].includes(c?.type) ? c.type : 'candles', grid: typeof c?.grid === 'boolean' ? c.grid : true, crosshair: typeof c?.crosshair === 'boolean' ? c.crosshair : true, zoom: Number.isFinite(c?.zoom) ? Math.max(-6, Math.min(6, c.zoom)) : 0 } })
    }
    if (valid.length) {
      const primary = valid.find(p => p.id === 'primary') ?? panel('primary')
      panels.splice(0, panels.length, primary, ...valid.filter(p => p.id !== 'primary').slice(0, 3))
    }
  }
  const has = (id: unknown): id is string => typeof id === 'string' && panels.some(p => p.id === id)
  return { version: 1, panels, active: has(v.active) ? v.active : panels[0].id, layout: LAYOUTS.includes(v.layout!) ? v.layout! : panels.length > 1 ? 'grid' : 'single', ratios: [0, 1].map(i => typeof v.ratios?.[i] === 'number' && Number.isFinite(v.ratios[i]) && v.ratios[i] >= 0.15 && v.ratios[i] <= 0.85 ? v.ratios[i] : 0.5) as [number, number], maximized: has(v.maximized) ? v.maximized : null, linkRange: v.linkRange === true, linkCursor: v.linkCursor === true }
}
export function setLayout(state: ChartWorkspaceState, layout: WorkspaceLayout): ChartWorkspaceState { return { ...state, layout } }
export function duplicatePanel(state: ChartWorkspaceState, id: string, source?: PanelSource): ChartWorkspaceState {
  const p = state.panels.find(x => x.id === id)
  if (!p || state.panels.length >= 4) return state
  let n = 1; while (state.panels.some(x => x.id === `panel-${n}`)) n++
  const next = { ...p, id: `panel-${n}`, source: source ?? structuredClone(p.source), controls: { ...p.controls } }
  return { ...state, panels: [...state.panels, next], active: next.id, layout: state.panels.length === 1 ? 'side-by-side' : 'grid' }
}
export function closePanel(state: ChartWorkspaceState, id: string): ChartWorkspaceState {
  if (id === 'primary' || state.panels.length === 1) return state
  const panels = state.panels.filter(p => p.id !== id)
  return { ...state, panels, active: state.active === id ? panels[0].id : state.active, maximized: state.maximized === id ? null : state.maximized }
}

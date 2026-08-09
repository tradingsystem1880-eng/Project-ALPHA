// Curated workspaces are built through Dockview's public API rather than serialized internal JSON.
// Users can switch presets, rearrange every panel, and save their own workspace independently.

import type { DockviewApi } from 'dockview-react'

export const LAYOUT_KEY = 'alpha.layout.v3'
export const LEGACY_LAYOUT_KEYS = ['alpha.layout.v2', 'alpha.layout'] as const

/**
 * Component ids present in repository-backed v2 layouts. They intentionally map to themselves:
 * v3 retained every historical id. If a component is renamed later, keep its old key here and
 * change only the value to the new registry id so persisted layouts remain migratable.
 */
export const V2_PANEL_COMPONENT_ALIASES: Readonly<Record<string, string>> = {
  ActivityFeed: 'ActivityFeed',
  AiConsole: 'AiConsole',
  DataExplorer: 'DataExplorer',
  Glossary: 'Glossary',
  JobMonitor: 'JobMonitor',
  OptionsGreeks: 'OptionsGreeks',
  PaperMonitor: 'PaperMonitor',
  Pipeline: 'Pipeline',
  PriceChart: 'PriceChart',
  ProviderSystem: 'ProviderSystem',
  RiskMonitor: 'RiskMonitor',
  RunBrowser: 'RunBrowser',
  RunDetail: 'RunDetail',
  Screener: 'Screener',
  StrategyLab: 'StrategyLab',
  Workspaces: 'Workspaces',
}

export type WorkspacePresetId =
  | 'research'
  | 'market'
  | 'development'
  | 'kronos'
  | 'ml'
  | 'portfolio'
  | 'operations'

interface PresetPanel {
  key: string
  component: string
  title: string
  anchor?: string
  direction?: 'above' | 'below' | 'left' | 'right' | 'within'
  initialWidth?: number
  initialHeight?: number
  inactive?: boolean
  params?: Record<string, unknown>
}

export interface WorkspacePreset {
  id: WorkspacePresetId
  name: string
  shortName: string
  requiredComponents: string[]
  panels: PresetPanel[]
}

export const WORKSPACE_PRESETS: WorkspacePreset[] = [
  {
    // Spec §2.1: the Research Command Center is the research-first front door.
    id: 'research',
    name: 'Research Command Center',
    shortName: 'RESEARCH',
    requiredComponents: ['ResearchBacklog', 'ResearchCockpit', 'EvidenceHub', 'CodexBench'],
    panels: [
      { key: 'cockpit', component: 'ResearchCockpit', title: 'Research Cockpit' },
      { key: 'backlog', component: 'ResearchBacklog', title: 'Research Backlog', anchor: 'cockpit', direction: 'left', initialWidth: 300 },
      { key: 'codex', component: 'CodexBench', title: 'Codex Bench', anchor: 'cockpit', direction: 'right', initialWidth: 420 },
      { key: 'hub', component: 'EvidenceHub', title: 'Evidence Hub', anchor: 'cockpit', direction: 'below', initialHeight: 320 },
      { key: 'chart', component: 'PriceChart', title: 'Asset Chart', anchor: 'backlog', direction: 'within', inactive: true },
      { key: 'runs', component: 'RunBrowser', title: 'Runs', anchor: 'backlog', direction: 'within', inactive: true },
      { key: 'jobs', component: 'JobMonitor', title: 'Jobs', anchor: 'hub', direction: 'within', inactive: true },
    ],
  },
  {
    id: 'market',
    name: 'Market Desk',
    shortName: 'MARKET',
    requiredComponents: ['PriceChart', 'DataExplorer', 'Screener', 'NativeTearSheet', 'AssetMemory'],
    panels: [
      { key: 'price', component: 'PriceChart', title: 'Market Chart' },
      { key: 'symbols', component: 'DataExplorer', title: 'Universe', anchor: 'price', direction: 'left', initialWidth: 250 },
      { key: 'screener', component: 'Screener', title: 'Market Data', anchor: 'symbols', direction: 'within', inactive: true },
      { key: 'tearsheet', component: 'NativeTearSheet', title: 'Quant Tear Sheet', anchor: 'price', direction: 'right', initialWidth: 430 },
      { key: 'memory', component: 'AssetMemory', title: 'Asset Memory', anchor: 'tearsheet', direction: 'within', inactive: true },
      { key: 'runs', component: 'RunBrowser', title: 'Runs', anchor: 'tearsheet', direction: 'within', inactive: true },
      { key: 'paper', component: 'PaperMonitor', title: 'Sandbox Blotter', anchor: 'price', direction: 'below', initialHeight: 245 },
      { key: 'activity', component: 'ActivityFeed', title: 'Activity', anchor: 'paper', direction: 'within', inactive: true },
      { key: 'jobs', component: 'JobMonitor', title: 'Jobs', anchor: 'paper', direction: 'within', inactive: true },
    ],
  },
  {
    id: 'development',
    name: 'Development Center',
    shortName: 'DEVELOP',
    requiredComponents: ['DevelopmentCenter', 'Pipeline', 'StrategyLab', 'NativeTearSheet', 'AssetMemory'],
    panels: [
      { key: 'center', component: 'DevelopmentCenter', title: 'Development Center' },
      { key: 'runs', component: 'RunBrowser', title: 'Experiment Runs', anchor: 'center', direction: 'left', initialWidth: 330 },
      { key: 'chart', component: 'PriceChart', title: 'Evidence Chart', anchor: 'center', direction: 'within', inactive: true },
      { key: 'pipeline', component: 'Pipeline', title: 'Validation Workflow', anchor: 'center', direction: 'below', initialHeight: 275 },
      { key: 'lab', component: 'StrategyLab', title: 'Run Configuration', anchor: 'center', direction: 'right', initialWidth: 420 },
      { key: 'tear', component: 'NativeTearSheet', title: 'Evidence', anchor: 'lab', direction: 'within', inactive: true },
      { key: 'memory', component: 'AssetMemory', title: 'Asset Memory', anchor: 'runs', direction: 'within', inactive: true },
      { key: 'jobs', component: 'JobMonitor', title: 'Jobs', anchor: 'lab', direction: 'below', initialHeight: 230 },
    ],
  },
  {
    id: 'kronos',
    name: 'Kronos Forecast Studio',
    shortName: 'KRONOS',
    requiredComponents: ['KronosStudio', 'RunBrowser'],
    panels: [
      { key: 'forecast', component: 'KronosStudio', title: 'Kronos Forecast Studio' },
      { key: 'runs', component: 'RunBrowser', title: 'Forecast Runs', anchor: 'forecast', direction: 'left', initialWidth: 320, params: { defaultKind: 'forecast' } },
      { key: 'detail', component: 'RunDetail', title: 'Run Evidence', anchor: 'forecast', direction: 'right', initialWidth: 460, inactive: true, params: { runScope: 'forecast' } },
      { key: 'tear', component: 'NativeTearSheet', title: 'Quant Tear Sheet', anchor: 'detail', direction: 'within', inactive: true, params: { runScope: 'forecast' } },
      { key: 'jobs', component: 'JobMonitor', title: 'Forecast Jobs', anchor: 'forecast', direction: 'below', initialHeight: 230 },
      { key: 'system', component: 'ProviderSystem', title: 'Model Readiness', anchor: 'jobs', direction: 'within', inactive: true },
    ],
  },
  {
    id: 'ml',
    name: 'ML Research',
    shortName: 'ML LAB',
    requiredComponents: ['MlDiagnostics', 'MlResearch', 'RunBrowser', 'NativeTearSheet', 'AssetMemory'],
    panels: [
      { key: 'diagnostics', component: 'MlDiagnostics', title: 'ML Signal Tear Sheet' },
      { key: 'ml', component: 'MlResearch', title: 'ML Control', anchor: 'diagnostics', direction: 'left', initialWidth: 360 },
      { key: 'runs', component: 'RunBrowser', title: 'Research Runs', anchor: 'ml', direction: 'within', inactive: true, params: { defaultKind: 'runs', defaultCommand: 'ml_replay' } },
      { key: 'agent', component: 'AiConsole', title: 'Agent Research', anchor: 'ml', direction: 'within', inactive: true },
      { key: 'memory', component: 'AssetMemory', title: 'Asset Memory', anchor: 'ml', direction: 'within', inactive: true },
      { key: 'lab', component: 'StrategyLab', title: 'Experiment Configuration', anchor: 'diagnostics', direction: 'right', initialWidth: 390 },
      { key: 'tear', component: 'NativeTearSheet', title: 'Canonical Replay Tear Sheet', anchor: 'diagnostics', direction: 'below', initialHeight: 310, params: { runScope: 'ml-replay' } },
      { key: 'jobs', component: 'JobMonitor', title: 'Training Jobs', anchor: 'lab', direction: 'below', initialHeight: 230 },
    ],
  },
  {
    id: 'portfolio',
    name: 'Portfolio & Risk',
    shortName: 'PORTFOLIO',
    requiredComponents: ['RunBrowser', 'RunDetail', 'RiskMonitor', 'NativeTearSheet'],
    panels: [
      { key: 'detail', component: 'RunDetail', title: 'Portfolio Evidence', params: { runScope: 'portfolio' } },
      { key: 'runs', component: 'RunBrowser', title: 'Portfolio Runs', anchor: 'detail', direction: 'left', initialWidth: 330, params: { allowedKinds: ['portfolio', 'cross_sectional'] } },
      { key: 'risk', component: 'RiskMonitor', title: 'Scenario Risk', anchor: 'detail', direction: 'right', initialWidth: 390, params: { runScope: 'portfolio' } },
      { key: 'tear', component: 'NativeTearSheet', title: 'Quant Tear Sheet', anchor: 'detail', direction: 'below', initialHeight: 320, params: { runScope: 'portfolio' } },
      { key: 'chart', component: 'PriceChart', title: 'Asset Chart', anchor: 'risk', direction: 'within', inactive: true },
    ],
  },
  {
    id: 'operations',
    name: 'Operations',
    shortName: 'OPS',
    requiredComponents: ['ProviderSystem', 'PaperMonitor', 'JobMonitor', 'ActivityFeed'],
    panels: [
      { key: 'system', component: 'ProviderSystem', title: 'Providers & System' },
      { key: 'workspaces', component: 'Workspaces', title: 'Saved Workspaces', anchor: 'system', direction: 'within', inactive: true },
      { key: 'paper', component: 'PaperMonitor', title: 'Sandbox Sessions', anchor: 'system', direction: 'right', initialWidth: 650 },
      { key: 'activity', component: 'ActivityFeed', title: 'Activity Tape', anchor: 'system', direction: 'below', initialHeight: 260 },
      { key: 'runs', component: 'RunBrowser', title: 'Run Store', anchor: 'activity', direction: 'within', inactive: true },
      { key: 'jobs', component: 'JobMonitor', title: 'Jobs & Logs', anchor: 'paper', direction: 'below', initialHeight: 260 },
    ],
  },
]

export function getWorkspacePreset(id: WorkspacePresetId): WorkspacePreset {
  const preset = WORKSPACE_PRESETS.find((candidate) => candidate.id === id)
  if (!preset) throw new Error(`unknown workspace preset: ${id}`)
  return preset
}

export function buildWorkspaceLayout(api: DockviewApi, id: WorkspacePresetId): void {
  const preset = getWorkspacePreset(id)
  const added = new Map<string, string>()
  api.clear()

  for (const panel of preset.panels) {
    const referencePanel = panel.anchor ? added.get(panel.anchor) : undefined
    if (panel.anchor && !referencePanel) {
      throw new Error(`preset ${id}: missing anchor ${panel.anchor}`)
    }
    const created = api.addPanel({
      id: `v3-${id}-${panel.key}`,
      component: panel.component,
      title: panel.title,
      params: panel.params,
      inactive: panel.inactive,
      initialWidth: panel.initialWidth,
      initialHeight: panel.initialHeight,
      ...(referencePanel
        ? { position: { referencePanel, direction: panel.direction ?? 'right' } }
        : {}),
    })
    added.set(panel.key, created.id)
  }
  api.panels[0]?.api.setActive()
}

export function buildDeskLayout(api: DockviewApi): void {
  buildWorkspaceLayout(api, 'market')
}

interface LayoutStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

type JsonRecord = Record<string, unknown>

function isRecord(value: unknown): value is JsonRecord {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

/** Canonicalize a real Dockview v2 document atomically; unknown panels reject the whole layout. */
export function migrateV2Layout(value: unknown): JsonRecord | null {
  if (!isRecord(value) || !isRecord(value.grid) || !isRecord(value.panels)) return null
  const grid = value.grid
  if (
    !isRecord(grid.root) ||
    typeof grid.width !== 'number' ||
    typeof grid.height !== 'number' ||
    (grid.orientation !== 'HORIZONTAL' && grid.orientation !== 'VERTICAL')
  ) {
    return null
  }
  const entries = Object.entries(value.panels)
  if (entries.length === 0) return null
  const panels: JsonRecord = {}
  for (const [panelId, rawPanel] of entries) {
    if (
      !isRecord(rawPanel) ||
      rawPanel.id !== panelId ||
      typeof rawPanel.contentComponent !== 'string'
    ) {
      return null
    }
    if (!Object.hasOwn(V2_PANEL_COMPONENT_ALIASES, rawPanel.contentComponent)) return null
    const canonical = V2_PANEL_COMPONENT_ALIASES[rawPanel.contentComponent]
    if (!canonical) return null
    panels[panelId] = { ...rawPanel, contentComponent: canonical }
  }
  return { ...value, panels }
}

/** Restore v3 first, then migrate v2/v1 without deleting or rewriting either legacy key. */
export function restoreStoredLayout(api: DockviewApi, storage: LayoutStorage): boolean {
  for (const key of [LAYOUT_KEY, ...LEGACY_LAYOUT_KEYS]) {
    const saved = storage.getItem(key)
    if (!saved) continue
    try {
      const parsed: unknown = JSON.parse(saved)
      const layout = key === LAYOUT_KEY ? parsed : migrateV2Layout(parsed)
      if (layout === null) continue
      api.fromJSON(layout as never)
      if (api.panels.length === 0) {
        api.clear()
        continue
      }
      if (key !== LAYOUT_KEY) storage.setItem(LAYOUT_KEY, JSON.stringify(layout))
      return true
    } catch {
      api.clear()
    }
  }
  return false
}

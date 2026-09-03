/**
 * Document and dock registries (spec 2026-09-01 §4.2, Approach A).
 *
 * The six fixed screens became two declarative registries: DOCUMENTS lists every window a
 * profile may open in the MDI area (one entry per `WindowId`, so a profile manifest can never name
 * a window that does not exist), and DOCKS lists the four docked panels around it. A document
 * holds one or more panes; panes sharing a document become tabs inside it. The shell mounts only
 * the active document, so no hidden document keeps polling behind a tab. Which documents a profile
 * shows is the manifest's decision (`profiles.ts`), never this file's.
 */

import type { FunctionComponent } from 'react'

import type { PanelHandleProps } from '../context/panelHandle'
import { ActivityFeed } from '../panels/ActivityFeed'
import { AiConsole } from '../panels/AiConsole'
import { CodexBench } from '../panels/CodexBench'
import { CompareRuns } from '../panels/CompareRuns'
import { DataManager } from '../panels/DataManager'
import { EvidenceHub } from '../panels/EvidenceHub'
import { GovernanceDocument } from '../panels/Governance'
import { JobMonitor } from '../panels/JobMonitor'
import { KronosStudio } from '../panels/KronosStudio'
import { MlDiagnostics } from '../panels/MlDiagnostics'
import { OptionsGreeks } from '../panels/OptionsGreeks'
import { PaperMonitor } from '../panels/PaperMonitor'
import { Pipeline } from '../panels/Pipeline'
import { PriceChart } from '../panels/PriceChart'
import { ProviderSystem } from '../panels/ProviderSystem'
import { ResearchBacklog } from '../panels/ResearchBacklog'
import { ResearchCockpit } from '../panels/ResearchCockpit'
import { ResearchDataExplorer } from '../panels/ResearchDataExplorer'
import { RiskMonitor } from '../panels/RiskMonitor'
import { Screener } from '../panels/Screener'
import { StrategyLab } from '../panels/StrategyLab'
import { AssetMemory, DevelopmentCenter, MlResearch } from '../panels/V3Workbenches'
import { RunDetail } from '../panels/rundetail'
import type { DockId, WindowId } from './profiles'

export type DocumentKind =
  | 'chart'
  | 'report'
  | 'compare'
  | 'build'
  | 'research'
  | 'governance'
  | 'forecast'
  | 'ml'
  | 'jobs'
  | 'paper'
  | 'data'
  | 'tools'

export const DOCUMENT_KINDS: readonly DocumentKind[] = Object.freeze([
  'chart',
  'report',
  'compare',
  'build',
  'research',
  'governance',
  'forecast',
  'ml',
  'jobs',
  'paper',
  'data',
  'tools',
])

export interface DocumentPane {
  name: string
  title: string
  component: FunctionComponent<PanelHandleProps>
  params?: Record<string, unknown>
  /** `side` panes render in a narrower column beside the main panes; default `main`. */
  area?: 'main' | 'side'
}

export interface DocumentDefinition {
  id: WindowId
  kind: DocumentKind
  /** MDI tab and title-bar text. */
  title: string
  /** Panes in declaration order; more than one becomes tabs inside the document. */
  panes: readonly DocumentPane[]
}

export const DOCUMENTS: readonly DocumentDefinition[] = [
  {
    id: 'chart',
    kind: 'chart',
    title: 'Chart',
    panes: [{ name: 'PriceChart', title: 'Price', component: PriceChart }],
  },
  {
    id: 'report',
    kind: 'report',
    title: 'Strategy Performance Report',
    panes: [{ name: 'RunDetail', title: 'Report', component: RunDetail }],
  },
  {
    id: 'compare',
    kind: 'compare',
    title: 'Compare',
    panes: [{ name: 'CompareRuns', title: 'Compare', component: CompareRuns }],
  },
  {
    id: 'build',
    kind: 'build',
    title: 'Build',
    panes: [
      { name: 'StrategyLab', title: 'Strategy Development', component: StrategyLab },
      { name: 'DevelopmentCenter', title: 'Development Center', component: DevelopmentCenter },
      { name: 'Pipeline', title: 'Development Next Step', component: Pipeline, area: 'side' },
      { name: 'AiConsole', title: 'Standalone Sandbox', component: AiConsole, area: 'side' },
    ],
  },
  {
    id: 'research',
    kind: 'research',
    title: 'Research',
    panes: [
      { name: 'ResearchCockpit', title: 'Research Case', component: ResearchCockpit },
      { name: 'EvidenceHub', title: 'Evidence', component: EvidenceHub },
      { name: 'ResearchBacklog', title: 'Backlog', component: ResearchBacklog, area: 'side' },
      {
        name: 'Literature',
        title: 'Literature',
        component: EvidenceHub,
        params: { initialSection: 'literature', compactLiterature: true },
        area: 'side',
      },
      { name: 'CodexBench', title: 'Codex Research', component: CodexBench, area: 'side' },
    ],
  },
  {
    id: 'governance',
    kind: 'governance',
    title: 'Governance',
    panes: [{ name: 'Governance', title: 'Governance', component: GovernanceDocument }],
  },
  {
    id: 'forecast',
    kind: 'forecast',
    title: 'Forecast',
    panes: [{ name: 'KronosStudio', title: 'Forecast', component: KronosStudio }],
  },
  {
    id: 'ml-lab',
    kind: 'ml',
    title: 'Machine learning',
    panes: [
      { name: 'MlResearch', title: 'ML lab', component: MlResearch },
      { name: 'MlDiagnostics', title: 'ML diagnostics', component: MlDiagnostics },
      { name: 'RiskMonitor', title: 'Risk', component: RiskMonitor },
      { name: 'AssetMemory', title: 'Findings', component: AssetMemory, area: 'side' },
    ],
  },
  {
    id: 'jobs',
    kind: 'jobs',
    title: 'Jobs & providers',
    panes: [
      { name: 'JobMonitor', title: 'Jobs', component: JobMonitor },
      { name: 'ProviderSystem', title: 'Providers & system', component: ProviderSystem },
      { name: 'ActivityFeed', title: 'Activity', component: ActivityFeed, area: 'side' },
    ],
  },
  {
    id: 'paper',
    kind: 'paper',
    title: 'Paper sessions',
    panes: [{ name: 'PaperMonitor', title: 'Paper sessions', component: PaperMonitor }],
  },
  // Equities-only windows.
  {
    id: 'options',
    kind: 'tools',
    title: 'Options Calculator',
    panes: [{ name: 'OptionsGreeks', title: 'Options Calculator', component: OptionsGreeks }],
  },
  {
    id: 'screener',
    kind: 'tools',
    title: 'Market Overview',
    panes: [{ name: 'Screener', title: 'Market Overview', component: Screener }],
  },
  {
    // Split/dividend actions arrive with a Tiingo pull; the Data Manager is where they are pulled
    // and where the stored history that carries them is listed.
    id: 'corporate-actions',
    kind: 'data',
    title: 'Corporate actions',
    panes: [{ name: 'DataManager', title: 'Data Manager', component: DataManager }],
  },
  // Crypto-only windows: each opens the governed Crypto Data Center on its own section.
  {
    id: 'funding',
    kind: 'data',
    title: 'Funding',
    panes: [
      {
        name: 'FundingData',
        title: 'Funding',
        component: ResearchDataExplorer,
        params: { initialSection: 'derivatives', initialFamily: 'funding' },
      },
    ],
  },
  {
    id: 'open-interest',
    kind: 'data',
    title: 'Open interest',
    panes: [
      {
        name: 'OpenInterestData',
        title: 'Open interest',
        component: ResearchDataExplorer,
        params: { initialSection: 'derivatives', initialFamily: 'open_interest' },
      },
    ],
  },
  {
    id: 'onchain',
    kind: 'data',
    title: 'On-chain metrics',
    panes: [
      {
        name: 'OnchainData',
        title: 'On-chain metrics',
        component: ResearchDataExplorer,
        params: { initialSection: 'onchain', initialFamily: 'onchain_metrics' },
      },
    ],
  },
  {
    id: 'dex',
    kind: 'data',
    title: 'DEX pools',
    panes: [
      {
        name: 'DexData',
        title: 'DEX pools',
        component: ResearchDataExplorer,
        params: { initialSection: 'dex', initialFamily: 'dex_pools' },
      },
    ],
  },
  {
    // The registered BTCUSDT crowding question (ADR-0033) is a research case; the cockpit's
    // Bybit crowding lane is where it is captured and read.
    id: 'crowding',
    kind: 'research',
    title: 'Crypto crowding',
    panes: [{ name: 'CrowdingCase', title: 'Crypto crowding', component: ResearchCockpit }],
  },
]

/** The document a run browser row, the Navigator and a `#run=` deep link open. */
export const REPORT_DOCUMENT: WindowId = 'report'

export function documentOf(id: WindowId): DocumentDefinition {
  const found = DOCUMENTS.find((item) => item.id === id)
  if (!found) throw new Error(`unknown document ${String(id)}`)
  return found
}

export type DockSide = 'left' | 'right' | 'bottom'

export interface DockDefinition {
  id: DockId
  side: DockSide
  title: string
  /** Tab labels inside the dock, in order; empty when the dock is one panel. */
  tabs: readonly string[]
}

export const DOCKS: readonly DockDefinition[] = [
  { id: 'MarketWatch', side: 'left', title: 'Market Watch', tabs: ['Symbols', 'Details', 'Data'] },
  { id: 'Navigator', side: 'left', title: 'Navigator', tabs: [] },
  { id: 'DataManager', side: 'right', title: 'Data Manager', tabs: [] },
  {
    id: 'Toolbox',
    side: 'bottom',
    title: 'Toolbox',
    tabs: ['Jobs', 'Trades', 'Backtests', 'Data pulls', 'Log'],
  },
]

export function dockOf(id: DockId): DockDefinition {
  const found = DOCKS.find((item) => item.id === id)
  if (!found) throw new Error(`unknown dock ${String(id)}`)
  return found
}

/** Main and side panes in declaration order; a document with no side panes is one column. */
export function panesByArea(definition: DocumentDefinition): {
  main: DocumentPane[]
  side: DocumentPane[]
} {
  return {
    main: definition.panes.filter((pane) => (pane.area ?? 'main') === 'main'),
    side: definition.panes.filter((pane) => pane.area === 'side'),
  }
}

// The panel registry: the shell instantiates a Dockview panel by its component id, and the command
// palette lists what can be opened. New panels (later modules) register here with no shell change.

import type { IDockviewPanelProps } from 'dockview-react'
import type { FunctionComponent } from 'react'

import { ActivityFeed } from './ActivityFeed'
import { AiConsole } from './AiConsole'
import { DataExplorer } from './DataExplorer'
import { EvidenceHub } from './EvidenceHub'
import { Glossary } from './Glossary'
import { JobMonitor } from './JobMonitor'
import { KronosStudio } from './KronosStudio'
import { MlDiagnostics } from './MlDiagnostics'
import { NativeTearSheet } from './NativeTearSheet'
import { OptionsGreeks } from './OptionsGreeks'
import { PaperMonitor } from './PaperMonitor'
import { Pipeline } from './Pipeline'
import { PriceChart } from './PriceChart'
import { ProviderSystem } from './ProviderSystem'
import { ResearchBacklog } from './ResearchBacklog'
import { ResearchCockpit } from './ResearchCockpit'
import { RiskMonitor } from './RiskMonitor'
import { RunBrowser } from './RunBrowser'
import { Screener } from './Screener'
import { RunDetail } from './rundetail'
import { StrategyLab } from './StrategyLab'
import { AssetMemory, DevelopmentCenter, MlResearch } from './V3Workbenches'
import { Workspaces } from './Workspaces'
import { guarded } from './guarded'

export interface PanelMenuItem {
  component: string
  title: string
  hint?: string
}

const RAW_PANELS: Record<string, FunctionComponent<IDockviewPanelProps>> = {
  RunBrowser,
  RunDetail,
  ActivityFeed,
  JobMonitor,
  KronosStudio,
  MlDiagnostics,
  Pipeline,
  PaperMonitor,
  StrategyLab,
  PriceChart,
  DataExplorer,
  OptionsGreeks,
  RiskMonitor,
  Screener,
  ProviderSystem,
  ResearchBacklog,
  ResearchCockpit,
  EvidenceHub,
  Workspaces,
  AiConsole,
  Glossary,
  NativeTearSheet,
  DevelopmentCenter,
  MlResearch,
  AssetMemory,
}

export const PANELS: Record<string, FunctionComponent<IDockviewPanelProps>> = Object.fromEntries(
  Object.entries(RAW_PANELS).map(([name, Panel]) => [name, guarded(name, Panel)]),
)

// Panels openable from the ⌘K palette (Run Detail is opened from a run row, so it's not listed).
export const PANEL_MENU: PanelMenuItem[] = [
  { component: 'RunBrowser', title: 'Run Browser', hint: 'runs' },
  { component: 'ActivityFeed', title: 'Activity', hint: 'live desk tape' },
  { component: 'JobMonitor', title: 'Jobs', hint: 'consoles·cancel' },
  { component: 'Pipeline', title: 'Pipeline', hint: 'the loop·next steps' },
  { component: 'PaperMonitor', title: 'Paper Monitor', hint: 'sandbox·orders·positions' },
  { component: 'StrategyLab', title: 'Strategy Lab', hint: 'launch' },
  { component: 'PriceChart', title: 'Price', hint: 'candles' },
  { component: 'DataExplorer', title: 'Data Explorer', hint: 'symbols' },
  { component: 'OptionsGreeks', title: 'Options', hint: 'greeks' },
  { component: 'RiskMonitor', title: 'Risk', hint: 'scenarios' },
  { component: 'Screener', title: 'Screener', hint: 'quote·news' },
  { component: 'ProviderSystem', title: 'Providers & System', hint: 'readiness·configuration' },
  { component: 'AiConsole', title: 'AI Research', hint: 'compare·console' },
  { component: 'Workspaces', title: 'Workspaces', hint: 'layouts' },
  { component: 'Glossary', title: 'Glossary', hint: 'metric definitions' },
  { component: 'NativeTearSheet', title: 'Quant Tear Sheet', hint: 'native·artifact only' },
  { component: 'KronosStudio', title: 'Kronos Forecast Studio', hint: 'OHLCV paths·calibration' },
  { component: 'DevelopmentCenter', title: 'Development Center', hint: 'projects·stages' },
  { component: 'ResearchBacklog', title: 'Research Backlog', hint: 'every case·buckets' },
  { component: 'ResearchCockpit', title: 'Research Cockpit', hint: 'thesis·protocol·D0 pilot' },
  { component: 'EvidenceHub', title: 'Evidence Hub', hint: 'for·against·falsification' },
  { component: 'MlResearch', title: 'ML Research', hint: 'Qlib·OOS signals' },
  { component: 'MlDiagnostics', title: 'ML Signal Tear Sheet', hint: 'IC·folds·LightGBM provenance' },
  { component: 'AssetMemory', title: 'Asset Memory', hint: 'cited findings·negative results' },
]

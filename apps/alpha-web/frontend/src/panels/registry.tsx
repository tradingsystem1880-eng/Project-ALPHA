// The panel registry: the shell instantiates a Dockview panel by its component id, and the command
// palette lists what can be opened. New panels (later modules) register here with no shell change.

import type { IDockviewPanelProps } from 'dockview-react'
import type { FunctionComponent } from 'react'

import { AiConsole } from './AiConsole'
import { DataExplorer } from './DataExplorer'
import { OptionsGreeks } from './OptionsGreeks'
import { PriceChart } from './PriceChart'
import { RiskMonitor } from './RiskMonitor'
import { RunBrowser } from './RunBrowser'
import { Screener } from './Screener'
import { RunDetail } from './RunDetail'
import { StrategyLab } from './StrategyLab'
import { Workspaces } from './Workspaces'

export interface PanelMenuItem {
  component: string
  title: string
  hint?: string
}

export const PANELS: Record<string, FunctionComponent<IDockviewPanelProps>> = {
  RunBrowser,
  RunDetail,
  StrategyLab,
  PriceChart,
  DataExplorer,
  OptionsGreeks,
  RiskMonitor,
  Screener,
  Workspaces,
  AiConsole,
}

// Panels openable from the ⌘K palette (Run Detail is opened from a run row, so it's not listed).
export const PANEL_MENU: PanelMenuItem[] = [
  { component: 'RunBrowser', title: 'Run Browser', hint: 'runs' },
  { component: 'StrategyLab', title: 'Strategy Lab', hint: 'launch' },
  { component: 'PriceChart', title: 'Price', hint: 'candles' },
  { component: 'DataExplorer', title: 'Data Explorer', hint: 'symbols' },
  { component: 'OptionsGreeks', title: 'Options', hint: 'greeks' },
  { component: 'RiskMonitor', title: 'Risk', hint: 'scenarios' },
  { component: 'Screener', title: 'Screener', hint: 'quote·news' },
  { component: 'AiConsole', title: 'AI Research', hint: 'compare·console' },
  { component: 'Workspaces', title: 'Workspaces', hint: 'layouts' },
]

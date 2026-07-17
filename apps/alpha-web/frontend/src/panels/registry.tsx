// The panel registry: the shell instantiates a Dockview panel by its component id, and the command
// palette lists what can be opened. New panels (later modules) register here with no shell change.

import type { IDockviewPanelProps } from 'dockview-react'
import type { FunctionComponent } from 'react'

import { DataExplorer } from './DataExplorer'
import { PriceChart } from './PriceChart'
import { RunBrowser } from './RunBrowser'
import { RunDetail } from './RunDetail'
import { StrategyLab } from './StrategyLab'

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
}

// Panels openable from the ⌘K palette (Run Detail is opened from a run row, so it's not listed).
export const PANEL_MENU: PanelMenuItem[] = [
  { component: 'RunBrowser', title: 'Run Browser', hint: 'runs' },
  { component: 'StrategyLab', title: 'Strategy Lab', hint: 'launch' },
  { component: 'PriceChart', title: 'Price', hint: 'candles' },
  { component: 'DataExplorer', title: 'Data Explorer', hint: 'symbols' },
]

// The panel registry: the shell instantiates a Dockview panel by its component id, and the command
// palette lists what can be opened. New panels (later modules) register here with no shell change.

import type { IDockviewPanelProps } from 'dockview-react'
import type { FunctionComponent } from 'react'

import { ErrorBoundary } from '../components/ErrorBoundary'
import { ActivityFeed } from './ActivityFeed'
import { AiConsole } from './AiConsole'
import { DataExplorer } from './DataExplorer'
import { JobMonitor } from './JobMonitor'
import { Glossary } from './Glossary'
import { OptionsGreeks } from './OptionsGreeks'
import { PriceChart } from './PriceChart'
import { RiskMonitor } from './RiskMonitor'
import { RunBrowser } from './RunBrowser'
import { Screener } from './Screener'
import { RunDetail } from './rundetail'
import { StrategyLab } from './StrategyLab'
import { Workspaces } from './Workspaces'

export interface PanelMenuItem {
  component: string
  title: string
  hint?: string
}

// Every panel renders inside its own error boundary: Dockview mounts panels in separate React
// roots, so containment has to happen here — one crashed panel must never blank the desk.
function guarded(
  name: string,
  Panel: FunctionComponent<IDockviewPanelProps>,
): FunctionComponent<IDockviewPanelProps> {
  const Guarded: FunctionComponent<IDockviewPanelProps> = (props) => (
    <ErrorBoundary panel={name}>
      <Panel {...props} />
    </ErrorBoundary>
  )
  Guarded.displayName = `Guarded(${name})`
  return Guarded
}

const RAW_PANELS: Record<string, FunctionComponent<IDockviewPanelProps>> = {
  RunBrowser,
  RunDetail,
  ActivityFeed,
  JobMonitor,
  StrategyLab,
  PriceChart,
  DataExplorer,
  OptionsGreeks,
  RiskMonitor,
  Screener,
  Workspaces,
  AiConsole,
  Glossary,
}

export const PANELS: Record<string, FunctionComponent<IDockviewPanelProps>> = Object.fromEntries(
  Object.entries(RAW_PANELS).map(([name, Panel]) => [name, guarded(name, Panel)]),
)

// Panels openable from the ⌘K palette (Run Detail is opened from a run row, so it's not listed).
export const PANEL_MENU: PanelMenuItem[] = [
  { component: 'RunBrowser', title: 'Run Browser', hint: 'runs' },
  { component: 'ActivityFeed', title: 'Activity', hint: 'live desk tape' },
  { component: 'JobMonitor', title: 'Jobs', hint: 'consoles·cancel' },
  { component: 'StrategyLab', title: 'Strategy Lab', hint: 'launch' },
  { component: 'PriceChart', title: 'Price', hint: 'candles' },
  { component: 'DataExplorer', title: 'Data Explorer', hint: 'symbols' },
  { component: 'OptionsGreeks', title: 'Options', hint: 'greeks' },
  { component: 'RiskMonitor', title: 'Risk', hint: 'scenarios' },
  { component: 'Screener', title: 'Screener', hint: 'quote·news' },
  { component: 'AiConsole', title: 'AI Research', hint: 'compare·console' },
  { component: 'Workspaces', title: 'Workspaces', hint: 'layouts' },
  { component: 'Glossary', title: 'Glossary', hint: 'metric definitions' },
]

// The panel registry: the shell instantiates a Dockview panel by its component id, and the command
// palette lists what can be opened. New panels (later modules) register here with no shell change.

import type { IDockviewPanelProps } from 'dockview-react'
import type { FunctionComponent } from 'react'

import { RunBrowser } from './RunBrowser'

export interface PanelMenuItem {
  component: string
  title: string
  hint?: string
}

export const PANELS: Record<string, FunctionComponent<IDockviewPanelProps>> = {
  RunBrowser,
}

export const PANEL_MENU: PanelMenuItem[] = [
  { component: 'RunBrowser', title: 'Run Browser', hint: 'runs' },
]

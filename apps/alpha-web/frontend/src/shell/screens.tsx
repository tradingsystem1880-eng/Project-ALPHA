/**
 * Six purpose-built screens, replacing free-form docking.
 *
 * The old model asked you to assemble your own workspace out of 22 floating panels and
 * then remember where you put them. Docking is a good answer when nobody can predict what
 * a user needs beside what; here the workflow is known — look at data, build a run, read
 * the result, compare results, use a studio, operate the machine — so each screen is laid
 * out once, deliberately, for the job it serves.
 *
 * Layouts are plain CSS grid. A screen declares regions and which panel fills each; the
 * shell mounts only the active screen, so no hidden panel keeps polling behind a tab.
 */

import type { FunctionComponent } from 'react'

import type { PanelHandleProps } from '../context/panelHandle'
import { ActivityFeed } from '../panels/ActivityFeed'
import { AiConsole } from '../panels/AiConsole'
import { CodexBench } from '../panels/CodexBench'
import { DataExplorer } from '../panels/DataExplorer'
import { EvidenceHub } from '../panels/EvidenceHub'
import { Glossary } from '../panels/Glossary'
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
import { CompareRuns } from '../panels/CompareRuns'

export type ScreenId = 'explore' | 'build' | 'results' | 'compare' | 'studios' | 'operate'

export interface ScreenPane {
  /** Grid area name; the screen's CSS decides where it sits. */
  area: string
  name: string
  title: string
  component: FunctionComponent<PanelHandleProps>
  /** Panes in the same area become tabs within it. */
  group?: string
}

export interface ScreenDefinition {
  id: ScreenId
  label: string
  /** One line under the screen tabs saying what this screen is for. */
  purpose: string
  /** CSS class carrying the grid template; see styles/screens.css. */
  layout: string
  panes: ScreenPane[]
}

export const SCREENS: ScreenDefinition[] = [
  {
    id: 'explore',
    label: 'Explore',
    purpose: 'Look at market data before committing to a strategy.',
    layout: 'screen--explore',
    panes: [
      { area: 'main', name: 'PriceChart', title: 'Price', component: PriceChart },
      { area: 'side', name: 'DataExplorer', title: 'Symbols & data', component: DataExplorer },
      { area: 'side', name: 'ResearchDataExplorer', title: 'Research data', component: ResearchDataExplorer },
      { area: 'side', name: 'ResearchBacklog', title: 'Research backlog', component: ResearchBacklog },
      { area: 'side', name: 'EvidenceHub', title: 'Evidence', component: EvidenceHub },
      { area: 'side', name: 'Screener', title: 'Quotes & news', component: Screener },
      { area: 'side', name: 'OptionsGreeks', title: 'Options', component: OptionsGreeks },
    ],
  },
  {
    id: 'build',
    label: 'Build',
    purpose: 'Configure and launch a run, and follow it while it works.',
    layout: 'screen--build',
    panes: [
      { area: 'main', name: 'StrategyLab', title: 'Strategy lab', component: StrategyLab },
      { area: 'side', name: 'Pipeline', title: 'What next', component: Pipeline },
      { area: 'side', name: 'ResearchCockpit', title: 'Research case', component: ResearchCockpit },
      { area: 'side', name: 'CodexBench', title: 'Codex research', component: CodexBench },
      { area: 'foot', name: 'JobMonitor', title: 'Jobs', component: JobMonitor },
    ],
  },
  {
    id: 'results',
    label: 'Results',
    purpose: 'Read one run: its figures, and what each of them says.',
    layout: 'screen--results',
    panes: [
      { area: 'main', name: 'RunDetail', title: 'Report', component: RunDetail },
    ],
  },
  {
    id: 'compare',
    label: 'Compare',
    purpose: 'Put runs side by side and see where they actually differ.',
    layout: 'screen--compare',
    panes: [{ area: 'main', name: 'CompareRuns', title: 'Compare', component: CompareRuns }],
  },
  {
    id: 'studios',
    label: 'Studios',
    purpose: 'Forecasting, machine learning and portfolio risk.',
    layout: 'screen--studios',
    panes: [
      { area: 'main', name: 'KronosStudio', title: 'Forecast', component: KronosStudio },
      { area: 'main', name: 'MlResearch', title: 'ML lab', component: MlResearch },
      { area: 'main', name: 'MlDiagnostics', title: 'ML diagnostics', component: MlDiagnostics },
      { area: 'main', name: 'RiskMonitor', title: 'Risk', component: RiskMonitor },
      { area: 'side', name: 'AssetMemory', title: 'Findings', component: AssetMemory },
    ],
  },
  {
    id: 'operate',
    label: 'Operate',
    purpose: 'Jobs, paper sessions, providers and machine readiness.',
    layout: 'screen--operate',
    panes: [
      { area: 'main', name: 'DevelopmentCenter', title: 'Projects', component: DevelopmentCenter },
      { area: 'main', name: 'PaperMonitor', title: 'Paper sessions', component: PaperMonitor },
      { area: 'main', name: 'ProviderSystem', title: 'Providers & system', component: ProviderSystem },
      { area: 'side', name: 'ActivityFeed', title: 'Activity', component: ActivityFeed },
      { area: 'foot', name: 'AiConsole', title: 'AI console', component: AiConsole },
      { area: 'foot', name: 'Glossary', title: 'Glossary', component: Glossary },
    ],
  },
]

export function screen(id: ScreenId): ScreenDefinition {
  const found = SCREENS.find((item) => item.id === id)
  if (!found) throw new Error(`unknown screen ${id}`)
  return found
}

/** Panes grouped by area, preserving declaration order so tab order is deliberate. */
export function areasOf(definition: ScreenDefinition): [string, ScreenPane[]][] {
  const areas = new Map<string, ScreenPane[]>()
  for (const pane of definition.panes) {
    areas.set(pane.area, [...(areas.get(pane.area) ?? []), pane])
  }
  return [...areas.entries()]
}

/** Which screen a run browser row should open. */
export const RESULTS_SCREEN: ScreenId = 'results'

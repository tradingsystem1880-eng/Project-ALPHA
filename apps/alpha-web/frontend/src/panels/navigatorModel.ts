// Navigator tree (spec 2026-09-01 §4.2 item 4): Strategies · Backtests · Research cases · Data ·
// Scripts · Paper sandbox. Runs and projects are filed by the server's `market` field only — a
// `symbol` is never read to guess a market — and `unknown` rows always stay visible under their
// own leaf so nothing the owner produced can disappear. `showAll` lifts the profile filter.

import type { PaperSession, ProjectSummary, RunListItem, StrategyDef } from '../api/types'
import type { Profile } from '../state/settings'
import { profile as manifest } from '../shell/profiles'
import type { StorageRow } from './dataManagerModel'
import { venueLabel as providerLabel } from './marketWatchModel'

export const NAVIGATOR_GROUPS = [
  'Strategies',
  'Backtests',
  'Research cases',
  'Data',
  'Scripts',
  'Paper sandbox',
] as const
export type NavigatorGroupLabel = (typeof NAVIGATOR_GROUPS)[number]

export type NavigatorAction =
  | { kind: 'run'; runId: string }
  | { kind: 'project'; projectId: string }
  | { kind: 'symbol'; symbol: string }
  | { kind: 'none' }

export interface NavigatorLeaf {
  id: string
  label: string
  sub: string | null
  tone: 'none' | 'ok' | 'warn' | 'bad'
  action: NavigatorAction
}

export interface NavigatorGroup {
  label: string
  leaves: NavigatorLeaf[]
  /** Rows the profile filter would hide but the market is unknown; always shown. */
  unknown: NavigatorLeaf[]
}

export interface NavigatorInput {
  profile: Profile
  showAll: boolean
  runs: readonly RunListItem[]
  projects: readonly ProjectSummary[]
  strategies: readonly StrategyDef[]
  sessions: readonly PaperSession[]
  storage: StorageRow
  /** Venue display name → stored pairs on it (from the Market Watch provenance reads). */
  pairsByVenue?: Readonly<Record<string, number>>
}

export const MARKET_UNKNOWN_LABEL = 'Market unknown'

function file<T extends { market: 'crypto' | 'equities' | 'unknown' }>(
  rows: readonly T[],
  profile: Profile,
  showAll: boolean,
): { shown: T[]; unknown: T[] } {
  const shown = rows.filter((row) => showAll || row.market === profile)
  const unknown = showAll ? [] : rows.filter((row) => row.market === 'unknown')
  return { shown, unknown }
}

function runLeaf(run: RunListItem): NavigatorLeaf {
  return {
    id: `run:${run.run_id}`,
    label: run.display_name,
    sub: run.run_id.slice(0, 8),
    tone: run.passed === true ? 'ok' : run.passed === false ? 'bad' : 'none',
    action: { kind: 'run', runId: run.run_id },
  }
}

function projectLeaf(project: ProjectSummary): NavigatorLeaf {
  return {
    id: `project:${project.project_id}`,
    label: project.name,
    sub: project.research_gate_state === 'open' ? 'research gate open' : project.status,
    tone: project.research_gate_state === 'open' ? 'warn' : 'none',
    action: { kind: 'project', projectId: project.project_id },
  }
}

/** A project is a research case until its gate is passed, overridden or not required. */
export function isStrategyProject(project: Pick<ProjectSummary, 'research_gate_state'>): boolean {
  return project.research_gate_state !== 'open'
}

export function navigatorTree(input: NavigatorInput): NavigatorGroup[] {
  const runs = file(input.runs, input.profile, input.showAll)
  const strategies = file(input.projects.filter(isStrategyProject), input.profile, input.showAll)
  const cases = file(
    input.projects.filter((project) => !isStrategyProject(project)),
    input.profile,
    input.showAll,
  )
  const { providers } = manifest(input.profile)
  const dataLeaves: NavigatorLeaf[] = providers.map((provider) => {
    const name = providerLabel(provider) ?? provider
    const pairs = input.pairsByVenue?.[name] ?? 0
    return {
      id: `venue:${provider}`,
      label: pairs ? `${name} (${pairs} pair${pairs === 1 ? '' : 's'})` : name,
      sub: null,
      tone: 'none',
      action: { kind: 'none' },
    }
  })
  dataLeaves.push({
    id: 'storage:expansion',
    label: input.storage.label,
    sub: null,
    tone: input.storage.tone === 'ok' ? 'ok' : 'warn',
    action: { kind: 'none' },
  })
  return [
    { label: 'Strategies', leaves: strategies.shown.map(projectLeaf), unknown: strategies.unknown.map(projectLeaf) },
    { label: 'Backtests', leaves: runs.shown.map(runLeaf), unknown: runs.unknown.map(runLeaf) },
    { label: 'Research cases', leaves: cases.shown.map(projectLeaf), unknown: cases.unknown.map(projectLeaf) },
    { label: 'Data', leaves: dataLeaves, unknown: [] },
    {
      label: 'Scripts',
      leaves: input.strategies.map((strategy) => ({
        id: `script:${strategy.name}`,
        label: strategy.name,
        sub: strategy.supports_live_paper ? 'paper-capable' : null,
        tone: 'none',
        action: { kind: 'none' },
      })),
      unknown: [],
    },
    {
      label: 'Paper sandbox',
      leaves: input.sessions.map((session) => ({
        id: `paper:${session.session_id}`,
        label: `${session.symbol} · ${session.strategy}`,
        sub: `${session.execution_mode} · ${session.status}`,
        tone: session.status === 'failed' ? 'bad' : session.status === 'running' ? 'ok' : 'none',
        action: { kind: 'symbol', symbol: session.symbol },
      })),
      unknown: [],
    },
  ]
}

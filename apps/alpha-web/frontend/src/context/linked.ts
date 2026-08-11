// Linked workstation context. Workspace schema v3 keeps the flat active projection for older
// readers and adds independent A/B/C/D contexts for professional multi-desk linking.

import { useEffect, useState, useSyncExternalStore } from 'react'

export const LINK_GROUPS = ['A', 'B', 'C', 'D'] as const
export type LinkGroup = (typeof LINK_GROUPS)[number]
export type Timeframe = '1D'

export interface GroupLinkedState {
  projectId: string | null
  versionId: string | null
  symbol: string | null
  universe: string | null
  timeframe: Timeframe
  start: string | null
  end: string | null
  snapshotId: string | null
  runId: string | null
}

export interface LinkedState extends GroupLinkedState {
  schemaVersion: 3
  linkGroup: LinkGroup
}

export interface LinkedWorkspaceState extends LinkedState {
  groups: Record<LinkGroup, GroupLinkedState>
}

export const DEFAULT_LINKED: LinkedState = {
  schemaVersion: 3,
  linkGroup: 'A',
  projectId: null,
  versionId: null,
  symbol: null,
  universe: null,
  timeframe: '1D',
  start: null,
  end: null,
  snapshotId: null,
  runId: null,
}

const DEFAULT_GROUP: GroupLinkedState = linkedGroup(DEFAULT_LINKED)
const GROUP_SET = new Set<string>(LINK_GROUPS)

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function isLinkGroup(value: unknown): value is LinkGroup {
  return typeof value === 'string' && GROUP_SET.has(value)
}

function fieldValue(
  source: Record<string, unknown>,
  fallback: string | null,
  ...keys: string[]
): string | null {
  for (const key of keys) {
    if (!Object.hasOwn(source, key)) continue
    const value = source[key]
    if (typeof value === 'string') return value.trim() || null
    if (value === null) return null
  }
  return fallback
}

export function linkedGroup(value: LinkedState): GroupLinkedState {
  return {
    projectId: value.projectId,
    versionId: value.versionId,
    symbol: value.symbol,
    universe: value.universe,
    timeframe: value.timeframe,
    start: value.start,
    end: value.end,
    snapshotId: value.snapshotId,
    runId: value.runId,
  }
}

export function migrateLinkedGroup(
  value: unknown,
  fallback: GroupLinkedState = DEFAULT_GROUP,
): GroupLinkedState {
  const source = record(value)
  const candidateTimeframe = fieldValue(source, fallback.timeframe, 'timeframe')
  const timeframe: Timeframe =
    candidateTimeframe === '1D' || candidateTimeframe === 'daily' ? '1D' : fallback.timeframe

  return {
    projectId: fieldValue(source, fallback.projectId, 'projectId', 'project_id', 'project'),
    versionId: fieldValue(source, fallback.versionId, 'versionId', 'version_id', 'version'),
    symbol: fieldValue(source, fallback.symbol, 'symbol'),
    universe: fieldValue(source, fallback.universe, 'universe'),
    timeframe,
    start: fieldValue(source, fallback.start, 'start'),
    end: fieldValue(source, fallback.end, 'end'),
    snapshotId: fieldValue(source, fallback.snapshotId, 'snapshotId', 'snapshot_id', 'snapshot'),
    runId: fieldValue(source, fallback.runId, 'runId', 'run_id'),
  }
}

export function linkedForGroup(
  workspace: LinkedWorkspaceState,
  group: LinkGroup,
): LinkedState {
  return { schemaVersion: 3, linkGroup: group, ...workspace.groups[group] }
}

/**
 * Upgrade flat v1/v2/v3 contexts and grouped v3 contexts. The active group's fields remain at the
 * top level so old v3 readers continue to receive the exact shape they understand.
 */
export function migrateLinkedWorkspace(value: unknown): LinkedWorkspaceState {
  const source = record(value)
  const candidateGroup = fieldValue(source, 'A', 'linkGroup', 'link_group')
  const linkGroup = isLinkGroup(candidateGroup) ? candidateGroup : 'A'
  const flatActive = migrateLinkedGroup(source)
  const rawGroups = record(source.groups)
  const hasGroupedState = Object.hasOwn(source, 'groups')
  const groups = Object.fromEntries(
    LINK_GROUPS.map((group) => {
      const fallback = group === linkGroup ? flatActive : DEFAULT_GROUP
      const grouped = hasGroupedState && Object.hasOwn(rawGroups, group)
        ? migrateLinkedGroup(rawGroups[group], fallback)
        : fallback
      return [group, { ...grouped }]
    }),
  ) as Record<LinkGroup, GroupLinkedState>

  return {
    schemaVersion: 3,
    linkGroup,
    ...groups[linkGroup],
    groups,
  }
}

/** Return the active flat projection retained for all existing panel consumers. */
export function migrateLinked(value: unknown): LinkedState {
  const workspace = migrateLinkedWorkspace(value)
  return linkedForGroup(workspace, workspace.linkGroup)
}

let workspaceState = migrateLinkedWorkspace(DEFAULT_LINKED)
let activeState = linkedForGroup(workspaceState, workspaceState.linkGroup)
const listeners = new Set<() => void>()

function publish(next: LinkedWorkspaceState): void {
  workspaceState = next
  activeState = linkedForGroup(next, next.linkGroup)
  listeners.forEach((listener) => listener())
}

function withGroups(
  linkGroup: LinkGroup,
  groups: Record<LinkGroup, GroupLinkedState>,
): LinkedWorkspaceState {
  return {
    schemaVersion: 3,
    linkGroup,
    ...groups[linkGroup],
    groups,
  }
}

export function getLinked(): LinkedState {
  return activeState
}

export function getLinkedWorkspace(): LinkedWorkspaceState {
  return workspaceState
}

export function setGroupLinked(group: LinkGroup, patch: Partial<GroupLinkedState>): void {
  const current = workspaceState.groups[group]
  const groups = {
    ...workspaceState.groups,
    [group]: migrateLinkedGroup({ ...current, ...patch }, current),
  }
  publish(withGroups(workspaceState.linkGroup, groups))
}

export function setLinked(patch: Partial<LinkedState>): void {
  const linkGroup = isLinkGroup(patch.linkGroup) ? patch.linkGroup : workspaceState.linkGroup
  const current = workspaceState.groups[linkGroup]
  const groups = {
    ...workspaceState.groups,
    [linkGroup]: migrateLinkedGroup({ ...current, ...patch }, current),
  }
  publish(withGroups(linkGroup, groups))
}

export function restoreLinked(value: unknown): void {
  publish(migrateLinkedWorkspace(value))
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb)
  return () => {
    listeners.delete(cb)
  }
}

export function useLinked(): LinkedState {
  return useSyncExternalStore(subscribe, getLinked, getLinked)
}

export function useLinkedWorkspace(): LinkedWorkspaceState {
  return useSyncExternalStore(subscribe, getLinkedWorkspace, getLinkedWorkspace)
}

// Local state for a panel input that seeds from, and follows, one active linked-context field. The
// panel still calls setLinked({...}) itself to broadcast a new value to the active group.
export function useLinkedField(
  field: keyof LinkedState,
  fallback: string,
): [string, (value: string) => void] {
  const current = useLinked()[field]
  const [value, setValue] = useState(typeof current === 'string' ? current : fallback)
  useEffect(() => {
    if (typeof current === 'string') setValue(current || fallback)
  }, [current, fallback])
  return [value, setValue]
}

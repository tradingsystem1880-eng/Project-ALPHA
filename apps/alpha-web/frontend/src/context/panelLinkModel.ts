import {
  DEFAULT_LINKED,
  LINK_GROUPS,
  linkedForGroup,
  linkedGroup,
  migrateLinkedGroup,
  type GroupLinkedState,
  type LinkedState,
  type LinkedWorkspaceState,
  type LinkGroup,
} from './linked'

export type PanelBindingMode = 'follow-active' | 'pinned-to-group' | 'unlinked-local'

export interface PanelLinkBinding {
  mode: PanelBindingMode
  group: LinkGroup
  local: GroupLinkedState
}

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function group(value: unknown, fallback: LinkGroup): LinkGroup {
  return typeof value === 'string' && LINK_GROUPS.includes(value as LinkGroup)
    ? (value as LinkGroup)
    : fallback
}

function mode(value: unknown): PanelBindingMode {
  if (value === 'pinned-to-group' || value === 'pinned_to_group' || value === 'pinned') {
    return 'pinned-to-group'
  }
  if (value === 'unlinked-local' || value === 'unlinked_local' || value === 'local') {
    return 'unlinked-local'
  }
  return 'follow-active'
}

function legacyRun(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

/** Canonicalize saved panel params. A legacy explicit runId remains panel-local, as before. */
export function migratePanelBinding(
  value: unknown,
  seed: LinkedState = DEFAULT_LINKED,
  legacyRunId?: unknown,
): PanelLinkBinding {
  const source = record(value)
  const hasBinding = Object.keys(source).length > 0
  const seededLocal = linkedGroup(seed)
  const pinnedRunId = legacyRun(legacyRunId)
  if (!hasBinding && pinnedRunId) {
    return {
      mode: 'unlinked-local',
      group: seed.linkGroup,
      local: { ...seededLocal, runId: pinnedRunId },
    }
  }
  return {
    mode: mode(source.mode ?? source.bindingMode ?? source.binding_mode),
    group: group(source.group ?? source.linkGroup ?? source.link_group, seed.linkGroup),
    local: migrateLinkedGroup(source.local ?? source.context, seededLocal),
  }
}

export function resolvePanelLinked(
  workspace: LinkedWorkspaceState,
  binding: PanelLinkBinding,
): LinkedState {
  if (binding.mode === 'follow-active') {
    return linkedForGroup(workspace, workspace.linkGroup)
  }
  if (binding.mode === 'pinned-to-group') {
    return linkedForGroup(workspace, binding.group)
  }
  return { schemaVersion: 3, linkGroup: binding.group, ...binding.local }
}

export function patchLocalPanelBinding(
  binding: PanelLinkBinding,
  patch: Partial<LinkedState>,
): PanelLinkBinding {
  return {
    ...binding,
    local: migrateLinkedGroup({ ...binding.local, ...patch }, binding.local),
  }
}

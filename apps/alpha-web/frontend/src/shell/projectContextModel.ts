import type { ProjectPage, ResearchCasePage } from '../api/types'
import type { LinkedState } from '../context/linked'
import type { Profile } from '../state/settings'

export interface ProjectChoice { id: string; label: string }
/** Both inventories use the canonical project identity; research cases may precede a strategy. */
export function projectChoices(projects: ProjectPage['items'], cases: ResearchCasePage['items'], profile: Profile): ProjectChoice[] {
  const choices = new Map<string, ProjectChoice>()
  const excluded = new Set(projects.filter(p => p.market !== profile && p.market !== 'unknown').map(p => p.project_id))
  for (const p of projects) if (!excluded.has(p.project_id)) choices.set(p.project_id, { id: p.project_id, label: p.name })
  for (const c of cases) if (!excluded.has(c.case_id) && !choices.has(c.case_id)) choices.set(c.case_id, { id: c.case_id, label: c.title })
  return [...choices.values()].sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id))
}

/** Leaving project context retains the viewed market/window, but never its frozen run evidence. */
export function projectSelectionPatch(current: LinkedState, projectId: string | null): Partial<LinkedState> {
  return { projectId, ...(projectId === null ? { symbol: current.symbol, start: current.start, end: current.end, versionId: null, runId: null, snapshotId: null } : {}) }
}

/** Follow server pagination; reject nonadvancing pages instead of looping or claiming completeness. */
export async function inventoryPages<T>(read: (offset: number) => Promise<{ items: T[]; offset: number; limit: number; has_more: boolean }>): Promise<T[]> {
  const rows: T[] = []
  let offset = 0
  for (;;) {
    const page = await read(offset)
    if (page.offset !== offset || !Number.isInteger(page.limit) || page.limit <= 0 || (page.has_more && !page.items.length)) throw new Error('Project inventory returned nonadvancing pagination')
    rows.push(...page.items)
    if (!page.has_more) return rows
    offset = page.offset + page.limit
  }
}

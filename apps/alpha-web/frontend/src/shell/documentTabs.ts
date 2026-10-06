import type { Profile } from '../state/settings'
import { workflowPages, type PageId } from './workflowModel'
export interface TerminalDocument { key: string; title: string; page: PageId; pane?: string; runId?: string }
export function restoreDocumentTabs(raw: unknown, profile: Profile): TerminalDocument[] {
  if (!Array.isArray(raw)) return []
  const pages = workflowPages(profile), result: TerminalDocument[] = []
  for (const value of raw.slice(0, 40)) {
    if (!value || typeof value !== 'object') continue
    const page = pages.find(p => p.id === value.page)
    const pane = page?.panes.find(p => p.name === value.pane)
    if (!page || (!pane && page.id !== 'overview')) continue
    const runId = typeof value.runId === 'string' && /^[a-f0-9]{16}$/.test(value.runId) ? value.runId : undefined
    const key = `${profile}:${page.id}:${pane?.name ?? ''}:${runId ?? ''}`
    if (!result.some(p => p.key === key)) result.push({ key, title: pane?.title ?? page.title, page: page.id, pane: pane?.name, runId })
  }
  return result
}

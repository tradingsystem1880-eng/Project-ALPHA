import { describe, expect, it } from 'vitest'
import { DOCUMENTS } from './documents'
import { workflowPages, resolveWorkflow, workflowHash } from './workflowModel'

describe('workflow navigation', () => {
  it('keeps every existing document pane reachable in its market', () => {
    for (const profile of ['crypto', 'equities'] as const) {
      const pages = workflowPages(profile)
      const panes = pages.flatMap(page => page.panes.map(pane => pane.name))
      for (const doc of DOCUMENTS) {
        if (profile === 'crypto' && doc.id === 'corporate-actions') continue
        if (profile === 'equities' && ['funding', 'open-interest', 'onchain', 'dex', 'crowding'].includes(doc.id)) continue
        for (const pane of doc.panes) expect(panes).toContain(pane.name)
      }
      expect(panes).toEqual(expect.arrayContaining(['DataManager', 'MarketWatch', 'Navigator', 'Alerts', 'DataPulls']))
    }
  })
  it('round trips page links and retains legacy run links', () => {
    expect(resolveWorkflow(workflowHash('research', 'Literature'), 'crypto')).toEqual({ page: 'research', pane: 'Literature', runId: null })
    expect(resolveWorkflow('#run=0123456789abcdef', 'crypto')).toEqual({ page: 'results', pane: 'RunDetail', runId: '0123456789abcdef' })
    expect(resolveWorkflow('#page=data&pane=FundingData', 'equities').pane).toBe('DataManager')
    expect(resolveWorkflow('#page=unknown', 'crypto').page).toBe('overview')
  })
})

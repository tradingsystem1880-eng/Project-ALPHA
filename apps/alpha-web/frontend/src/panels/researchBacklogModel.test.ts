import { describe, expect, it } from 'vitest'

import { groupResearchBacklog } from './researchBacklogModel'
import type { ResearchCaseSummary } from './researchCockpitModel'

function row(overrides: Partial<ResearchCaseSummary>): ResearchCaseSummary {
  return {
    case_id: 'case-x',
    title: 'Case',
    original_idea: 'Idea',
    phase: 'triage',
    execution_state: 'idle',
    outcome: null,
    disposition: null,
    next_action: 'Codex checks feasibility.',
    responsibility: 'codex',
    latest_finding: null,
    blocker: null,
    recovery_action: null,
    completed_milestones: 2,
    total_milestones: 9,
    owner_pinned: false,
    priority: { falsifiability: 0, data_readiness: 0, novelty: 0, information_gain_per_cost: 0 },
    budget: { approved_units: 0, consumed_units: 0, unit: 'minutes' },
    updated_at: '2026-08-08T01:00:00Z',
    ...overrides,
  }
}

describe('research backlog grouping', () => {
  it('groups sorted cases under ordered bucket headers and omits empty buckets', () => {
    const groups = groupResearchBacklog([
      row({ case_id: 'closed-1', phase: 'closed' }),
      row({ case_id: 'ready-1' }),
      row({ case_id: 'owner-1', responsibility: 'owner' }),
      row({ case_id: 'running-1', execution_state: 'running' }),
    ])
    expect(groups.map((group) => group.bucket)).toEqual([
      'needs_owner',
      'running',
      'ready',
      'closed',
    ])
    expect(groups.map((group) => group.label)).toEqual(['Needs you', 'running', 'ready', 'closed'])
    expect(groups.map((group) => group.cases.map((item) => item.case_id))).toEqual([
      ['owner-1'],
      ['running-1'],
      ['ready-1'],
      ['closed-1'],
    ])
  })

  it('orders cases inside a bucket by pin, priority, recency, then id', () => {
    const groups = groupResearchBacklog([
      row({ case_id: 'b', updated_at: '2026-08-08T01:00:00Z' }),
      row({ case_id: 'a', updated_at: '2026-08-08T01:00:00Z' }),
      row({ case_id: 'newer', updated_at: '2026-08-09T01:00:00Z' }),
      row({ case_id: 'pinned', owner_pinned: true, updated_at: '2026-08-01T01:00:00Z' }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0]!.cases.map((item) => item.case_id)).toEqual(['pinned', 'newer', 'a', 'b'])
  })
})

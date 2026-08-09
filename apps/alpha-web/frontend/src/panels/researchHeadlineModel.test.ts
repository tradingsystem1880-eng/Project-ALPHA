import { describe, expect, it } from 'vitest'

import type { ResearchEvidenceHubSections } from '../api/types'
import { headlineBoard } from './researchHeadlineModel'

function sectionsWith(overrides: {
  dataStatus?: string
  explorationStatus?: string
  dimensions?: Array<{ dimension_id: string; state: string }>
}): ResearchEvidenceHubSections {
  return {
    overview: {
      scorecard: {
        dimensions: (overrides.dimensions ?? []).map((entry) => ({
          ...entry,
          label: entry.dimension_id,
          basis: 'test',
        })),
      },
    },
    data: { status: overrides.dataStatus ?? 'NOT_TESTED' },
    exploration: { status: overrides.explorationStatus ?? 'NOT_TESTED' },
  } as unknown as ResearchEvidenceHubSections
}

describe('headlineBoard', () => {
  it('renders exactly six categories, one per registered headline chart', () => {
    const board = headlineBoard(sectionsWith({}))
    expect(board).toHaveLength(6)
    expect(new Set(board.map((category) => category.id)).size).toBe(6)
    expect(board.map((category) => category.id)).toEqual([
      'data_and_event_validity',
      'primary_association_and_matched_control',
      'parameter_neighborhood_stability',
      'confounder_and_regime_decomposition',
      'sealed_confirmation_or_transportability',
      'null_power_and_multiplicity',
    ])
  })

  it('shows honest NOT TESTED states before any evidence exists', () => {
    const board = headlineBoard(sectionsWith({}))
    for (const category of board) {
      expect(category.status).toBe('NOT TESTED')
    }
  })

  it('derives live statuses from served hub data only', () => {
    const board = headlineBoard(
      sectionsWith({
        dataStatus: 'ADEQUATE',
        explorationStatus: 'TESTED',
        dimensions: [
          { dimension_id: 'temporal_stability', state: 'strong' },
          { dimension_id: 'regime_robustness', state: 'not_tested' },
          { dimension_id: 'cross_asset_stability', state: 'not_tested' },
          { dimension_id: 'falsification', state: 'passed' },
        ],
      }),
    )
    const byId = new Map(board.map((category) => [category.id, category.status]))
    expect(byId.get('data_and_event_validity')).toBe('ADEQUATE')
    expect(byId.get('primary_association_and_matched_control')).toBe('TESTED')
    expect(byId.get('parameter_neighborhood_stability')).toBe('STRONG')
    expect(byId.get('null_power_and_multiplicity')).toBe('PASSED')
  })
})

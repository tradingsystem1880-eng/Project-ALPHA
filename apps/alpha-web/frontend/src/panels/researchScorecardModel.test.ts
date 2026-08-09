import { describe, expect, it } from 'vitest'

import scenarios from './__fixtures__/researchScorecard.json'
import {
  SCORECARD_DIMENSION_IDS,
  deriveResearchScorecard,
  type ResearchScorecardInputs,
  type ResearchScorecardResult,
} from './researchScorecardModel'

interface DriftScenario {
  name: string
  inputs: ResearchScorecardInputs
  expected: ResearchScorecardResult
}

const DRIFT_SCENARIOS = scenarios as unknown as DriftScenario[]

describe('research scorecard drift guard: TS twin vs committed Python fixture', () => {
  it('ships at least the three canonical scenarios', () => {
    expect(DRIFT_SCENARIOS.length).toBeGreaterThanOrEqual(3)
    expect(DRIFT_SCENARIOS.map((scenario) => scenario.name)).toEqual([
      'closed_inconclusive',
      'closed_supported',
      'deep_live_d1_evidence',
      'fresh_triage_unresolved',
      'registered_audited_limiting',
      'screened_mixed_literature',
    ])
  })

  it.each(DRIFT_SCENARIOS.map((scenario) => [scenario.name, scenario] as const))(
    '%s: the TypeScript twin derives the Python-recorded scorecard exactly',
    (_name, scenario) => {
      expect(deriveResearchScorecard(scenario.inputs)).toEqual(scenario.expected)
    },
  )
})

describe('research scorecard derivation semantics', () => {
  const fresh = DRIFT_SCENARIOS.find((scenario) => scenario.name === 'fresh_triage_unresolved')

  it('keeps the twelve dimensions in registered order', () => {
    expect(SCORECARD_DIMENSION_IDS).toHaveLength(12)
    const derived = deriveResearchScorecard(fresh!.inputs)
    expect(derived.dimensions.map((dimension) => dimension.dimension_id)).toEqual(
      [...SCORECARD_DIMENSION_IDS],
    )
  })

  it('never emits a numeric aggregate or confidence score', () => {
    const derived = deriveResearchScorecard(fresh!.inputs) as unknown as Record<string, unknown>
    expect(Object.keys(derived).sort()).toEqual([
      'dimensions',
      'recommendation',
      'scorecard_schema',
      'unresolved_questions',
    ])
  })

  it('recommends contradiction and invalid outcomes with their fixed vocabulary', () => {
    const base = fresh!.inputs
    expect(
      deriveResearchScorecard({ ...base, outcome: 'CONTRADICTED' }).recommendation.value,
    ).toBe('EVIDENCE DOES NOT SUPPORT CONTINUATION')
    expect(deriveResearchScorecard({ ...base, outcome: 'INVALID' }).recommendation.value).toBe(
      'REFORMULATE HYPOTHESIS',
    )
    expect(deriveResearchScorecard({ ...base, outcome: 'SUPPORTED' }).recommendation.value).toBe(
      'READY FOR STRATEGY RESEARCH',
    )
  })
})

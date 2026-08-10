import { describe, expect, it } from 'vitest'

import scenarios from './__fixtures__/researchChecklist.json'
import {
  CHECKLIST_QUESTION_IDS,
  deriveResearchChecklist,
  type ResearchChecklistResult,
} from './researchChecklistModel'
import { findingChipClass } from './researchChipModel'
import type { ResearchScorecardInputs } from './researchScorecardModel'

interface DriftScenario {
  name: string
  inputs: ResearchScorecardInputs
  expected: ResearchChecklistResult
}

const DRIFT_SCENARIOS = scenarios as unknown as DriftScenario[]

describe('research checklist drift guard: TS twin vs committed Python fixture', () => {
  it('ships the same canonical scenarios as the scorecard fixture', () => {
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
    '%s: the TypeScript twin derives the Python-recorded checklist exactly',
    (_name, scenario) => {
      expect(deriveResearchChecklist(scenario.inputs)).toEqual(scenario.expected)
    },
  )
})

describe('research checklist derivation semantics', () => {
  const fresh = DRIFT_SCENARIOS.find((scenario) => scenario.name === 'fresh_triage_unresolved')

  it('keeps the fourteen questions in spec order, numbered 1..14', () => {
    expect(CHECKLIST_QUESTION_IDS).toHaveLength(14)
    const derived = deriveResearchChecklist(fresh!.inputs)
    expect(derived.questions.map((row) => row.question_id)).toEqual(
      [...CHECKLIST_QUESTION_IDS],
    )
    expect(derived.questions.map((row) => row.number)).toEqual(
      derived.questions.map((_, index) => index + 1),
    )
  })

  it('answers every question with a typed status, never a numeric aggregate', () => {
    const derived = deriveResearchChecklist(fresh!.inputs) as unknown as Record<string, unknown>
    expect(Object.keys(derived).sort()).toEqual(['checklist_schema', 'questions'])
    for (const row of deriveResearchChecklist(fresh!.inputs).questions) {
      expect(Object.keys(row).sort()).toEqual(
        ['answer', 'binding', 'number', 'question', 'question_id', 'status'],
      )
      expect(row.status).not.toMatch(/^[0-9.]+$/)
    }
  })

  it('always reports residual uncertainty and never fakes untested rungs', () => {
    const derived = deriveResearchChecklist(fresh!.inputs)
    const byId = new Map(derived.questions.map((row) => [row.question_id, row]))
    expect(byId.get('residual_uncertainty')!.status).toBe('TESTED')
    expect(byId.get('regime_dependence')!.status).toBe('NOT_TESTED')
    expect(byId.get('economic_hurdle')!.status).toBe('NOT_TESTED')
  })

  it('colors typed finding statuses without ever upgrading neutral evidence', () => {
    expect(findingChipClass('SUPPORTED')).toBe('chip pass')
    expect(findingChipClass('PASSED')).toBe('chip pass')
    expect(findingChipClass('CONTRADICTED')).toBe('chip fail')
    expect(findingChipClass('BELOW_HURDLE')).toBe('chip fail')
    // An exploratory TESTED result and every not-run status stay neutral.
    expect(findingChipClass('TESTED')).toBe('chip')
    expect(findingChipClass('NOT_TESTED')).toBe('chip')
    expect(findingChipClass('INCONCLUSIVE')).toBe('chip')
  })

  it('prefers the sealed confirmation classification for effect existence', () => {
    const supported = DRIFT_SCENARIOS.find((scenario) => scenario.name === 'closed_supported')
    const derived = deriveResearchChecklist(supported!.inputs)
    expect(derived.questions[0].status).toBe('SUPPORTED')
    expect(derived.questions[0].answer).toContain('Sealed confirmation')
  })
})

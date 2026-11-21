import { describe, expect, it } from 'vitest'
import type { IdeaFile, IdeaListRow, IdeaTest } from '../../api/types'
import {
  aimText, dataFacts, defaultRun, hypothesisPairs, ideaPairs, ideaSteps, NOT_STATED, newestFirst, ruleSentence, timeline, toolRows, triesText,
} from './ideaModel'

const reading = (word: string | null) => ({
  sentence: 's', evidence: { word, because: [] }, measures: [], aim: { rows: [] }, counts: { trial_n: 3, family_trials: 1, variants_tried: 2 },
  checks: [{ name: 'data-health', state: 'sound', detail: 'the data health check is clean' }],
})
function run(id: string, day: string, extra: Partial<IdeaTest> = {}): IdeaTest {
  return {
    kind: 'rule test', id, recorded_at: `${day}T10:00:00+00:00`, word: 'too little to read', checks: [], figures_available: ['equity_underwater'], labels: [], studies: [],
    totals: {}, problem: null, reading: reading('too little to read'),
    aim: { measure: 'out-of-sample Sharpe', observed: 0.75, aim: 0.78, relation: 'within the uncertainty of the aim' },
    tested: { asset: 'SPY', rule: 'ma_cross (fast=5, slow=20)', data_from: '2020-01-02', data_to: '2024-06-28', scored_from: '2022-01-03', scored_to: '2024-06-28', held_back: 'This test saw the reserved period.', assets: [] },
    ...extra,
  } as IdeaTest
}
const find: IdeaTest = {
  kind: 'setup find', id: 'f1', recorded_at: '2026-11-18T09:00:00+00:00', checks: [], figures_available: [], labels: [], tested: { assets: ['SPY'] },
  totals: { accepted: 12, pending: 1, set_aside: 3 }, studies: [{ id: 's1', reading: 'Too few occurrences (12) to judge.', labels: [] }],
} as unknown as IdeaTest
function file(extra: Partial<IdeaFile> = {}): IdeaFile {
  return {
    card: { id: 'abc', claim: 'Quiet weeks lead to a bigger move.', mechanism: 'Under-reaction.', baseline: 'Buy and hold.' },
    map: [], follows: [], readings: [find, run('a'.repeat(16), '2026-11-19'), run('b'.repeat(16), '2026-11-20', { reading: null, word: null, problem: 'the stored run could not be read' })],
    counts: {}, open_points: { not_stated: ['what would disprove it'], map_not_yet: ['held-back confirmation'], too_little_to_read: [], next_steps: [] },
    readings_total: 3, readings_shown_from: 0, ...extra,
  } as unknown as IdeaFile
}

describe('ideaModel', () => {
  it('sorts cards newest first and keeps ties stable', () => {
    const rows = [{ id: 'b', saved_at: '2026-11-01T00:00:00+00:00' }, { id: 'a', saved_at: '2026-11-01T00:00:00+00:00' }, { id: 'c', saved_at: '2026-11-05T00:00:00+00:00' }, { id: 'd', saved_at: null }] as IdeaListRow[]
    expect(newestFirst(rows).map(r => r.id)).toEqual(['c', 'a', 'b', 'd'])
  })
  it('says "not stated" for an empty card field, never a blank', () => {
    expect(ideaPairs(file()).find(([l]) => l === 'The other side of the trade')?.[1]).toBe(NOT_STATED)
    expect(hypothesisPairs(file()).find(([l]) => l.startsWith('What would prove'))?.[1]).toBe(NOT_STATED)
  })
  it('picks the newest run that has a reading', () => {
    expect(defaultRun(file())?.id).toBe('a'.repeat(16))
    expect(defaultRun(file({ readings: [find] }))).toBeNull()
  })
  it('writes the rule as a plain sentence', () => {
    expect(ruleSentence(run('a', '2026-11-19'))).toBe('The rule is ma cross, with fast 5, slow 20 on SPY.')
    expect(ruleSentence(null)).toBe('No rule is recorded for this test.')
  })
  it('lists the data facts as one row and names data health', () => {
    const facts = dataFacts(run('a', '2026-11-19'))
    expect(facts.map(([l]) => l)).toEqual(['Assets', 'Data span', 'Scored span', 'Held back', 'Data health'])
    expect(facts[1][1]).toBe('2020-01-02 to 2024-06-28')
    expect(facts[4][1]).toContain('sound')
  })
  it('builds one timeline row per linked test, with the problem kept', () => {
    const rows = timeline(file())
    expect(rows.map(r => r.kind)).toEqual(['setup find', 'rule test', 'rule test'])
    expect(rows[0].aim).toBe('12 accepted, 1 pending, 3 set aside')
    expect(rows[1].aim).toBe('Sharpe 0.75 against 0.78: within the uncertainty of the aim')
    expect(rows[1].tries).toBe('trial 3 · 1 try in the family · 2 variants')
    expect(rows[2].problem).toContain('could not be read')
    expect(rows[2].word).toBe('not readable')
  })
  it('handles a missing aim and missing counts in words', () => {
    expect(aimText(run('a', '2026-11-19', { aim: null }))).toBe('no aim stored')
    expect(triesText(run('a', '2026-11-19', { reading: null }))).toBe('tries not recorded')
  })
  it('collects stored tool results across runs', () => {
    const check = { tool: 'costs.break_even', word: 'exploratory', reading: 'r', file: 'f', labels: ['exploratory'] }
    const rows = toolRows(file({ readings: [run('a'.repeat(16), '2026-11-19', { checks: [check] })] } as Partial<IdeaFile>))
    expect(rows).toEqual([{ ...check, run: 'a'.repeat(16) }])
  })
  it('counts every step and marks RD-Agent as not built', () => {
    const steps = ideaSteps(file(), defaultRun(file()))
    expect(steps.map(s => s.number)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
    const by = Object.fromEntries(steps.map(s => [s.id, s]))
    expect(by.idea.state).toBe('some')
    expect(by.tests.count).toBe('3')
    expect(by.charts.count).toBe('1')
    expect(by.rdagent.state).toBe('not-built')
    expect(by.follow.state).toBe('empty')
    expect(by.open.count).toBe('2')
  })
  it('shows every step empty for a card with no tests', () => {
    const empty = file({ readings: [] })
    const by = Object.fromEntries(ideaSteps(empty, null).map(s => [s.id, s]))
    expect(by.tests.state).toBe('empty')
    expect(by.data.state).toBe('empty')
    expect(by.charts.count).toBe('0')
  })
})

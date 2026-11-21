import { describe, expect, it } from 'vitest'
import { CLEAR, FAULT, NO_AIM, SOME } from './__fixtures__/readings'
import {
  aimSentence, manifestWord, aimSourceLine, countLines, runWord, MEASURE_HINTS, EVIDENCE_STEPS, evidenceStep, faultText, parseReading, rangePicture,
} from './readingModel'

describe('parseReading', () => {
  it('reads every part of a stored reading', () => {
    const reading = parseReading(SOME)
    expect(reading?.sentence).toContain('Out-of-sample Sharpe 0.75')
    expect(reading?.checks.map(check => check.state)).toEqual(['sound', 'sound', 'not-checked'])
    expect(reading?.evidence.word).toBe('some evidence')
    expect(reading?.aim.rows[0].interval).toEqual([0.1, 1.4])
    expect(reading?.measures[0].interval).toEqual([0.1, 1.4])
    expect(reading?.counts.best_of).toBe(6)
  })
  it('returns null for anything that is not a reading', () => {
    for (const bad of [null, undefined, 3, 'x', [], {}, { sentence: 'a', checks: 'no' }]) expect(parseReading(bad)).toBeNull()
  })
  it('refuses an evidence word that is not one of the four', () => {
    expect(parseReading({ ...SOME, evidence: { word: 'supported', because: [] } })).toBeNull()
  })
  it('keeps the fault and marks its numbers as not to be read', () => {
    const reading = parseReading(FAULT)
    expect(faultText(reading!)).toBe('a fill came at or before its decision (look-ahead)')
    expect(reading?.measures.every(row => row.notToBeRead)).toBe(true)
    expect(faultText(parseReading(SOME)!)).toBeNull()
  })
})

describe('evidence scale', () => {
  it('has four steps in the fixed order and marks the current one', () => {
    expect(EVIDENCE_STEPS).toEqual(['too little to read', 'not clear of chance', 'some evidence', 'clear of chance'])
    expect(evidenceStep('some evidence')).toBe(2)
    expect(evidenceStep('too little to read')).toBe(0)
    expect(evidenceStep('fault')).toBe(-1)
    expect(evidenceStep(null)).toBe(-1)
  })
})

describe('against the aim', () => {
  // The picture is to scale: the four values span the line with a tenth of the span as padding at each end.
  // The expected positions are worked by hand for each case (percent from the left edge).
  const row = (aim: number, observed: number | null, interval: [number, number], relation: string) => ({ measure: 'm', aim, observed, interval, relation })
  const near = (value: number | null, expected: number) => expect(value).toBeCloseTo(expected, 3)

  it('draws the tick inside the bar when the aim is within the range', () => {
    const picture = rangePicture(row(0.9, 0.75, [0.1, 1.4], 'within the uncertainty of the aim'))!
    near(picture.left, 8.3333); near(picture.right, 91.6667); near(picture.aim, 59.6154); near(picture.observed, 50)
  })
  it('draws the tick right of the bar when the aim is above the range', () => {
    const picture = rangePicture(row(1.55, 0.75, [0.1, 1.4], 'below the aim'))!
    near(picture.left, 8.3333); near(picture.right, 83.046); near(picture.aim, 91.6667); near(picture.observed, 45.6897)
    expect(picture.aim).toBeGreaterThan(picture.right)
  })
  it('draws the tick left of the bar when the aim is below the range', () => {
    const picture = rangePicture(row(0.2, 0.9, [0.5, 1.5], 'above the aim'))!
    near(picture.left, 27.5641); near(picture.right, 91.6667); near(picture.aim, 8.3333); near(picture.observed, 53.2051)
    expect(picture.aim).toBeLessThan(picture.left)
  })
  it('draws the bar and tick without a dot when no observed value was stored', () => {
    const picture = rangePicture(row(0.9, null, [0.1, 1.4], 'within the uncertainty of the aim'))!
    expect(picture.observed).toBeNull()
    near(picture.aim, 59.6154)
  })
  it('uses the stored fixtures: one above the range, one below', () => {
    const above = rangePicture(parseReading(SOME)!.aim.rows[0])!
    expect(above.aim).toBeGreaterThan(above.right)
    const below = rangePicture(parseReading(CLEAR)!.aim.rows[0])!
    expect(below.aim).toBeLessThan(below.left)
  })
  it('draws nothing without an interval', () => {
    expect(rangePicture({ measure: 'm', aim: 1, observed: 1, interval: null, relation: 'above the aim' })).toBeNull()
    expect(rangePicture({ measure: 'm', aim: 1, observed: 1, interval: [2, 1], relation: 'above the aim' })).toBeNull()
  })
  it('words the comparison and its source', () => {
    const row = parseReading(SOME)!.aim.rows[0]
    expect(aimSentence(row, 'default')).toBe('Out-of-sample Sharpe 0.75 against buy-and-hold 1.55')
    expect(aimSentence(row, 'card')).toBe('Out-of-sample Sharpe 0.75 against the aim 1.55')
    expect(aimSourceLine('default')).toBe('Default aim: beat buy-and-hold over the same days, with no costs. The aim’s own uncertainty is not included.')
    expect(aimSourceLine('card')).toBe('Aim from the idea card')
    expect(aimSourceLine('none')).toBe('No aim was recorded for this reading.')
    expect(parseReading(NO_AIM)!.aim.rows).toEqual([])
  })
})

describe('counts', () => {
  it('says each count in plain words and labels a repeat', () => {
    const counts = parseReading(SOME)!.counts
    expect(countLines(counts, [])).toEqual(['Ledger entry 3', 'Family counted as 6 tries', 'Best of 6 variants'])
    expect(countLines(counts, ['repeat'])).toContain('A repeat of an earlier test; it still counts as another try')
    expect(countLines({ trial_n: null, family_trials: null, best_of: null, variants_tried: null, family_id: null }, [])).toEqual([])
  })
})

describe('words for a run in a list', () => {
  it('shows the stored evidence word, else the old letter, else nothing', () => {
    expect(runWord('some evidence', 'B')).toEqual({ text: 'some evidence', old: false })
    expect(runWord('fault', 'B')).toEqual({ text: 'fault', old: false })
    expect(runWord(null, 'C')).toEqual({ text: 'graded C under the old rules', old: true })
    expect(runWord(undefined, 'PASS')).toEqual({ text: 'graded PASS under the old rules', old: true })
    expect(runWord(undefined, '')).toBeNull()
    expect(runWord(null, null)).toBeNull()
  })
  it('has a plain-words hint for every measure the command line names', () => {
    expect(MEASURE_HINTS['deflated Sharpe']).toBe('Sharpe after allowing for the number of ideas tried')
    expect(MEASURE_HINTS['cross-validated mean Sharpe']).toBe('Average over many re-splits of the test period')
  })
})

describe('old grade wording stays on old records', () => {
  it('shows the old letter for an old manifest and nothing for a current-contract run without a reading', () => {
    const old = { verdict: { overall: 'B' } }
    expect(manifestWord(old)?.text).toBe('graded B under the old rules')
    expect(manifestWord({ ...old, labels: ['quick'] })).toBeNull()
  })
})

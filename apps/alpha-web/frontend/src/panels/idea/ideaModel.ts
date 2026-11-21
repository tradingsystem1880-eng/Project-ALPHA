// The Ideas page as plain data. The command line states every word and number; this module only
// orders them, names the steps and counts what is there. No grade, no advice, no new statistic.

import type { IdeaFile, IdeaFollow, IdeaListRow, IdeaTest, IdeaToolCheck } from '../../api/types'

export const NOT_STATED = 'not stated'
export const NO_RDAGENT = 'No RD-Agent work is linked to this idea yet.'

export type StepState = 'done' | 'some' | 'empty' | 'not-built'
export interface StepSummary { id: string; number: number; title: string; state: StepState; count: string }

export const STATE_WORD: Record<StepState, string> = {
  done: 'recorded', some: 'partly recorded', empty: 'nothing recorded yet', 'not-built': 'not built yet',
}

const bound = (a: string, b: string): number => (a < b ? -1 : a > b ? 1 : 0)

/** Cards newest first by the day the card file was written; ties by id so the order is stable. */
export function newestFirst(rows: readonly IdeaListRow[]): IdeaListRow[] {
  return [...rows].sort((a, b) => bound(b.saved_at ?? '', a.saved_at ?? '') || bound(a.id, b.id))
}

export const shortDay = (iso: string | null | undefined): string => (iso ? iso.slice(0, 10) : 'date not recorded')
const plural = (n: number, one: string, many = `${one}s`): string => `${n} ${n === 1 ? one : many}`
const filled = (value: string | null | undefined): string => (value && value.trim() ? value : NOT_STATED)

export const runsOf = (file: IdeaFile): IdeaTest[] => file.readings.filter(item => item.kind === 'rule test')
export const findsOf = (file: IdeaFile): IdeaTest[] => file.readings.filter(item => item.kind === 'setup find')

export const evidenceWord = (test: IdeaTest): string => test.word ?? (test.problem ? 'not readable' : 'no evidence word recorded')

/** The newest rule test that has a reading; else the newest rule test; else nothing. */
export function defaultRun(file: IdeaFile): IdeaTest | null {
  const runs = runsOf(file)
  const read = runs.filter(item => item.reading)
  const pool = read.length ? read : runs
  return pool.length ? pool[pool.length - 1] : null
}

export type Pair = [label: string, value: string]

export function ideaPairs(file: IdeaFile): Pair[] {
  const card = file.card
  return [
    ['The idea, in the owner’s words', filled(card.claim)], ['Source', filled(card.source)],
    ['Why it could work', filled(card.mechanism)], ['The other side of the trade', filled(card.other_side)],
  ]
}

export function hypothesisPairs(file: IdeaFile): Pair[] {
  const card = file.card
  return [
    ['What would prove it wrong', filled(card.disproved_by)], ['The baseline it must beat', filled(card.baseline)],
    ['How often it happens', filled(card.how_often)], ['How long a trade is held', filled(card.held_for)],
    ['How long a signal takes to form', filled(card.signal_forms)], ['How long the edge should last', filled(card.edge_lasts)],
  ]
}

/** "ma_cross (fast=5, slow=20)" as a plain sentence; the stored text stays in the disclosure. */
export function ruleSentence(test: IdeaTest | null): string {
  const rule = test?.tested.rule
  if (!rule) return 'No rule is recorded for this test.'
  const match = /^([^(]+?)(?: \((.*)\))?$/.exec(rule)
  const kind = (match?.[1] ?? rule).replaceAll('_', ' ')
  const settings = match?.[2] ? `, with ${match[2].replaceAll('=', ' ')}` : ''
  const asset = test.tested.asset && test.tested.asset !== 'not recorded' ? ` on ${test.tested.asset}` : ''
  return `The rule is ${kind}${settings}${asset}.`
}

export function dataFacts(test: IdeaTest | null): Pair[] {
  if (!test) return []
  const t = test.tested
  const span = (a: string | null | undefined, b: string | null | undefined): string => (a && b ? `${a} to ${b}` : 'not recorded')
  const health = test.reading?.checks.find(item => item.name === 'data-health')
  return [
    ['Assets', t.asset ?? 'not recorded'], ['Data span', span(t.data_from, t.data_to)], ['Scored span', span(t.scored_from, t.scored_to)],
    ['Held back', t.held_back ?? 'No held-back period is recorded for this test.'],
    ['Data health', health ? `${health.state === 'not-checked' ? 'not checked' : health.state}: ${health.detail}` : 'not recorded'],
  ]
}

export function aimText(test: IdeaTest): string {
  const aim = test.aim
  if (!aim || aim.observed === null || aim.observed === undefined || aim.aim === null || aim.aim === undefined) return 'no aim stored'
  return `Sharpe ${aim.observed.toFixed(2)} against ${aim.aim.toFixed(2)}: ${aim.relation ?? 'relation not recorded'}`
}

export function triesText(test: IdeaTest): string {
  const c = test.reading?.counts
  if (!c) return 'tries not recorded'
  const parts = [
    c.trial_n !== null && c.trial_n !== undefined ? `trial ${c.trial_n}` : null,
    c.family_trials !== null && c.family_trials !== undefined ? plural(c.family_trials, 'try', 'tries') + ' in the family' : null,
    c.variants_tried !== null && c.variants_tried !== undefined ? plural(c.variants_tried, 'variant') : null,
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : 'tries not recorded'
}

export interface TimelineRow { id: string; kind: string; day: string; word: string; aim: string; tries: string; problem: string | null; checks: number }

export function timeline(file: IdeaFile): TimelineRow[] {
  return file.readings.map(test => {
    const find = test.kind === 'setup find'
    const t = test.totals
    return {
      id: test.id, kind: test.kind, day: shortDay(test.recorded_at), problem: test.problem ?? null, checks: test.checks.length,
      word: find ? test.studies.find(s => !s.problem)?.reading ?? 'no study yet' : evidenceWord(test),
      aim: find ? `${t.accepted ?? '?'} accepted, ${t.pending ?? '?'} pending, ${t.set_aside ?? '?'} set aside` : aimText(test),
      tries: find ? `${plural(test.studies.length, 'study', 'studies')} linked` : triesText(test),
    }
  })
}

export interface ToolRow extends IdeaToolCheck { run: string }
export const toolRows = (file: IdeaFile): ToolRow[] => runsOf(file).flatMap(test => test.checks.map(check => ({ ...check, run: test.id })))

export function followLine(item: IdeaFollow): string {
  return `Follow ${item.follow_id}, version ${item.version}: ${item.state}; ${plural(item.sessions, 'session')} recorded on ${item.assets.join(', ') || 'no asset'}. Paper only.`
}

export function ideaSteps(file: IdeaFile, selected: IdeaTest | null): StepSummary[] {
  const card = file.card
  const stated = (names: (keyof typeof card)[]): StepState => {
    const have = names.filter(name => filled(card[name] as string | null) !== NOT_STATED).length
    return have === names.length ? 'done' : have ? 'some' : 'empty'
  }
  const count = (have: number, total: number): string => `${have} of ${total}`
  const runs = runsOf(file)
  const tools = toolRows(file)
  const figures = selected?.figures_available.length ?? 0
  const open = file.open_points
  const hypo = ['disproved_by', 'baseline', 'how_often', 'held_for'] as const
  const idea = ['claim', 'source', 'mechanism', 'other_side'] as const
  const checkRows = selected?.reading?.checks.length ?? 0
  return [
    { id: 'idea', number: 1, title: 'Idea', state: stated([...idea]), count: count(idea.filter(n => filled(card[n]) !== NOT_STATED).length, 4) },
    { id: 'hypothesis', number: 2, title: 'Hypothesis', state: stated([...hypo]), count: count(hypo.filter(n => filled(card[n]) !== NOT_STATED).length, 4) },
    { id: 'rule', number: 3, title: 'Rule as built', state: runs.length ? 'done' : 'empty', count: String(runs.length) },
    { id: 'data', number: 4, title: 'Data used', state: selected ? 'done' : 'empty', count: selected ? '1 row' : '0' },
    { id: 'tests', number: 5, title: 'Tests run', state: file.readings.length ? 'done' : 'empty', count: String(file.readings.length) },
    { id: 'charts', number: 6, title: 'Charts', state: figures ? 'done' : 'empty', count: String(figures) },
    { id: 'checks', number: 7, title: 'Checks', state: checkRows ? 'done' : 'empty', count: String(checkRows) },
    { id: 'tools', number: 8, title: 'Tools run', state: tools.length ? 'done' : 'empty', count: String(tools.length) },
    { id: 'rdagent', number: 9, title: 'RD-Agent steps', state: 'not-built', count: '0' },
    { id: 'follow', number: 10, title: 'Forward follow', state: file.follows.length ? 'done' : 'empty', count: String(file.follows.length) },
    { id: 'open', number: 11, title: 'Open points', state: open.map_not_yet.length || open.not_stated.length ? 'some' : 'done',
      count: String(open.map_not_yet.length + open.not_stated.length) },
  ]
}

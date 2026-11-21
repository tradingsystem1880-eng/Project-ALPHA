import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import type { IdeaFile, IdeaList, IdeaListRow, IdeaTest } from '../../api/types'
import { IdeaCardsNoticeView } from './IdeaCardsNotice'
import { IdeaListView, IdeaPageView } from './IdeaWorkspace'

const noop = () => undefined
const row = (id: string, saved: string): IdeaListRow => ({ id, claim: `Claim ${id}`, tested: false, not_stated: ['a'], tests_linked: 2, saved_at: saved })
const run: IdeaTest = {
  kind: 'rule test', id: 'a'.repeat(16), recorded_at: '2026-11-19T10:00:00+00:00', word: 'too little to read', checks: [
    { tool: 'costs.break_even', word: 'exploratory', reading: 'Costs would have to reach 14 basis points.', file: 'f.json', labels: ['exploratory'] }],
  figures_available: ['equity_underwater'], labels: [], studies: [], totals: {}, problem: null, reading: null,
  aim: { measure: 'out-of-sample Sharpe', observed: 0.75, aim: 0.78, relation: 'within the uncertainty of the aim' },
  tested: { asset: 'SPY', rule: 'ma_cross (fast=5, slow=20)', data_from: '2020-01-02', data_to: '2024-06-28', scored_from: '2022-01-03', scored_to: '2024-06-28', held_back: 'held', assets: [] },
} as unknown as IdeaTest
const file = (extra: Partial<IdeaFile> = {}): IdeaFile => ({
  card: { id: 'abc123abc123', claim: 'Quiet weeks lead to a bigger move.', mechanism: 'Under-reaction.' }, map: [], follows: [], readings: [run],
  counts: {}, open_points: { not_stated: ['what would disprove it'], map_not_yet: [], too_little_to_read: [], next_steps: [] }, readings_total: 1, readings_shown_from: 0, ...extra,
} as unknown as IdeaFile)
const page = (f: IdeaFile | null, error: string | null = null) =>
  renderToStaticMarkup(<IdeaPageView file={f} error={error} selectedRun={null} onSelectRun={noop} onBack={noop} />)

describe('IdeaListView', () => {
  it('lists cards newest first', () => {
    const data: IdeaList = { cards: [row('aaaa', '2026-11-01T00:00:00+00:00'), row('bbbb', '2026-11-05T00:00:00+00:00')], total: 2, truncated: false }
    const html = renderToStaticMarkup(<IdeaListView data={data} error={null} onOpen={noop} />)
    expect(html.indexOf('Claim bbbb')).toBeLessThan(html.indexOf('Claim aaaa'))
    expect(html).toContain('2 idea cards, newest first')
  })
  it('says honestly when there is no card and when the read failed', () => {
    expect(renderToStaticMarkup(<IdeaListView data={{ cards: [], total: 0, truncated: false }} error={null} onOpen={noop} />)).toContain('No idea card is written yet')
    expect(renderToStaticMarkup(<IdeaListView data={null} error="boom" onOpen={noop} />)).toContain('role="alert"')
  })
})

describe('IdeaPageView', () => {
  it('shows the eleven steps in the navigator and every section', () => {
    const html = page(file())
    for (let n = 1; n <= 11; n += 1) expect(html).toContain(`data-step="${['idea', 'hypothesis', 'rule', 'data', 'tests', 'charts', 'checks', 'tools', 'rdagent', 'follow', 'open'][n - 1]}"`)
    for (const id of ['idea', 'hypothesis', 'rule', 'data', 'tests', 'charts', 'checks', 'tools', 'rdagent', 'follow', 'open']) expect(html).toContain(`id="idea-step-${id}"`)
  })
  it('shows the rule sentence, the spec disclosure and the data row for the default run', () => {
    const html = page(file())
    expect(html).toContain('The rule is ma cross, with fast 5, slow 20 on SPY.')
    expect(html).toContain('See the exact spec')
    expect(html).toContain('2020-01-02 to 2024-06-28')
  })
  it('puts a timeline row, the aim and a stored tool result on the page', () => {
    const html = page(file())
    expect(html).toContain('Sharpe 0.75 against 0.78: within the uncertainty of the aim')
    expect(html).toContain('costs.break_even')
    expect(html).toContain('aria-pressed="true"')
  })
  it('says no RD-Agent work is linked and shows honest empty states for a bare card', () => {
    const html = page(file({ readings: [], card: { id: 'abc123abc123', claim: null } } as unknown as Partial<IdeaFile>))
    expect(html).toContain('No RD-Agent work is linked to this idea yet.')
    expect(html).toContain('No test or setup find is linked to this idea yet.')
    expect(html).toContain('No rule test is selected, so there are no charts.')
    expect(html).toContain('No stored tool result is linked to this idea yet.')
    expect(html).toContain('No paper follow names this idea yet.')
    expect(html).toContain('not stated')
  })
  it('shows a paper follow with the paper-only words', () => {
    const follow = { follow_id: 'f1f1f1f1f1f1', kind: 'rule_test', source_id: 'x', assets: ['SPY'], version: 2, started_at: '2026-11-17T08:00:00+00:00', state: 'active', sessions: 4, stop_reason: '' }
    expect(page(file({ follows: [follow] } as unknown as Partial<IdeaFile>))).toContain('active; 4 sessions recorded on SPY. Paper only.')
  })
  it('shows loading and error states', () => {
    expect(page(null)).toContain('Loading this idea')
    expect(page(null, 'There is no idea card')).toContain('role="alert"')
  })
  it('uses no grade or advice words', () => {
    expect(page(file()).replace(/<[^>]+>/g, ' ')).not.toMatch(/\b(passed|failed|pass|fail|profit|verdict)\b/i)
  })
})

describe('IdeaCardsNoticeView', () => {
  it('shows the count, the newest card and a link to Ideas', () => {
    const data: IdeaList = { cards: [row('aaaa', '2026-11-01T00:00:00+00:00'), row('bbbb', '2026-11-05T00:00:00+00:00')], total: 2, truncated: false }
    const html = renderToStaticMarkup(<IdeaCardsNoticeView data={data} />)
    expect(html).toContain('2 idea cards written.')
    expect(html).toContain('Claim bbbb')
    expect(html).toContain('href="#page=research&amp;pane=IdeaWorkspace"')
  })
  it('shows nothing when no card exists', () => {
    expect(renderToStaticMarkup(<IdeaCardsNoticeView data={{ cards: [], total: 0, truncated: false }} />)).toBe('')
    expect(renderToStaticMarkup(<IdeaCardsNoticeView data={null} />)).toBe('')
  })
})

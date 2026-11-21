import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { CLEAR, FAULT, NO_AIM, NOT_CLEAR, reading as make, SOME, TOO_LITTLE, WITHIN } from '../panels/__fixtures__/readings'
import { BANNED } from '../panels/__fixtures__/scanWords'
import { parseReading } from '../panels/readingModel'
import { EvidenceScale, ReadingBlock, SetupReadingBlock } from './ReadingBlock'

const render = (value: Record<string, unknown> | null, extra: { oldLetter?: string | null; labels?: string[] } = {}): string =>
  renderToStaticMarkup(<ReadingBlock reading={value === null ? null : parseReading(value)} {...extra} />)

describe('the reading block', () => {
  it('shows checks, the sentence, the scale, the aim, measures, counts and the footer in that order', () => {
    const html = render(SOME)
    const order = ['Fact checks', 'Out-of-sample Sharpe 0.75; buy-and-hold', 'Evidence strength', 'Against the aim', 'Measures', 'Counts',
      'A reading describes the evidence. It is not advice and not an approval.'].map(text => html.indexOf(text))
    expect(order.every(index => index >= 0)).toBe(true)
    expect([...order].sort((a, b) => a - b)).toEqual(order)
  })

  it('shows the costs and annualisation lines of a run that stored them, and nothing for an older run', () => {
    const costs = { line: 'Costs: 2 basis points fee and 5 slippage per side, the default for a US stock.', periods: 'Annualised with 252 periods a year (daily).' }
    const html = render({ ...SOME, costs })
    expect(html).toContain(costs.line)
    expect(html).toContain(costs.periods)
    expect(render({ ...SOME, costs: { line: null, periods: null, reason: 'x' } })).not.toContain('Costs:')
    expect(render(SOME)).not.toContain('Costs:')
  })

  it('shows each fact check as an icon and a word', () => {
    const html = render(SOME)
    expect(html).toContain('data-state="sound"')
    expect(html).toContain('data-state="not-checked"')
    expect(html).toContain('not checked')
    expect(html).not.toContain('data-state="fault"')
  })

  it.each([
    [SOME, 'some evidence', 2], [CLEAR, 'clear of chance', 3], [NOT_CLEAR, 'not clear of chance', 1], [TOO_LITTLE, 'too little to read', 0],
  ])('marks the current step of the four-step scale for %#', (value, word, step) => {
    const html = render(value)
    expect(html).toContain(`Evidence strength: ${word}`)
    expect(html.match(/aria-current="step"/g)).toHaveLength(1)
    const items = html.split('<li').filter(part => part.includes('data-step='))
    expect(items).toHaveLength(4)
    expect(items[step]).toContain('aria-current="step"')
    expect(html).toContain('Random-data tests held: 3 of 3.')
  })

  it('shows the aim row with its relation words, a range picture and the source line', () => {
    const html = render(SOME)
    expect(html).toContain('Out-of-sample Sharpe 0.75 against buy-and-hold 1.55')
    expect(html).toContain('below the aim')
    expect(html).toContain('Default aim: beat buy-and-hold')
    expect(html).toContain('role="img"')
    expect(html).toContain('the aim 1.55; below the aim')
    expect(render(WITHIN)).toContain('within the uncertainty of the aim')
    expect(render(WITHIN)).toContain('the aim 0.90; within the uncertainty of the aim')
    expect(render(CLEAR)).toContain('Aim from the idea card')
    expect(render(CLEAR)).toContain('above the aim')
  })

  it('says so when there is no aim row, and draws no picture', () => {
    const html = render(NO_AIM)
    expect(html).toContain('No aim was recorded for this reading.')
    expect(html).not.toContain('role="img"')
  })

  it('lists the measures with their 95% range and basis, and the counts in words', () => {
    const html = render(SOME)
    expect(html).toContain('>0.10 to 1.40<')
    expect(html).toContain('walk-forward out-of-sample, after costs')
    expect(html).toContain('Ledger entry 3')
    expect(html).toContain('Family counted as 6 tries')
    expect(html).toContain('Best of 6 variants')
    expect(render(SOME, { labels: ['repeat'] })).toContain('A repeat of an earlier test; it still counts as another try')
  })

  it('replaces the whole block with a fault panel and hides its numbers behind a disclosure', () => {
    const html = render(FAULT)
    expect(html).toContain('Fault: a fill came at or before its decision (look-ahead). Fix this first. No reading.')
    expect(html).toContain('Show numbers that are not to be read')
    expect(html).toContain('<details')
    for (const part of ['Against the aim', 'aria-current="step"', 'Evidence strength']) expect(html).not.toContain(part)
    expect(html).toContain('role="alert"')
  })

  it('says graded <letter> under the old rules when only a letter is known', () => {
    const html = render(null, { oldLetter: 'C' })
    expect(html).toContain('graded C under the old rules')
    expect(html).toContain('muted')
    expect(html).not.toContain('Evidence strength')
    expect(render(null)).toContain('No reading was recorded for this test.')
    expect(render(null, { oldLetter: 'X' })).not.toContain('graded X')
  })

  it('reads as a description, never a verdict', () => {
    const html = render(make('some evidence'))
    expect(html).not.toMatch(BANNED)
    expect(html).not.toContain('var(--verdict')
    expect(html).not.toContain('var(--up)')
    expect(html).not.toContain('var(--down)')
  })
})

describe('the evidence scale on its own', () => {
  it('marks nothing for an unknown word', () => {
    expect(renderToStaticMarkup(<EvidenceScale word="fault" />)).not.toContain('aria-current')
  })
})

describe('Setup Lab reading block', () => {
  const props = { sentence: 'Average 5-bar return 0.41% after costs; random dates did this well in 3.00% of 2,000 draws.', kind: 'study' as const }
  it('shows the evidence word with the scale, the sentence and the family line', () => {
    const html = renderToStaticMarkup(<SetupReadingBlock {...props} evidence="some evidence" oldWording={false} position={2} count={3} />)
    expect(html).toContain('Evidence strength: some evidence')
    expect(html).toContain('aria-current="step"')
    expect(html).toContain(props.sentence)
    expect(html).toContain('Setup study 2 of 3 recorded for this idea.')
    expect(html).not.toContain('(old wording)')
    expect(html).toContain('The figure adjusted for the number of studies is shown by <code class="mono">alpha setup study</code>.')
    expect(html).toContain('A reading describes the evidence. It is not advice and not an approval.')
  })
  it('marks an old record as old wording', () => {
    const html = renderToStaticMarkup(<SetupReadingBlock {...props} evidence="not clear of chance" oldWording position={null} count={4} />)
    expect(html).toContain('not clear of chance (old wording)')
    expect(html).toContain('Setup study: not among the 4 studies recorded for this idea.')
  })
  it('says when nothing is stored', () => {
    const html = renderToStaticMarkup(<SetupReadingBlock sentence={null} kind="trade" evidence={null} oldWording={false} position={null} count={null} />)
    expect(html).toContain('No evidence word was recorded.')
    expect(html).not.toContain('Setup trade')
    expect(html).not.toContain('adjusted for the number')
  })
  it('adds a plain-words hint to every measure and explains the basis once', () => {
    const html = render(SOME)
    expect(html).toContain('Sharpe after allowing for the number of ideas tried')
    expect(html).toContain('Trades that were opened and later closed')
    expect(html).toContain('tested on later days than the rule learned from')
    expect(html).toContain('Exact basis as stored')
  })
  it('keeps the default aim line to two short sentences', () => {
    const line = render(SOME).match(/Default aim:[^<]*/)?.[0] ?? ''
    expect(line.split('. ').length).toBe(2)
  })
})

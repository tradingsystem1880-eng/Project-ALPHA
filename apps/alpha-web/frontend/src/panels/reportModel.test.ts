import { describe, expect, it } from 'vitest'

import type { FigureCatalogueItem } from '../api/types'
import { reportTree, summaryRows, tradesCsv, watermarkChip } from './reportModel'

function figure(id: string, section: string, available = true): FigureCatalogueItem {
  return {
    figure_id: id,
    section,
    title: id,
    summary: '',
    panel_count: 1,
    available,
    unavailable_reason: available ? null : 'no artifact',
  }
}

const CATALOGUE = [
  figure('equity', 'performance'),
  figure('drawdown', 'risk'),
  figure('entries', 'signals'),
  figure('pnl', 'trades'),
  figure('null', 'robustness'),
  figure('paths', 'monte_carlo'),
  figure('quantiles', 'forecast'),
  figure('claims', 'research'),
]

describe('report tree', () => {
  it('groups are the five spec groups in order and Summary is the first leaf', () => {
    const tree = reportTree({ kind: 'runs', isValidate: true, hasTrades: true, items: CATALOGUE })
    expect(tree.map((group) => group.label)).toEqual([
      'Strategy Analysis',
      'Trade Analysis',
      'Periodical Analysis',
      'Robustness',
      'Settings & data',
    ])
    expect(tree[0].leaves[0]).toMatchObject({ id: 'summary', label: 'Summary', empty: false })
  })

  it('lands every catalogue figure in exactly one leaf, unknown sections included', () => {
    const tree = reportTree({ kind: 'runs', isValidate: true, hasTrades: true, items: CATALOGUE })
    const ids = tree.flatMap((group) => group.leaves.flatMap((leaf) => leaf.figureIds))
    expect([...ids].sort()).toEqual(CATALOGUE.map((item) => item.figure_id).sort())
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('keeps leaves without evidence present but marked empty with a reason', () => {
    const tree = reportTree({ kind: 'optim', isValidate: false, hasTrades: false, items: [] })
    const leaves = Object.fromEntries(
      tree.flatMap((group) => group.leaves.map((leaf) => [leaf.id, leaf] as const)),
    )
    expect(leaves['trades']).toMatchObject({ empty: true, reason: 'no trades recorded' })
    expect(leaves['gates']).toMatchObject({ empty: true, reason: 'not a validate run' })
    expect(leaves['stress']).toMatchObject({ empty: true })
    expect(leaves['performance']).toMatchObject({ empty: true, reason: 'no figures in this section' })
    expect(leaves['summary'].empty).toBe(false)
    expect(leaves['artifacts'].empty).toBe(false)
  })

  it('marks a figure leaf empty when none of its figures is drawable', () => {
    const tree = reportTree({
      kind: 'runs',
      isValidate: false,
      hasTrades: false,
      items: [figure('equity', 'performance', false)],
    })
    const performance = tree[0].leaves.find((leaf) => leaf.id === 'performance')
    expect(performance).toMatchObject({ empty: true, figureIds: ['equity'] })
  })
})

describe('summary rows', () => {
  it('shows only recorded manifest values and names what is not recorded', () => {
    const rows = summaryRows({
      command: 'validate',
      params: { strategy_name: 'ma_crossover' },
      symbol: 'XRP/USDT',
      snapshot_id: 'snap-2024',
      starting_equity: 100_000,
      final_equity: 112_500,
      n_trades: 42,
      metrics: { sharpe: 1.234, max_drawdown: -0.181 },
      dsr: { dsr: 0.91 },
      verdict: { overall: 'PASS' },
      metadata: { first_ts: '2019-01-01T00:00:00+00:00', last_ts: '2026-06-30T00:00:00+00:00' },
    })
    const byLabel = Object.fromEntries(rows.map((row) => [row.label, row.value]))
    expect(byLabel['Strategy']).toBe('ma_crossover')
    expect(byLabel['Symbol']).toBe('XRP/USDT')
    expect(byLabel['Period']).toBe('2019-01-01 → 2026-06-30')
    expect(byLabel['Starting equity']).toBe('100,000.00')
    expect(byLabel['Final equity']).toBe('112,500.00')
    expect(byLabel['Trades']).toBe('42')
    expect(byLabel['Sharpe']).toBe('1.234')
    expect(byLabel['Max drawdown']).toBe('-0.181')
    expect(byLabel['Deflated Sharpe']).toBe('0.910')
    expect(byLabel['Verdict']).toBe('PASS')
    expect(byLabel['Win rate']).toBe('not recorded')
    expect(byLabel['Profit factor']).toBe('not recorded')
    expect(byLabel['Exposure']).toBe('not recorded')
    expect(byLabel['Max drawdown date']).toBe('not recorded')
    expect(rows.some((row) => /NaN|undefined|null/.test(row.value))).toBe(false)
  })

  it('never computes a value the manifest did not record', () => {
    const rows = summaryRows({ command: 'backtest_run', symbol: 'SPY', n_trades: 3 })
    const labels = rows.map((row) => row.label)
    expect(labels).not.toContain('Net profit')
    expect(labels).not.toContain('Period')
    expect(rows.find((row) => row.label === 'Trades')?.value).toBe('3')
  })
})

describe('watermark chip', () => {
  const gate = 'EXPLORATORY / RESEARCH GATE NOT COMPLETED'
  it('collapses the two banners into one chip that carries both sentences', () => {
    expect(watermarkChip(gate, 'LEGACY_CONTEXT_UNKNOWN')).toEqual({
      text: gate,
      title:
        `${gate} — launched under an owner research-gate override. `
        + 'LEGACY_CONTEXT_UNKNOWN — this run is not governed research evidence.',
    })
    expect(watermarkChip(gate, gate)?.title).toBe(
      `${gate} — launched under an owner research-gate override.`,
    )
    expect(watermarkChip(null, 'STANDALONE_UNQUALIFIED')).toEqual({
      text: 'STANDALONE_UNQUALIFIED',
      title: 'STANDALONE_UNQUALIFIED — this run is not governed research evidence.',
    })
    expect(watermarkChip(null, null)).toBeNull()
  })
})

describe('trade count and CSV', () => {
  it('names the trade count on the leaf once the rows are loaded', () => {
    const leaf = (count: number | null | undefined, hasTrades = true) =>
      reportTree({ kind: 'runs', isValidate: true, hasTrades, tradeCount: count, items: [] })
        .flatMap((group) => group.leaves)
        .find((item) => item.id === 'trades')!.label
    expect(leaf(143)).toBe('List of trades (143)')
    expect(leaf(null)).toBe('List of trades')
    expect(leaf(undefined)).toBe('List of trades')
    expect(leaf(0, false)).toBe('List of trades')
  })

  it('exports the trade rows exactly, escaping only what CSV requires', () => {
    expect(tradesCsv([])).toBe('')
    expect(
      tradesCsv([
        { entry_ts: '2024-01-02', pnl: 1.5, note: 'a, "quoted"', empty: null },
        { entry_ts: '2024-01-03', pnl: -2, note: 'plain', empty: null },
      ]),
    ).toBe('entry_ts,pnl,note,empty\n2024-01-02,1.5,"a, ""quoted""",\n2024-01-03,-2,plain,')
  })
})

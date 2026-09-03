import { describe, expect, it } from 'vitest'

import type { PaperSession, ProjectSummary, RunListItem, StrategyDef } from '../api/types'
import { storageRow } from './dataManagerModel'
import { MARKET_UNKNOWN_LABEL, NAVIGATOR_GROUPS, isStrategyProject, navigatorTree } from './navigatorModel'

const run = (id: string, market: RunListItem['market'], symbol: string | null, passed: boolean | null = null) =>
  ({ run_id: id, display_name: `Run ${id.slice(0, 4)}`, market, symbol, passed }) as RunListItem

const project = (id: string, market: ProjectSummary['market'], gate: ProjectSummary['research_gate_state']) =>
  ({ project_id: id, name: `Project ${id}`, market, research_gate_state: gate, status: 'active' }) as ProjectSummary

const script = (name: string) => ({ name, supports_live_paper: false }) as StrategyDef
const session = (id: string, status: PaperSession['status']) =>
  ({ session_id: id, symbol: 'BTC/USDT', strategy: 'sma', execution_mode: 'local_sandbox', status }) as PaperSession

const READY = storageRow({ state: 'ready', blocker: null, bulk_root_label: 'Expansion', free_bytes: 1e12, total_bytes: 2e12 })

function tree(overrides: Partial<Parameters<typeof navigatorTree>[0]> = {}) {
  return navigatorTree({
    profile: 'crypto',
    showAll: false,
    runs: [],
    projects: [],
    strategies: [],
    sessions: [],
    storage: READY,
    ...overrides,
  })
}

describe('navigatorModel', () => {
  it('builds the six groups in spec order', () => {
    expect(tree().map((group) => group.label)).toEqual([...NAVIGATOR_GROUPS])
    expect([...NAVIGATOR_GROUPS]).toEqual(['Strategies', 'Backtests', 'Research cases', 'Data', 'Scripts', 'Paper sandbox'])
  })

  it('files backtests by the server market field only, never by symbol text', () => {
    const runs = [
      run('aaaaaaaa11111111', 'crypto', 'BTC/USDT', true),
      // The server says equities even though the symbol looks like a pair: it is filed as equities.
      run('bbbbbbbb22222222', 'equities', 'BTC/USDT', false),
      run('cccccccc33333333', 'unknown', 'SPY'),
    ]
    const backtests = tree({ runs }).find((group) => group.label === 'Backtests')!
    expect(backtests.leaves.map((leaf) => leaf.id)).toEqual(['run:aaaaaaaa11111111'])
    expect(backtests.leaves[0]).toMatchObject({ label: 'Run aaaa', sub: 'aaaaaaaa', tone: 'ok', action: { kind: 'run', runId: 'aaaaaaaa11111111' } })
    expect(backtests.unknown.map((leaf) => leaf.id)).toEqual(['run:cccccccc33333333'])
    const equities = navigatorTree({ profile: 'equities', showAll: false, runs, projects: [], strategies: [], sessions: [], storage: READY })
    expect(equities[1].leaves.map((leaf) => leaf.id)).toEqual(['run:bbbbbbbb22222222'])
    expect(MARKET_UNKNOWN_LABEL).toBe('Market unknown')
  })

  it('shows every row when showAll is on', () => {
    const runs = [run('a', 'crypto', null), run('b', 'equities', null), run('c', 'unknown', null)]
    const backtests = tree({ runs, showAll: true })[1]
    expect(backtests.leaves).toHaveLength(3)
    expect(backtests.unknown).toEqual([])
  })

  it('splits projects into strategies and research cases by the research gate', () => {
    const projects = [project('p1', 'crypto', 'passed'), project('p2', 'crypto', 'open'), project('p3', 'unknown', 'not_required')]
    const groups = tree({ projects })
    expect(isStrategyProject({ research_gate_state: 'open' })).toBe(false)
    expect(groups[0].leaves.map((leaf) => leaf.id)).toEqual(['project:p1'])
    expect(groups[0].unknown.map((leaf) => leaf.id)).toEqual(['project:p3'])
    expect(groups[2].leaves[0]).toMatchObject({ id: 'project:p2', sub: 'research gate open', tone: 'warn' })
  })

  it('lists the venues by display name with their stored pair counts, and the Expansion SSD', () => {
    const data = tree({ pairsByVenue: { Binance: 5, Coinbase: 2, Bybit: 1 } })[3]
    expect(data.leaves.map((leaf) => leaf.label)).toEqual([
      'CCXT',
      'Binance (5 pairs)',
      'Bybit (1 pair)',
      'CoinGecko',
      'GeckoTerminal',
      'Coin Metrics',
      'Expansion SSD mounted',
    ])
    expect(data.leaves.every((leaf) => leaf.sub === null)).toBe(true)
    expect(tree()[3].leaves[1].label).toBe('Binance')
    const unmounted = storageRow({ state: 'blocked', blocker: 'bulk_volume_not_mounted', bulk_root_label: 'Expansion', free_bytes: null, total_bytes: null })
    const ssd = tree({ storage: unmounted })[3].leaves.at(-1)
    expect(ssd).toMatchObject({ label: 'Expansion SSD not mounted', tone: 'warn' })
  })

  it('lists scripts and paper sessions', () => {
    const groups = tree({ strategies: [script('sma_cross')], sessions: [session('s1', 'running'), session('s2', 'failed')] })
    expect(groups[4].leaves[0]).toMatchObject({ label: 'sma_cross', action: { kind: 'none' } })
    expect(groups[5].leaves.map((leaf) => leaf.tone)).toEqual(['ok', 'bad'])
    expect(groups[5].leaves[0].label).toBe('BTC/USDT · sma')
  })
})

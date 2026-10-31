import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import type { DailyRuleEvidence } from '../api/dailyRule'
import { DailyRuleInspector, DailyRuleSummary } from './DailyRuleReport'

// Artificial accounting fixture only. These rows do not establish real-market acceptance.
const summary = { run_id: 'b'.repeat(16), starting_equity: 1000, final_equity: 990,
  orders: 2, fills: 2, rejected: 0, n_trades: 1, gross_pnl: -8, net_pnl: -10, fees_total: 2 }
const evidence: DailyRuleEvidence = {
  schema: 'DailyRuleEvidenceV1', run_id: 'a'.repeat(16), available: true,
  outcome: 'exploratory_complete',
  watermark: 'Artificial engineering fixture only', claim_scope: 'exploratory', data_origin: 'artificial',
  provenance: { query_sha256: 'query-hash', canonical_chart_snapshot_id: 'snapshot-id',
    currency: 'USDT', quantity_unit: 'BTC', no_historical_point_in_time_claim: true },
  roles: { baseline: summary, control: { ...summary, run_id: 'c'.repeat(16), final_equity: 1000,
    orders: 0, fills: 0, n_trades: 0, gross_pnl: 0, net_pnl: 0, fees_total: 0 } },
  accounting: { role: 'baseline', rows: [{ ts: '2000-01-22T00:00:00Z', currency: 'USDT',
    cash: 990, position_units: 0, commission: 2, fees_total: 2, event: 'fill', fill_sequence_id: 2 }],
    total: 101, has_more: true, next_offset: 100 },
  selectors: { equity: 'equity.json' }, artifact_sha256: { 'economics.json': 'd'.repeat(64) },
}

afterEach(() => vi.unstubAllGlobals())

describe('daily study recorded report', () => {
  it('dates final equity from each role opening quote and discloses its later decision without inferring a fill', () => {
    const terminal = { valuation_basis: 'last_admitted_open_quote' as const,
      opening_quote_at: '2000-02-03T00:00:00+00:00',
      valuation_at: '2000-02-03T00:00:00.000001+00:00', terminal_liquidation: false as const,
      terminal_decision: 'unfilled_without_next_admitted_quote' as const,
      final_decision_at: '2000-02-04T00:00:00+00:00' }
    const recorded = { ...evidence, roles: {
      baseline: { ...summary, terminal },
      control: { ...evidence.roles.control, terminal: { ...terminal,
        valuation_at: '2001-05-06T00:00:00.000001+00:00',
        opening_quote_at: '2001-05-06T00:00:00+00:00',
        final_decision_at: '2001-05-07T00:00:00+00:00' } },
    } }
    const html = renderToStaticMarkup(createElement(DailyRuleSummary, { evidence: recorded }))
    const row = html.match(/<tr[^>]*><th scope="row">Final equity<\/th>[\s\S]*?<\/tr>/)?.[0]
    expect(row).toBeDefined()
    for (const text of ['990', '1000', 'Last admitted opening quote', 'No forced liquidation',
      terminal.valuation_at, terminal.opening_quote_at, terminal.final_decision_at,
      '2001-05-06T00:00:00.000001+00:00', '2001-05-07T00:00:00+00:00',
      ': no next admitted quote recorded; no fill inferred']) expect(row).toContain(text)
    expect(row).not.toContain('2022')
    expect(row).not.toContain('closing quote')
  })

  it('does not invent a terminal timestamp, liquidation policy or decision for older evidence', () => {
    const html = renderToStaticMarkup(createElement(DailyRuleSummary, { evidence }))
    expect(html).toContain('Terminal valuation not recorded')
    expect(html).not.toContain('No forced liquidation')
    expect(html).not.toContain(': no next admitted quote recorded; no fill inferred')
  })

  it('shows baseline/control identities and recorded loss and zero without a success badge', () => {
    const html = renderToStaticMarkup(createElement(DailyRuleSummary, { evidence }))
    expect(html).toContain('Artificial engineering fixture only')
    expect(html).toContain(summary.run_id)
    expect(html).toContain(evidence.roles.control.run_id)
    expect(html).toContain('>-10<')
    expect(html).toContain('>0<')
    expect(html).toContain('Exploratory recorded results. No promotion or trading approval.')
    expect(html).not.toContain('SUPPORTED')
  })

  it('preserves query/snapshot/hash/units and paged raw accounting in the evidence inspector', () => {
    const html = renderToStaticMarkup(createElement(DailyRuleInspector, {
      evidence, role: 'baseline', offset: 0, onPage: () => undefined,
    }))
    for (const value of ['query-hash', 'snapshot-id', 'USDT', 'BTC', 'equity.json',
      'd'.repeat(64), 'commission', 'position units', '2000-01-22T00:00:00Z']) expect(html).toContain(value)
    expect(html).toContain('More accounting rows exist')
    expect(html).toContain('disabled="">Previous accounting page')
    expect(html).not.toContain('disabled="">Next accounting page')
  })

  it('keeps a rejected zero-fill control explicitly inconclusive', () => {
    const rejected: DailyRuleEvidence = { ...evidence,
      outcome: 'accounting_rejection_inconclusive',
      roles: { ...evidence.roles, control: { ...evidence.roles.control,
        orders: 1, rejected: 1, fills: 0, n_trades: 0, starting_equity: 1000, final_equity: 1000,
        gross_pnl: 0, net_pnl: 0, fees_total: 0 } },
    }
    const html = renderToStaticMarkup(createElement(DailyRuleSummary, { evidence: rejected }))
    expect(html).toContain('Inconclusive: accounting rejection.')
    expect(html).toContain('control: 1 rejected order(s), 0 fills.')
    expect(html).toContain('Rejected orders prevent a valid baseline/control comparison.')
    expect(html).toContain('href="#daily-rejected-counts"')
    expect(html).toContain('id="daily-rejected-counts"')
    expect(html).not.toContain('Exploratory recorded results.')
  })

  it('does not imply a completed outcome when the server records none', () => {
    const html = renderToStaticMarkup(createElement(DailyRuleSummary, {
      evidence: { ...evidence, outcome: null },
    }))
    expect(html).toContain('Outcome not recorded.')
    expect(html).not.toContain('Exploratory recorded results.')
  })

  it('does not manufacture missing accounting or role values', () => {
    const missing = { ...evidence, roles: { ...evidence.roles,
      baseline: { ...summary, gross_pnl: null } },
      accounting: { role: 'baseline' as const, rows: [], total: 0, has_more: false, next_offset: null } }
    expect(renderToStaticMarkup(createElement(DailyRuleSummary, { evidence: missing })))
      .toContain('not recorded')
    const html = renderToStaticMarkup(createElement(DailyRuleInspector, {
      evidence: missing, role: 'baseline', offset: 0, onPage: () => undefined,
    }))
    expect(html).toContain('No accounting rows on this page')
    expect(html).toContain('disabled="">Next accounting page')
  })

  it('requests the exact bounded role/page and rejects invalid pagination before fetching', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(evidence)))
    vi.stubGlobal('fetch', fetchMock)
    await api.dailyRuleEvidence('a/b', 'control', 100)
    expect(fetchMock).toHaveBeenCalledWith('/api/runs/a%2Fb/daily-rule-evidence?role=control&limit=100&offset=100')
    expect(() => api.dailyRuleEvidence('a', 'baseline', -1)).toThrow(RangeError)
    expect(() => api.dailyRuleEvidence('a', 'baseline', 1.5)).toThrow(RangeError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

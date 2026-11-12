import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { RiskReport } from '../api/types'
import { RiskMetricBasis } from './RiskMetricBasis'

const basis: NonNullable<RiskReport['provenance']['metric_basis']> = {
  schema_version: 1,
  anchor_kind: 'first_recorded_equity',
  anchor_ts: '2024-01-01T00:00:00+00:00',
  anchor_value: 900,
  anchor_units: 'recorded_equity_units',
  initial_capital_status: 'unknown',
  external_cash_flow_status: 'unknown',
  return_accumulation: 'compounded_simple_returns',
  drawdown_convention: 'non_positive_fraction_from_scenario_wealth_peaks',
  benchmark_adjustment: 'none_by_projection',
  pre_anchor_losses: 'not_measured',
}
const provenance: RiskReport['provenance'] = {
  source_run_id: 'synthetic', source_command: 'c04_fixture',
  source_artifact: 'equity_curve.parquet', source_artifact_sha256: 'a'.repeat(64),
  snapshot_id: null, snapshot_hash: null, research_cutoff: null,
  as_of: null, timezone: 'UTC', derived_projection: true,
  metric_namespace: 'alpha_validation.scenario', periods_per_year: 365, confidence: .95,
}

function render(value: unknown): string {
  return renderToStaticMarkup(createElement(RiskMetricBasis, {
    provenance: { ...provenance, metric_basis: value } as RiskReport['provenance'],
  }))
}

describe('actual metric basis render', () => {
  it('discloses source anchoring, scenario conventions and unknown evidence without currency', () => {
    const html = render(basis)
    expect(html).toContain('365 periods/year')
    expect(html).toContain('compounded simple returns')
    expect(html).toContain('each scenario’s own')
    expect(html).toContain('900')
    expect(html).toContain(basis.anchor_ts)
    expect(html).toContain('Initial-capital baseline: unknown')
    expect(html).toContain('External cash-flow coverage: unknown')
    expect(html).toContain('No benchmark adjustment')
    expect(html).not.toContain('USD')
  })
  it.each([undefined, null])('renders a truthful legacy fallback for %s', (value) => {
    expect(render(value)).toContain('Legacy response: metric basis unavailable')
    expect(render(value)).toContain('are unknown')
  })
  it.each([
    { ...basis, schema_version: 2 }, { ...basis, initial_capital_status: 'verified' },
    { ...basis, anchor_value: NaN }, { ...basis, anchor_ts: 'bad' },
    { ...basis, return_accumulation: 'sum' },
  ])('does not render unsupported data as a verified convention', (value) => {
    const html = render(value)
    expect(html).toContain('Unsupported or invalid metric basis')
    expect(html).toContain('are unknown')
    expect(html).not.toContain('900')
  })
})

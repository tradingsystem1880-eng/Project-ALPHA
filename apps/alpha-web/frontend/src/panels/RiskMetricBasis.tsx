import type { RiskReport } from '../api/types'

type Provenance = RiskReport['provenance']

export function RiskMetricBasis({ provenance }: { provenance: Provenance }) {
  const basis = provenance.metric_basis
  const supported = basis?.schema_version === 1
    && basis.anchor_kind === 'first_recorded_equity'
    && Number.isFinite(basis.anchor_value) && basis.anchor_value > 0
    && typeof basis.anchor_ts === 'string' && Number.isFinite(Date.parse(basis.anchor_ts))
    && basis.anchor_units === 'recorded_equity_units'
    && basis.initial_capital_status === 'unknown'
    && basis.external_cash_flow_status === 'unknown'
    && basis.return_accumulation === 'compounded_simple_returns'
    && basis.drawdown_convention === 'non_positive_fraction_from_scenario_wealth_peaks'
    && basis.benchmark_adjustment === 'none_by_projection'
    && basis.pre_anchor_losses === 'not_measured'
  if (!supported) {
    return (
      <div className="risk-provenance" role="note" aria-label="Scenario metric basis" style={{ fontSize: 12, lineHeight: 1.5 }}>
        <span>{basis == null ? 'Legacy response: metric basis unavailable.' : 'Unsupported or invalid metric basis.'}</span>
        <span>Initial-capital baseline and external cash-flow coverage are unknown.</span>
      </div>
    )
  }
  return (
    <div className="risk-provenance" role="note" aria-label="Scenario metric basis" style={{ fontSize: 12, lineHeight: 1.5 }}>
      <span>ALPHA scenario recomputation · compounded simple returns · {provenance.periods_per_year} periods/year.</span>
      <span>Drawdown is a non-positive fraction from each scenario’s own compounded-wealth peaks, including its normalized initial anchor.</span>
      <span>Source anchor (first recorded row): <b className="mono">{String(basis.anchor_value)}</b> recorded equity units at <time>{basis.anchor_ts}</time>.</span>
      <span>Initial-capital baseline: unknown. External cash-flow coverage: unknown. Losses before the source anchor are not measured.</span>
      <span>No benchmark adjustment by this projection.</span>
    </div>
  )
}

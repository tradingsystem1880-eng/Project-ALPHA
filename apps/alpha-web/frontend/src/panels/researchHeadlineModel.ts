// The Evidence Hub headline board (spec §9, report_plan.headline_charts): at most six
// categories, one chip per category, every status derived from already-served hub data.
// Pure render-state projection only — no metric or verdict composition here.
import type { ResearchEvidenceHubSections } from '../api/types'

export interface HeadlineCategory {
  id: string
  label: string
  status: string
}

type HubSections = ResearchEvidenceHubSections

function dimensionState(sections: HubSections, dimensionId: string): string {
  const entry = sections.overview.scorecard.dimensions.find(
    (dimension) => dimension.dimension_id === dimensionId,
  )
  return (entry?.state ?? 'not_tested').replaceAll('_', ' ').toUpperCase()
}

export function headlineBoard(sections: HubSections): HeadlineCategory[] {
  return [
    {
      id: 'data_and_event_validity',
      label: 'Data & event validity',
      status: sections.data.status.replaceAll('_', ' ').toUpperCase(),
    },
    {
      id: 'primary_association_and_matched_control',
      label: 'Primary association',
      status: sections.exploration.status.replaceAll('_', ' ').toUpperCase(),
    },
    {
      id: 'parameter_neighborhood_stability',
      label: 'Temporal & parameter stability',
      status: dimensionState(sections, 'temporal_stability'),
    },
    {
      id: 'confounder_and_regime_decomposition',
      label: 'Confounders & regimes',
      status: dimensionState(sections, 'regime_robustness'),
    },
    {
      id: 'sealed_confirmation_or_transportability',
      label: 'Confirmation / transportability',
      status: dimensionState(sections, 'cross_asset_stability'),
    },
    {
      id: 'null_power_and_multiplicity',
      label: 'Nulls & falsification',
      status: dimensionState(sections, 'falsification'),
    },
  ]
}

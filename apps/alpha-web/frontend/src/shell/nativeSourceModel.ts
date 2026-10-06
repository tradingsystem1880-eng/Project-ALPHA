import type { ArchiveChartDataset } from '../api/client'
import { archivePairLabel, storedPairLabel } from '../components/assetChoices'
import type { PanelSource } from './chartWorkspaceModel'
/** Discovery candidates only; an owner selects the exact archive before verified reads. */
export function nativeSources(source: PanelSource, datasets: ArchiveChartDataset[]): ArchiveChartDataset[] {
  if (source.kind === 'run' || source.kind === 'primary') return []
  if (source.kind === 'archive') return datasets.filter(d => d.instrument === source.dataset.instrument && d.provider === source.dataset.provider && d.venue === source.dataset.venue && d.market_type === source.dataset.market_type && d.family === source.dataset.family && d.units === source.dataset.units && d.timestamp_convention === source.dataset.timestamp_convention)
  return datasets.filter(d => archivePairLabel(d).toUpperCase() === storedPairLabel(source.symbol).toUpperCase() || d.instrument.toUpperCase() === source.symbol.toUpperCase())
}

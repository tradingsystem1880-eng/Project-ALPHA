/** Labels group aliases; selecting a source always retains its exact identity. */
import type { ArchiveChartDataset } from '../api/client'

export type AssetChoice =
  | { kind: 'stored'; id: string; symbol: string; description: string }
  | { kind: 'archive'; id: string; dataset: ArchiveChartDataset; description: string }
export interface AssetGroup { label: string; choices: AssetChoice[] }

export function storedPairLabel(symbol: string): string {
  return symbol.replace(/^(.+)-(USD|USDT|USDC)$/i, '$1/$2')
}
export function archivePairLabel(dataset: ArchiveChartDataset): string {
  return dataset.base_asset && dataset.quote_asset
    ? `${dataset.base_asset}/${dataset.quote_asset}` : dataset.instrument
}
export function assetGroups(symbols: readonly string[], archives: readonly ArchiveChartDataset[]): AssetGroup[] {
  const groups = new Map<string, AssetChoice[]>()
  const add = (label: string, choice: AssetChoice) => {
    const choices = groups.get(label) ?? []
    if (!choices.some(item => item.id === choice.id)) choices.push(choice)
    groups.set(label, choices)
  }
  for (const symbol of symbols) add(storedPairLabel(symbol), {
    kind: 'stored', id: `stored:${symbol}`, symbol, description: `Stored ${symbol} · daily`,
  })
  for (const dataset of archives) add(archivePairLabel(dataset), {
    kind: 'archive', id: `archive:${dataset.manifest_id}`, dataset,
    description: `${dataset.venue} · ${dataset.market_type} · ${dataset.frequency} · ${dataset.instrument} · ${dataset.start?.slice(0, 10) ?? '?'} → ${dataset.end?.slice(0, 10) ?? '?'} · ${dataset.manifest_id.slice(0, 10)}`,
  })
  return [...groups].sort(([a], [b]) => a.localeCompare(b)).map(([label, choices]) => ({ label, choices }))
}

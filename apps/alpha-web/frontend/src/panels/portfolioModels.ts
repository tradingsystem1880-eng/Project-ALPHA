export type CorrelationCell = {
  asset_a: string
  asset_b: string
  correlation: number | null
}

export type AllocationCell = {
  ts: number
  symbol: string
}

export function buildCorrelationMatrix(rows: CorrelationCell[]) {
  const symbols = Array.from(
    new Set(rows.flatMap((row) => [row.asset_a, row.asset_b])),
  ).sort((left, right) => left.localeCompare(right))
  const byPair = new Map(rows.map((row) => [`${row.asset_a}\u0000${row.asset_b}`, row.correlation]))
  return {
    symbols,
    values: symbols.map((assetA) =>
      symbols.map((assetB) => byPair.get(`${assetA}\u0000${assetB}`) ?? null),
    ),
  }
}

export function latestAllocationRows<T extends AllocationCell>(rows: T[]): T[] {
  if (!rows.length) return []
  const latest = Math.max(...rows.map((row) => row.ts))
  return rows
    .filter((row) => row.ts === latest)
    .sort((left, right) => left.symbol.localeCompare(right.symbol))
}

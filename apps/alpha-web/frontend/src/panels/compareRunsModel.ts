import { shortId } from '../util/format'

/** A comparison winner exists only when at least two values are comparable and one is unique. */
export function uniqueComparisonMaximum(values: ReadonlyArray<number | null>): number | null {
  const numeric = values.filter((value): value is number => value !== null)
  if (numeric.length < 2) return null
  const maximum = Math.max(...numeric)
  return numeric.filter((value) => value === maximum).length === 1 ? maximum : null
}

interface CompareRowIdentity {
  symbol: string | null
  symbols: string[] | null
  command: string | null
}

export interface CompareColumn {
  id: string
  kind: string
  asset: string
}

const assetsOf = (row: CompareRowIdentity): string[] => (row.symbols?.length ? row.symbols : row.symbol ? [row.symbol] : [])

/** A column head: short run id, the plain kind of run, and the asset. A rule test says `rule test`, not its command. */
export function compareColumn(
  runId: string,
  row: CompareRowIdentity,
  listed: { rule_test_labels: string[] | null; kind: string } | undefined,
): CompareColumn {
  const isRuleTest = listed ? listed.rule_test_labels !== null : false
  const kind = isRuleTest ? 'rule test' : (row.command ?? listed?.kind ?? 'run').replace(/_/g, ' ')
  return { id: shortId(runId), kind, asset: assetsOf(row).join(', ') || '—' }
}

/** The one note above the table: two assets differ by design; one asset on two snapshots is worth saying. */
export function compareNotice(
  rows: readonly CompareRowIdentity[],
  sameSnapshot: boolean,
): 'different assets' | 'different snapshots' | null {
  const assets = new Set(rows.map((row) => assetsOf(row).join(',')))
  if (assets.size > 1) return 'different assets'
  return sameSnapshot ? null : 'different snapshots'
}

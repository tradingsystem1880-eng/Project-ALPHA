/** A comparison winner exists only when at least two values are comparable and one is unique. */
export function uniqueComparisonMaximum(values: ReadonlyArray<number | null>): number | null {
  const numeric = values.filter((value): value is number => value !== null)
  if (numeric.length < 2) return null
  const maximum = Math.max(...numeric)
  return numeric.filter((value) => value === maximum).length === 1 ? maximum : null
}

export function runKindMatches(
  runKind: string,
  selectedKind: string,
  allowedKinds: readonly string[],
): boolean {
  return (allowedKinds.length === 0 || allowedKinds.includes(runKind))
    && (selectedKind === 'all' || runKind === selectedKind)
}

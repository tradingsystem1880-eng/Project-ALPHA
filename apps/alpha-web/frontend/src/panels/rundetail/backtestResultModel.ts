import type { RunDetail } from '../../api/types'

const object = (value: unknown): Record<string, unknown> | null =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : null
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const exact = (value: number): string => Object.is(value, -0) ? '-0' : String(value)

/** Legacy runs without a command/verdict use RunDetail's existing plain-backtest convention. */
export function isBacktestRun(detail: RunDetail): boolean {
  const manifest = object(detail.manifest)
  const command = manifest?.command
  return detail.kind === 'runs' && (typeof command === 'string'
    ? command.startsWith('backtest_')
    : manifest?.verdict === undefined)
}

/** Eligibility only: byte verification is owned by the existing run/equity API, not this UI. */
export function backtestSource(detail: RunDetail, selectedRun: string): { runId: string; sha256: string } | null {
  const manifest = object(detail.manifest)
  const artifact = object(object(manifest?.artifacts)?.['equity_curve.parquet'])
  if (detail.run_id !== selectedRun || detail.kind !== 'runs' || detail.has_equity !== true
    || manifest?.run_id !== selectedRun || manifest.command !== 'backtest_run'
    || manifest.schema_version !== 3 || manifest.run_identity_version !== 3
    || manifest.artifact_contract_version !== 3
    || typeof artifact?.sha256 !== 'string' || !/^[a-f0-9]{64}$/i.test(artifact.sha256)) return null
  return { runId: selectedRun, sha256: artifact.sha256 }
}

/** Validate the typed API boundary defensively; display backend values, never recompute a metric. */
export function backtestResult(input: unknown): {
  observations: string; timestampUnixSeconds: string; timestampUtc: string; drawdown: string
} | null {
  const series = object(input)
  const ts: unknown = series?.ts
  const equity: unknown = series?.equity
  const drawdown: unknown = series?.drawdown
  if (!Array.isArray(ts) || !Array.isArray(equity) || !Array.isArray(drawdown)
    || !ts.length || ts.length !== equity.length || ts.length !== drawdown.length) return null
  for (let index = 0; index < ts.length; index++) {
    if (!finite(ts[index]) || !finite(equity[index]) || !finite(drawdown[index])
      || ts[index] < -62167219200 || ts[index] >= 253402300800
      || drawdown[index] > 0 || (index > 0 && ts[index] <= ts[index - 1])) return null
  }
  // The server's fallback for a nonpositive peak is not an interpretable drawdown fraction.
  if (equity[0] <= 0) return null
  const lastTimestamp = ts[ts.length - 1]
  // Display the containing whole UTC second; retain exact API precision separately.
  const timestampUtc = new Date(Math.floor(lastTimestamp) * 1000).toISOString()
    .replace('T', ' ').replace('.000Z', ' UTC')
  return { observations: String(ts.length), timestampUnixSeconds: exact(lastTimestamp), timestampUtc,
    drawdown: exact(drawdown[drawdown.length - 1]) }
}

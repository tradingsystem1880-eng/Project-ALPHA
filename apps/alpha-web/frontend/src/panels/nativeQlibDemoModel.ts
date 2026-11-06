export interface NativeScore { session_ts: string; symbol: string; score: number; synthetic_target: number }
export interface NativeDiagnostic { session_ts: string; ic: number; rank_ic: number }
export interface NativeQlibResult {
  schema_version: 1; synthetic: true; admission: 'not_admitted'; source: 'upstream_qrun'
  run_id: string; status: 'FINISHED'; qlib_version: string; model: string; seed: number
  train_rows: number; valid_rows: number; test_rows: number; sessions: number; symbols: number
  features: number; threads: number; rounds: number; wall_seconds: number
  command: string; config: string; target_description: string
  input_sha256: string; config_sha256: string; qrun_source_sha256: string
  metrics: { ic: number; rank_ic: number }; predictions: NativeScore[]; diagnostics: NativeDiagnostic[]
  artifact_sha256: Record<string, string>
}

/** This one recorded synthetic file is a display source, never an admitted experiment. */
export function readNativeQlibDemo(value: unknown): NativeQlibResult {
  const data = value as NativeQlibResult | null
  const invalid = () => { throw new Error('Native Qlib demo artifact is invalid or not explicitly synthetic.') }
  if (!data || data.schema_version !== 1 || data.synthetic !== true || data.admission !== 'not_admitted'
    || data.source !== 'upstream_qrun' || data.status !== 'FINISHED'
    || !/^[a-f0-9]{32}$/.test(data.run_id) || typeof data.command !== 'string'
    || typeof data.config !== 'string' || !Array.isArray(data.predictions) || !Array.isArray(data.diagnostics)
    || data.predictions.length !== 128 || data.test_rows !== 128 || data.diagnostics.length !== 16
    || !Number.isFinite(data.metrics?.ic) || !Number.isFinite(data.metrics?.rank_ic)) return invalid()
  let previous = -Infinity
  const keys = new Set<string>()
  for (const row of data.predictions) {
    if (!row || typeof row.symbol !== 'string' || !row.symbol.startsWith('SYN')
      || !Number.isFinite(row.score) || !Number.isFinite(row.synthetic_target)) return invalid()
    const time = Date.parse(row.session_ts), key = `${row.session_ts}/${row.symbol}`
    if (!Number.isFinite(time) || time < previous || keys.has(key)) return invalid()
    previous = time; keys.add(key)
  }
  previous = -Infinity
  for (const row of data.diagnostics) {
    const time = Date.parse(row?.session_ts)
    if (!Number.isFinite(time) || time <= previous || !Number.isFinite(row.ic) || !Number.isFinite(row.rank_ic)) return invalid()
    previous = time
  }
  return data
}

export interface NativeBalanceEvent { sequence: number; timestamp: string; account_balance: number; locked_balance: number; free_balance: number; currency: string }
export interface NativeOrder { id: string; timestamp: string; instrument: string; side: string; quantity: string; status: string; price: number }
export interface NativeFill { id: string; order_id: string; timestamp: string; side: string; quantity: string; price: string; commission: string; currency: string }
export interface NativePosition { id: string; opened_at: string; closed_at: string; entry: string; peak_quantity: string; open_price: number; close_price: number; realized_pnl: string }
export interface NativeNautilusResult {
  schema_version: 1; synthetic: true; admission: 'not_admitted'; source: 'upstream_nautilus'
  balance_kind: 'account_balance_events_not_equity'; version: string; upstream_commit: string
  strategy: string; strategy_sha256: string; run_id: string; config_id: string; selected_run: string
  instrument: string; currency: string; input_ticks: number; simulation_seconds: number
  producer_runs: number; producer_processes: number; normalized_reports_agree: boolean
  normalized_reports_sha256: string; reproduction_template: string; native_config: Record<string, unknown>
  balances: NativeBalanceEvent[]; orders: NativeOrder[]; fills: NativeFill[]; positions: NativePosition[]
  transfer: { library_file_id: string; bytes: number; sha256: string; inventory_files_verified: number }
  artifact_sha256: Record<string, string>
  account_events_csv: string
}

/** Validate this fixed, unadmitted native recording without collapsing equal-time events. */
export function readNativeNautilusDemo(value: unknown): NativeNautilusResult {
  const data = value as NativeNautilusResult | null
  const invalid = () => { throw new Error('Native Nautilus artifact is invalid or not explicitly synthetic account-balance data.') }
  if (!data || data.schema_version !== 1 || data.synthetic !== true || data.admission !== 'not_admitted'
    || data.source !== 'upstream_nautilus' || data.balance_kind !== 'account_balance_events_not_equity'
    || data.version !== '1.228.0' || !data.native_config || typeof data.reproduction_template !== 'string' || typeof data.account_events_csv !== 'string'
    || !Array.isArray(data.balances) || data.balances.length !== 31
    || !Array.isArray(data.orders) || data.orders.length !== 30
    || !Array.isArray(data.fills) || data.fills.length !== 30
    || !Array.isArray(data.positions) || data.positions.length !== 15) return invalid()
  let previous = -Infinity
  for (const [index, row] of data.balances.entries()) {
    const time = Date.parse(row?.timestamp)
    if (!row || row.sequence !== index || !Number.isFinite(time) || time < previous || row.currency !== 'USD'
      || ![row.account_balance, row.locked_balance, row.free_balance].every(Number.isFinite)) return invalid()
    previous = time
  }
  for (const rows of [data.orders, data.fills]) {
    previous = -Infinity
    for (const row of rows) {
      const time = Date.parse(row?.timestamp)
      if (!row || typeof row.id !== 'string' || !Number.isFinite(time) || time < previous || !Number.isFinite(Number(row.price))) return invalid()
      previous = time
    }
  }
  previous = -Infinity
  for (const row of data.positions) {
    const time = Date.parse(row?.closed_at), opened = Date.parse(row?.opened_at)
    if (!row || !Number.isFinite(time) || !Number.isFinite(opened) || opened > time || time < previous) return invalid()
    previous = time
  }
  return data
}

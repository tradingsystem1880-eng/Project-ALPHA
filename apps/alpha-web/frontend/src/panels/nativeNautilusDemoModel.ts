export interface NativeBalanceEvent { sequence: number; timestamp: string; account_balance: number; locked_balance: number; free_balance: number; currency: string }
export interface NativeOrder { id: string; timestamp: string; instrument: string; side: string; quantity: string; status: string; price: number }
export interface NativeFill { id: string; order_id: string; timestamp: string; side: string; quantity: string; price: string; commission: string; currency: string }
export interface NativePosition { id: string; opened_at: string; closed_at: string; entry: string; peak_quantity: string; open_price: number; close_price: number; realized_pnl: string }
export interface NativeNautilusResult {
  schema_version: 1; synthetic: true; admission: 'not_admitted'; source: 'upstream_nautilus' | 'upstream_qrun_to_nautilus'
  balance_kind: 'account_balance_events_not_equity'; version: string; upstream_commit: string
  strategy: string; strategy_sha256: string; run_id: string; config_id: string; selected_run: string
  instrument: string; currency: string; input_ticks: number; simulation_seconds: number
  producer_runs: number; producer_processes: number | null; normalized_reports_agree: boolean
  normalized_reports_sha256: string; reproduction_template: string; native_config: Record<string, unknown>
  balances: NativeBalanceEvent[]; orders: NativeOrder[]; fills: NativeFill[]; positions: NativePosition[]
  transfer?: { library_file_id: string; bytes: number; sha256: string; inventory_files_verified: number }
  artifact_sha256: Record<string, string>
  account_events_csv: string
  pipeline?: { qlib_run_id: string; predictions_total: number; predictions_consumed: number; instrument: string; availability_is_modeled: true; unconsumed: string; links: { session_ts: string; symbol: string; instrument_id: string; score: number; signal: number; available_at: string; executable_at: string }[] }
}

/** Validate this fixed, unadmitted native recording without collapsing equal-time events. */
export function readNativeNautilusDemo(value: unknown, pipeline = false): NativeNautilusResult {
  const data = value as NativeNautilusResult | null
  const invalid = () => { throw new Error('Native Nautilus artifact is invalid or not explicitly synthetic account-balance data.') }
  if (!data || data.schema_version !== 1 || data.synthetic !== true || data.admission !== 'not_admitted'
    || data.source !== (pipeline ? 'upstream_qrun_to_nautilus' : 'upstream_nautilus') || data.balance_kind !== 'account_balance_events_not_equity'
    || data.version !== '1.228.0' || !data.native_config || typeof data.reproduction_template !== 'string' || typeof data.account_events_csv !== 'string'
    || !Array.isArray(data.balances) || !Array.isArray(data.orders)
    || !Array.isArray(data.fills) || !Array.isArray(data.positions)) return invalid()
  if (!pipeline && (data.balances.length !== 31 || data.orders.length !== 30
    || data.fills.length !== 30 || data.positions.length !== 15)) return invalid()

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
  if (pipeline) validatePipeline(data, invalid)
  return data
}


/** Cross-check only this fixed synthetic long/flat recording; never grant execution authority. */
function validatePipeline(data: NativeNautilusResult, invalid: () => never): void {
  const link = data.pipeline
  if (!link || !/^[a-f0-9]{32}$/.test(link.qlib_run_id) || link.predictions_total !== 128
    || link.predictions_consumed !== 16 || link.availability_is_modeled !== true
    || link.instrument !== 'SYN00.SIM' || data.instrument !== link.instrument
    || !Array.isArray(link.links) || link.links.length !== 16 || data.input_ticks !== 17
    || data.balances.length !== data.input_ticks + data.fills.length) return invalid()
  let previous = -Infinity
  for (const [index, row] of link.links.entries()) {
    const origin = Date.parse(row?.session_ts), available = Date.parse(row?.available_at), executable = Date.parse(row?.executable_at)
    const terminal = new Date(origin + 86_400_000)
    while (terminal.getUTCDay() === 0 || terminal.getUTCDay() === 6) terminal.setUTCDate(terminal.getUTCDate() + 1)
    const expected = index + 1 < link.links.length ? Date.parse(link.links[index + 1].session_ts) : terminal.getTime()
    if (!row || row.symbol !== 'SYN00' || row.instrument_id !== link.instrument
      || !Number.isFinite(row.score) || row.signal !== (row.score > 0 ? 1 : 0)
      || !Number.isFinite(origin) || origin <= previous || origin % 86_400_000 !== 0
      || available !== origin + 23 * 3600_000 || executable <= available || executable !== expected) return invalid()
    previous = origin
  }
  const orders = new Map(data.orders.map(row => [row.id, row]))
  if (orders.size !== data.orders.length || new Set(data.fills.map(row => row.id)).size !== data.fills.length
    || data.orders.length !== data.fills.length || data.native_config.fixed_quantity !== 1
    || data.orders.some(row => row.instrument !== link.instrument || Number(row.quantity) !== 1 || row.status !== 'FILLED')) return invalid()
  let position = 0, used = 0
  const orderIds = new Set<string>()
  for (const row of link.links) {
    const fills = data.fills.filter(fill => Date.parse(fill.timestamp) === Date.parse(row.executable_at))
    if (fills.length !== (position === row.signal ? 0 : 1)) return invalid()
    if (fills.length) {
      const fill = fills[0], order = orders.get(fill.order_id)
      const side = row.signal === 1 ? 'BUY' : 'SELL'
      if (!order || orderIds.has(order.id) || fill.side !== side || order.side !== side
        || Number(fill.quantity) !== 1 || !(Number(fill.price) > 0)
        || Number(order.price) !== Number(fill.price) || Date.parse(order.timestamp) !== Date.parse(fill.timestamp)) return invalid()
      orderIds.add(order.id)
    }
    used += fills.length; position = row.signal
  }
  if (used !== data.fills.length || data.native_config.terminal_position_units !== position) return invalid()
  const buys = data.fills.filter(fill => fill.side === 'BUY'), sells = data.fills.filter(fill => fill.side === 'SELL')
  if (data.positions.length !== sells.length) return invalid()
  for (const [index, row] of data.positions.entries()) {
    if (row.entry !== 'BUY' || Number(row.peak_quantity) !== 1
      || Date.parse(row.opened_at) !== Date.parse(buys[index].timestamp)
      || Date.parse(row.closed_at) !== Date.parse(sells[index].timestamp)
      || row.open_price !== Number(buys[index].price) || row.close_price !== Number(sells[index].price)) return invalid()
  }
}

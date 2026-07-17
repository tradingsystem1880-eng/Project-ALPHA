// Shapes returned by the FastAPI JSON layer (apps/alpha-web/src/alpha_web/api/*.py).

export interface RunListItem {
  run_id: string
  kind: string
  command: string | null
  label: string | null
  symbol: string | null
  symbols: string[] | null
  passed: boolean | null
  verdict: string | null
  mtime: number
}

export interface RunList {
  total: number
  items: RunListItem[]
}

export interface RunDetail {
  run_id: string
  kind: string
  mtime: number
  manifest: Record<string, unknown>
  has_equity: boolean
  has_trades: boolean
  has_tearsheet: boolean
  has_forecast: boolean
}

export interface EquitySeries {
  ts: number[]
  equity: number[]
  drawdown: number[]
}

export interface ForecastSeries {
  history_ts: number[]
  history: number[]
  forecast_ts: number[]
  forecast: number[]
  p10: number[] | null
  p90: number[] | null
}

export interface Candle {
  t: number
  o: number
  h: number
  l: number
  c: number
  v: number
}

export interface Candles {
  symbol: string
  snapshot_id: string | null
  bars: Candle[]
}

export interface ParamSpec {
  name: string
  type: string
  default: number
  min: number | null
  max: number | null
  help: string
}

export interface StrategyDef {
  name: string
  params: ParamSpec[]
  has_tier1_surrogate: boolean
}

export interface CommandOption {
  name: string
  flag: string | null
  type: string
  default: unknown
  required: boolean
  multiple: boolean
  help: string
  choices: string[] | null
}

export interface CommandArg {
  name: string
  type: string
  required: boolean
  nargs: number
}

export interface CommandDef {
  id: string
  run_type: string | null
  args: CommandArg[]
  options: CommandOption[]
}

export interface JobSummary {
  job_id: string
  command: string
  kind: string | null
  status: string
  created_at: number
  run_id: string | null
  returncode: number | null
  n_lines: number
}

export interface JobDetail extends JobSummary {
  lines: string[]
}

export interface PanelParam {
  name: string
  type: string
  default: unknown
}

export interface PanelDef {
  id: string
  title: string
  component: string
  linked: boolean
  data: { endpoint: string; method: string }[]
  params: PanelParam[]
}

export interface AppsManifest {
  panels: PanelDef[]
  commands: string
  strategies: string
}

export type TradeRow = Record<string, string | number | null>

export interface WorkspaceMeta {
  slug: string
  name: string
  updated: number | null
}

export interface WorkspaceDoc {
  name: string
  linked_context: {
    symbol: string | null
    start: string | null
    end: string | null
    runId: string | null
  }
  dockview: Record<string, unknown>
}

export interface RiskScenario {
  name: string
  sharpe: number | null
  annual_vol: number
  max_drawdown: number
  value_at_risk: number
  expected_shortfall: number
  total_return: number
}

export interface RiskReport {
  run_id: string
  confidence: number
  scenarios: RiskScenario[]
}

export interface OptionGreeks {
  spot: number
  strike: number
  rate: number
  vol: number
  days: number
  kind: string
  price: number
  delta: number
  gamma: number
  vega: number
  theta: number
  rho: number
  implied_vol?: number
  market_price?: number
}

export interface OptionCurvePoint {
  spot: number
  price: number
  delta: number
  gamma: number
  vega: number
  theta: number
}

export interface OptionCurve {
  strike: number
  vol: number
  days: number
  rate: number
  kind: string
  points: OptionCurvePoint[]
}

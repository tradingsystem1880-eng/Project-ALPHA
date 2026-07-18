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
  has_nulls?: boolean
  has_trials?: boolean
  has_forecast_paths?: boolean
  has_propfirm_paths?: boolean
  has_origins?: boolean
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
  q25?: number[]
  q75?: number[]
  mean?: number[]
}

export interface ForecastPaths {
  samples: { sample: number; closes: number[] }[]
  ts: number[]
}

export interface NullTiers {
  tiers: { tier: string; statistics: number[] }[]
}

export interface OptimTrials {
  trials: { trial: number; returns: number[] }[]
}

export interface PropfirmPaths {
  paths: {
    passed: boolean[]
    busted: boolean[]
    days_to_pass: (number | null)[]
    payout: number[]
  }
}

export interface ForecastOrigins {
  origin_ts: number[]
  pre_cutoff: boolean[]
  crps: number[]
  crps_rw: number[]
  crps_bootstrap: number[]
  realized_end_return: number[]
  median_end_return: number[]
  hit: boolean[]
  cover50: boolean[]
  cover80: boolean[]
  cover90: boolean[]
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

export interface ScreenerQuote {
  symbol: string
  current: number
  change: number
  percent_change: number
  high: number
  low: number
  open: number
  prev_close: number
}

export interface ScreenerNewsItem {
  headline: string
  source: string
  url: string
  datetime: number
  summary: string
}

export interface ScreenerNews {
  symbol: string
  items: ScreenerNewsItem[]
}

export interface ResearchRow {
  strategy: string
  total_return: number | null
  final_equity?: number
  n_trades?: number
  error: string | null
}

export interface ResearchReport {
  symbol: string
  n_bars: number
  ranked: ResearchRow[]
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

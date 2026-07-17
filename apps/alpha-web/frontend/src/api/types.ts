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

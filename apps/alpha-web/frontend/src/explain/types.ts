// The explanation engine's shared shapes.
//
// Wire types describe the run manifests defensively: every field optional/nullable, because the
// store holds a mix of schema versions and non-finite stats arrive as null (allow_nan=False on
// the Python side). Story types are what panels render — always in BOTH voices: `narrative`
// (plain-English, teaches) and `terse` (annotation for fast scanning); the UI picks per the
// explain-mode setting.

// ---- manifest wire types (validate / gauntlet, schema_version 2) --------------------------

export interface FoldRow {
  index: number
  train_start: number
  train_end: number
  test_start: number
  test_end: number
  n_test: number
  oos_return: number | null
  oos_sharpe: number | null
  oos_cagr: number | null
}

export interface NullTierRow {
  tier: 'returns_level' | 'full_engine' | string
  observed: number | null
  percentile: number | null
  p_value: number | null
  threshold: number | null
  passed: boolean
  n_paths: number
  convention_divergence: number | null
  flagged_low_fidelity: boolean
}

export interface CIRow {
  metric: string
  point: number | null
  lower: number | null
  upper: number | null
  confidence: number
}

export interface DSRBlock {
  sharpe: number | null
  psr: number | null
  dsr: number | null
  expected_max_sharpe: number | null
  n_trials: number
  threshold: number
  passed: boolean
}

export interface CPCVBlock {
  n_folds: number
  mean_sharpe: number | null
  std_sharpe: number | null
  frac_positive: number | null
  passed: boolean
}

export interface VerdictBlock {
  edge: string
  robustness: string
  risk: string
  sample: string
  overall: string
  detail: Record<string, number | null>
}

export interface GateOutcome {
  name: string
  passed: boolean
  detail: Record<string, number | null>
}

/** A validate-run manifest (schema v2). All analytical blocks optional for older manifests. */
export interface ValidateManifest {
  schema_version?: number
  run_id?: string
  metadata?: Record<string, unknown>
  oos_metrics?: Record<string, number | null>
  folds?: FoldRow[]
  nulls?: NullTierRow[]
  cis?: CIRow[]
  outcomes?: GateOutcome[]
  dsr?: DSRBlock
  cpcv?: CPCVBlock
  verdict?: VerdictBlock
  passed?: boolean
  forecast?: Record<string, unknown>
}

// ---- optim / portfolio / propfirm / forecast manifests ------------------------------------

export interface OptimManifest {
  command?: string
  symbol?: string
  n_configs?: number
  n_oos?: number
  best_config?: [string, number][]
  best_sharpe?: number | null
  configs?: [string, number][][]
  sharpes?: (number | null)[]
  dsr?: { psr?: number | null; dsr?: number | null; expected_max_sharpe?: number | null; n_trials?: number; passed?: boolean }
  pbo?: { pbo?: number | null; n_splits?: number; passed?: boolean }
  reality_check?: { p_value?: number | null; passed?: boolean }
  spa?: { p_value?: number | null; passed?: boolean }
  passed?: boolean
}

export interface PropfirmManifest {
  command?: string
  firm?: string
  source?: string
  n_paths?: number
  horizon_days?: number
  rules?: Record<string, number | boolean | null>
  metrics?: {
    pass_probability?: number | null
    bust_probability?: number | null
    payout_probability?: number | null
    median_days_to_pass?: number | null
    expected_payout?: number | null
  }
}

export interface PortfolioManifest {
  command?: string
  symbols?: string[]
  weighting?: string
  n_periods?: number
  metrics?: Record<string, number | null>
  psr?: number | null
  dsr?: number | null
  sharpe_ci?: { lower?: number | null; upper?: number | null }
  cagr_ci?: { lower?: number | null; upper?: number | null }
  legs?: { symbol: string; n_oos: number; oos_sharpe: number | null; weight: number | null }[]
  long_short?: boolean
  n_long?: number
}

export interface ForecastManifest {
  command?: string
  symbol?: string
  params?: Record<string, number | string | null>
  origin?: Record<string, unknown>
  pretrain?: { cutoff?: string | null; overlap?: boolean }
  summary?: {
    prob_up?: number | null
    median_end_return?: number | null
    p05_end_return?: number | null
    p95_end_return?: number | null
  }
  // forecast_eval
  n_origins_pre?: number
  n_origins_post?: number
  summary_pre_cutoff?: ForecastEvalSummary
  summary_post_cutoff?: ForecastEvalSummary
}

export interface ForecastEvalSummary {
  n_origins?: number
  crps_mean?: number | null
  crps_rw_mean?: number | null
  crps_bootstrap_mean?: number | null
  skill_vs_rw?: number | null
  skill_vs_bootstrap?: number | null
  coverage50?: number | null
  coverage80?: number | null
  coverage90?: number | null
  hit_rate?: number | null
}

// ---- story types ---------------------------------------------------------------------------

export type Tone = 'good' | 'warn' | 'bad' | 'info'

/** One explained fact, in both voices. */
export interface Explained {
  /** Short expert annotation (one line). */
  terse: string
  /** Plain-English story: what this is, what the numbers say, what it means here. */
  narrative: string
  tone: Tone
}

export interface StatChip {
  label: string
  value: string
  /** Glossary key — renders the label as a hoverable term when set. */
  term?: string
}

/** The full story of one validation gate. */
export interface GateStory extends Explained {
  gate: string
  title: string
  passed: boolean | null
  /** What this gate tests, independent of this run's numbers (teaching text). */
  tests: string
  stats: StatChip[]
}

/** One verdict dimension, explained against its grading bands. */
export interface DimensionStory extends Explained {
  dimension: 'edge' | 'robustness' | 'risk' | 'sample' | 'overall'
  grade: string
}

/** A rule-based "what to try next" recommendation. */
export interface Suggestion {
  title: string
  why: string
  /** Prefill for the Strategy Lab / jobs API ({command, args}), when directly actionable. */
  action?: { command: string; args: string }
}

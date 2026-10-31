/** Read-only recorded daily-study projection. Values and units are supplied by the CLI. */
export type DailyRuleRole = 'baseline' | 'control'

export interface DailyRuleTerminalEvidence {
  valuation_basis: 'last_admitted_open_quote'
  valuation_at: string
  opening_quote_at: string
  terminal_liquidation: false
  terminal_decision: 'unfilled_without_next_admitted_quote'
  final_decision_at: string
}

export interface DailyRuleRoleSummary {
  run_id: string
  final_equity: number | null
  starting_equity: number | null
  orders: number
  fills: number
  rejected: number
  n_trades: number
  gross_pnl: number | null
  net_pnl: number | null
  fees_total: number | null
  terminal?: DailyRuleTerminalEvidence | null
}

export interface DailyRuleEvidence {
  schema: 'DailyRuleEvidenceV1'
  run_id: string
  available: boolean
  outcome: 'exploratory_complete' | 'accounting_rejection_inconclusive' | null
  watermark: string
  claim_scope: string
  data_origin: string
  provenance: Record<string, unknown>
  roles: Record<DailyRuleRole, DailyRuleRoleSummary>
  accounting: {
    role: DailyRuleRole
    rows: Record<string, unknown>[]
    total: number
    has_more: boolean
    next_offset: number | null
  }
  selectors: Record<string, unknown>
  artifact_sha256: Record<string, unknown>
}

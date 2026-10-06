import { getJSON, postJSON } from './client'
import type { components } from './generated'
type JobStatus = components['schemas']['JobStatus']

type Schema = components['schemas']
export type RuleExplanation = Schema['RuleEvaluationResponse']
export type AssistantContext = Schema['AssistantContext']
export type AssistantAction = Schema['AssistantTurnRequest']['action']
export type AssistantSession = Schema['AssistantSession']
export const edgeApi = {
  evaluate: (rules_id: string, symbol: string, as_of: string | null) => postJSON<RuleExplanation>('/api/rules/evaluate', { rules_id, symbol, as_of }),
  readiness: () => getJSON<Schema['AssistantReadiness']>('/api/assistant/readiness'),
  createSession: (context: AssistantContext) => postJSON<AssistantSession>('/api/assistant/sessions', { context }),
  check: (id: string) => postJSON<{ valid: boolean; context_hash: string }>(`/api/assistant/sessions/${encodeURIComponent(id)}/check`, {}),
  session: (id: string) => getJSON<AssistantSession>(`/api/assistant/sessions/${encodeURIComponent(id)}`),
  turn: (id: string, action: AssistantAction, message: string) => postJSON<JobStatus>(`/api/assistant/sessions/${encodeURIComponent(id)}/turns`, { action, message }),
}

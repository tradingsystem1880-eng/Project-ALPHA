/** Closed advisory investigation contracts; browser never supplies filesystem paths. */
export interface Proxy { symbol: string; asset_class: 'stock' | 'etf'; role: 'asset' | 'market' | 'sector' | 'other' }
export interface Draft { plan_sha256: string; start: string; end: string; provider: 'tiingo'; currency: 'USD'; venue: 'US'; calendar: 'XNYS'; series: Proxy[]; limitation: string }
export interface Investigation {
  id: string; run_id: string; question: string; cutoff: string; parent_id: string | null
  status: 'ready' | 'running' | 'completed' | 'failed' | 'interrupted' | 'blocked'
  error: string | null; active_job_id: string | null; requests_remaining: number; turns_remaining: number
  can_resume: boolean; can_followup: boolean; comparison_draft: Draft | null
  acquisition_status: 'not_started' | 'succeeded' | 'failed' | 'incomplete'; comparison_child_id: string | null
  progress: {stage: string; message: string}[]; receipts: Record<string, unknown>[]
  report: {findings: {observation: string; receipt_ids: string[]}[]; hypotheses: string[]; next_tests: string[]; limitations: string[]} | null
}
export interface Eligibility { run_id: string; eligible: boolean; cutoff: string | null; reason: string | null }
interface Job { job_id: string; status: string }
async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/investigations${path}`, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  })
  if (!response.ok) throw new Error(`Investigation request failed (${response.status}): ${await response.text()}`)
  return response.json() as Promise<T>
}
export const investigations = {
  eligibility: (run: string) => request<Eligibility>(`/eligibility/${encodeURIComponent(run)}`),
  list: (run: string) => request<Investigation[]>(`?run_id=${encodeURIComponent(run)}`),
  create: (run: string, question: string) => request<Investigation>('', {run_id: run, question}),
  show: (id: string) => request<Investigation>(`/${encodeURIComponent(id)}`),
  turn: (id: string, followup?: string) => request<Job>(`/${encodeURIComponent(id)}/turns`, {followup: followup ?? null}),
  draft: (id: string, series: Proxy[]) => request<Draft>(`/${encodeURIComponent(id)}/comparison-plan`, {series}),
  acquire: (id: string, hash: string) => request<Job>(`/${encodeURIComponent(id)}/comparisons`, {plan_sha256: hash}),
}

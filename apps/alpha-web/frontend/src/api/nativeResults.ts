/** Dedicated display projection of the server's NativeStockOperatorResultV1 contract. */
export interface NativeDispatch { job_id: string; reservation_id: string; owner_id: string; spec_sha256: string; profile_sha256: string }
interface NativeBase { status: 'completed' | 'invalid' | 'unavailable'; reason: string }
export interface NativeCompleted extends NativeBase {
  status: 'completed'
  dispatch: NativeDispatch
  provenance: { receipt_sha256: string; trace_sha256: string; checkpoint_sha256: string }
  receipt: { source_sha256: string; charged_stages: string[]; fake_model_attempts: number; fake_tool_attempts: number; actual_model_calls: number }
  result: { synthetic_score: number; unit: 'fixture_only' }
}
export type NativeJobEvidence = NativeCompleted | (NativeBase & { status: 'invalid' | 'unavailable' })
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export function isNativeJobId(value: string): boolean { return UUID.test(value) }
const invalid = (): never => { throw new Error('Native result response is invalid.') }
function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : invalid()
}
function text(value: unknown, max = 256): string { return typeof value === 'string' && value.length > 0 && value.length <= max ? value : invalid() }
function digest(value: unknown): string { const result = text(value, 64); return /^[a-f0-9]{64}$/.test(result) ? result : invalid() }

/** Parse displayed evidence. Never infer completion from transport success. */
export function readNativeJobResult(value: unknown, requestedJob: string): NativeJobEvidence {
  const body = object(value)
  if (body.schema !== 'NativeStockOperatorResultV1' || body.operation !== 'recover_native_stock_result' || body.classification !== 'synthetic_only_unqualified' || body.resume_allowed !== false || body.scientific_acceptance !== 'not_admitted') invalid()
  const reason = text(body.reason)
  if (body.status === 'invalid' || body.status === 'unavailable') {
    if (['receipt', 'result', 'feedback'].some(key => Object.hasOwn(body, key))) invalid()
    return { status: body.status, reason }
  }
  if (body.status !== 'completed') invalid()
  const dispatch = object(body.dispatch), proof = object(body.provenance), receipt = object(body.receipt)
  const request = object(receipt.request), result = object(body.result), feedback = object(body.feedback)
  const job = text(dispatch.job_id, 36)
  if (!isNativeJobId(job) || job.toLowerCase() !== requestedJob.toLowerCase() || request.job_id !== job || proof.owner_receipt_match !== 'verified') invalid()
  const owner = text(dispatch.owner_id, 200), reservation = text(dispatch.reservation_id, 200), spec = digest(dispatch.spec_sha256)
  if (request.owner_id !== owner || request.reservation_id !== reservation || request.spec_sha256 !== spec) invalid()
  if (receipt.schema !== 'StockRDLoopReceiptV1' || receipt.actual_model_calls !== 0 || receipt.fake_model_attempts !== 2 || receipt.fake_tool_attempts !== 2 || receipt.routes_enabled !== false || receipt.scientific_acceptance !== 'not_admitted' || receipt.resumed_without_repeating !== true || receipt.checkpoint_unchanged !== true || receipt.replay_rejected !== true || feedback.decision !== false || feedback.acceptable !== false) invalid()
  const stages = ['direct_exp_gen', 'coding', 'running', 'feedback', 'record']
  if (!Array.isArray(receipt.charged_stages) || receipt.charged_stages.length !== stages.length || !receipt.charged_stages.every((stage, index) => stage === stages[index])) invalid()
  const trace = digest(proof.trace_sha256), checkpoint = digest(proof.checkpoint_sha256)
  if (trace !== receipt.trace_sha256 || checkpoint !== receipt.checkpoint_sha256 || result.unit !== 'fixture_only' || typeof result.synthetic_score !== 'number' || !Number.isFinite(result.synthetic_score)) invalid()
  return {
    status: 'completed', reason,
    dispatch: { job_id: job, owner_id: owner, reservation_id: reservation, spec_sha256: spec, profile_sha256: digest(dispatch.profile_sha256) },
    provenance: { receipt_sha256: digest(proof.receipt_sha256), trace_sha256: trace, checkpoint_sha256: checkpoint },
    receipt: { source_sha256: digest(receipt.source_sha256), charged_stages: stages, fake_model_attempts: 2, fake_tool_attempts: 2, actual_model_calls: 0 },
    result: { synthetic_score: result.synthetic_score as number, unit: 'fixture_only' },
  }
}

export async function fetchNativeJobResult(job: string, signal: AbortSignal): Promise<NativeJobEvidence> {
  if (!isNativeJobId(job)) throw new Error('Enter a valid native job UUID.')
  let response: Response
  try { response = await fetch(`/api/native-jobs/${encodeURIComponent(job)}/result`, { signal, cache: 'no-store' }) }
  catch { throw new Error('Native result request failed. Check the local backend and retry.') }
  if (!response.ok) throw new Error(`Native result request failed (HTTP ${response.status}). Retry the read.`)
  let value: unknown
  try { value = await response.json() } catch { throw new Error('Native result response is invalid.') }
  return readNativeJobResult(value, job)
}

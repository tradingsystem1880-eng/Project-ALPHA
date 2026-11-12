import { afterEach, describe, expect, it, vi } from 'vitest'
import { isNativeJobId, readNativeJobResult, fetchNativeJobResult } from './nativeResults'

const JOB = '00000000-0000-4000-8000-000000000001'
const other = '00000000-0000-4000-8000-000000000002'
const digest = 'a'.repeat(64)
export function completed() {
  return {
    schema: 'NativeStockOperatorResultV1', operation: 'recover_native_stock_result',
    classification: 'synthetic_only_unqualified', status: 'completed', reason: 'verified',
    scientific_acceptance: 'not_admitted', resume_allowed: false,
    dispatch: { job_id: JOB, reservation_id: 'synthetic-reservation', owner_id: 'synthetic-owner', spec_sha256: digest, profile_sha256: digest },
    provenance: { owner_receipt_match: 'verified', receipt_sha256: digest, trace_sha256: digest, checkpoint_sha256: digest },
    receipt: { schema: 'StockRDLoopReceiptV1', source_sha256: digest, request: { job_id: JOB, reservation_id: 'synthetic-reservation', owner_id: 'synthetic-owner', spec_sha256: digest }, charged_stages: ['direct_exp_gen', 'coding', 'running', 'feedback', 'record'], fake_model_attempts: 2, fake_tool_attempts: 2, actual_model_calls: 0, resumed_without_repeating: true, checkpoint_unchanged: true, replay_rejected: true, routes_enabled: false, scientific_acceptance: 'not_admitted', trace_sha256: digest, checkpoint_sha256: digest },
    result: { synthetic_score: -0.125, unit: 'fixture_only' }, feedback: { decision: false, acceptable: false },
  }
}
const unavailable = () => ({ schema: 'NativeStockOperatorResultV1', operation: 'recover_native_stock_result', classification: 'synthetic_only_unqualified', status: 'unavailable', reason: 'missing_evidence', resume_allowed: false, scientific_acceptance: 'not_admitted' })
afterEach(() => vi.unstubAllGlobals())
describe('native result typed read boundary', () => {
  it('accepts bound completed evidence and explicit incomplete states', () => {
    expect(readNativeJobResult(completed(), JOB).status).toBe('completed')
    expect(readNativeJobResult(unavailable(), JOB).status).toBe('unavailable')
    expect(readNativeJobResult({ ...unavailable(), status: 'invalid' }, JOB).status).toBe('invalid')
  })
  it('rejects malformed, promoted, mismatched and incomplete value-bearing evidence', () => {
    for (const change of [null, {}, { ...completed(), resume_allowed: true }, { ...completed(), classification: 'production' }, { ...completed(), result: { synthetic_score: Infinity, unit: 'fixture_only' } }, { ...completed(), feedback: { decision: true, acceptable: true } }, { ...completed(), provenance: { ...completed().provenance, owner_receipt_match: 'mismatch' } }, { ...unavailable(), result: null }, { ...completed(), status: 'unavailable' }]) expect(() => readNativeJobResult(change, JOB)).toThrow('Native result response is invalid.')
    expect(() => readNativeJobResult(completed(), other)).toThrow()
    const bad = completed(); bad.receipt.actual_model_calls = 1
    expect(() => readNativeJobResult(bad, JOB)).toThrow()
  })
  it('accepts UUID only, sends one same-origin read without selectors and never caches', async () => {
    expect(isNativeJobId('../owner')).toBe(false)
    expect(isNativeJobId(`${JOB}?profile=other`)).toBe(false)
    expect(isNativeJobId(JOB.toUpperCase())).toBe(true)
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(unavailable())))
    vi.stubGlobal('fetch', fetch)
    const signal = new AbortController().signal
    await fetchNativeJobResult(JOB, signal)
    expect(fetch).toHaveBeenCalledWith(`/api/native-jobs/${JOB}/result`, { signal, cache: 'no-store' })
    await expect(fetchNativeJobResult('../owner', signal)).rejects.toThrow('Enter a valid native job UUID.')
    expect(fetch).toHaveBeenCalledTimes(1)
  })
  it('redacts HTTP, JSON and network errors without fallback', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response('dummy-secret', { status: 503 })).mockResolvedValueOnce(new Response('dummy-secret')).mockRejectedValueOnce(new Error('dummy-secret'))
    vi.stubGlobal('fetch', fetch)
    for (let i = 0; i < 3; i++) await expect(fetchNativeJobResult(JOB, new AbortController().signal)).rejects.not.toThrow('dummy-secret')
    expect(fetch).toHaveBeenCalledTimes(3)
  })
})

/** CLI-authoritative diagnostics; contract types come from the generated production API. */
import type { components } from './generated'

type Schema = components['schemas']
export type RetainedCoverageRequest = Pick<Schema['RetainedCoverageRequest'],
  'coverage_start' | 'coverage_end' | 'as_of' | 'expected_cadence_seconds' | 'max_verify_artifact_bytes'>
export type RetainedCoverageRows = Schema['RetainedCoverageRows']
export type RetainedCoverageResponse = Schema['RetainedCoverageResponse']

export async function inspectRetainedCoverage(
  manifestId: string, request: RetainedCoverageRequest, signal: AbortSignal,
): Promise<RetainedCoverageResponse> {
  const response = await fetch(
    `/api/crypto-data/quality/${encodeURIComponent(manifestId)}/retained-coverage`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request), signal, cache: 'no-store' },
  )
  if (!response.ok) throw new Error('Retained coverage request unavailable. Check the explicit grid and limits, then retry.')
  let report: RetainedCoverageResponse
  try { report = await response.json() as RetainedCoverageResponse }
  catch { throw new Error('Retained coverage response unavailable: invalid JSON.') }
  if (!report || typeof report !== 'object' || report.manifest_id !== manifestId || report.execution_authority !== false
      || report.provider_history_complete !== false || report.point_in_time_eligibility !== false
      || report.inspection_provider_calls !== 0
      || !['inspected', 'unavailable'].includes(report.audit_state)) {
    throw new Error('Retained coverage response unavailable: identity or diagnostic contract differs.')
  }
  return report
}

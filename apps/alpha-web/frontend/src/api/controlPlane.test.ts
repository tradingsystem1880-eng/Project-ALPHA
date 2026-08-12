import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, clearImmutableApiCache } from './client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function apiError(message: string, status: number): Response {
  return jsonResponse(
    {
      schema_version: 1,
      code: status === 422 ? 'request_invalid' : 'service_unavailable',
      message,
      recovery_action: 'Retry after resolving the blocker.',
      field_errors: [],
      request_id: 'request-test',
    },
    status,
  )
}

afterEach(() => {
  clearImmutableApiCache()
  vi.unstubAllGlobals()
})

describe('control-plane API client', () => {
  it('reads the provider and system projections from their stable endpoints', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ paper_enabled: false }))
    vi.stubGlobal('fetch', fetchMock)

    await api.providers()
    await api.system()

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/providers')
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/system')
  })

  it('encodes a session id and advances the paper-event cursor', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', fetchMock)

    await api.paperEvents('unsafe/id', 41)

    expect(fetchMock).toHaveBeenCalledWith('/api/paper/sessions/unsafe%2Fid/events?after=41')
  })

  it('cancels through the linked job endpoint with DELETE', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: 'cancelled' }))
    vi.stubGlobal('fetch', fetchMock)

    const response = await api.cancel('job-7')

    expect(response.ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith('/api/jobs/job-7', { method: 'DELETE' })
  })

  it('surfaces non-success responses for panel error states', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('offline', { status: 503 })))

    await expect(api.providers()).rejects.toThrow('503')
  })

  it('uses bounded artifact endpoints for causal charts and native analytics', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ trace_status: 'trace_unavailable' }))
      .mockResolvedValueOnce(jsonResponse({ available: false }))
    vi.stubGlobal('fetch', fetchMock)

    await api.chartBundle('0123456789abcdef', 5000)
    await api.nativeTearsheet('0123456789abcdef')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/runs/0123456789abcdef/chart-bundle?limit=5000',
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/runs/0123456789abcdef/native-tearsheet?point_limit=750',
    )
  })

  it('deduplicates immutable run projections and retries a rejected request', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ run_id: 'run-cache' }))
      .mockResolvedValueOnce(apiError('temporary', 503))
      .mockResolvedValueOnce(jsonResponse({ run_id: 'run-retry' }))
    vi.stubGlobal('fetch', fetchMock)

    const [first, second] = await Promise.all([api.run('run-cache'), api.run('run-cache')])
    expect(first).toBe(second)
    expect(fetchMock).toHaveBeenCalledOnce()

    await expect(api.run('run-retry')).rejects.toThrow('temporary')
    await expect(api.run('run-retry')).resolves.toMatchObject({ run_id: 'run-retry' })
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('extracts ApiErrorV1 messages without leaking JSON response framing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(apiError('run has no equity stream', 422)))

    await expect(api.providers()).rejects.toThrow('422 — run has no equity stream')
    await expect(api.providers()).rejects.not.toThrow('{"message"')
  })

  it('sends the linked date window with the causal chart bundle request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ trace_status: 'available' }))
    vi.stubGlobal('fetch', fetchMock)

    await api.chartBundle('0123456789abcdef', 2000, '2026-01-02', '2026-03-31')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/runs/0123456789abcdef/chart-bundle?limit=2000&start=2026-01-02&end=2026-03-31',
    )
  })

  it('reads project lineage and keeps ML behind its explicit capability service', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ items: [], limit: 50, offset: 0, has_more: false }))
      .mockResolvedValueOnce(jsonResponse({ available: false }))
      .mockResolvedValueOnce(jsonResponse({ job_id: 'job-1', status: 'queued' }))
      .mockResolvedValueOnce(jsonResponse({ job_id: 'job-1', status: 'running' }))
    vi.stubGlobal('fetch', fetchMock)

    await api.projects()
    await api.mlStatus()
    const accepted = await api.createMlExperiment('project/id')
    await api.developmentJob(accepted.job_id)

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/projects?limit=50&offset=0')
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/ml/status')
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/ml/experiments', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ project_id: 'project/id' }),
    })
    expect(fetchMock).toHaveBeenNthCalledWith(4, '/api/development/jobs/job-1?event_tail=true')
  })

  it('reads a bounded Qlib diagnostic tear sheet without accepting an unbounded offset', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ available: false }))
    vi.stubGlobal('fetch', fetchMock)

    await api.mlTearsheet('unsafe/id', 500)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/ml/exchanges/unsafe%2Fid/tear-sheet?feature_limit=50&timeline_limit=500&timeline_offset=500&history_limit=200',
    )
    expect(() => api.mlTearsheet('exchange', 1_000_001)).toThrow(RangeError)
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('uses typed immutable setup, AgentBrief, and bounded evidence ledger endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({})))
    vi.stubGlobal('fetch', fetchMock)

    await api.createStrategyVersion('project/id', {
      strategy_name: 'ts_momentum',
      source_fingerprint: 'git:abc',
      definition: { lookback: 252 },
      parameter_space: { lookback: [126, 252] },
    })
    await api.createExperiment('project/id', {
      version_id: 'sv/id',
      snapshot_id: 'snapshot-1',
      universe: ['AAPL', 'MSFT'],
      split_policy: { train: 504, test: 63 },
      costs: { fee_bps: 1 },
      seeds: { master: 7 },
      stage_config: { tier1_paths: 1000 },
    })
    await api.agentBrief('project/id', 25)
    await api.evidence({
      asset: 'BRK/B',
      projectId: 'project/id',
      status: 'corroborated',
      asOf: '2026-07-19',
      limit: 25,
      offset: 5,
    })

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/projects/project%2Fid/versions',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/projects/project%2Fid/experiments',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/projects/project%2Fid/agent-brief?evidence_limit=25',
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      '/api/evidence?asset=BRK%2FB&project_id=project%2Fid&status=corroborated&as_of=2026-07-19&limit=25&offset=5',
    )
  })

  it('previews and launches only a typed strategy-development suite action', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ ready: true }))
      .mockResolvedValueOnce(jsonResponse({ job_id: 'suite-1', status: 'starting' }))
      .mockResolvedValueOnce(jsonResponse({ job_id: 'suite-1', status: 'cancellation_requested' }))
    vi.stubGlobal('fetch', fetchMock)

    await api.suitePlan('project/id', 'experiment/id', 'three_null_families')
    await api.runSuite('project/id', 'experiment/id', 'three_null_families', {})
    await api.cancelDevelopmentJob('suite/id')

    const prefix = '/api/projects/project%2Fid/experiments/experiment%2Fid/suite/three_null_families'
    expect(fetchMock).toHaveBeenNthCalledWith(1, `${prefix}/plan`)
    expect(fetchMock).toHaveBeenNthCalledWith(2, `${prefix}/run`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: '{}',
    })
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/development/jobs/suite%2Fid', {
      method: 'DELETE',
    })
  })

  it('uses explicit owner endpoints for holdout, candidate, and sandbox decision records', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({})))
    vi.stubGlobal('fetch', fetchMock)

    await api.sealHoldout('project/id', {
      experiment_id: 'ex/id',
      actor: 'owner',
      reason: 'reserve',
      start_date: '2026-04-01',
      end_date: '2026-06-30',
    })
    await api.transitionExperimentStage('project/id', 'ex/id', 'candidate', {
      state: 'pass',
      reason: 'frozen',
    })
    await api.freezeDecision('project/id', 'ex/id', {
      verdict: 'revise',
      actor: 'owner',
      reason: 'more research required',
      negative_results_acknowledged: true,
    })

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/projects/project%2Fid/holdouts/seal',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/projects/project%2Fid/experiments/ex%2Fid/stages/candidate/state',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/projects/project%2Fid/experiments/ex%2Fid/decision',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, runContextForProject } from './client'

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('bounded Research Case API client', () => {
  it('binds empirical launches and comparisons to explicit run context', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({})))
    vi.stubGlobal('fetch', fetchMock)
    const governed = runContextForProject('project/id')

    await api.launch('validate', 'SPY', governed)
    await api.researchCompare('SPY', governed)
    await api.researchCompare('SPY', runContextForProject(null))

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/jobs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ command: 'validate', args: 'SPY', run_context: governed }),
    })
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/research/compare?symbol=SPY&context_kind=governed_project&project_id=project%2Fid',
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/research/compare?symbol=SPY&context_kind=standalone_sandbox',
    )
  })

  it('uses only the bounded Gate-1 capture/read/preflight/propose/pilot/status/report routes', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({})))
    vi.stubGlobal('fetch', fetchMock)

    await api.researchCapture({ idea: 'SPY may bounce after a point-in-time double bottom.' })
    await api.researchCase('project/id')
    await api.researchProposalOptions('project/id')
    await api.researchProposal('project/id', {
      source_pack_id: 'sp_pack',
      answer_bundle_id: 'synthetic_spy_60m_four_hour_v1',
      dataset_ref_id: null,
      expected_case_revision: 'a'.repeat(64),
    })
    await api.researchPilot('project/id')
    await api.researchStatus('project/id')
    await api.researchProgressReport('project/id')

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/research/cases', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ idea: 'SPY may bounce after a point-in-time double bottom.' }),
    })
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/research/cases/project%2Fid')
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/research/cases/project%2Fid/proposal-options',
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      '/api/research/cases/project%2Fid/proposal',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(5, '/api/research/cases/project%2Fid/launch', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ stage: 'pilot' }),
    })
    expect(fetchMock).toHaveBeenNthCalledWith(6, '/api/research/cases/project%2Fid/status')
    expect(fetchMock).toHaveBeenNthCalledWith(7, '/api/research/cases/project%2Fid/report')
  })

  it('adds only the ADR-0021 read-plane routes: list, evidence hub, scorecard', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({})))
    vi.stubGlobal('fetch', fetchMock)

    await api.researchCases()
    await api.researchCases({ limit: 25, offset: 5 })
    await api.researchEvidenceHub('project/id')
    await api.researchScorecard('project/id')

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/research/cases?limit=50&offset=0')
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/research/cases?limit=25&offset=5')
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/research/cases/project%2Fid/evidence-hub',
    )
    expect(fetchMock).toHaveBeenNthCalledWith(4, '/api/research/cases/project%2Fid/scorecard')
  })

  it('adds only the ADR-0022 Codex read routes: packets, notes, protocols', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({})))
    vi.stubGlobal('fetch', fetchMock)

    await api.researchContextPackets('project/id')
    await api.researchContextPacket('cp_abc')
    await api.researchNotes('project/id', { limit: 30 })
    await api.researchProtocols()

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/research/cases/project%2Fid/context-packets?limit=50&offset=0',
    )
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/research/context-packets/cp_abc')
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/research/cases/project%2Fid/notes?limit=30&offset=0',
    )
    expect(fetchMock).toHaveBeenNthCalledWith(4, '/api/research/protocols')
  })

  it('does not expose owner approval, decision, D2 reveal, deep, or trading methods', () => {
    for (const method of [
      'researchApprove',
      'researchDecision',
      'researchRevealD2',
      'researchDeep',
      'researchPython',
      'researchPaper',
      'researchOrder',
    ]) {
      expect(api).not.toHaveProperty(method)
    }
  })
})

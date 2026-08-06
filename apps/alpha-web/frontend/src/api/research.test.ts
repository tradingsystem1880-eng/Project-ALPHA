import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from './client'

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
  it('uses only the six Gate-1 capture/read/propose/pilot/status/report routes', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({})))
    vi.stubGlobal('fetch', fetchMock)

    await api.researchCapture({ idea: 'SPY may bounce after a point-in-time double bottom.' })
    await api.researchCase('project/id')
    await api.researchProposal('project/id', {
      source_pack_id: 'sp_pack',
      answers: {
        chart_construction: 'spy_rth_60m_four_hour_window',
        event_availability: 'second_trough_confirmable',
        primary_outcome: 'four_trading_hour_return_25bp',
      },
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
      '/api/research/cases/project%2Fid/proposal',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(4, '/api/research/cases/project%2Fid/launch', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ stage: 'pilot' }),
    })
    expect(fetchMock).toHaveBeenNthCalledWith(5, '/api/research/cases/project%2Fid/status')
    expect(fetchMock).toHaveBeenNthCalledWith(6, '/api/research/cases/project%2Fid/report')
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

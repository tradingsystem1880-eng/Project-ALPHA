import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from './client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

afterEach(() => {
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
})

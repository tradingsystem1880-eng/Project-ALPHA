import { describe, expect, it, vi } from 'vitest'

import {
  requireSuccessfulWorkspaceResponse,
  workspaceMutation,
  workspaceViewState,
} from './workspaceModel'

describe('workspace durability states', () => {
  it('distinguishes loading, error, empty, and ready projections', () => {
    expect(workspaceViewState(null, null)).toBe('loading')
    expect(workspaceViewState(null, 'offline')).toBe('error')
    expect(workspaceViewState([], null)).toBe('empty')
    expect(workspaceViewState([{ slug: 'desk' }], null)).toBe('ready')
  })

  it.each(['SAVE', 'OPEN', 'DELETE'] as const)(
    'returns a visible %s-specific message when a mutation rejects',
    async (operation) => {
      const action = vi.fn().mockRejectedValue(new Error('control plane unavailable'))

      await expect(workspaceMutation(operation, action)).resolves.toBe(
        `${operation} FAILED · control plane unavailable`,
      )
      expect(action).toHaveBeenCalledOnce()
    },
  )

  it('keeps successful mutations clear and rejects non-success delete responses', async () => {
    await expect(workspaceMutation('OPEN', async () => undefined)).resolves.toBeNull()
    expect(() =>
      requireSuccessfulWorkspaceResponse(new Response(null, { status: 503, statusText: 'Offline' })),
    ).toThrow('503 Offline')
  })
})

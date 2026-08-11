export type WorkspaceViewState = 'loading' | 'error' | 'empty' | 'ready'

export function workspaceViewState(
  items: readonly unknown[] | null,
  loadError: string | null,
): WorkspaceViewState {
  if (loadError) return 'error'
  if (items === null) return 'loading'
  return items.length === 0 ? 'empty' : 'ready'
}

function message(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason)
}

export async function workspaceMutation(
  operation: 'SAVE' | 'OPEN' | 'DELETE',
  action: () => Promise<void>,
): Promise<string | null> {
  try {
    await action()
    return null
  } catch (reason) {
    return `${operation} FAILED · ${message(reason)}`
  }
}

export function requireSuccessfulWorkspaceResponse(response: Response): void {
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`.trim())
}
